from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env  (config.py is backend/app/core/config.py)
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Application settings, read from environment variables or backend/.env."""

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = (
        "http://localhost:5500,http://127.0.0.1:5500,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    # Knowledge-base uploads. Kept OUTSIDE frontend/, which is publicly served at /app/.
    storage_dir: Path = BACKEND_DIR / "storage" / "documents"
    max_upload_mb: int = 10

    # Chunking: words per chunk, and roughly how many words neighbouring chunks share.
    chunk_words: int = 500
    chunk_overlap_words: int = 75

    # Local embeddings through Ollama. Runs on this machine; no paid API is involved.
    ollama_url: str = "http://127.0.0.1:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimension: int = 768  # how many numbers nomic-embed-text returns per text
    ollama_timeout_seconds: float = 120  # the first call also loads the model into memory

    # Semantic search. How many chunks to return at most, and the lowest cosine similarity
    # accepted as "relevant". INITIAL PROTOTYPE THRESHOLD, measured on 2026-09-22 with
    # nomic-embed-text and the test knowledge base: answered questions scored 0.578-0.828,
    # unrelated or unanswered ones 0.386-0.532. Re-measure when documents or model change.
    search_top_k: int = 3
    search_similarity_threshold: float = 0.55

    # Answer generation (RAG) with a local model through Ollama.
    llm_model: str = "llama3.2:3b"
    llm_timeout_seconds: float = 180   # a CPU-only machine can be slow, above all on the first call
    llm_context_tokens: int = 4096     # room for the rules + up to 3 chunks of 500 words + the question
    llm_max_answer_tokens: int = 200   # answers are asked to be 1-3 sentences; this is a hard cap
    llm_temperature: float = 0.0       # always pick the most likely words: no creative variation

    # Human handoff: how long "Talk to Human Support" stays valid after the AI could not answer.
    handoff_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
