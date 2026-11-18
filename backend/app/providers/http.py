"""Shared HTTP error handling for language-model providers."""

from collections.abc import Mapping
from typing import Any

import httpx

from app.providers.exceptions import (
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderUnavailableError,
)


def raise_for_provider_response(response: httpx.Response, provider: str) -> None:
    """Map HTTP failures to safe, provider-neutral exceptions."""
    if response.is_success:
        return
    if response.status_code == 429:
        raise ProviderRateLimitError(f"{provider} rate limit exceeded.")
    if response.status_code in {408, 425, 500, 502, 503, 504}:
        raise ProviderUnavailableError(
            f"{provider} is temporarily unavailable (HTTP {response.status_code})."
        )
    raise ProviderResponseError(
        f"{provider} request failed (HTTP {response.status_code})."
    )


def response_text(payload: Mapping[str, Any], provider: str) -> str:
    """Extract a non-empty response string from a provider payload."""
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    raise ProviderResponseError(f"{provider} returned no generated text.")


def request_error(provider: str, exc: Exception) -> ProviderUnavailableError:
    """Convert transport and timeout failures without exposing request secrets."""
    if isinstance(exc, httpx.TimeoutException):
        return ProviderUnavailableError(f"{provider} request timed out.")
    return ProviderUnavailableError(f"{provider} request could not be completed.")
