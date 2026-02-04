import logging
from typing import Dict, List

import requests

from .base import ModelClient

logger = logging.getLogger(__name__)


class GrokClient(ModelClient):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"
        self.model_name = "grok-4-1-fast"

    def supports_vision(self) -> bool:
        return True

    async def generate_response(self, history: List[Dict]) -> str:
        try:
            url = f"{self.base_url}/responses"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            api_params = {
                "input": history,
                "model": self.model_name,
                "tools": [{"type": "web_search"}],
                "tool_choice": "auto",
                "store": False,
            }

            response = requests.post(url, headers=headers, json=api_params)
            logger.info(f"Response status: {response.status_code}")
            response.raise_for_status()

            response_data = response.json()

            # Parse the response
            content_blocks = response_data.get("output", [{}])[0].get("content", [])
            content = "".join(
                block.get("text", "")
                for block in content_blocks
                if block.get("type") == "output_text"
            ).strip()

            logger.info(f"Response length: {len(content)} characters")
            return content

        except Exception as e:
            logger.error(f"Error generating Grok response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
