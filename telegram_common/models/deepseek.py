import logging
import os
from datetime import datetime, timezone
from typing import BinaryIO, Dict, List

import requests
from openai import OpenAI

from .base import ModelClient
from .speech_tags import (
    GROK_STT_URL,
    GROK_TTS_URL,
    MIME_TYPES,
    SPEECH_TAG_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

SEARCH_RESULT_LIMIT = 5


class DeepSeekClient(ModelClient):
    """LLM via DeepSeek, speech I/O via Grok TTS/STT (no Grok LLM calls)."""

    def __init__(
        self,
        deepseek_api_key: str,
        grok_api_key: str = None,
        model_name: str = "deepseek-v4-pro",
        reasoning_effort: str = "high",
        enable_search: bool = True,
        enable_speech: bool = False,
    ):
        self.deepseek_api_key = deepseek_api_key
        self.grok_api_key = grok_api_key
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort
        self.enable_search = enable_search
        self.enable_speech = enable_speech
        self.speech_format = "mp3"  # Grok TTS returns MP3

        self._deepseek = OpenAI(
            api_key=deepseek_api_key,
            base_url="https://api.deepseek.com",
        )

        if enable_speech and not grok_api_key:
            raise ValueError(
                "enable_speech=True requires grok_api_key for TTS/STT endpoints"
            )

    # ── capabilities ──────────────────────────────────────────────────────

    def supports_vision(self) -> bool:
        return False

    # ── chat / reasoning / search ──────────────────────────────────────────

    def _search_web(self, query: str) -> str:
        """Search the web via DuckDuckGo and return formatted results.

        Returns an empty string if search fails or returns nothing.
        """
        try:
            from ddgs import DDGS  # lazy import

            logger.info(f"DDGS search: query='{query[:100]}'")
            results = list(DDGS().text(query, max_results=SEARCH_RESULT_LIMIT))

            if not results:
                logger.info("DDGS search returned no results")
                return ""

            formatted = []
            for i, r in enumerate(results, 1):
                formatted.append(
                    f"{i}. {r['title']}\n"
                    f"   {r['href']}\n"
                    f"   {r['body']}"
                )

            context = "\n\n".join(formatted)
            logger.info(
                f"DDGS search done: {len(results)} results, "
                f"{len(context)} chars"
            )
            return context

        except Exception as e:
            logger.warning(
                f"DDGS search failed, proceeding without results: "
                f"{type(e).__name__}: {str(e)}"
            )
            return ""

    async def generate_response(self, history: List[Dict]) -> str:
        try:
            total_chars = sum(
                len(msg.get("content", "") or "")
                if isinstance(msg.get("content"), str)
                else 0
                for msg in history
            )

            # Build the messages list, injecting search context if enabled
            messages = list(history)  # shallow copy — don't mutate caller's list

            if self.enable_search:
                # Extract the last user message as a search query
                last_user = None
                for msg in reversed(messages):
                    if msg["role"] == "user" and isinstance(msg["content"], str):
                        last_user = msg["content"]
                        break

                if last_user:
                    search_context = self._search_web(last_user)
                    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                    context_parts = [f"Current time: {now}"]
                    if search_context:
                        context_parts.append(
                            f"Web search results for '{last_user[:200]}':\n\n{search_context}\n\n"
                            f"Use these results to inform your answer. Cite sources where relevant."
                        )
                    messages.insert(
                        len(messages) - 1,
                        {
                            "role": "system",
                            "content": "\n\n".join(context_parts),
                        },
                    )

            total_chars = sum(
                len(msg.get("content", "") or "")
                if isinstance(msg.get("content"), str)
                else 0
                for msg in messages
            )
            logger.info(
                f"DeepSeek API call: model={self.model_name}, messages={len(messages)}, "
                f"estimated_input_chars={total_chars}"
            )

            kwargs: dict = {
                "model": self.model_name,
                "messages": messages,
            }

            response = self._deepseek.chat.completions.create(**kwargs)

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
            return (
                "Oops, my circuits are a bit scrambled right now! \U0001f916 "
                "Try again in a minute or two."
            )

    # ── speech tagging (via DeepSeek LLM, not Grok) ────────────────────────

    async def _tag_for_speech(self, text: str) -> str:
        """Annotate plain text with expressive speech tags using DeepSeek.

        Falls back to plain text if the tagging call fails.
        """
        try:
            logger.info(f"Speech tagging: annotating {len(text)} chars")

            response = self._deepseek.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SPEECH_TAG_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.3,
            )

            tagged = response.choices[0].message.content

            if not tagged:
                logger.warning(
                    "Speech tagging returned empty content, using plain text"
                )
                return text

            tagged = tagged.strip()
            logger.info(
                f"Speech tagging done: {len(text)} -> {len(tagged)} chars"
            )
            logger.info(f"Original text: {text}")
            logger.info(f"Tagged text:  {tagged}")
            return tagged

        except Exception as e:
            logger.warning(
                f"Speech tagging failed, falling back to plain text: "
                f"{type(e).__name__}: {str(e)}"
            )
            return text

    # ── speech I/O (Grok TTS / STT — no LLM calls) ────────────────────────

    async def generate_speech(
        self, text: str, voice: str = "ara", language: str = "en"
    ) -> bytes:
        """Generate speech via Grok TTS, with DeepSeek speech tagging."""
        if not self.enable_speech:
            raise ValueError("Speech functionality not enabled for this client")

        try:
            tagged_text = await self._tag_for_speech(text)

            logger.info(
                f"Grok TTS: {len(tagged_text)} chars, "
                f"voice={voice}, language={language}"
            )

            response = requests.post(
                GROK_TTS_URL,
                headers={
                    "Authorization": f"Bearer {self.grok_api_key}",
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

    async def transcribe_audio(
        self, audio_file: BinaryIO, filename: str = "audio.ogg"
    ) -> str:
        """Transcribe audio using Grok's Speech-to-Text API."""
        try:
            logger.info(f"Grok STT: transcribing {filename}")
            audio_file.seek(0)

            ext = os.path.splitext(filename)[1].lower()
            mime_type = MIME_TYPES.get(ext, "audio/ogg")

            response = requests.post(
                GROK_STT_URL,
                headers={"Authorization": f"Bearer {self.grok_api_key}"},
                files={"file": (filename, audio_file, mime_type)},
                data={"language": "en"},
            )
            response.raise_for_status()

            result = response.json()
            text = result["text"].strip()
            duration = result.get("duration", 0)
            logger.info(
                f"Grok STT done: {len(text)} chars, {duration:.1f}s audio"
            )
            return text

        except requests.HTTPError as e:
            logger.error(
                f"Grok STT HTTP error: {e.response.status_code} - {e.response.text}"
            )
            return (
                "Sorry, I couldn't transcribe that audio. "
                "The speech service returned an error."
            )
        except Exception as e:
            logger.error(f"Grok STT error: {type(e).__name__}: {str(e)}")
            return "Sorry, I couldn't transcribe that audio. Please try again."
