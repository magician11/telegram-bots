from openai import OpenAI
import logging
from typing import List, Dict
from .base import ModelClient

logger = logging.getLogger(__name__)

class GrokClient(ModelClient):
    def __init__(self, api_key: str, model_name: str = "grok-3-mini"):

        logger.info(f"GrokClient: Initializing with model {model_name}")
        logger.info(f"GrokClient: API key present: {bool(api_key and len(api_key) > 10)}")

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )
        self.model_name = model_name

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=history
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"GrokClient API Error: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
