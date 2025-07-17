from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import Update,Voice, Audio
from telegram.ext import ContextTypes
from fastapi import Request
import logging
import re
import time
from html import escape as html_escape
import os
from datetime import datetime, timezone
from .audio_utils import AudioFileManager, validate_audio_size, format_file_size
import tempfile
from io import BytesIO
from .payments import create_upgrade_keyboard, handle_successful_payment

logger = logging.getLogger(__name__)

MAX_CONVERSATION_HISTORY = 22
PROCESSED_UPDATES_EXPIRY = 3600  # 1 hour = 3600 seconds

def reset_daily_usage_if_new_day(user_data: dict) -> None:
    """Reset daily usage counter if it's a new day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if user_data["daily_usage"]["date"] != today:
        user_data["daily_usage"]["count"] = 0
        user_data["daily_usage"]["date"] = today

def init_user_data(system_prompt: str, bot_config: dict = None):
    """Initialize user data structure."""
    # Only add system prompt to history if it exists (for conversational bots)
    history = []
    if system_prompt and system_prompt.strip():
        history = [{"role": "system", "content": system_prompt}]

    return {
        "history": history,
        "daily_usage": {
            "count": 0,
            "date": "",
            "limit": (bot_config or {}).get("daily_limit", float('inf'))
        },
        "is_premium": False
    }

async def check_user_access(user_data: dict, update: Update, bot_config: dict = None) -> bool:
    """Check if user can send messages based on usage."""

    # If user has premium, always allow
    if user_data.get("is_premium", False):
        return True

    # Reset usage if new day
    reset_daily_usage_if_new_day(user_data)

    # Check if user has messages left (handles both free and freemium bots)
    if user_data["daily_usage"]["count"] >= user_data["daily_usage"]["limit"]:
        # Only show upgrade prompt if there's actually a limit configured
        if bot_config and "daily_limit" in bot_config:
            await send_upgrade_prompt(update, bot_config)
        return False

    # Increment usage counter
    user_data["daily_usage"]["count"] += 1
    return True

async def send_upgrade_prompt(update: Update, bot_config: dict):
    """Send upgrade message when user hits daily limit."""
    price_stars = bot_config.get("premium_price_stars", 100)
    price_usd = price_stars / 100

    # Pass the bot instance to create_upgrade_keyboard
    keyboard = await create_upgrade_keyboard(bot_config, update.get_bot())

    await update.message.reply_text(
        f"🤖 <b>Daily limit reached!</b>\n\n"
        f"You've used your {bot_config['daily_limit']} free messages today.\n"
        f"Come back tomorrow, or upgrade to Premium for unlimited chats!\n\n"
        f"✨ <b>Premium: ${price_usd:.2f}/month</b>\n"
        f"• Unlimited daily conversations\n\n"
        f"Tap the button below to get started! ⭐",
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command."""
    user_id = str(update.effective_user.id)
    logger.info(f"User {user_id} started the bot")
    conversations = context.bot_data["conversations"]
    bot_config = context.bot_data.get("bot_config")
    speech_only = context.bot_data.get("speech_only", False)
    bot_name = context.bot_data.get("bot_name", "Assistant")

    conversations[user_id] = init_user_data(context.bot_data["system_prompt"], bot_config)

    if speech_only:
        await update.message.reply_text(
            f"🎙️ **Welcome to {bot_name}!** ✨\n\n"
            "I'm your magical speech conversion assistant:\n\n"
            "🎙️ **Send voice messages** → I'll transcribe them to text\n"
            "📝 **Send text messages** → I'll convert them to speech\n"
            "📤 **Forward messages** → I'll convert them automatically\n\n"
            "Just start sending! No special commands needed.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("Hi! What's your name? And how can I help you today?")

def markdown_to_telegram_html(text):
    """
    Convert markdown to simple HTML that Telegram can reliably display.
    Handles basic formatting with proper tag nesting and validation.
    """
    # First remove any existing HTML tags to prevent issues
    text = re.sub(r'<[^>]+>', '', text)

    # Escape special characters (before converting markdown to HTML)
    # Escape < that isn't part of a proper HTML tag
    text = re.sub(r'<(?![/]?[a-z]+>)', '&lt;', text)

    # Convert markdown to HTML with proper nesting
    # We'll process in multiple passes with careful ordering

    # Step 1: Convert code blocks first (they shouldn't contain other formatting)
    text = re.sub(r'```.*?\n(.*?)```', r'<pre>\1</pre>', text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)

    # Step 2: Convert bold-italic combinations (processed before individual formats)
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<b><i>\1</i></b>', text)

    # Step 3: Convert bold (must come before italic to prevent conflicts)
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

    # Step 4: Convert italic
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)

    # Step 5: Convert strikethrough
    text = re.sub(r'~~(.*?)~~', r'<s>\1</s>', text)

    # Step 6: Convert headers to bold
    text = re.sub(r'^#+\s+(.*?)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # Step 7: Validate all tags are properly closed
    stack = []
    i = 0
    result = []

    while i < len(text):
        if text.startswith('<b>', i):
            stack.append('b')
            result.append('<b>')
            i += 3
        elif text.startswith('<i>', i):
            stack.append('i')
            result.append('<i>')
            i += 3
        elif text.startswith('<s>', i):
            stack.append('s')
            result.append('<s>')
            i += 3
        elif text.startswith('<code>', i):
            stack.append('code')
            result.append('<code>')
            i += 6
        elif text.startswith('<pre>', i):
            stack.append('pre')
            result.append('<pre>')
            i += 5
        elif text.startswith('</b>', i) and stack and stack[-1] == 'b':
            stack.pop()
            result.append('</b>')
            i += 4
        elif text.startswith('</i>', i) and stack and stack[-1] == 'i':
            stack.pop()
            result.append('</i>')
            i += 4
        elif text.startswith('</s>', i) and stack and stack[-1] == 's':
            stack.pop()
            result.append('</s>')
            i += 4
        elif text.startswith('</code>', i) and stack and stack[-1] == 'code':
            stack.pop()
            result.append('</code>')
            i += 7
        elif text.startswith('</pre>', i) and stack and stack[-1] == 'pre':
            stack.pop()
            result.append('</pre>')
            i += 6
        else:
            # Skip any unmatched closing tags
            if text.startswith('</', i):
                # Find the next '>'
                gt_pos = text.find('>', i)
                if gt_pos != -1:
                    i = gt_pos + 1
                    continue
            result.append(text[i])
            i += 1

    # Close any remaining open tags
    while stack:
        tag = stack.pop()
        result.append(f'</{tag}>')

    # After existing processing (stack-based tag closing):
    processed_text = ''.join(result)

    # Step 8: Escape special characters not in valid tags
    def replace_match(match):
        if match.group(1):
            return match.group(1)  # Preserve valid tags
        return html_escape(match.group(3))

    pattern = re.compile(
        r'(</?(b|i|s|a|code|pre)\b[^>]*>)|([<>&])',
        flags=re.IGNORECASE
    )

    return pattern.sub(replace_match, processed_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for incoming messages."""
    try:
        user_id = str(update.effective_user.id)

        # Check if this is a successful payment
        if update.message.successful_payment:
            await handle_successful_payment(update, context)
            return

        user_message = update.message.text
        logger.info(f"Received message from {user_id}: {user_message}")

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Get conversation history from persistent storage
        conversations = context.bot_data["conversations"]
        bot_config = context.bot_data.get("bot_config")

        # Initialize user data if not exists
        if user_id not in conversations:
            conversations[user_id] = init_user_data(context.bot_data["system_prompt"], bot_config)

        user_data = conversations[user_id]

        # Check if user can send messages
        if not await check_user_access(user_data, update, bot_config):
            return

        history = user_data["history"]

        # Append the user's message
        history.append({"role": "user", "content": user_message})

        # Log the full conversation history
        logger.info(f"Current conversation history for user {user_id}:")
        for idx, msg in enumerate(history):
            logger.info(f"  [{idx}] {msg['role']}: {msg['content']}")

        # Generate a response using the model client
        model_client = context.bot_data["model_client"]
        logger.info(f"Calling model API with user message: {user_message}")

        # Improved error handling for model responses
        try:
            response_text = await model_client.generate_response(user_message, history)
            if not response_text or response_text.strip() == "":
                logger.error("Received empty response from model API")
                raise ValueError("Empty response from API")
            logger.info(f"Bot response: {response_text} ({len(response_text)} characters)")
        except Exception as e:
            logger.error(f"Error getting response from model: {str(e)}")
            raise  # Re-raise to be caught by the outer try/except

        # Convert Markdown to HTML
        html_response = markdown_to_telegram_html(response_text)
        logger.info(f"HTML response: {html_response} ({len(html_response)} characters)")

        # Append the assistant's response (store the original markdown version)
        history.append({"role": "assistant", "content": response_text})

        # Trim the conversation history if it gets too long
        if len(history) > MAX_CONVERSATION_HISTORY:
            history = [history[0]] + history[-(MAX_CONVERSATION_HISTORY-1):]  # Keep system prompt + last (MAX-1) messages

        # Save the updated conversation history
        user_data["history"] = history
        conversations[user_id] = user_data

        logger.info(f"Sending response to user {user_id}")
        await update.message.reply_text(html_response, parse_mode="HTML")
        logger.info(f"Response sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}, type: {type(e).__name__}")
        await update.message.reply_text("Sorry, I'm having trouble right now. Could you try again in a moment?")

async def webhook_handler(request: Request, token: str, application, processed_updates):
    """Handle incoming webhook updates with protection against race conditions."""
    if token != os.environ.get("TELEGRAM_TOKEN"):
        return {"error": "Invalid token"}

    try:
        update_data = await request.json()
        current_time = time.time()

        # Clean up old entries
        expired_keys = []
        for key, value in list(processed_updates.items()):
            if isinstance(value, dict) and 'timestamp' in value:
                if current_time - value['timestamp'] > PROCESSED_UPDATES_EXPIRY:
                    expired_keys.append(key)
            elif isinstance(value, bool) and value is True:
                processed_updates[key] = {'timestamp': current_time}

        for key in expired_keys:
            logger.info(f"Removing expired update record: {key}")
            del processed_updates[key]

        # Get update ID
        update_id = str(update_data.get('update_id'))

        # Check if this update is already being processed or has been processed
        if update_id in processed_updates:
            value = processed_updates[update_id]

            # Check if it's in "processing" state (temporary state before completion)
            if isinstance(value, dict) and value.get('status') == 'processing':
                processing_time = current_time - value.get('timestamp', 0)
                logger.info(f"Update {update_id} is already being processed for {processing_time:.1f} seconds")
                return {"ok": True, "info": "Update already being processed"}
            else:
                logger.info(f"Skipping duplicate update {update_id}")
                return {"ok": True, "info": "Update already processed"}

        # Mark as "being processed" immediately
        processed_updates[update_id] = {
            'timestamp': current_time,
            'status': 'processing'
        }
        logger.info(f"Started processing update {update_id}")

        # Process the update
        update = Update.de_json(update_data, application.bot)
        await application.process_update(update)

        # Mark as completed
        processed_updates[update_id] = {
            'timestamp': current_time,
            'status': 'completed'
        }
        logger.info(f"Successfully processed update {update_id}")

        return {"ok": True}
    except Exception as e:
        # In case of error, still mark the update as processed to prevent retries
        if 'update_id' in locals():
            processed_updates[update_id] = {
                'timestamp': current_time,
                'status': 'error',
                'error': str(e)
            }
            logger.error(f"Error processing update {update_id}: {str(e)}")
        else:
            logger.error(f"Error processing webhook: {str(e)}")
        return {"ok": False, "error": str(e)}

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /clear command."""
    user_id = str(update.effective_user.id)
    conversations = context.bot_data["conversations"]
    bot_config = context.bot_data.get("bot_config")
    speech_only = context.bot_data.get("speech_only", False)
    bot_name = context.bot_data.get("bot_name", "Assistant")

    # Reset the conversation but PRESERVE usage tracking
    if user_id in conversations:
        user_data = conversations[user_id]

        # Only reset the conversation history, keep daily_usage and is_premium
        system_prompt = context.bot_data["system_prompt"]
        if system_prompt and system_prompt.strip():
            user_data["history"] = [{"role": "system", "content": system_prompt}]
        else:
            user_data["history"] = []  # Empty history for speech-only bots

        reset_daily_usage_if_new_day(user_data)
        conversations[user_id] = user_data  # Force Modal Dict save

        # Create appropriate response message
        if speech_only:
            response_msg = f"🎙️ {bot_name} ready for speech conversion! Send text or voice messages."
        elif not bot_config or "daily_limit" not in bot_config:
            # Free bot
            response_msg = "Conversation history has been cleared!"
        elif user_data.get("is_premium", False):
            # Premium user
            response_msg = "Conversation history has been cleared! (Premium - unlimited messages)"
        else:
            # Freemium user - show remaining count
            daily_usage = user_data["daily_usage"]
            remaining = max(0, daily_usage["limit"] - daily_usage["count"])
            response_msg = (
                f"Conversation history has been cleared!\n\n"
                f"📊 You have {remaining} messages remaining today."
            )
    else:
        # New user - initialize normally
        conversations[user_id] = init_user_data(context.bot_data["system_prompt"], bot_config)
        if speech_only:
            response_msg = f"🎙️ {bot_name} ready for speech conversion! Send text or voice messages."
        else:
            response_msg = "Conversation history has been cleared!"

    logger.info(f"Cleared conversation history for user {user_id}")
    await update.message.reply_text(response_msg)

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for voice messages - convert speech to text."""
    try:
        user_id = str(update.effective_user.id)
        voice = update.message.voice

        logger.info(f"Received voice message from {user_id}: {voice.duration}s, {voice.file_size} bytes")

        # Validate file size
        if not validate_audio_size(voice.file_size):
            await update.message.reply_text(
                f"Voice message too large ({format_file_size(voice.file_size)}). "
                f"Please send a shorter message (max 20MB)."
            )
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Get the model client
        model_client = context.bot_data["model_client"]

        # Check if speech is enabled
        if not hasattr(model_client, 'enable_speech') or not model_client.enable_speech:
            await update.message.reply_text(
                "🎙️ Speech processing is not enabled for this bot."
            )
            return

        temp_file = None
        try:
            # Download the voice file
            file = await context.bot.get_file(voice.file_id)

            # Create temporary file
            temp_file = AudioFileManager.create_temp_file(".ogg")
            await file.download_to_drive(temp_file.name)

            # Transcribe the audio
            with open(temp_file.name, 'rb') as audio_file:
                transcription = await model_client.transcribe_audio(audio_file, "voice.ogg")

            if transcription and transcription.strip():
                # Send transcription with voice emoji
                await update.message.reply_text(f"🎙️ *Transcription:*\n\n{transcription}", parse_mode="Markdown")
                logger.info(f"Transcribed voice message for user {user_id}: {len(transcription)} characters")
            else:
                await update.message.reply_text("🤔 I couldn't understand the audio. Please try speaking more clearly.")

        finally:
            # Cleanup
            if temp_file:
                AudioFileManager.cleanup_temp_file(temp_file.name)

    except Exception as e:
        logger.error(f"Error processing voice message: {str(e)}")
        await update.message.reply_text(
            "Sorry, I had trouble processing your voice message. Please try again."
        )

async def handle_text_to_speech(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for text messages - convert ALL text to speech."""
    try:
        user_id = str(update.effective_user.id)
        text = update.message.text

        logger.info(f"TTS request from {user_id}: {len(text)} characters")

        # Validate text length (TTS services have limits)
        if len(text) > 4000:
            await update.message.reply_text(
                "Text too long for speech conversion. Please keep it under 4000 characters."
            )
            return

        if not text.strip():
            await update.message.reply_text("Please send some text to convert to speech.")
            return

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="record_voice")

        # Get the model client
        model_client = context.bot_data["model_client"]

        # Check if speech is enabled
        if not hasattr(model_client, 'enable_speech') or not model_client.enable_speech:
            await update.message.reply_text(
                "🔊 Speech generation is not enabled for this bot."
            )
            return

        # Generate speech from the text
        audio_bytes = await model_client.generate_speech(text)

        # Send as voice message
        audio_file = BytesIO(audio_bytes)
        audio_file.name = "speech.ogg"

        await context.bot.send_voice(
            chat_id=update.effective_chat.id,
            voice=audio_file,
            caption=f"🔊 _{text[:100]}{'...' if len(text) > 100 else ''}_",
            parse_mode="Markdown"
        )

        logger.info(f"Generated speech for user {user_id}: {len(audio_bytes)} bytes")

    except Exception as e:
        logger.error(f"Error generating speech: {str(e)}")
        await update.message.reply_text(
            "Sorry, I had trouble converting your text to speech. Please try again."
        )

async def initialize_bot(token: str, model_client, system_prompt: str, conversations, bot_config: dict = None, speech_only: bool = False, bot_name: str = "Assistant"):
    application = Application.builder().token(token).build()
    application.bot_data["model_client"] = model_client
    application.bot_data["bot_name"] = bot_name

    # For speech-only, we don't need system prompt at all
    if speech_only:
        application.bot_data["system_prompt"] = ""
    else:
        # For conversational bots, use provided system prompt or fallback
        if not system_prompt:
            system_prompt = "You are a helpful assistant."
        application.bot_data["system_prompt"] = f"{system_prompt} Keep responses conversational and max 11 sentences."

    application.bot_data["conversations"] = conversations
    application.bot_data["bot_config"] = bot_config
    application.bot_data["speech_only"] = speech_only

    # Add basic handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear))

    if speech_only:
        # Speech-only bot: ONLY convert between text and speech, no conversation
        logger.info("Initializing speech-only bot handlers")
        application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
        application.add_handler(MessageHandler(filters.AUDIO, handle_voice_message))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_to_speech))
    else:
        # Regular chat bot: ONLY text conversation, no speech features
        logger.info("Initializing regular chat bot handlers")
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await application.initialize()
    return application
