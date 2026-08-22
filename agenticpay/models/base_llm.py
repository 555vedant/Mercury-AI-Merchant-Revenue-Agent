"""Provider-neutral text-generation interface."""
from abc import ABC, abstractmethod
from typing import Optional

class BaseLLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: Optional[int] = None, **kwargs: object) -> str:
        """Generate text from a prompt."""
