from openai import OpenAI
from typing import List, Dict
from .base import ModelClient

class DeepSeekClient(ModelClient):
    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=history,
                max_tokens=1111
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            return "Sorry, I'm having trouble generating a response right now."
