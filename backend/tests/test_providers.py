import asyncio

import httpx
import pytest
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.providers.exceptions import (
    ProviderConfigurationError,
    ProviderUnavailableError,
)
from app.providers.factory import get_llm_provider
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider
import app.providers.factory as provider_factory


class Answer(BaseModel):
    answer: str


def run(coroutine):
    return asyncio.run(coroutine)


def test_provider_selection(monkeypatch):
    monkeypatch.setattr(
        provider_factory,
        "settings",
        Settings(
            DATABASE_URL="postgresql+psycopg://db",
            SECRET_KEY="secret",
            LLM_PROVIDER="ollama",
        ),
    )
    get_llm_provider.cache_clear()
    provider = get_llm_provider()
    assert isinstance(provider, OllamaProvider)
    get_llm_provider.cache_clear()


def test_invalid_provider_configuration():
    with pytest.raises(ValidationError, match="LLM_PROVIDER"):
        Settings(
            DATABASE_URL="postgresql+psycopg://db",
            SECRET_KEY="secret",
            LLM_PROVIDER="unknown",
        )


def test_gemini_requires_api_key():
    with pytest.raises(ProviderConfigurationError, match="GEMINI_API_KEY"):
        GeminiProvider(api_key=None, model="gemini-test")


def test_gemini_initialization_does_not_make_network_request():
    provider = GeminiProvider(api_key="test-key", model="gemini-test")
    assert provider.model == "gemini-test"
    assert provider.timeout_seconds == 60.0


def test_ollama_initialization():
    provider = OllamaProvider(
        base_url="http://localhost:11434/",
        model="llama-test",
    )
    assert provider.base_url == "http://localhost:11434"
    assert provider.model == "llama-test"


def test_gemini_generation_and_structured_output(monkeypatch):
    provider = GeminiProvider(api_key="test-key", model="gemini-test")

    async def fake_request(**kwargs):
        if kwargs.get("response_schema") is not None:
            return {
                "candidates": [{
                    "content": {"parts": [{"text": '{"answer":"structured"}'}]}
                }]
            }
        return {
            "candidates": [{
                "content": {"parts": [{"text": "generated"}]}
            }]
        }

    monkeypatch.setattr(provider, "_request_json", fake_request)
    assert run(provider.generate("prompt")) == "generated"
    result = run(provider.generate_structured("prompt", Answer))
    assert result.answer == "structured"


def test_ollama_generation_and_context_helpers(monkeypatch):
    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama-test",
    )

    async def fake_request(**kwargs):
        return {"message": {"content": "response"}}

    monkeypatch.setattr(provider, "_request_json", fake_request)
    assert run(provider.generate("prompt")) == "response"
    assert run(provider.answer("question", context="evidence")) == "response"
    assert run(provider.summarize("long text")) == "response"


def test_provider_http_response_parsing_without_external_network():
    async def handler(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={"message": {"content": "transport response"}},
        )

    provider = OllamaProvider(
        base_url="http://testserver",
        model="llama-test",
        transport=httpx.MockTransport(handler),
    )
    assert run(provider.generate("prompt")) == "transport response"


def test_provider_failure_is_not_converted_to_a_fake_response(monkeypatch):
    provider = GeminiProvider(api_key="test-key", model="gemini-test")

    async def failed_request(**kwargs):
        raise ProviderUnavailableError("Gemini request timed out.")

    monkeypatch.setattr(provider, "_request_json", failed_request)
    with pytest.raises(ProviderUnavailableError):
        run(provider.generate("prompt"))
