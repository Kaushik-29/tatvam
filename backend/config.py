"""
MedResolve — central runtime configuration for the longitudinal (STAIR-Clinical) stack.

Every value can be overridden with an environment variable of the same name.
"""

import os
import secrets
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# SQLAlchemy URL. SQLite is the development default; PostgreSQL works unchanged, e.g.
#   DATABASE_URL=postgresql+psycopg2://medresolve:medresolve@localhost:5432/medresolve
DATABASE_URL = _env("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'medresolve.db').as_posix()}")

# Local LLM (Ollama)
OLLAMA_URL = _env("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT_S = float(_env("OLLAMA_TIMEOUT_S", "180"))
USE_OLLAMA = _env("USE_OLLAMA", "1") == "1"

# Retrieval
EMBEDDING_MODEL = _env("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_CACHE_DIR = MODELS_DIR / "embeddings"
REFERENCE_INDEX_DIR = DATA_DIR / "datasets" / "medical_knowledge" / "processed"

# STAIR-Clinical selector backend: "lora" (fine-tuned adapter), "ollama" (zero-shot,
# validated), or "structural" (BM25 + dense scoring over ToC titles; no LLM).
STAIR_BACKEND = _env("STAIR_BACKEND", "auto")
STAIR_ADAPTER_DIR = Path(_env("STAIR_ADAPTER_DIR", str(MODELS_DIR / "stair_clinical" / "adapters" / "current")))

# Auth
_secret_file = DATA_DIR / ".jwt_secret"


def _load_secret() -> str:
    if os.environ.get("JWT_SECRET"):
        return os.environ["JWT_SECRET"]
    _secret_file.parent.mkdir(parents=True, exist_ok=True)
    if not _secret_file.exists():
        _secret_file.write_text(secrets.token_hex(32), encoding="utf-8")
    return _secret_file.read_text(encoding="utf-8").strip()


JWT_SECRET = _load_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(_env("JWT_EXPIRE_MINUTES", "720"))

UPLOAD_DIR = DATA_DIR / "uploads"
