"""Shared base class for negotiation agents."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from agenticpay.models.base_llm import BaseLLM

class BaseAgent(ABC):
    def __init__(self, model: BaseLLM, role_description: str, name: str):
        self.model, self.role_description, self.name = model, role_description, name
        self.context: Dict[str, Any] = {}
        self.initialized = False
    def initialize(self, context: Dict[str, Any]) -> None:
        self.context, self.initialized = context, True
    @abstractmethod
    def respond(self, conversation_history: List[Dict[str, Any]], current_state: Dict[str, Any]) -> str:
        """Return the next negotiation message."""
    def _history_text(self, history: List[Dict[str, Any]]) -> str:
        return "\n".join(f"{m.get('role', 'agent').title()}: {m.get('content', '')}" for m in history) or "No messages yet."
