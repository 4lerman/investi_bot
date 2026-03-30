WELCOME = (
    "👋 Welcome to your Investment Assistant!\n\n"
    "I'll help you manage your portfolio, alert you when to sell, "
    "give you weekly reviews, and suggest what to buy each month.\n\n"
    "Let's get started. What's your monthly investment budget? (e.g. 95)"
)

HELP = (
    "📖 Available commands:\n\n"
    "/start — Welcome message and setup\n"
    "/add — Add a stock to your portfolio\n"
    "/remove — Remove a stock from your portfolio\n"
    "/portfolio — View your current holdings and performance\n"
    "/analyze — Get Claude AI analysis of your portfolio\n"
    "/alerts — Check for sell alerts right now\n"
    "/weekly — Generate your weekly portfolio review\n"
    "/suggest — Get monthly buy suggestions for your budget\n"
    "/settings — View and update your preferences\n"
    "/budget — Set your monthly investment budget\n"
    "/risk — Set your risk tolerance (low/medium/high)\n"
    "/shariah — Toggle halal (Shariah-compliant) investment mode\n\n"
    "💡 This is not financial advice."
)

ASK_TICKER = "What's the ticker symbol? (e.g. AAPL for Apple)"
ASK_SHARES = "How many shares do you want to add? (e.g. 10 or 0.5 for fractional)"
ASK_BUDGET = "What's your monthly investment budget? (e.g. 95)"
ASK_RISK = "What's your risk tolerance?"
ASK_GOAL = "What's your investment goal?"
ASK_ALERT_PCT = "Set your sell-alert threshold (%). I'll warn you when a stock drops this much below your buy price. (e.g. 10)"

INVALID_NUMBER = "Please enter a valid number (e.g. 95 or 45.50)."
INVALID_TICKER = "Please enter a valid ticker symbol (letters only, e.g. AAPL)."
EMPTY_PORTFOLIO = "You have no holdings yet. Click '➕ Add Stock' below to begin."
GENERIC_ERROR = "Something went wrong. Please try again in a moment."
CLAUDE_ERROR = "Could not reach the AI right now. Please try again in a moment."
PRICE_NOT_FOUND = "Could not find price data for {ticker}. Please check the ticker symbol."

SETTINGS_SAVED = "✅ Settings saved!"
BUDGET_SAVED = "✅ Monthly budget set to ${budget:.2f}."
RISK_SAVED = "✅ Risk tolerance set to {risk}."
GOAL_SAVED = "✅ Goal set to {goal}."
ALERT_SAVED = "✅ Sell-alert threshold set to {pct:.0f}%."

HOLDING_ADDED = (
    "✅ Added {shares} share(s) of {ticker} at ${buy_price:.2f} each.\n"
    "Current price: {current_price}\n"
    "P&L since purchase: {pnl}"
)

HOLDING_REMOVED = "✅ Removed {ticker} from your portfolio."
HOLDING_NOT_FOUND = "No holding found for {ticker} in your portfolio."

NO_ALERTS = "✅ No sell alerts right now. Your portfolio looks okay."

DISCLAIMER = "\n\n⚠️ This is not financial advice."


def format_portfolio(holdings: list[dict], prices: dict[str, float], sort_by: str = "default") -> str:
    if not holdings:
        return EMPTY_PORTFOLIO

    lines = ["📊 Your Portfolio\n"]
    total_invested = sum(h["shares"] * h["buy_price"] for h in holdings)
    
    stats = []
    total_current = 0.0
    for h in holdings:
        ticker = h["ticker"]
        shares = h["shares"]
        buy_price = h["buy_price"]
        cost = shares * buy_price
        current = prices.get(ticker)
        
        stat = {
            "ticker": ticker,
            "shares": shares,
            "buy_price": buy_price,
            "cost": cost,
            "current": current,
            "value": cost,
            "pnl": 0.0,
            "pct": 0.0,
            "available": False
        }

        if current:
            value = shares * current
            stat["value"] = value
            stat["pnl"] = value - cost
            stat["pct"] = ((current - buy_price) / buy_price) * 100
            stat["available"] = True
            
        stats.append(stat)
        total_current += stat["value"]
        
    if sort_by == "value":
        stats.sort(key=lambda s: s["value"], reverse=True)
    elif sort_by == "performance":
        stats.sort(key=lambda s: s["pct"], reverse=True)
        
    for s in stats:
        pct_weight = (s["value"] / total_current * 100) if total_current > 0 else 0
        
        if s["available"]:
            if s["pct"] >= 10:
                flag = "🔥"
            elif s["pct"] >= 0:
                flag = "🟢"
            elif s["pct"] >= -10:
                flag = "🟡"
            else:
                flag = "🩸"
                
            lines.append(
                f"{flag} {s['ticker']}  {s['shares']} share(s)  "
                f"${s['buy_price']:.2f} → ${s['current']:.2f}  "
                f"{s['pnl']:+.2f} ({s['pct']:+.1f}%) | ${s['value']:.2f} ({pct_weight:.1f}%)"
            )
        else:
            lines.append(f"❓ {s['ticker']}  {s['shares']} share(s)  ${s['buy_price']:.2f}  (price unavailable) | ({pct_weight:.1f}%)")

    overall_pnl = total_current - total_invested
    overall_pct = (overall_pnl / total_invested * 100) if total_invested else 0

    lines.append("\n───────────────────")
    lines.append(f"Invested:      ${total_invested:.2f}")
    lines.append(f"Current value: ${total_current:.2f}")
    lines.append(f"Total P&L:     {overall_pnl:+.2f} ({overall_pct:+.1f}%)")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def format_suggestions(
    suggestions: list[dict], budget: float,
    prices: dict[str, float] | None = None,
) -> str:
    if not suggestions:
        return "Could not generate suggestions right now. Please try again."

    lines = [f"💡 Buy Suggestions for ${budget:.0f} this month\n"]
    risk_icons = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}

    for i, s in enumerate(suggestions, 1):
        risk = s.get("risk", "Medium")
        icon = risk_icons.get(risk, "🟡")
        ticker = s.get("ticker", "?")

        if prices and ticker in prices:
            price_line = f"   Current price: ${prices[ticker]:.2f} per share\n"
        elif prices is not None:
            price_line = "   Current price: unavailable (ticker not found)\n"
        else:
            price_line = ""

        lines.append(
            f"{i}. {ticker} — {s.get('name', '?')}  (${s.get('amount', 0):.0f})\n"
            f"   {s.get('reason', '')}\n"
            f"{price_line}"
            f"   Risk: {icon} {risk}\n"
            f"   Watch out for: {s.get('watchout', '')}"
        )

    lines.append(DISCLAIMER)
    return "\n\n".join(lines)
