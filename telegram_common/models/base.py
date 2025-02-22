from abc import ABC, abstractmethod

class ModelClient(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str, history: list) -> str:
        """Generate a response based on the prompt and conversation history."""
        pass
