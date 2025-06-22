import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ContextTypes, CallbackQueryHandler

logger = logging.getLogger(__name__)

async def create_upgrade_keyboard(bot_config: dict) -> InlineKeyboardMarkup:
    """Create inline keyboard for upgrade prompt."""
    price_stars = bot_config.get("premium_price_stars", 100)
    price_usd = price_stars / 100

    keyboard = [
        [InlineKeyboardButton(
            f"⭐ Upgrade for ${price_usd:.2f}/month",
            callback_data=f"upgrade_premium_{price_stars}"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_upgrade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle upgrade button press."""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("upgrade_premium_"):
        price_stars = int(query.data.split("_")[-1])
        bot_config = context.bot_data.get("bot_config", {})

        # Create subscription invoice link
        invoice_link = await create_subscription_invoice(
            context.bot,
            price_stars,
            bot_config
        )

        await query.edit_message_text(
            f"🎉 <b>Ready to upgrade!</b>\n\n"
            f"Tap the link below to subscribe with Telegram Stars:\n\n"
            f"💫 <a href='{invoice_link}'>Subscribe for ${price_stars/100:.2f}/month</a>\n\n"
            f"After payment, you'll have unlimited access immediately!",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

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
        return "https://t.me/your_bot"  # Fallback

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

        await update.message.reply_text(
            "🎉 <b>Welcome to Premium!</b>\n\n"
            "You now have unlimited daily conversations! "
            "Thank you for supporting the bot! 💫",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error handling successful payment: {str(e)}")
        await update.message.reply_text(
            "Payment received, but there was an issue upgrading your account. "
            "Please contact support."
        )
