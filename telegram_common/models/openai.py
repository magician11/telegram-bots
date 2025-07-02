from openai import OpenAI
from typing import List, Dict
import logging
from .base import ModelClient

logger = logging.getLogger(__name__)

class OpenAIClient(ModelClient):
    def __init__(self, api_key: str, model_name: str = "gpt-4", max_tokens: int = 555):
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name
        self.max_tokens = max_tokens

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        try:
            logger.info(f"OpenAI API call with max_tokens: {self.max_tokens}, model: {self.model_name}")

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=history,
                max_tokens=self.max_tokens
            )

            content = response.choices[0].message.content.strip()
            logger.info(f"OpenAI response length: {len(content)} characters")

            return content
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
