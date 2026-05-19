import logging
from typing import Dict, List

from openai import OpenAI

from .base import ModelClient

logger = logging.getLogger(__name__)


class GrokClient(ModelClient):
    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
        self.model_name = "grok-latest"

    def supports_vision(self) -> bool:
        return True

    async def generate_response(self, history: List[Dict]) -> str:
        try:
            logger.info(
                f"Grok API call: model={self.model_name}, messages={len(history)}"
            )

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=history,
            )

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            content = choice.message.content

            logger.info(
                f"Grok response: finish_reason={finish_reason}, "
                f"content_length={len(content) if content else 0} chars"
            )

            if content is None:
                logger.error(
                    f"Grok returned None content. finish_reason={finish_reason}."
                )
                return ""

            return content.strip()

        except Exception as e:
            logger.error(
                f"Error generating Grok response: {type(e).__name__}: {str(e)}"
            )
            return "Sorry, I'm having trouble generating a response right now."
