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
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
        self.model_name = "grok-latest"

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
