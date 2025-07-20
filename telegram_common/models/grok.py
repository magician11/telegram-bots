import requests
from typing import List, Dict
import logging
from .base import ModelClient

logger = logging.getLogger(__name__)

class GrokClient(ModelClient):
    def __init__(self, api_key: str, model_name: str = "grok-4-latest", search_mode: str = "auto", max_tokens: int = 555):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"
        self.model_name = model_name
        self.max_tokens = max_tokens

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
                "max_tokens": self.max_tokens,
                "search_parameters": {
                    "mode": self.search_mode
                }
            }

            logger.info(f"API call with max_tokens: {self.max_tokens}")
            response = requests.post(url, headers=headers, json=api_params)

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response body: {response.text}")

            response.raise_for_status()

            response_data = response.json()
            content = response_data["choices"][0]["message"]["content"].strip()

            logger.info(f"Response length: {len(content)} characters")
            return content

        except Exception as e:
            logger.error(f"Error generating Grok response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
