from openai import OpenAI
from typing import List, Dict
from .base import ModelClient

class OpenAIClient(ModelClient):
    def __init__(self, api_key: str, model_name: str = "gpt-4"):
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=history
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            return "Sorry, I'm having trouble generating a response right now."
