"""Errors raised by language-model providers."""


class ProviderError(RuntimeError):
    """Base error for provider configuration, transport, or response failures."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider cannot be configured safely."""


class ProviderUnavailableError(ProviderError):
    """Raised when a provider cannot be reached or is unavailable."""


class ProviderRateLimitError(ProviderError):
    """Raised when a provider rate limit is reached."""


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an unusable response."""
