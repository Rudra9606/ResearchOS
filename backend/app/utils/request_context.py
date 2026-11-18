"""Context-local request metadata used to correlate logs safely."""

from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar("researchos_request_id", default="-")
