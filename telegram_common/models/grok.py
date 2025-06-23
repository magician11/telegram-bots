import requests
from typing import List, Dict
import logging
from .base import ModelClient

logger = logging.getLogger(__name__)

class GrokClient(ModelClient):
    def __init__(self, api_key: str, model_name: str = "grok-3-latest", search_mode: str = "auto"):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"
        self.model_name = model_name

        # Validate search_mode parameter
        valid_options = ["auto", "on", "off"]
        if search_mode not in valid_options:
            raise ValueError(f"search_mode must be one of {valid_options}, got: {search_mode}")

        self.search_mode = search_mode

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        try:
            url = f"{self.base_url}/chat/completions"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            # Prepare the API call parameters
            api_params = {
                "model": self.model_name,
                "messages": history,
                "search_parameters": {
                    "mode": self.search_mode
                }
            }

            logger.info(f"Full API params: {api_params}")

            response = requests.post(url, headers=headers, json=api_params)
            response.raise_for_status()
            response_data = response.json()

            return response_data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Error generating Grok response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
