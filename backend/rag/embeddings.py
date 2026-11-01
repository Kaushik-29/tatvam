"""
BGE-M3 dense embeddings with a content-addressed on-disk cache.

Vectors are L2-normalized (cosine == inner product) and cached per text SHA-1 so
that re-indexing, new uploads and evaluation runs never re-encode known texts.
"""

import atexit
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from backend import config

logger = logging.getLogger("MedResolve.Embeddings")


class CachedEmbedder:
    def __init__(self, model_name: str = config.EMBEDDING_MODEL, cache_dir: Path = config.EMBEDDING_CACHE_DIR,
                 max_seq_length: int = 256):
        self.model_name = model_name
        self.cache_dir = Path(cache_dir) / model_name.replace("/", "__")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_seq_length = max_seq_length
        self._model = None
        self._lock = threading.RLock()
        self._mem: Dict[str, np.ndarray] = {}
        self._pending: List[str] = []
        self._load_shards()
        atexit.register(self.flush)

    # ------------------------------------------------------------------ cache
    def _load_shards(self):
        for keys_file in sorted(self.cache_dir.glob("shard_*.json")):
            vecs = np.load(keys_file.with_suffix(".npy"))
            keys = json.loads(keys_file.read_text(encoding="utf-8"))
            for k, v in zip(keys, vecs):
                self._mem[k] = v

    def _persist(self, keys: List[str], vecs: np.ndarray):
        """Writes one shard. Names are unique per process/time so concurrent writers never collide;
        the .json key file is written last so a half-written shard is never loaded."""
        if not keys:
            return
        base = self.cache_dir / f"shard_{int(time.time() * 1000)}_{os.getpid()}_{uuid.uuid4().hex[:6]}"
        np.save(base.with_suffix(".npy"), vecs.astype(np.float32))
        base.with_suffix(".json").write_text(json.dumps(keys), encoding="utf-8")

    def flush(self):
        """Persists buffered small encodes (called automatically at exit)."""
        with self._lock:
            if self._pending:
                keys = list(self._pending)
                self._persist(keys, np.stack([self._mem[k] for k in keys]))
                self._pending.clear()

    def compact(self):
        """Merges all shards into one (run when no other process is writing)."""
        with self._lock:
            self.flush()
            shards = sorted(self.cache_dir.glob("shard_*.json"))
            if len(shards) <= 1:
                return
            keys = list(self._mem)
            self._persist(keys, np.stack([self._mem[k] for k in keys]))
            newest = max(self.cache_dir.glob("shard_*.json"), key=lambda p: p.stat().st_mtime)
            for s in shards:
                if s != newest:
                    s.unlink()
                    s.with_suffix(".npy").unlink(missing_ok=True)

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    @property
    def dim(self) -> int:
        return 1024 if "bge-m3" in self.model_name.lower() else self.model.get_sentence_embedding_dimension()

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model %s", self.model_name)
            self._model = SentenceTransformer(self.model_name, device="cpu")
            self._model.max_seq_length = self.max_seq_length
        return self._model

    def encode(self, texts: Sequence[str], batch_size: int = 32, show_progress: bool = False,
               persist_every: int = 2048, persist: bool = True) -> np.ndarray:
        keys = [self.key(t) for t in texts]
        missing = list(dict.fromkeys(k_t for k_t in zip(keys, texts) if k_t[0] not in self._mem))
        if missing:
            with self._lock:
                for i in range(0, len(missing), persist_every):
                    chunk = missing[i:i + persist_every]
                    vecs = self.model.encode([t for _, t in chunk], batch_size=batch_size,
                                             normalize_embeddings=True, show_progress_bar=show_progress)
                    vecs = np.asarray(vecs, dtype=np.float32)
                    for (k, _), v in zip(chunk, vecs):
                        self._mem[k] = v
                    if not persist:
                        continue
                    if len(chunk) >= 256:
                        self._persist([k for k, _ in chunk], vecs)
                    else:                                   # buffer small encodes
                        self._pending.extend(k for k, _ in chunk)
                    if show_progress:
                        logger.info("encoded %d/%d new texts", min(i + persist_every, len(missing)), len(missing))
            if len(self._pending) >= 1024:
                self.flush()
        if not keys:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.stack([self._mem[k] for k in keys]).astype(np.float32)

    def encode_query(self, text: str) -> np.ndarray:
        """Query vectors are not persisted (one-off texts)."""
        return self.encode([text], persist=False)[0]


_default: Optional[CachedEmbedder] = None


def get_embedder() -> CachedEmbedder:
    global _default
    if _default is None:
        _default = CachedEmbedder()
    return _default
