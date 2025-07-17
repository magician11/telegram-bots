import os
import logging
from fastapi import FastAPI, Request
from .bot import initialize_bot, webhook_handler
from .models import ModelClient, OllamaClient, DeepSeekClient, OpenAIClient, GrokClient
from .audio_utils import AudioFileManager, validate_audio_size, format_file_size
import time

logger = logging.getLogger(__name__)

__all__ = [
    'initialize_bot',
    'webhook_handler',
    'ModelClient',
    'OllamaClient',
    'DeepSeekClient',
    'OpenAIClient',
    'GrokClient',
    'create_bot_app',
    'AudioFileManager',
    'validate_audio_size',
    'format_file_size'
]

def create_bot_app(
    model_class,
    model_kwargs: dict,
    conversations,
    processed_updates,
    system_prompt: str = "",  # Optional with default empty string
    bot_config: dict = None,
    startup_checks: bool = False,
    speech_only: bool = False,
    bot_name: str = "Assistant"
) -> FastAPI:
    """Create and configure a FastAPI app with bot functionality."""
    web_app = FastAPI()

    @web_app.on_event("startup")
    async def startup_event():
        logger.info("=== STARTUP: Beginning bot initialization ===")

        model_client = model_class(**model_kwargs)
        logger.info(f"STARTUP: Model client created: {type(model_client).__name__}")

        # Handle Ollama-specific startup if needed
        if startup_checks and isinstance(model_client, OllamaClient):
            logger.info("STARTUP: Starting Ollama service...")
            if not model_client.start_ollama_service():
                raise RuntimeError("Failed to start Ollama service")
            if not model_client.ensure_model_available():
                raise RuntimeError("Failed to ensure model availability")

        # For speech-only bots, validate that speech is enabled
        if speech_only:
            if not hasattr(model_client, 'enable_speech') or not model_client.enable_speech:
                raise RuntimeError("Speech-only bot requires a model client with enable_speech=True")
            logger.info("STARTUP: Speech-only bot mode enabled")

        telegram_token = os.environ.get("TELEGRAM_TOKEN")
        if not telegram_token:
            raise RuntimeError("TELEGRAM_TOKEN environment variable not set")

        logger.info("STARTUP: About to initialize bot...")
        logger.info(f"STARTUP: bot_config = {bot_config}")
        logger.info(f"STARTUP: speech_only = {speech_only}")
        logger.info(f"STARTUP: bot_name = {bot_name}")

        web_app.state.application = await initialize_bot(
            telegram_token,
            model_client,
            system_prompt,
            conversations,
            bot_config,
            speech_only,
            bot_name
        )

        logger.info("=== STARTUP: Bot initialization complete ===")

    @web_app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": time.time()
        }

    @web_app.post("/webhook/{token}")
    async def webhook_endpoint(token: str, request: Request):
        return await webhook_handler(
            request,
            token,
            web_app.state.application,
            processed_updates
        )

    return web_app
