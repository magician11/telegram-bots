# telegram-common

A shared Python package for reusable Telegram bot functionality. This package provides common utilities, handlers, and setup code for building and managing Telegram bots, making it easier to develop and maintain multiple bots with shared logic.

## Features

- 🤖 **Multiple AI Model Support**: OpenAI GPT, DeepSeek, and Ollama
- 🔄 **Webhook Management**: Built-in webhook setup and handling
- 💬 **Conversation Memory**: Persistent conversation history management
- 🎨 **Markdown Support**: Automatic Markdown to HTML conversion for Telegram
- 🔒 **Duplicate Protection**: Smart duplicate update handling
- ⚡ **FastAPI Integration**: Ready-to-deploy FastAPI applications
- 🛠️ **CLI Tools**: Command-line utilities for bot management

## Installation

```bash
pip install telegram-common
```

## Quick Start

### Basic Bot Setup

```python
from telegram_common import create_bot_app, OpenAIClient
import uvicorn

# Configure your bot
app = create_bot_app(
    model_class=OpenAIClient,
    model_kwargs={
        "api_key": "your-openai-api-key",
        "model_name": "gpt-4",
        "system_prompt": "You are a helpful assistant."
    },
    telegram_token="your-telegram-bot-token",
    conversations={},  # Will store conversation history
    processed_updates={}  # Prevents duplicate processing
)

# Run the server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Setting Up Webhook

Use the built-in CLI tool to set your webhook:

```bash
telegram-set-webhook --token YOUR_BOT_TOKEN --url https://yourdomain.com
```

Or programmatically:

```python
from telegram_common.admin.set_webhook import set_webhook
import asyncio

asyncio.run(set_webhook("YOUR_BOT_TOKEN", "https://yourdomain.com"))
```

## Supported AI Models

### OpenAI

```python
from telegram_common import OpenAIClient

client = OpenAIClient(
    api_key="your-openai-api-key",
    model_name="gpt-4",  # or "gpt-3.5-turbo"
    system_prompt="You are a helpful assistant."
)
```

### DeepSeek

```python
from telegram_common import DeepSeekClient

client = DeepSeekClient(
    api_key="your-deepseek-api-key",
    base_url="https://api.deepseek.com",
    system_prompt="You are a helpful assistant."
)
```

### Ollama (Local Models)

```python
from telegram_common import OllamaClient

client = OllamaClient(
    model_name="llama2",  # or any Ollama model
    system_prompt="You are a helpful assistant."
)

# For Ollama, you may need to start the service and ensure model availability
app = create_bot_app(
    model_class=OllamaClient,
    model_kwargs={
        "model_name": "llama2",
        "system_prompt": "You are a helpful assistant."
    },
    telegram_token="your-telegram-bot-token",
    conversations={},
    processed_updates={},
    startup_checks=True  # This will start Ollama service and pull model if needed
)
```

## Environment Variables

The following environment variables are commonly used:

- `TELEGRAM_TOKEN`: Your Telegram bot token (required)
- `OPENAI_API_KEY`: Your OpenAI API key (if using OpenAI)
- `DEEPSEEK_API_KEY`: Your DeepSeek API key (if using DeepSeek)

## Advanced Usage

### Custom Model Implementation

You can create your own model client by inheriting from `ModelClient`:

```python
from telegram_common.models import ModelClient
from typing import List, Dict

class CustomModelClient(ModelClient):
    def __init__(self, api_key: str, system_prompt: str):
        self.api_key = api_key
        self.system_prompt = system_prompt
    
    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        # Implement your custom logic here
        return "Your custom response"
```

### Manual Bot Initialization

For more control over the bot setup:

```python
from telegram_common import initialize_bot, webhook_handler
from fastapi import FastAPI, Request

app = FastAPI()
conversations = {}
processed_updates = {}

@app.on_event("startup")
async def startup_event():
    model_client = OpenAIClient(
        api_key="your-api-key",
        system_prompt="You are a helpful assistant."
    )
    
    app.state.application = await initialize_bot(
        "your-telegram-token",
        model_client,
        "You are a helpful assistant.",
        conversations
    )

@app.post("/webhook/{token}")
async def webhook_endpoint(token: str, request: Request):
    return await webhook_handler(
        request,
        token,
        app.state.application,
        processed_updates
    )
```

## Bot Commands

The bot includes these built-in commands:

- `/start` - Initialize or restart the conversation
- `/clear` - Clear conversation history

## Deployment

### Docker Example

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Modal.com Example

```python
import modal

app = modal.App("telegram-bot")

@app.function(
    image=modal.Image.debian_slim().pip_install(
        "telegram-common",
        "uvicorn"
    ),
    secrets=[
        modal.Secret.from_name("telegram-secrets")
    ]
)
@modal.asgi_app()
def fastapi_app():
    from telegram_common import create_bot_app, OpenAIClient
    import os
    
    return create_bot_app(
        model_class=OpenAIClient,
        model_kwargs={
            "api_key": os.environ["OPENAI_API_KEY"],
            "system_prompt": os.environ["SYSTEM_PROMPT"]
        },
        telegram_token=os.environ["TELEGRAM_TOKEN"],
        conversations={},
        processed_updates={}
    )
```

## Configuration

### Conversation Settings

- **MAX_CONVERSATION_HISTORY**: Maximum number of messages to keep in conversation history (default: 22)
- **PROCESSED_UPDATES_EXPIRY**: How long to remember processed updates in seconds (default: 3600)

## Error Handling

The package includes comprehensive error handling:

- **Network Issues**: Automatic retry logic for temporary failures
- **API Errors**: Graceful degradation with user-friendly error messages
- **Duplicate Updates**: Prevention of processing the same update multiple times
- **Invalid Requests**: Proper validation and error responses

## Logging

The package uses Python's standard logging module. Configure logging in your application:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions:
- Create an issue on GitHub
- Email: support@golightlyplus.com

## Changelog

### v1.0.0
- Initial stable release
- Support for OpenAI, DeepSeek, and Ollama models
- FastAPI integration
- Webhook management
- CLI tools
- Comprehensive error handling