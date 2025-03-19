from openai import OpenAI
import logging
from typing import List, Dict
from .base import ModelClient

logger = logging.getLogger(__name__)

class DeepSeekClient(ModelClient):
    def __init__(self, api_key: str, base_url: str, system_prompt: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.system_prompt = system_prompt

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        try:
            # The history already includes the system prompt, so we don't need to add it again
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=history,  # Use the existing history (includes system prompt)
                stream=False,
                max_tokens=555
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
