import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes, CallbackQueryHandler

logger = logging.getLogger(__name__)

async def create_upgrade_keyboard(bot_config: dict, bot) -> InlineKeyboardMarkup:
    """Create inline keyboard for upgrade prompt with direct URL button."""
    price_stars = bot_config.get("premium_price_stars", 100)
    price_usd = price_stars / 100

    # Create the subscription link immediately
    invoice_link = await create_subscription_invoice(bot, price_stars, bot_config)

    keyboard = [
        [InlineKeyboardButton(
            f"⭐ Upgrade for ${price_usd:.2f}/month",
            url=invoice_link
        )]
    ]
    return InlineKeyboardMarkup(keyboard)

async def create_subscription_invoice(bot, price_stars: int, bot_config: dict) -> str:
    """Create a subscription invoice link."""
    try:
        invoice_link = await bot.create_invoice_link(
            title="Premium Subscription",
            description="Unlimited AI conversations with premium features",
            payload=f"premium_subscription_{price_stars}",
            currency="XTR",  # Telegram Stars
            prices=[{"label": "Monthly Access", "amount": price_stars}],
            subscription_period=2592000,  # 30 days in seconds
            max_tip_amount=0,
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False
        )
        logger.info(f"Created subscription invoice link: {invoice_link}")
        return invoice_link
    except Exception as e:
        logger.error(f"Error creating subscription invoice: {str(e)}")
        bot_info = await bot.get_me()
        return f"https://t.me/{bot_info.username}"  # Fallback

async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle successful payment webhook."""
    try:
        payment = update.message.successful_payment
        user_id = str(update.effective_user.id)

        logger.info(f"Successful payment from user {user_id}: {payment.telegram_payment_charge_id}")

        # Upgrade user to premium
        conversations = context.bot_data["conversations"]
        if user_id in conversations:
            conversations[user_id]["is_premium"] = True
            logger.info(f"Upgraded user {user_id} to premium")

        bot_name_info = await context.bot.get_my_name()

        await update.message.reply_text(
            "🎉 <b>Welcome to Premium!</b>\n\n"
            "You now have unlimited daily conversations! "
            f"Thank you for supporting {bot_name_info.name}! 💫",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error handling successful payment: {str(e)}")
        await update.message.reply_text(
            "Payment received, but there was an issue upgrading your account. "
            "Please contact support."
        )
