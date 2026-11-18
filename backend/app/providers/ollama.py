"""Local Ollama provider using the Ollama HTTP API."""

import json
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.providers.base import LLMProvider
from app.providers.exceptions import (
    ProviderConfigurationError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from app.providers.http import raise_for_provider_response, request_error

T = TypeVar("T", bound=BaseModel)


class OllamaProvider(LLMProvider):
    """Async provider for a locally running Ollama server."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not base_url.strip():
            raise ProviderConfigurationError("OLLAMA_BASE_URL must not be empty.")
        if not model.strip():
            raise ProviderConfigurationError("OLLAMA_MODEL must not be empty.")
        if timeout_seconds <= 0:
            raise ProviderConfigurationError("LLM_TIMEOUT_SECONDS must be positive.")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self._transport,
        )

    @staticmethod
    def _messages(prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    async def _request_json(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        body: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(prompt, system_prompt),
            "stream": False,
        }
        if options:
            body["options"] = options
        if response_schema is not None:
            body["format"] = response_schema
        try:
            async with self._client() as client:
                response = await client.post(f"{self.base_url}/api/chat", json=body)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise request_error("Ollama", exc) from exc
        raise_for_provider_response(response, "Ollama")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Ollama returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError("Ollama returned an invalid response shape.")
        return payload

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        try:
            text = payload["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderResponseError("Ollama returned no message content.") from exc
        if not isinstance(text, str) or not text.strip():
            raise ProviderResponseError("Ollama returned empty generated text.")
        return text.strip()

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload = await self._request_json(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._extract_text(payload)

    async def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        payload = await self._request_json(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_schema=self._model_schema(response_model),
        )
        try:
            return response_model.model_validate_json(self._extract_text(payload))
        except (ValidationError, json.JSONDecodeError) as exc:
            raise ProviderResponseError(
                "Ollama returned structured output that did not match the requested schema."
            ) from exc

    async def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages(prompt, system_prompt),
            "stream": True,
        }
        if temperature is not None or max_tokens is not None:
            body["options"] = {
                key: value
                for key, value in {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }.items()
                if value is not None
            }
        try:
            async with self._client() as client:
                async with client.stream(
                    "POST", f"{self.base_url}/api/chat", json=body
                ) as response:
                    raise_for_provider_response(response, "Ollama")
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        payload = json.loads(line)
                        text = self._extract_text(payload)
                        if text:
                            yield text
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise request_error("Ollama", exc) from exc

    async def health_check(self) -> bool:
        try:
            async with self._client() as client:
                response = await client.get(f"{self.base_url}/api/tags")
            raise_for_provider_response(response, "Ollama")
        except (httpx.TimeoutException, httpx.RequestError, ProviderUnavailableError):
            return False
        return True
