import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot import messages

logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a generic message to notify the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Note that update can be an Update, or it can be something else if an error
    # happened outside of a standard update hook.
    if isinstance(update, Update):
        try:
            if update.effective_message:
                await update.effective_message.reply_text(messages.GENERIC_ERROR)
            elif update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(messages.GENERIC_ERROR)
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")
