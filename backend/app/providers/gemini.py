"""Google Gemini provider using the Generative Language REST API."""

import json
import asyncio
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.providers.base import LLMProvider
from app.providers.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from app.providers.http import raise_for_provider_response, request_error

T = TypeVar("T", bound=BaseModel)


class GeminiProvider(LLMProvider):
    """Async Gemini provider with JSON-schema constrained generation."""

    _base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key or not api_key.strip():
            raise ProviderConfigurationError(
                "GEMINI_API_KEY is required when LLM_PROVIDER=gemini."
            )
        if not model.strip():
            raise ProviderConfigurationError("GEMINI_MODEL must not be empty.")
        if timeout_seconds <= 0:
            raise ProviderConfigurationError("LLM_TIMEOUT_SECONDS must be positive.")
        if max_retries < 0:
            raise ProviderConfigurationError("LLM_MAX_RETRIES must not be negative.")
        self._api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self._transport,
        )

    def _url(self, *, stream: bool = False) -> str:
        operation = "streamGenerateContent" if stream else "generateContent"
        suffix = "&alt=sse" if stream else ""
        return f"{self._base_url}/{self.model}:{operation}?key={self._api_key}{suffix}"

    @staticmethod
    def _body(
        prompt: str,
        *,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }
        if system_prompt:
            body["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        generation_config: dict[str, Any] = {}
        if temperature is not None:
            generation_config["temperature"] = temperature
        if max_tokens is not None:
            generation_config["maxOutputTokens"] = max_tokens
        if response_schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = response_schema
        if generation_config:
            body["generationConfig"] = generation_config
        return body

    async def _request_json(
        self,
        *,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = self._body(
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_schema=response_schema,
        )
        for attempt in range(self.max_retries + 1):
            try:
                async with self._client() as client:
                    response = await client.post(self._url(), json=body)
                raise_for_provider_response(response, "Gemini")
                break
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if attempt >= self.max_retries:
                    raise request_error("Gemini", exc) from exc
                await asyncio.sleep(min(2**attempt, 8))
            except (ProviderRateLimitError, ProviderUnavailableError):
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(min(2**attempt, 8))
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Gemini returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise ProviderResponseError("Gemini returned an invalid response shape.")
        return payload

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str:
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            text = "".join(part["text"] for part in parts if "text" in part)
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError("Gemini returned no candidate content.") from exc
        if not text.strip():
            raise ProviderResponseError("Gemini returned empty generated text.")
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
                "Gemini returned structured output that did not match the requested schema."
            ) from exc

    async def stream(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        try:
            async with self._client() as client:
                async with client.stream(
                    "POST",
                    self._url(stream=True),
                    json=self._body(
                        prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ),
                ) as response:
                    raise_for_provider_response(response, "Gemini")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        payload = json.loads(line[5:].strip())
                        text = self._extract_text(payload)
                        if text:
                            yield text
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            raise request_error("Gemini", exc) from exc

    async def health_check(self) -> bool:
        try:
            await self._request_json(
                prompt="Reply with the word OK.",
                system_prompt="Health check.",
                temperature=0,
                max_tokens=4,
            )
        except ProviderUnavailableError:
            return False
        return True
