from openai import OpenAI
from typing import List, Dict
import logging
from .base import ModelClient

logger = logging.getLogger(__name__)

class DeepSeekClient(ModelClient):
    def __init__(self, api_key: str, max_tokens: int = 555):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.max_tokens = max_tokens

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        try:
            logger.info(f"DeepSeek API call with max_tokens: {self.max_tokens}")

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=history,
                max_tokens=self.max_tokens
            )

            content = response.choices[0].message.content.strip()
            logger.info(f"DeepSeek response length: {len(content)} characters")

            return content
        except Exception as e:
            logger.error(f"Error generating DeepSeek response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
