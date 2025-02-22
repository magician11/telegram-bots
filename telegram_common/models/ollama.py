import requests
import logging
import subprocess
import time
from typing import List, Dict
from .base import ModelClient
from ..utils import escape_markdown

logger = logging.getLogger(__name__)

class OllamaClient(ModelClient):
    def __init__(self, model_name: str, system_prompt: str):
        self.model_name = model_name
        self.system_prompt = system_prompt

    def start_ollama_service(self):
        """Start the Ollama service and wait for it to be ready."""
        subprocess.Popen(["ollama", "serve"])
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    logger.info("Ollama service is running")
                    return True
            except:
                logger.info(f"Waiting for Ollama service... ({i+1}/{max_retries})")
                time.sleep(2)
        logger.error("Ollama service failed to start")
        return False

    def ensure_model_available(self):
        """Ensure the model is available, pulling it if necessary."""
        try:
            # First try to list models
            response = requests.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                logger.info(f"Available models: {models}")  # Add this for debugging

                # Check if model exists
                model_exists = any(model["name"] == self.model_name for model in models)

                if not model_exists:
                    logger.info(f"Model '{self.model_name}' not found, pulling...")
                    result = subprocess.run(
                        ["ollama", "pull", self.model_name],
                        capture_output=True,
                        text=True
                    )
                    logger.info(f"Pull output: {result.stdout}")
                    if result.returncode != 0:
                        logger.error(f"Pull error: {result.stderr}")
                        return False

                else:
                    logger.info(f"Model '{self.model_name}' found")
                return True

        except Exception as e:
            logger.error(f"Error ensuring model availability: {str(e)}")
            return False

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        """Generate a response using the Ollama API."""
        try:
            logger.debug(f"Generating response for prompt: {prompt[:100]}...")  # Log first 100 chars

            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": self.model_name,
                    "messages": history,
                    "stream": False,
                },
            )

            logger.debug(f"Raw API response: {response.text[:500]}...")  # Log first 500 chars

            response_data = response.json()
            if "message" in response_data and "content" in response_data["message"]:
                raw_content = response_data["message"]["content"].strip()
                logger.debug(f"Raw content before escaping: {raw_content[:200]}...")  # Log first 200 chars

                escaped_content = escape_markdown(raw_content)
                logger.debug(f"Escaped content: {escaped_content[:200]}...")  # Log first 200 chars

                return escaped_content
            else:
                logger.error(f"Unexpected response format: {response_data}")
                return "Sorry, I'm having trouble generating a response right now."

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}", exc_info=True)  # Added exc_info for stack trace
            return "Sorry, I'm having trouble generating a response right now."
