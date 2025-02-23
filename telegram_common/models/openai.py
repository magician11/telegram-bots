from openai import OpenAI
import logging
from typing import List, Dict
from .base import ModelClient

logger = logging.getLogger(__name__)

class OpenAIClient(ModelClient):
    def __init__(self, api_key: str, model_name: str = "gpt-4", system_prompt: str = None):
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name
        self.system_prompt = system_prompt

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=history,
                stream=False,
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
