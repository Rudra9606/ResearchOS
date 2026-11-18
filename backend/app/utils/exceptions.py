"""Custom application exceptions for ResearchOS."""


class ResearchOSException(Exception):
    """Base exception for ResearchOS application."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: dict | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(ResearchOSException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", details: dict | None = None):
        super().__init__(message=message, status_code=401, details=details)


class AuthorizationError(ResearchOSException):
    """Raised when authorization fails."""

    def __init__(self, message: str = "Access denied", details: dict | None = None):
        super().__init__(message=message, status_code=403, details=details)


class NotFoundError(ResearchOSException):
    """Raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found", details: dict | None = None):
        super().__init__(message=message, status_code=404, details=details)


class ValidationError(ResearchOSException):
    """Raised when input validation fails."""

    def __init__(self, message: str = "Validation error", details: dict | None = None):
        super().__init__(message=message, status_code=400, details=details)


class DocumentProcessingError(ResearchOSException):
    """Raised when document processing fails."""

    def __init__(self, message: str = "Document processing failed", details: dict | None = None):
        super().__init__(message=message, status_code=422, details=details)


class RAGRetrievalError(ResearchOSException):
    """Raised when RAG retrieval fails."""

    def __init__(self, message: str = "RAG retrieval failed", details: dict | None = None):
        super().__init__(message=message, status_code=500, details=details)


class AgentExecutionError(ResearchOSException):
    """Raised when an agent execution fails."""

    def __init__(self, message: str = "Agent execution failed", details: dict | None = None):
        super().__init__(message=message, status_code=500, details=details)


class LLMError(ResearchOSException):
    """Raised when LLM API calls fail."""

    def __init__(self, message: str = "LLM API error", details: dict | None = None):
        super().__init__(message=message, status_code=500, details=details)