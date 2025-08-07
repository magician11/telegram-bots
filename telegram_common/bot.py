from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes
from fastapi import Request
import logging
import re
import time
import base64
from html import escape as html_escape
import os
from datetime import datetime, timezone, timedelta
from .audio_utils import AudioFileManager, validate_audio_size, format_file_size
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
            "date": ""
        },
        "is_premium": False
    }

async def check_user_access(user_data: dict, update: Update, bot_config: dict = None) -> bool:
    # If user has premium, always allow
    if user_data.get("is_premium", False):
        return True

    # Reset usage if new day
    reset_daily_usage_if_new_day(user_data)

    # Get current limit from bot_config, not stored user data
    current_limit = (bot_config or {}).get("daily_limit", float('inf'))

    # Check if user has messages left
    if user_data["daily_usage"]["count"] >= current_limit:
        user_id = update.effective_user.id
        logger.info(f"User {user_id} hit daily message limit of {current_limit}.")
        if bot_config and "daily_limit" in bot_config:
            await send_upgrade_prompt(update, bot_config)
        return False

    # Increment usage counter
    user_data["daily_usage"]["count"] += 1
    return True

def get_time_until_reset() -> str:
    """Calculate time remaining until daily usage resets (midnight UTC)."""
    now = datetime.now(timezone.utc)

    # Calculate next midnight UTC
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    time_remaining = tomorrow - now

    # Extract hours and minutes
    hours = int(time_remaining.total_seconds() // 3600)
    minutes = int((time_remaining.total_seconds() % 3600) // 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"

async def send_upgrade_prompt(update: Update, bot_config: dict):
    """Send upgrade message when user hits daily limit."""
    price_stars = bot_config.get("premium_price_stars", 100)
    price_usd = price_stars / 100

    # Calculate time until reset
    reset_time = get_time_until_reset()

    # Pass the bot instance to create_upgrade_keyboard
    keyboard = await create_upgrade_keyboard(bot_config, update.get_bot())

    await update.message.reply_text(
        f"🤖 <b>Daily limit reached!</b>\n\n"
        f"You've used your {bot_config['daily_limit']} free messages today.\n"
        f"⏰ Free messages reset in: <b>{reset_time}</b>\n\n"
        f"Or upgrade to Premium for unlimited chats!\n\n"
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
    model_client = context.bot_data["model_client"]
    system_prompt = context.bot_data["system_prompt"]

    user_data = init_user_data(system_prompt, bot_config)

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
        # Generate AI-powered opening based on the bot's persona
        try:
            # Simple prompt that lets the AI's personality shine through
            opening_generation_prompt = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Generate a brief, friendly opening message for a new user. Ask for their name and how you can help them. Stay fully in character and be welcoming. Keep it under 60 words. You may use markdown formatting for emphasis."}
            ]

            logger.info(f"Generating personalized opening for user {user_id}")
            opening_message = await model_client.generate_response(opening_generation_prompt)

            # Fallback if generation fails or returns empty
            if not opening_message or opening_message.strip() == "":
                opening_message = "Hi! What's your name? And how can I help you today?"
                logger.warning(f"AI opening generation failed for user {user_id}, using fallback")

        except Exception as e:
            logger.error(f"Error generating opening for user {user_id}: {e}")
            opening_message = "Hi! What's your name? And how can I help you today?"

        # Send the opening message with markdown support
        await update.message.reply_text(opening_message, parse_mode="Markdown")

        # Record in conversation history so the AI knows what it asked
        user_data["history"].append({"role": "assistant", "content": opening_message})
        logger.info(f"Opening message sent and recorded for user {user_id}: {opening_message}")

    conversations[user_id] = user_data

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

async def process_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE, message_content, message_type: str = "text"):
    """Shared message processing logic for text, photos, etc."""
    try:
        user_id = str(update.effective_user.id)
        logger.info(f"Processing {message_type} message from {user_id}")

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Get conversation data
        conversations = context.bot_data["conversations"]
        bot_config = context.bot_data.get("bot_config")

        # Initialize user data if needed
        if user_id not in conversations:
            conversations[user_id] = init_user_data(context.bot_data["system_prompt"], bot_config)

        user_data = conversations[user_id]

        # Check usage limits
        if not await check_user_access(user_data, update, bot_config):
            return

        # Add message to history
        history = user_data["history"]
        history.append({"role": "user", "content": message_content})

        # Log conversation history
        logger.info(f"Current conversation history for user {user_id}:")
        for idx, msg in enumerate(history):
            content_preview = str(msg['content']) if isinstance(msg['content'], str) else "[complex content]"
            logger.info(f"  [{idx}] {msg['role']}: {content_preview}")

        # Generate response
        model_client = context.bot_data["model_client"]
        logger.info(f"Calling model API for {message_type} message")

        try:
            response_text = await model_client.generate_response(history)
            if not response_text or response_text.strip() == "":
                logger.error("Received empty response from model API")
                raise ValueError("Empty response from API")
            logger.info(f"Bot response: {response_text} ({len(response_text)} characters)")
        except Exception as e:
            logger.error(f"Error getting response from model: {str(e)}")
            raise

        # Convert markdown to HTML and send
        html_response = markdown_to_telegram_html(response_text)
        history.append({"role": "assistant", "content": response_text})

        # Trim history if needed
        if len(history) > MAX_CONVERSATION_HISTORY:
            history = [history[0]] + history[-(MAX_CONVERSATION_HISTORY-1):]

        # Save updated conversation
        user_data["history"] = history
        conversations[user_id] = user_data

        logger.info(f"Sending response to user {user_id}")
        await update.message.reply_text(html_response, parse_mode="HTML")
        logger.info(f"Response sent to user {user_id}")

    except Exception as e:
        logger.error(f"Error processing {message_type} message: {str(e)}, type: {type(e).__name__}")
        await update.message.reply_text("Sorry, I'm having trouble right now. Could you try again in a moment?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for text messages."""
    if update.message.successful_payment:
        await handle_successful_payment(update, context)
        return

    user_message = update.message.text
    await process_user_message(update, context, user_message, "text")

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for photo messages with optional caption."""
    try:
        photo = update.message.photo[-1]  # Get largest size
        caption = update.message.caption or "What do you see in this image?"

        # Validate file size (20MB as per X.AI docs)
        max_size = 20 * 1024 * 1024
        if photo.file_size > max_size:
            await update.message.reply_text(
                f"Image too large ({format_file_size(photo.file_size)}). Please send a smaller image (max 20MB)."
            )
            return

        # Check if model supports vision
        model_client = context.bot_data["model_client"]
        if not hasattr(model_client, 'supports_vision') or not model_client.supports_vision():
            await update.message.reply_text(
                "Sorry, this bot doesn't support image analysis. Please send text messages instead."
            )
            return

        # Download and encode image
        try:
            file = await context.bot.get_file(photo.file_id)
            file_bytes = await file.download_as_bytearray()
            base64_image = base64.b64encode(file_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Error downloading/encoding image: {str(e)}")
            await update.message.reply_text("Sorry, I couldn't process that image. Please try again.")
            return

        # Create vision message content
        content = [
            {"type": "text", "text": caption},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
        ]

        # Use shared processor
        await process_user_message(update, context, content, "photo")

    except Exception as e:
        logger.error(f"Error processing photo message: {str(e)}")
        await update.message.reply_text("Sorry, I had trouble processing your image. Please try again.")

async def webhook_handler(request: Request, token: str, application, processed_updates):
    """Handle incoming webhook updates with protection against race conditions."""
    if token != os.environ.get("TELEGRAM_TOKEN"):
        return {"error": "Invalid token"}

    current_time = time.time()

    try:
        update_data = await request.json()

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
            current_limit = (bot_config or {}).get("daily_limit", float('inf'))
            remaining = max(0, current_limit - daily_usage["count"])
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
    """Handler for voice messages and audio files - convert speech to text."""
    try:
        user_id = str(update.effective_user.id)

        # Handle both voice messages and audio files
        audio_obj = update.message.voice or update.message.audio

        if not audio_obj:
            logger.error("No voice or audio data found in message")
            await update.message.reply_text("No audio data found in your message.")
            return

        # Use original filename for audio files, default for voice messages
        if update.message.audio and hasattr(audio_obj, 'file_name') and audio_obj.file_name:
            filename = audio_obj.file_name
            extension = os.path.splitext(filename)[1] or ".m4a"  # fallback if no extension
        else:
            filename = "voice.ogg"
            extension = ".ogg"

        logger.info(f"Received audio from {user_id}: {audio_obj.duration}s, {audio_obj.file_size} bytes, filename: {filename}")

        # Validate file size
        if not validate_audio_size(audio_obj.file_size):
            await update.message.reply_text(
                f"Audio message too large ({format_file_size(audio_obj.file_size)}). "
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
            # Download the audio file
            file = await context.bot.get_file(audio_obj.file_id)

            # Create temporary file with correct extension
            temp_file = AudioFileManager.create_temp_file(extension)
            await file.download_to_drive(temp_file.name)
            temp_file.close()  # Close the file handle

            # Transcribe the audio using original filename
            with open(temp_file.name, 'rb') as audio_file:
                transcription = await model_client.transcribe_audio(audio_file, filename)

            if transcription and transcription.strip():
                # Send transcription with voice emoji
                await update.message.reply_text(f"🎙️ *Transcription:*\n\n{transcription}", parse_mode="Markdown")
                logger.info(f"Transcribed audio for user {user_id}: {len(transcription)} characters")
            else:
                await update.message.reply_text("🤔 I couldn't understand the audio. Please try speaking more clearly.")

        finally:
            # Cleanup
            if temp_file:
                AudioFileManager.cleanup_temp_file(temp_file.name)

    except Exception as e:
        logger.error(f"Error processing audio message: {str(e)}")
        await update.message.reply_text(
            "Sorry, I had trouble processing your audio message. Please try again."
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
        application.bot_data["system_prompt"] = f"{system_prompt} Keep responses to a maximum of 11 sentences."

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
        # Regular chat bot: ONLY text and images conversation, no speech features
        logger.info("Initializing regular chat bot handlers")
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))

    await application.initialize()
    return application
