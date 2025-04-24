from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes
from fastapi import Request
import logging
import re
import time
from html import escape as html_escape
import os

logger = logging.getLogger(__name__)

MAX_CONVERSATION_HISTORY = 22
PROCESSED_UPDATES_EXPIRY = 3600  # 1 hour = 3600 seconds

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command."""
    user_id = str(update.effective_user.id)
    logger.info(f"User {user_id} started the bot")
    conversations = context.bot_data["conversations"]
    conversations[user_id] = [{"role": "system", "content": context.bot_data["system_prompt"]}]
    await update.message.reply_text("Hi! How can I help you today?")

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
        user_message = update.message.text
        logger.info(f"Received message from {user_id}: {user_message}")

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Get conversation history from persistent storage
        conversations = context.bot_data["conversations"]
        history = conversations.get(user_id, [{"role": "system", "content": context.bot_data["system_prompt"]}])

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
            logger.info(f"Received valid response from model API: {len(response_text)} characters")
        except Exception as e:
            logger.error(f"Error getting response from model: {str(e)}")
            raise  # Re-raise to be caught by the outer try/except

        # Convert Markdown to HTML
        html_response = markdown_to_telegram_html(response_text)
        logger.info(f"Converted response to HTML: {len(html_response)} characters")

        # Append the assistant's response (store the original markdown version)
        history.append({"role": "assistant", "content": response_text})

        # Trim the conversation history if it gets too long
        if len(history) > MAX_CONVERSATION_HISTORY:
            history = [history[0]] + history[-(MAX_CONVERSATION_HISTORY-1):]  # Keep system prompt + last (MAX-1) messages

        # Save the updated conversation history
        conversations[user_id] = history

        logger.info(f"Sending response to user {user_id}")
        await update.message.reply_text(html_response, parse_mode="HTML")
        logger.info(f"Response sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}, type: {type(e).__name__}")
        await update.message.reply_text("Sorry, I'm having trouble right now. Could you try again in a moment?")

async def webhook_handler(request: Request, token: str, application, processed_updates):
    """Handle incoming webhook updates with expiry mechanism for old entries."""
    if token != os.environ.get("TELEGRAM_TOKEN"):
        return {"error": "Invalid token"}

    try:
        update_data = await request.json()
        current_time = time.time()

        # Clean up old entries (implement expiry)
        expired_keys = []
        for key, value in list(processed_updates.items()):
            # Check if the value is a dict with timestamp or just a boolean
            if isinstance(value, dict) and 'timestamp' in value:
                if current_time - value['timestamp'] > PROCESSED_UPDATES_EXPIRY:
                    expired_keys.append(key)
            # For backward compatibility with existing boolean entries
            elif isinstance(value, bool) and value is True:
                # Convert old boolean entries to timestamped entries
                processed_updates[key] = {'timestamp': current_time}

        # Remove expired entries
        for key in expired_keys:
            logger.info(f"Removing expired update record: {key}")
            del processed_updates[key]

        # Check for duplicate updates
        update_id = str(update_data.get('update_id'))
        if update_id in processed_updates:
            logger.info(f"Skipping duplicate update {update_id}")
            return {"ok": True, "info": "Update already processed"}

        # Process the update
        update = Update.de_json(update_data, application.bot)
        await application.process_update(update)

        # Mark as processed with timestamp
        processed_updates[update_id] = {'timestamp': current_time}
        logger.info(f"Successfully processed update {update_id}")

        return {"ok": True}
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return {"ok": False, "error": str(e)}

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /clear command."""
    user_id = str(update.effective_user.id)
    conversations = context.bot_data["conversations"]

    # Reset the conversation to just the system prompt
    conversations[user_id] = [{"role": "system", "content": context.bot_data["system_prompt"]}]

    logger.info(f"Cleared conversation history for user {user_id}")
    await update.message.reply_text("Conversation history has been cleared!")

# In the initialize_bot function, add the new handler:
async def initialize_bot(token: str, model_client, system_prompt: str, conversations):
    application = Application.builder().token(token).build()
    application.bot_data["model_client"] = model_client
    application.bot_data["system_prompt"] = system_prompt
    application.bot_data["conversations"] = conversations

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear", clear))  # Add this line
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    await application.initialize()
    return application
