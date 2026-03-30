import logging
from db import queries
from core import market, claude

logger = logging.getLogger(__name__)


async def check_user_alerts(user: dict, bot) -> None:
    """Check sell alerts for a single user and send messages if triggered."""
    user_id = user["user_id"]
    threshold = user.get("alert_pct", 10.0)

    holdings = await queries.get_holdings(user_id)
    if not holdings:
        return

    tickers = [h["ticker"] for h in holdings]
    prices = await market.get_prices(tickers)

    triggered = []
    for h in holdings:
        ticker = h["ticker"]
        price = prices.get(ticker)
        if not price:
            continue
        drop_pct = ((h["buy_price"] - price) / h["buy_price"]) * 100
        if drop_pct >= threshold:
            already_sent = await queries.was_alerted_today(user_id, ticker, "sell")
            if not already_sent:
                triggered.append((h, price, drop_pct))

    if not triggered:
        return

    try:
        analysis = await claude.check_sell_alerts(holdings, prices, threshold)
    except Exception as e:
        logger.error("Claude error during alert check for user %s: %s", user_id, e)
        analysis = "Consider reviewing this position."

    from bot import keyboards, messages
    for h, price, drop_pct in triggered:
        ticker = h["ticker"]
        text = (
            f"⚠️ SELL ALERT — {ticker}\n\n"
            f"You're down {drop_pct:.1f}% on {ticker}.\n"
            f"Your alert threshold is {threshold:.0f}%.\n\n"
            f"{analysis}"
            f"{messages.DISCLAIMER}"
        )
        try:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=keyboards.after_alert_keyboard(ticker),
            )
            await queries.log_alert(user_id, ticker, "sell")
        except Exception as e:
            logger.error("Failed to send alert to user %s: %s", user_id, e)
