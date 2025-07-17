from openai import OpenAI
from typing import List, Dict, BinaryIO
import logging
from .base import ModelClient

logger = logging.getLogger(__name__)

class OpenAIClient(ModelClient):
    def __init__(self, api_key: str, model_name: str = "gpt-4", max_tokens: int = 555, enable_speech: bool = False):
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.enable_speech = enable_speech

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        try:
            logger.info(f"OpenAI API call with max_tokens: {self.max_tokens}, model: {self.model_name}")

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=history,
                max_tokens=self.max_tokens
            )

            content = response.choices[0].message.content.strip()
            logger.info(f"OpenAI response length: {len(content)} characters")

            return content
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."

    async def transcribe_audio(self, audio_file: BinaryIO, filename: str = "audio.ogg") -> str:
        """Transcribe audio using OpenAI Whisper."""
        if not self.enable_speech:
            raise ValueError("Speech functionality not enabled for this client")

        try:
            logger.info(f"Transcribing audio file: {filename}")

            # Ensure file pointer is at the beginning
            audio_file.seek(0)

            transcript = self.client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=(filename, audio_file, "audio/ogg"),
                response_format="text"
            )

            logger.info(f"Transcription successful: {len(transcript)} characters")
            return transcript.strip()

        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return "Sorry, I couldn't transcribe that audio. Please try again."

    async def generate_speech(self, text: str, voice: str = "alloy") -> bytes:
        """Generate speech from text using OpenAI TTS."""
        if not self.enable_speech:
            raise ValueError("Speech functionality not enabled for this client")

        try:
            logger.info(f"Generating speech for text length: {len(text)} characters")

            response = self.client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=voice,
                input=text,
                response_format="opus"  # OGG Opus format for Telegram
            )

            audio_content = response.content
            logger.info(f"Speech generation successful: {len(audio_content)} bytes")
            return audio_content

        except Exception as e:
            logger.error(f"Error generating speech: {str(e)}")
            raise
