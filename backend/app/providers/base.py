"""Provider-agnostic language-model interface used by ResearchOS agents."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProvider(ABC):
    """Common async interface for configured language-model providers."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text from a prompt."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """Generate and validate a Pydantic structured response."""

    async def summarize(
        self,
        text: str,
        *,
        instruction: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Summarize supplied text without inventing unavailable context."""
        prompt = (
            f"{instruction}\n\n" if instruction else ""
        ) + "Summarize the following text:\n\n" + text
        return await self.generate(prompt, max_tokens=max_tokens)

    async def answer(
        self,
        question: str,
        *,
        context: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Answer a question, optionally constrained by supplied context."""
        prompt = question
        if context:
            prompt = (
                "Answer using only the supplied context. If the context is "
                "insufficient, say so explicitly.\n\n"
                f"Context:\n{context}\n\nQuestion:\n{question}"
            )
        return await self.generate(
            prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )

    async def generate_with_context(
        self,
        prompt: str,
        context: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a response grounded in an explicit context block."""
        return await self.answer(
            prompt,
            context=context,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Yield generated text chunks as they become available."""
        yield ""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return whether the configured provider is reachable and usable."""

    async def aclose(self) -> None:
        """Release provider resources, if any."""

    @staticmethod
    def _model_schema(response_model: type[T]) -> dict[str, Any]:
        return response_model.model_json_schema()
