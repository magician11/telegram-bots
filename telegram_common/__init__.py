from fastapi import FastAPI, Request
from .bot import initialize_bot, webhook_handler
from .models import ModelClient, OllamaClient, DeepSeekClient, OpenAIClient

__all__ = [
    'initialize_bot',
    'webhook_handler',
    'ModelClient',
    'OllamaClient',
    'DeepSeekClient',
    'OpenAIClient',
    'create_bot_app'
]

def create_bot_app(
    model_class,
    model_kwargs: dict,
    telegram_token: str,
    conversations,
    processed_updates,
    startup_checks: bool = False
) -> FastAPI:
    """Create and configure a FastAPI app with bot functionality."""
    web_app = FastAPI()

    @web_app.on_event("startup")
    async def startup_event():
        model_client = model_class(**model_kwargs)

        # Handle Ollama-specific startup if needed
        if startup_checks and isinstance(model_client, OllamaClient):
            if not model_client.start_ollama_service():
                raise RuntimeError("Failed to start Ollama service")
            if not model_client.ensure_model_available():
                raise RuntimeError("Failed to ensure model availability")

        web_app.state.application = await initialize_bot(
            telegram_token,
            model_client,
            model_kwargs["system_prompt"],
            conversations
        )

    @web_app.post("/webhook/{token}")
    async def webhook_endpoint(token: str, request: Request):
        return await webhook_handler(
            request,
            token,
            web_app.state.application,
            processed_updates
        )

    return web_app
