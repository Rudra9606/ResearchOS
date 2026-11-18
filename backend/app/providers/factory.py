"""Provider selection and reusable provider instances."""

from functools import lru_cache

from app.core.config import settings
from app.providers.base import LLMProvider
from app.providers.exceptions import ProviderConfigurationError
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider


def create_llm_provider() -> LLMProvider:
    """Create the configured provider, validating local configuration first."""
    provider_name = settings.LLM_PROVIDER.strip().lower()
    if provider_name == "gemini":
        return GeminiProvider(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
            max_retries=settings.LLM_MAX_RETRIES,
        )
    if provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        )
    raise ProviderConfigurationError(
        "Unsupported LLM_PROVIDER. Choose 'gemini' or 'ollama'."
    )


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """Return one reusable provider instance for the process."""
    return create_llm_provider()
