import requests
from typing import List, Dict
import logging
from .base import ModelClient

logger = logging.getLogger(__name__)

class GrokClient(ModelClient):
    def __init__(self, api_key: str, search_mode: str = "auto"):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"
        self.model_name = "grok-4-latest"

        # Validate search_mode parameter
        valid_options = ["auto", "on", "off"]
        if search_mode not in valid_options:
            raise ValueError(f"search_mode must be one of {valid_options}, got: {search_mode}")
        self.search_mode = search_mode

    def supports_vision(self) -> bool:
        """Grok 4 models support vision."""
        return True  # Grok 4 always supports vision

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        try:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            # Use the new max_completion_tokens parameter
            api_params = {
                "model": self.model_name,
                "messages": history,
                "search_parameters": {
                    "mode": self.search_mode
                }
            }

            response = requests.post(url, headers=headers, json=api_params)

            logger.info(f"Response status: {response.status_code}")
            response.raise_for_status()

            logger.info(f"Full API response: {response.text}")
            response_data = response.json()
            content = response_data["choices"][0]["message"]["content"].strip()

            logger.info(f"Response length: {len(content)} characters")
            return content

        except Exception as e:
            logger.error(f"Error generating Grok response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
