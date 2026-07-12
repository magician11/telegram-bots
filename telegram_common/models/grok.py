import logging
import os
from typing import BinaryIO, Dict, List

import requests
from openai import OpenAI

from .base import ModelClient

logger = logging.getLogger(__name__)

GROK_STT_URL = "https://api.x.ai/v1/stt"
GROK_TTS_URL = "https://api.x.ai/v1/tts"

SPEECH_TAG_SYSTEM_PROMPT = """\
You prepare text for a text-to-speech engine. Clean up anything that would
sound awkward when read aloud, then annotate with speech tags for natural,
expressive delivery. Use your judgement — insert tags where they make the
speech sound more human.

Cleanup:
- Remove bare URLs and citation markers like [[1]](https://...). If a
  citation adds meaningful context, rephrase it naturally (e.g. "as one
  study found"). Never read citation numbers or URLs aloud.
- Remove raw markdown, reference markers, and formatting artifacts.
- Do not alter the core meaning, facts, or tone.

Available inline tags:
[pause], [long-pause], [hum-tune], [laugh], [chuckle], [giggle], [cry],
[tsk], [tongue-click], [lip-smack], [breath], [inhale], [exhale], [sigh]

Available wrapping tags:
<soft>, <whisper>, <loud>, <build-intensity>, <decrease-intensity>,
<higher-pitch>, <lower-pitch>, <slow>, <fast>, <sing-song>, <singing>,
<laugh-speak>, <emphasis>

Important:
- Replace written emotional expressions with tags (e.g. "haha" -> [laugh],
  "*sigh*" -> [sigh]) rather than keeping both.
- Combine wrapping tags for layered delivery:
  <slow><soft>goodnight</soft></slow>
- Return ONLY the cleaned, tagged text — no preamble, no explanation."""

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
        model_name: str = "grok-4.5",
        reasoning_effort: str = "medium",
        enable_speech: bool = False,
    ):
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort  # "none", "low", "medium", "high"
        self.enable_speech = enable_speech
        self.speech_format = "mp3"  # xAI TTS returns MP3

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

    async def generate_speech(
        self, text: str, voice: str = "ara", language: str = "en"
    ) -> bytes:
        """Generate speech from text using Grok's Text-to-Speech API.

        Uses the xAI TTS endpoint: POST https://api.x.ai/v1/tts.
        Automatically annotates text with expressive speech tags before synthesis.
        Returns raw audio bytes (MP3 at 24 kHz / 128 kbps by default).
        """
        if not self.enable_speech:
            raise ValueError("Speech functionality not enabled for this client")

        try:
            # Annotate plain text with speech tags for expressive delivery
            tagged_text = await self._tag_for_speech(text)

            logger.info(
                f"Grok TTS: {len(tagged_text)} chars, voice={voice}, language={language}"
            )

            response = requests.post(
                GROK_TTS_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": tagged_text,
                    "voice_id": voice,
                    "language": language,
                },
            )
            response.raise_for_status()

            audio_bytes = response.content
            logger.info(f"Grok TTS done: {len(audio_bytes)} bytes")
            return audio_bytes

        except requests.HTTPError as e:
            logger.error(
                f"Grok TTS HTTP error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Grok TTS error: {type(e).__name__}: {str(e)}")
            raise

    async def _tag_for_speech(self, text: str) -> str:
        """Annotate plain text with expressive speech tags using the LLM.

        Uses the Responses API (same as generate_response) to annotate text
        with speech tags. Falls back to plain text if the tagging call fails.
        """
        try:
            logger.info(f"Speech tagging: annotating {len(text)} chars")

            response = self.client.responses.create(
                model=self.model_name,
                input=[
                    {"role": "system", "content": SPEECH_TAG_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
            )

            tagged = ""
            for item in response.output:
                if getattr(item, "type", None) == "message":
                    for block in getattr(item, "content", []):
                        if getattr(block, "type", None) == "output_text":
                            tagged = getattr(block, "text", "")
                            break
                    if tagged:
                        break

            if not tagged:
                logger.warning("Speech tagging returned empty content, using plain text")
                return text

            tagged = tagged.strip()
            logger.info(f"Speech tagging done: {len(text)} -> {len(tagged)} chars")
            logger.info(f"Original text: {text}")
            logger.info(f"Tagged text:  {tagged}")
            return tagged

        except Exception as e:
            logger.warning(
                f"Speech tagging failed, falling back to plain text: "
                f"{type(e).__name__}: {str(e)}"
            )
            return text

    def _convert_to_responses_format(self, history: List[Dict]) -> List[Dict]:
        """Convert Chat Completions content format to Responses API format.

        Chat Completions uses "text" and "image_url" types, while the
        Responses API uses "input_text" and "input_image" types.
        The image_url value is also unwrapped from {"url": "..."} to a plain string.
        """
        converted = []
        for msg in history:
            msg = dict(msg)
            content = msg.get("content")
            if isinstance(content, list):
                new_content = []
                for part in content:
                    part = dict(part)
                    part_type = part.get("type")
                    if part_type == "text":
                        part["type"] = "input_text"
                    elif part_type == "image_url":
                        part["type"] = "input_image"
                        # Unwrap image_url from {"url": "..."} to plain string
                        image_url = part.get("image_url")
                        if isinstance(image_url, dict):
                            part["image_url"] = image_url.get("url", "")
                    new_content.append(part)
                msg["content"] = new_content
            converted.append(msg)
        return converted

    async def generate_response(self, history: List[Dict]) -> str:
        try:
            logger.info(
                f"Grok API call: model={self.model_name}, messages={len(history)}, "
                f"reasoning={self.reasoning_effort}"
            )

            # Convert Chat Completions format to Responses API format for multimodal content
            history = self._convert_to_responses_format(history)

            kwargs: dict = {
                "model": self.model_name,
                "input": history,
                "tools": [{"type": "web_search"}],
                "tool_choice": "auto",
            }

            if self.reasoning_effort != "none":
                kwargs["reasoning"] = {"effort": self.reasoning_effort}

            response = self.client.responses.create(**kwargs)

            # Extract text from Responses API output format
            text = ""
            for item in response.output:
                if getattr(item, "type", None) == "message":
                    for block in getattr(item, "content", []):
                        if getattr(block, "type", None) == "output_text":
                            text = getattr(block, "text", "")
                            break
                    if text:
                        break

            # Extract usage metrics from raw dict (SDK doesn't map xAI extras)
            raw = response.model_dump()
            usage = raw.get("usage", {})
            num_sources = usage.get("num_sources_used", 0)
            reasoning_tokens = usage.get("output_tokens_details", {}).get(
                "reasoning_tokens", 0
            )
            web_search_calls = usage.get("server_side_tool_usage_details", {}).get(
                "web_search_calls", 0
            )

            logger.info(
                f"Grok response: content_length={len(text)} chars, "
                f"sources_used={num_sources}, web_search_calls={web_search_calls}, "
                f"reasoning_tokens={reasoning_tokens}"
            )

            if not text:
                logger.error(f"Grok returned empty text. status={response.status}")
                return ""

            return text.strip()

        except Exception as e:
            logger.error(
                f"Error generating Grok response: {type(e).__name__}: {str(e)}"
            )
            return "Oops, my circuits are a bit scrambled right now! \U0001f916 Try again in a minute or two."
