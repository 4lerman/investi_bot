import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application, ApplicationBuilder, CommandHandler, CallbackQueryHandler, PicklePersistence
from bot.error_handler import error_handler

from bot.handlers import (
    help_handler,
    portfolio_handler,
    analyze_handler,
    alerts_handler,
    weekly_handler,
    suggest_handler,
    settings_handler,
    remove_handler,
    risk_handler,
    shariah_handler,
    setup_conversation_handler,
    add_stock_conversation_handler,
    budget_conversation_handler,
    alert_conversation_handler,
    callback_handler,
)
from core.scheduler import setup_scheduler
from db.database import init_db

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    await init_db()
    logger.info("Database initialised.")

    scheduler = setup_scheduler(app.bot)
    scheduler.start()
    logger.info("Scheduler started.")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env")

    persistence = PicklePersistence(filepath="bot_state.pickle")
    app = (
        ApplicationBuilder()
        .token(token)
        .persistence(persistence)
        .post_init(post_init)
        .build()
    )

    # Global Error Handler
    app.add_error_handler(error_handler)

    # Conversation handlers first (they have priority)
    app.add_handler(setup_conversation_handler())
    app.add_handler(add_stock_conversation_handler())
    app.add_handler(budget_conversation_handler())
    app.add_handler(alert_conversation_handler())

    # Simple command handlers
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("portfolio", portfolio_handler))
    app.add_handler(CommandHandler("analyze", analyze_handler))
    app.add_handler(CommandHandler("alerts", alerts_handler))
    app.add_handler(CommandHandler("weekly", weekly_handler))
    app.add_handler(CommandHandler("suggest", suggest_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(CommandHandler("remove", remove_handler))
    app.add_handler(CommandHandler("risk", risk_handler))
    app.add_handler(CommandHandler("shariah", shariah_handler))

    # Inline button callbacks
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
