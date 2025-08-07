from abc import ABC, abstractmethod

class ModelClient(ABC):
    @abstractmethod
    async def generate_response(self, history: list) -> str:
        """Generate a response based on the conversation history."""
        pass
