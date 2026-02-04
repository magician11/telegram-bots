import logging
import re
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

            if response.status_code != 200:
                logger.error(f"Error response body: {response.text}")

            response.raise_for_status()
            response_data = response.json()

            output = response_data.get("output", [])

            # Collect all text from all output items
            all_text = []
            for item in output:
                if item.get("type") == "message":
                    content_blocks = item.get("content", [])
                    for block in content_blocks:
                        if block.get("type") == "output_text":
                            all_text.append(block.get("text", ""))

            content = "".join(all_text).strip()

            # Remove citation markers like [[1]](url)
            content = re.sub(r"\[\[\d+\]\]\([^)]+\)", "", content)

            logger.info(f"Response length: {len(content)} characters")

            return content if content else "I couldn't generate a response."

        except Exception as e:
            logger.error(f"Error generating Grok response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
