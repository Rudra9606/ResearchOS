"""Reusable Sentence Transformers embedding service."""

from functools import lru_cache
from threading import Lock
from typing import Sequence

from app.core.config import settings


class EmbeddingError(RuntimeError):
    """Raised when an embedding model cannot load or returns invalid vectors."""


class EmbeddingService:
    """Loads one configured embedding model and validates every output."""

    def __init__(
        self,
        model_name: str | None = None,
        dimension: int | None = None,
        device: str | None = None,
        model=None,
    ):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.dimension = dimension or settings.EMBEDDING_DIMENSION
        self.device = device if device is not None else settings.EMBEDDING_DEVICE
        self._model = model
        self._lock = Lock()

    def _get_model(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer

                    kwargs = {"device": self.device} if self.device else {}
                    self._model = SentenceTransformer(self.model_name, **kwargs)
                except Exception as exc:
                    raise EmbeddingError(
                        f"Unable to load embedding model '{self.model_name}'."
                    ) from exc
        return self._model

    def get_model(self):
        """Return the lazily loaded model for compatibility with callers."""
        return self._get_model()

    def _validate_dimension(self, embeddings: Sequence[Sequence[float]]) -> None:
        for embedding in embeddings:
            if len(embedding) != self.dimension:
                raise EmbeddingError(
                    f"Embedding model returned dimension {len(embedding)}; "
                    f"expected {self.dimension}."
                )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must contain non-empty strings.")
        model = self._get_model()
        try:
            encoded = model.encode(
                list(texts),
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            vectors = encoded.tolist() if hasattr(encoded, "tolist") else list(encoded)
        except Exception as exc:
            raise EmbeddingError("Embedding generation failed.") from exc
        self._validate_dimension(vectors)
        return [[float(value) for value in vector] for vector in vectors]

    def embed_query(self, query: str) -> list[float]:
        vectors = self.embed([query])
        return vectors[0]


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
