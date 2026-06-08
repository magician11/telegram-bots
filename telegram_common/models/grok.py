import logging
import os
from typing import BinaryIO, Dict, List

import requests
from openai import OpenAI

from .base import ModelClient

logger = logging.getLogger(__name__)

GROK_STT_URL = "https://api.x.ai/v1/stt"

MIME_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".mp4": "audio/mp4",
    ".m4a": "audio/mp4",
    ".mkv": "video/x-matroska",
}


class GrokClient(ModelClient):
    def __init__(
        self,
        api_key: str,
        model_name: str = "grok-4.3",
        search_mode: str = "auto",
        reasoning_effort: str = "medium",
    ):
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
        self.model_name = model_name
        self.search_mode = search_mode  # "off", "on", or "auto"
        self.reasoning_effort = reasoning_effort  # "none", "low", "medium", "high"

    def supports_vision(self) -> bool:
        return True

    async def transcribe_audio(
        self, audio_file: BinaryIO, filename: str = "audio.ogg"
    ) -> str:
        """Transcribe audio using Grok's Speech-to-Text API.

        Uses the xAI STT endpoint: POST https://api.x.ai/v1/stt.
        Supports WAV, MP3, OGG, Opus, FLAC, AAC, MP4, M4A, MKV.
        """
        try:
            logger.info(f"Grok STT: transcribing {filename}")
            audio_file.seek(0)

            ext = os.path.splitext(filename)[1].lower()
            mime_type = MIME_TYPES.get(ext, "audio/ogg")

            response = requests.post(
                GROK_STT_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (filename, audio_file, mime_type)},
                data={"language": "en"},
            )
            response.raise_for_status()

            result = response.json()
            text = result["text"].strip()
            duration = result.get("duration", 0)
            logger.info(f"Grok STT done: {len(text)} chars, {duration:.1f}s audio")
            return text

        except requests.HTTPError as e:
            logger.error(
                f"Grok STT HTTP error: {e.response.status_code} - {e.response.text}"
            )
            return "Sorry, I couldn't transcribe that audio. The speech service returned an error."
        except Exception as e:
            logger.error(f"Grok STT error: {type(e).__name__}: {str(e)}")
            return "Sorry, I couldn't transcribe that audio. Please try again."

    async def generate_response(self, history: List[Dict]) -> str:
        try:
            logger.info(
                f"Grok API call: model={self.model_name}, messages={len(history)}, "
                f"search={self.search_mode}, reasoning={self.reasoning_effort}"
            )

            kwargs: dict = {
                "model": self.model_name,
                "messages": history,
            }

            # xAI-specific params must go via extra_body (OpenAI SDK rejects unknown kwargs)
            extra_body: dict = {}
            if self.search_mode != "off":
                extra_body["search_parameters"] = {
                    "mode": self.search_mode,
                    "return_citations": True,
                }
            if self.reasoning_effort != "none":
                extra_body["reasoning_effort"] = self.reasoning_effort
            if extra_body:
                kwargs["extra_body"] = extra_body

            response = self.client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            finish_reason = choice.finish_reason
            content = choice.message.content

            # Extract search and reasoning usage from response
            usage = getattr(response, "usage", None)
            num_sources = usage.num_sources_used if usage else 0
            reasoning_tokens = 0
            if usage and hasattr(usage, "completion_tokens_details"):
                reasoning_tokens = getattr(
                    usage.completion_tokens_details, "reasoning_tokens", 0
                )

            # Log citations if the model searched the web
            citations = getattr(response, "citations", None)
            if citations:
                urls = [c.url if hasattr(c, "url") else str(c) for c in citations]
                logger.info(f"Grok citations ({len(citations)} sources): {urls}")

            logger.info(
                f"Grok response: finish_reason={finish_reason}, "
                f"content_length={len(content) if content else 0} chars, "
                f"sources_used={num_sources}, reasoning_tokens={reasoning_tokens}"
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
