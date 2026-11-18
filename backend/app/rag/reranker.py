"""Optional Sentence Transformers Cross-Encoder reranking."""

from typing import Any

from app.core.config import settings


class RerankerError(RuntimeError):
    """Raised when an enabled reranker cannot load or score."""


class CrossEncoderReranker:
    """Lazy, reusable cross-encoder with explicit disabled/fallback behavior."""

    def __init__(
        self,
        model_name: str | None = None,
        *,
        enabled: bool | None = None,
        device: str | None = None,
        model=None,
        raise_on_error: bool = False,
    ):
        self.model_name = model_name or settings.RERANKER_MODEL
        self.enabled = settings.RERANKER_ENABLED if enabled is None else enabled
        self.device = device if device is not None else settings.RERANKER_DEVICE
        self._model = model
        self.raise_on_error = raise_on_error

    def _get_model(self):
        if not self.enabled:
            return None
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                kwargs = {"device": self.device} if self.device else {}
                self._model = CrossEncoder(self.model_name, **kwargs)
            except Exception as exc:
                if self.raise_on_error:
                    raise RerankerError(
                        f"Unable to load reranker model '{self.model_name}'."
                    ) from exc
                return None
        return self._model

    def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not results or not self.enabled:
            return results[:top_k]
        model = self._get_model()
        if model is None:
            return results[:top_k]
        try:
            scores = model.predict([(query, result["content"]) for result in results])
        except Exception as exc:
            if self.raise_on_error:
                raise RerankerError("Reranker scoring failed.") from exc
            return results[:top_k]
        ranked = []
        for result, score in zip(results, scores):
            item = result.copy()
            item["rerank_score"] = float(score)
            ranked.append(item)
        return sorted(
            ranked, key=lambda item: item["rerank_score"], reverse=True
        )[:top_k]
