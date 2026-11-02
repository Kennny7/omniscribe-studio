# omniscribe-studio/services/shared-core/src/shared_core/config.py
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Project Paths
    DATA_DIR: Path = Path("./data")
    SQLITE_FALLBACK_PATH: Path = Path("./data/trait_engine/traits.db")
    TRAIT_JSONL_LOG_PATH: Path = Path("./data/trait_engine/trait_evolution_log.jsonl")

    # PostgreSQL
    POSTGRES_USER: str = "daoforge"
    POSTGRES_PASSWORD: str = "daoforge_secret_2026"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "omniscribe_db"

    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "daoforge_graph_2026"

    # Qdrant Vector DB
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    VECTOR_COLLECTION_NAME: str = "omniscribe_lore_chunks"
    EMBEDDING_DIM: int = 1024

    # Redis Bus
    REDIS_URL: str = "redis://localhost:6379/0"

    # Local LLM Endpoints (Ollama / vLLM / LiteLLM)
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: str = "ollama"
    DEFAULT_PROSE_MODEL: str = "openai/qwen2.5:14b"
    TRANSLATION_MODEL: str = "openai/dao-9b"
    UNCENSORED_MODEL: str = "openai/dolphin-mistral-nemo:12b"
    FAST_TAGGER_MODEL: str = "openai/qwen2.5:3b"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sqlite_dsn(self) -> str:
        self.SQLITE_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{self.SQLITE_FALLBACK_PATH}"


settings = Settings()