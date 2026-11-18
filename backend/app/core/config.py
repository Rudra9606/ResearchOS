from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):

    DATABASE_URL: str

    SECRET_KEY: str

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # LLM Provider Configuration
    LLM_PROVIDER: str = "gemini"  # "gemini" or "ollama"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    LLM_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0)
    LLM_MAX_RETRIES: int = Field(default=2, ge=0)

    # Web and academic research providers
    TAVILY_API_KEY: str | None = None
    TAVILY_MAX_RESULTS: int = Field(default=5, ge=1, le=20)
    TAVILY_SEARCH_DEPTH: str = "basic"
    TAVILY_MIN_RELEVANCE_SCORE: float | None = Field(default=None, ge=0, le=1)
    TAVILY_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)
    TAVILY_MAX_RETRIES: int = Field(default=2, ge=0)
    SEMANTIC_SCHOLAR_API_KEY: str | None = None
    CROSSREF_MAILTO: str | None = None
    ACADEMIC_SEARCH_ENABLED: bool = True
    ACADEMIC_MAX_RESULTS: int = Field(default=5, ge=1, le=50)
    ACADEMIC_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0)

    # Document Processing
    MAX_FILE_SIZE_MB: int = Field(default=50, ge=1, le=500)
    UPLOAD_DIR: str = "uploads"

    # RAG Configuration
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = Field(default=384, ge=1)
    EMBEDDING_DEVICE: str | None = None
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    RAG_VECTOR_TOP_K: int = Field(default=20, ge=1, le=100)
    RAG_BM25_TOP_K: int = Field(default=20, ge=1, le=100)
    RAG_RRF_K: int = Field(default=60, ge=1)
    BM25_K1: float = Field(default=1.5, gt=0)
    BM25_B: float = Field(default=0.75, ge=0, le=1)
    RERANKER_ENABLED: bool = True
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_DEVICE: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    @field_validator("LLM_PROVIDER")
    @classmethod
    def validate_llm_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"gemini", "ollama"}:
            raise ValueError("LLM_PROVIDER must be either 'gemini' or 'ollama'.")
        return normalized

    @field_validator("TAVILY_SEARCH_DEPTH")
    @classmethod
    def validate_tavily_search_depth(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"basic", "advanced"}:
            raise ValueError("TAVILY_SEARCH_DEPTH must be 'basic' or 'advanced'.")
        return normalized


settings = Settings()
