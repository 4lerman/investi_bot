import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from db import queries
from core import market, claude, alerts

logger = logging.getLogger(__name__)


async def check_all_alerts(bot) -> None:
    logger.info("Scheduler: running daily alert check")
    users = await queries.get_all_users()
    for user in users:
        try:
            await alerts.check_user_alerts(user, bot)
        except Exception as e:
            logger.error("Alert check failed for user %s: %s", user["user_id"], e)


async def reset_all_counts() -> None:
    logger.info("Scheduler: resetting analyze counts for the week")
    try:
        await queries.reset_analyze_counts()
    except Exception as e:
        logger.error("Failed to reset analyze counts: %s", e)


async def send_weekly_reviews(bot) -> None:
    logger.info("Scheduler: sending weekly reviews")
    from bot import messages
    users = await queries.get_all_users()
    for user in users:
        user_id = user["user_id"]
        try:
            holdings = await queries.get_holdings(user_id)
            if not holdings:
                continue
            tickers = [h["ticker"] for h in holdings]
            prices = await market.get_prices(tickers)
            review = await claude.generate_weekly_review(holdings, prices, user)
            await bot.send_message(chat_id=user_id, text=review + messages.DISCLAIMER)
            await queries.log_alert(user_id, "-", "weekly")
        except Exception as e:
            logger.error("Weekly review failed for user %s: %s", user_id, e)


async def send_monthly_suggestions(bot) -> None:
    logger.info("Scheduler: sending monthly suggestions")
    from bot import messages
    from core.watchlists import get_watchlist, fetch_watchlist_data

    users = await queries.get_all_users()
    for user in users:
        user_id = user["user_id"]
        try:
            holdings = await queries.get_holdings(user_id)
            budget = user.get("budget", 95.0)
            shariah = bool(user.get("shariah", 0))

            tickers = [h["ticker"] for h in holdings]
            prices = await market.get_prices(tickers) if tickers else {}

            watchlist = get_watchlist(shariah=shariah)
            watchlist_data = await fetch_watchlist_data(watchlist, exclude_tickers=tickers)

            suggestions = await claude.generate_buy_suggestions(
                holdings, user, budget, prices,
                watchlist_data=watchlist_data,
            )

            suggestion_prices = {t: info["price"] for t, info in watchlist_data.items()}

            text = messages.format_suggestions(suggestions, budget, suggestion_prices)
            await bot.send_message(chat_id=user_id, text=text)
            await queries.log_alert(user_id, "-", "monthly")
        except Exception as e:
            logger.error("Monthly suggestions failed for user %s: %s", user_id, e)


def setup_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    # Daily alert check — every weekday at market open (14:30 UTC = 9:30 AM ET)
    scheduler.add_job(
        check_all_alerts,
        CronTrigger(day_of_week="mon-fri", hour=14, minute=30),
        args=[bot],
        id="daily_alerts",
        replace_existing=True,
    )

    # Weekly review — every Sunday at 10:00 AM UTC
    scheduler.add_job(
        send_weekly_reviews,
        CronTrigger(day_of_week="sun", hour=10),
        args=[bot],
        id="weekly_reviews",
        replace_existing=True,
    )

    # Monthly suggestions — first day of each month at 9:00 AM UTC
    scheduler.add_job(
        send_monthly_suggestions,
        CronTrigger(day=1, hour=9),
        args=[bot],
        id="monthly_suggestions",
        replace_existing=True,
    )

    # Reset analyze counts — every Monday at 00:00 UTC
    scheduler.add_job(
        reset_all_counts,
        CronTrigger(day_of_week="mon", hour=0),
        id="reset_counts",
        replace_existing=True,
    )

    return scheduler
