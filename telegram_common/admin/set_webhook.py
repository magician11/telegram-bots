import logging
from telegram import Bot
from urllib.parse import urljoin

# Update the logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def set_webhook(token: str, webhook_url: str):
    """Set the webhook URL for the bot."""
    try:
        bot = Bot(token)
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Current webhook: {webhook_info.url}")

        # Construct the full webhook URL including the token path
        full_webhook_url = urljoin(webhook_url, f"webhook/{token}")
        logger.info(f"Constructed webhook URL: {full_webhook_url}")

        if webhook_info.url != full_webhook_url:
            logger.info(f"Setting webhook to: {full_webhook_url}")
            result = await bot.set_webhook(full_webhook_url)
            logger.info(f"Webhook set successfully: {result}")
        else:
            logger.info("Webhook already set correctly")

        # Add additional webhook info
        updated_webhook_info = await bot.get_webhook_info()
        logger.info(f"Final webhook configuration: {updated_webhook_info.to_dict()}")
    except Exception as e:
        logger.error(f"Error setting webhook: {str(e)}")
        raise
