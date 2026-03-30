import json
import logging
import os

from groq import Groq, APIError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 1000

SYSTEM_PROMPT = (
    "You are a friendly investment assistant for beginner investors. "
    "Always explain things in plain English with no financial jargon. "
    "Be encouraging and educational. Never make confident predictions. "
    "Always remind users this is not professional financial advice. "
    "Keep responses concise and well-structured for Telegram (use plain text, not markdown tables)."
)


def _holdings_summary(holdings: list[dict], prices: dict[str, float] | None = None) -> str:
    lines = []
    for h in holdings:
        ticker = h["ticker"]
        shares = h["shares"]
        buy_price = h["buy_price"]
        cost = shares * buy_price
        line = f"  {ticker}: {shares} shares @ ${buy_price:.2f} (cost ${cost:.2f})"
        if prices and ticker in prices:
            current = prices[ticker]
            pnl = (current - buy_price) * shares
            pct = ((current - buy_price) / buy_price) * 100
            line += f" | now ${current:.2f} | P&L ${pnl:+.2f} ({pct:+.1f}%)"
        lines.append(line)
    return "\n".join(lines) if lines else "  (no holdings)"


def _user_profile_summary(user_profile: dict) -> str:
    return (
        f"Risk tolerance: {user_profile.get('risk', 'medium')}, "
        f"Goal: {user_profile.get('goal', 'growth')}, "
        f"Monthly budget: ${user_profile.get('budget', 95):.0f}"
    )


async def analyze_portfolio(holdings: list[dict], user_profile: dict) -> str:
    summary = _holdings_summary(holdings)
    profile = _user_profile_summary(user_profile)
    prompt = (
        f"Please analyze this beginner investor's portfolio:\n\n"
        f"User profile: {profile}\n\n"
        f"Holdings:\n{summary}\n\n"
        "Give a brief, friendly health check: what's going well, what to watch, "
        "and one actionable tip. Keep it encouraging."
    )
    return await _call_llm(prompt)


async def check_sell_alerts(
    holdings: list[dict], prices: dict[str, float], threshold: float
) -> str:
    summary = _holdings_summary(holdings, prices)
    prompt = (
        f"This beginner investor has a sell-alert threshold of {threshold:.0f}%.\n\n"
        f"Holdings with current prices:\n{summary}\n\n"
        "Identify any stocks that are down more than the threshold. "
        "For each one, briefly explain what might be happening and give gentle, "
        "balanced advice on whether to hold or cut losses. "
        "Be supportive, not alarming."
    )
    return await _call_llm(prompt)


async def generate_weekly_review(
    holdings: list[dict], prices: dict[str, float], user_profile: dict
) -> str:
    summary = _holdings_summary(holdings, prices)
    profile = _user_profile_summary(user_profile)
    prompt = (
        f"Write a weekly portfolio review for a beginner investor.\n\n"
        f"User profile: {profile}\n\n"
        f"Holdings:\n{summary}\n\n"
        "Structure your response with these sections:\n"
        "Summary\nWhat went well\nWhat to watch\nLesson of the week\nYour action items\n\n"
        "Keep it warm, educational, and under 300 words."
    )
    return await _call_llm(prompt)


async def generate_buy_suggestions(
    holdings: list[dict], user_profile: dict, budget: float,
    prices: dict[str, float] | None = None,
    watchlist_data: dict[str, dict] | None = None,
) -> list[dict]:
    from core.watchlists import format_watchlist_for_prompt

    summary = _holdings_summary(holdings, prices)
    profile = _user_profile_summary(user_profile)
    shariah = user_profile.get("shariah", 0)

    num_suggestions = min(4, len(watchlist_data)) if watchlist_data else 4

    shariah_instruction = ""
    if shariah:
        shariah_instruction = (
            "IMPORTANT: This user requires Shariah-compliant (halal) investments only. "
            "All suggestions must be from the Shariah-compliant candidates provided.\n\n"
        )

    prompt = (
        f"Suggest {num_suggestions} ETFs for a beginner investor "
        f"with ${budget:.0f} to invest this month.\n\n"
        f"User profile: {profile}\n\n"
        f"{shariah_instruction}"
        f"Current holdings:\n{summary}\n\n"
        f"Do not suggest tickers the user already owns.\n"
    )

    if watchlist_data:
        candidates_text = format_watchlist_for_prompt(watchlist_data)
        prompt += (
            "You MUST pick your suggestions ONLY from the candidates listed below. "
            "Do not suggest any ticker not in this list.\n\n"
            f"Available candidates (with current prices and recent performance):\n"
            f"{candidates_text}\n\n"
        )

    prompt += (
        f"Return ONLY a JSON array with exactly {num_suggestions} objects. "
        "Each object must have:\n"
        '  "ticker": string (e.g. "VOO"),\n'
        '  "name": string (e.g. "Vanguard S&P 500 ETF"),\n'
        '  "reason": string (1-2 sentences why it fits this investor, '
        'referencing current price/performance data),\n'
        '  "amount": number (suggested dollar amount, total must not exceed budget),\n'
        '  "risk": string ("Low", "Medium", or "High"),\n'
        '  "watchout": string (one risk to be aware of)\n\n'
        "Return only the JSON array, no other text."
    )
    raw = await _call_llm(prompt)
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        suggestions = json.loads(text)

        # Validate tickers against watchlist
        if watchlist_data:
            valid_tickers = set(watchlist_data.keys())
            suggestions = [
                s for s in suggestions
                if s.get("ticker", "").upper() in valid_tickers
            ]

        return suggestions
    except Exception as e:
        logger.error("Failed to parse buy suggestions JSON: %s\nRaw: %s", e, raw)
        return []


async def _call_llm(prompt: str) -> str:
    import asyncio
    try:
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
    except APIError as e:
        logger.error("Groq API error: %s", e)
        raise
