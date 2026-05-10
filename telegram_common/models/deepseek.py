import logging
from typing import Dict, List

from openai import OpenAI

from .base import ModelClient

logger = logging.getLogger(__name__)


class DeepSeekClient(ModelClient):
    def __init__(self, api_key: str, max_tokens: int = 2048):
        self.client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        self.max_tokens = max_tokens

    async def generate_response(self, history: List[Dict]) -> str:
        try:
            # Rough token estimate for diagnostic logging only
            total_chars = sum(len(msg.get("content", "") or "") for msg in history)
            logger.info(
                f"DeepSeek API call: messages={len(history)}, "
                f"estimated_input_chars={total_chars}, max_tokens={self.max_tokens}"
            )

            response = self.client.chat.completions.create(
                model="deepseek-v4-pro", messages=history, max_tokens=self.max_tokens
            )

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            content = choice.message.content

            logger.info(
                f"DeepSeek response: finish_reason={finish_reason}, "
                f"content_length={len(content) if content else 0} chars"
            )

            if content is None:
                logger.error(
                    f"DeepSeek returned None content. finish_reason={finish_reason}. "
                    f"This may indicate content filtering or model refusal."
                )
                return ""

            content = content.strip()

            if not content:
                logger.error(
                    f"DeepSeek returned empty content. finish_reason={finish_reason}. "
                    f"Full choice: {choice}"
                )

            return content
        except Exception as e:
            logger.error(
                f"Error generating DeepSeek response: {type(e).__name__}: {str(e)}"
            )
            return "Sorry, I'm having trouble generating a response right now."
