import os
import logging
from telegram import Bot

logger = logging.getLogger(__name__)

async def set_webhook(token: str, webhook_url: str):
    """Set the webhook URL for the bot."""
    try:
        bot = Bot(token)
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Current webhook: {webhook_info.url}")

        if webhook_info.url != webhook_url:
            logger.info(f"Setting webhook to: {webhook_url}")
            await bot.set_webhook(webhook_url)
            logger.info("Webhook set successfully")
        else:
            logger.info("Webhook already set correctly")
    except Exception as e:
        logger.error(f"Error setting webhook: {str(e)}")
        raise
