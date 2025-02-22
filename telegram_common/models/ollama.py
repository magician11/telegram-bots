import requests
import logging
import subprocess
import time
from typing import List, Dict
from .base import ModelClient

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
            response = requests.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                if not any(model["name"] == self.model_name for model in models):
                    logger.info(f"Model '{self.model_name}' not found, pulling...")
                    subprocess.run(["ollama", "pull", self.model_name], check=True)
                else:
                    logger.info(f"Model '{self.model_name}' found, skipping pull")
                return True
        except Exception as e:
            logger.error(f"Error ensuring model availability: {str(e)}")
            return False

    async def generate_response(self, prompt: str, history: List[Dict]) -> str:
        """Generate a response using the Ollama API."""
        try:
            # The history already includes the system prompt, so we don't need to add it again
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": self.model_name,
                    "messages": history,  # Use the existing history (includes system prompt)
                    "stream": False,
                },
            )

            response_data = response.json()
            if "message" in response_data and "content" in response_data["message"]:
                return response_data["message"]["content"].strip()
            else:
                logger.error(f"Unexpected response format: {response_data}")
                return "Sorry, I'm having trouble generating a response right now."
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "Sorry, I'm having trouble generating a response right now."
