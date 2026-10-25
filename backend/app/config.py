from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    # .env is looked up in the project root first, then the working directory
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_DIR / ".env"), ".env"), extra="ignore"
    )

    # --- four NoSQL stores -------------------------------------------------
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "ctiplatform"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "cti"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "threat_chunks"

    # --- locally hosted LLM (NFR1: no mandatory cloud API) -----------------
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"  # 3B meets the 15 s GraphRAG p95 SLO on a laptop (README §6)
    llm_timeout_s: float = 60.0

    # --- embeddings: "tfidf" (offline, default) or "ollama" (nomic-embed-text)
    embedder: str = "tfidf"
    ollama_embed_model: str = "nomic-embed-text"

    # --- API / security ----------------------------------------------------
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    jwt_secret: str = "change-me-in-production-please-32b"
    jwt_expiry_minutes: int = 480
    # API key used by downstream firewall / EDR / SIEM consumers (enforcement path)
    consumer_api_key: str = "edr-consumer-key"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- GraphRAG query budgets (risk: hub nodes / corpus growth) ----------
    max_hops: int = 3
    hub_degree_threshold: int = 5      # USES in-degree at which a Malware node is a commodity hub
    max_neighbours_per_node: int = 12
    vector_top_k: int = 6
    min_citation_coverage: float = 0.5

    # --- LLM prompt budget (NFR2): prompt evaluation dominates local-LLM latency, so the model
    # sees a trimmed evidence pack; the UI and the audit log still get the full evidence.
    llm_max_facts: int = 30
    llm_max_docs: int = 6
    llm_doc_chars: int = 300
    llm_max_iocs: int = 12
    llm_num_predict: int = 320         # output-token cap (the answer is 3-8 sentences)
    llm_keep_alive: str = "30m"        # keep the model resident between questions

    auto_seed: bool = True


settings = Settings()
DATA_DIR.mkdir(parents=True, exist_ok=True)
