import asyncio
import argparse
import logging
from telegram_common.admin.set_webhook import set_webhook

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Set Telegram bot webhook URL')
    parser.add_argument('--token', required=True, help='Telegram bot token')
    parser.add_argument('--url', required=True, help='Webhook URL')

    args = parser.parse_args()

    logger.info(f"Setting webhook URL to: {args.url}")
    try:
        asyncio.run(set_webhook(args.token, args.url))
        logger.info("Webhook setup completed successfully")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        raise

if __name__ == "__main__":
    main()
