"""Base Agent class for all ResearchOS agents."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from app.providers.base import LLMProvider
from app.providers.factory import get_llm_provider


class BaseAgent(ABC):
    """Base class for all research agents."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's logic on the given state."""
        pass

    def _get_llm(self) -> LLMProvider:
        """Get the configured provider through the shared abstraction."""
        return get_llm_provider()