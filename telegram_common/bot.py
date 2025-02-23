from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import ContextTypes
from fastapi import Request
import logging
import os
from .utils import markdown_to_html

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command."""
    user_id = str(update.effective_user.id)
    logger.info(f"User {user_id} started the bot")
    conversations = context.bot_data["conversations"]
    conversations[user_id] = [{"role": "system", "content": context.bot_data["system_prompt"]}]
    await update.message.reply_text("Hi! How can I help you today?")

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

        # Generate a response using the model client
        model_client = context.bot_data["model_client"]
        response_text = await model_client.generate_response(user_message, history)
        logger.info(f"Response text: {response_text}")

        # Convert Markdown to HTML
        html_response = markdown_to_html(response_text)
        logger.info(f"Converted response: {html_response}")

        # Append the assistant's response (store the original markdown version)
        history.append({"role": "assistant", "content": response_text})

        # Trim the conversation history if it gets too long
        if len(history) > 10:
            history = [history[0]] + history[-9:]  # Keep the system prompt and the last 9 messages

        # Save the updated conversation history
        conversations[user_id] = history

        await update.message.reply_text(html_response, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        await update.message.reply_text("Sorry, I'm having trouble right now. Could you try again in a moment?")

async def webhook_handler(request: Request, token: str, application, processed_updates):
    """Handle incoming webhook updates."""
    if token != os.environ.get("TELEGRAM_TOKEN"):
        return {"error": "Invalid token"}

    try:
        update_data = await request.json()

        # Check for duplicate updates
        update_id = str(update_data.get('update_id'))
        if update_id in processed_updates:
            logger.info(f"Skipping duplicate update {update_id}")
            return {"ok": True, "info": "Update already processed"}

        # Mark as processed
        processed_updates[update_id] = True

        update = Update.de_json(update_data, application.bot)
        await application.process_update(update)
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
