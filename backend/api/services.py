"""Lazily constructed shared services (embedder, indexes, STAIR selector, LLM)."""

import logging
import threading
from typing import Optional

from backend import config
from backend.rag.pipeline import PipelineDeps

logger = logging.getLogger("MedResolve.Services")
_lock = threading.Lock()
_deps: Optional[PipelineDeps] = None


def get_deps() -> PipelineDeps:
    global _deps
    with _lock:
        if _deps is None:
            from backend.llm.ollama_client import OllamaClient
            from backend.rag.embeddings import get_embedder
            from backend.rag.reference_index import ReferenceIndex
            from backend.stair_retriever.selector import build_selector
            emb = get_embedder()
            try:
                ref = ReferenceIndex(emb)
            except Exception as e:                       # corpus not built yet
                logger.warning("Reference index unavailable: %s", e)
                ref = None
            sel = build_selector(config.STAIR_BACKEND, embedder=emb)
            llm = OllamaClient() if config.USE_OLLAMA else None
            _deps = PipelineDeps(embedder=emb, reference_index=ref, selector=sel, llm=llm)
            logger.info("Services ready: STAIR backend=%s, LLM=%s", sel.backend_name, llm.model if llm else None)
    return _deps
