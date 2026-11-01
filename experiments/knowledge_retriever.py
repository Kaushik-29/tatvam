"""
MedResolve — Medical Knowledge Ingestion and Retrieval Pipeline
Phase 5 Component

Implements:
1. Document ingestion and metadata preservation.
2. Passage extraction and chunking with full provenance.
3. Dense vector retrieval using SentenceTransformers + FAISS.
4. Lexical retrieval baseline using BM25Okapi.
5. Hybrid retrieval via Reciprocal Rank Fusion (RRF).
6. Result ranking and passage provenance formatting.
"""

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("MedResolve.Retriever")


@dataclass
class PassageMetadata:
    """Passage-level provenance and source metadata."""
    passage_id: str
    document_id: str
    document_title: str
    document_organization: str
    section_heading: str
    source_url: str
    publication_date: Optional[str]
    date_uncertainty_note: Optional[str]
    license_or_reuse_conditions: str
    document_type: str
    version: str
    access_date: Optional[str] = "2026-10-15"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Passage:
    """Clinical knowledge base passage."""
    passage_id: str
    text: str
    metadata: PassageMetadata

    @property
    def full_reference_citation(self) -> str:
        """Formatted citation string."""
        date_str = self.metadata.publication_date or "Date Unspecified"
        return f"{self.metadata.document_title} ({self.metadata.document_organization}, {date_str}) [{self.passage_id}]"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passage_id": self.passage_id,
            "text": self.text,
            "metadata": asdict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Passage":
        meta = PassageMetadata(**data["metadata"])
        return cls(passage_id=data["passage_id"], text=data["text"], metadata=meta)


@dataclass
class RetrievalResult:
    """Retrieved passage with ranking score and retrieval mode."""
    passage: Passage
    score: float
    rank: int
    retrieval_method: str  # 'dense_faiss', 'lexical_bm25', 'hybrid_rrf'
    dense_score: Optional[float] = None

    @property
    def citation(self) -> str:
        return self.passage.full_reference_citation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passage_id": self.passage.passage_id,
            "document_id": self.passage.metadata.document_id,
            "document_title": self.passage.metadata.document_title,
            "organization": self.passage.metadata.document_organization,
            "section_heading": self.passage.metadata.section_heading,
            "source_url": self.passage.metadata.source_url,
            "publication_date": self.passage.metadata.publication_date,
            "license": self.passage.metadata.license_or_reuse_conditions,
            "score": round(float(self.score), 4),
            "dense_score": round(float(self.dense_score), 4) if self.dense_score is not None else None,
            "rank": self.rank,
            "retrieval_method": self.retrieval_method,
            "text": self.passage.text,
            "citation": self.passage.full_reference_citation,
        }


def simple_tokenize(text: str) -> List[str]:
    """Lightweight clinical tokenizer for BM25: lowercase alphanumeric tokens."""
    tokens = re.findall(r"\b[a-zA-Z0-9_\-]+\b", text.lower())
    return [t for t in tokens if len(t) > 1]


class MedicalKnowledgeBase:
    """
    Manages document ingestion, dual-index construction (Dense FAISS + Lexical BM25),
    and evidence retrieval.
    """

    def __init__(
        self,
        knowledge_base_dir: str = "data/knowledge_base",
        embedding_model_name: str = "BAAI/bge-m3",
        use_fallback_mini_lm: bool = True,
    ):
        self.kb_dir = Path(knowledge_base_dir)
        self.manifest_path = self.kb_dir / "knowledge_manifest.json"
        self.embedding_model_name = embedding_model_name
        self.use_fallback_mini_lm = use_fallback_mini_lm

        self.passages: List[Passage] = []
        self.passage_id_to_passage: Dict[str, Passage] = {}

        # Lexical Index
        self.bm25: Optional[BM25Okapi] = None
        self.tokenized_corpus: List[List[str]] = []

        # Dense Index
        self.embedder: Optional[SentenceTransformer] = None
        self.faiss_index: Optional[faiss.IndexFlatIP] = None
        self.embedding_dimension: int = 1024

    def load_and_ingest(self) -> int:
        """
        Ingests all documents listed in knowledge_manifest.json, parses passages,
        and preserves provenance metadata.
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Knowledge manifest missing at {self.manifest_path}")

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.passages.clear()
        self.passage_id_to_passage.clear()

        for doc_entry in manifest.get("documents", []):
            doc_file = Path(doc_entry["file_path"])
            if not doc_file.exists():
                doc_file = self.kb_dir / "documents" / Path(doc_entry["file_path"]).name

            with open(doc_file, "r", encoding="utf-8") as f:
                doc_data = json.load(f)

            for p_dict in doc_data.get("passages", []):
                meta = PassageMetadata(
                    passage_id=p_dict["passage_id"],
                    document_id=doc_data["document_id"],
                    document_title=doc_data["title"],
                    document_organization=doc_data.get("author_or_organization", "Unknown Organization"),
                    section_heading=p_dict.get("section_heading", "General"),
                    source_url=doc_data.get("source_url", ""),
                    publication_date=doc_data.get("publication_or_revision_date"),
                    date_uncertainty_note=doc_data.get("date_uncertainty_note"),
                    license_or_reuse_conditions=doc_data.get("license_or_reuse_conditions", "Restricted / Check Source"),
                    document_type=doc_data.get("document_type", "Guideline"),
                    version=doc_data.get("version", "1.0"),
                )
                passage = Passage(
                    passage_id=p_dict["passage_id"],
                    text=p_dict["text"],
                    metadata=meta,
                )
                self.passages.append(passage)
                self.passage_id_to_passage[passage.passage_id] = passage

        logger.info(f"Ingested {len(self.passages)} passages across {len(manifest.get('documents', []))} documents.")
        return len(self.passages)

    def build_lexical_index(self):
        """Builds BM25 index over the ingested passage collection."""
        if not self.passages:
            self.load_and_ingest()

        self.tokenized_corpus = [simple_tokenize(p.text) for p in self.passages]
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        logger.info(f"Built BM25 lexical index over {len(self.passages)} passages.")

    def build_dense_index(self, index_cache_dir: Optional[str] = None):
        """
        Builds FAISS dense inner-product index using SentenceTransformer embeddings.
        Normalizes embeddings to unit L2 norm so inner product equals cosine similarity.
        """
        if not self.passages:
            self.load_and_ingest()

        cache_dir = Path(index_cache_dir) if index_cache_dir else self.kb_dir / "index"
        faiss_file = cache_dir / "dense_index.faiss"
        meta_file = cache_dir / "passage_ids.json"

        # Check if cached index exists and matches passage count
        if faiss_file.exists() and meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                cached_ids = json.load(f)
            if cached_ids == [p.passage_id for p in self.passages]:
                logger.info(f"Loading cached FAISS index from {faiss_file}")
                self.faiss_index = faiss.read_index(str(faiss_file))
                self.embedding_dimension = self.faiss_index.d
                self._init_embedder()
                return

        # Initialize embedder and compute embeddings
        self._init_embedder()
        texts = [f"{p.metadata.section_heading}\n{p.text}" for p in self.passages]
        logger.info(f"Computing dense embeddings for {len(texts)} passages with {self.embedding_model_name}...")

        t0 = time.time()
        embeddings = self.embedder.encode(texts, batch_size=8, show_progress_bar=False, normalize_embeddings=True)
        embeddings = np.array(embeddings, dtype=np.float32)
        logger.info(f"Dense embeddings computed in {time.time()-t0:.2f}s, shape: {embeddings.shape}")

        self.embedding_dimension = embeddings.shape[1]
        self.faiss_index = faiss.IndexFlatIP(self.embedding_dimension)
        self.faiss_index.add(embeddings)
        logger.info(f"Built FAISS dense index (dim={self.embedding_dimension}, total={self.faiss_index.ntotal}).")

        # Cache index
        cache_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.faiss_index, str(faiss_file))
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump([p.passage_id for p in self.passages], f, indent=2)
        logger.info(f"Cached FAISS index to {cache_dir}")

    def _init_embedder(self):
        """Loads SentenceTransformer with fallback."""
        if self.embedder is not None:
            return
        try:
            logger.info(f"Loading SentenceTransformer: {self.embedding_model_name}...")
            self.embedder = SentenceTransformer(self.embedding_model_name)
        except Exception as e:
            if self.use_fallback_mini_lm and self.embedding_model_name != "all-MiniLM-L6-v2":
                logger.warning(f"Failed to load {self.embedding_model_name} ({e}). Falling back to all-MiniLM-L6-v2.")
                self.embedding_model_name = "all-MiniLM-L6-v2"
                self.embedder = SentenceTransformer(self.embedding_model_name)
            else:
                raise e

    def search_lexical(self, query: str, top_k: int = 3) -> List[RetrievalResult]:
        """Performs BM25 lexical search."""
        if self.bm25 is None:
            self.build_lexical_index()

        query_tokens = simple_tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for rank, idx in enumerate(top_indices, 1):
            score = float(scores[idx])
            if score <= 0.0:
                continue
            passage = self.passages[idx]
            results.append(
                RetrievalResult(
                    passage=passage,
                    score=score,
                    rank=rank,
                    retrieval_method="lexical_bm25",
                )
            )
        return results

    def search_dense(self, query: str, top_k: int = 3) -> List[RetrievalResult]:
        """Performs FAISS dense semantic vector search."""
        if self.faiss_index is None:
            self.build_dense_index()

        q_emb = self.embedder.encode([query], normalize_embeddings=True, show_progress_bar=False)
        q_emb = np.array(q_emb, dtype=np.float32)

        scores, indices = self.faiss_index.search(q_emb, top_k)

        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0]), 1):
            if idx < 0 or idx >= len(self.passages):
                continue
            passage = self.passages[idx]
            results.append(
                RetrievalResult(
                    passage=passage,
                    score=float(score),
                    rank=rank,
                    retrieval_method="dense_faiss",
                    dense_score=float(score),
                )
            )
        return results

    def search_hybrid(
        self,
        query: str,
        top_k: int = 3,
        rrf_k: int = 60,
    ) -> List[RetrievalResult]:
        """
        Combines Dense FAISS and Lexical BM25 rankings using Reciprocal Rank Fusion (RRF).
        RRF Score: sum(1.0 / (rrf_k + rank_i))
        """
        dense_results = self.search_dense(query, top_k=top_k * 2)
        lexical_results = self.search_lexical(query, top_k=top_k * 2)

        dense_scores_map = {res.passage.passage_id: res.score for res in dense_results}
        rrf_scores: Dict[str, float] = {}

        for rank, res in enumerate(dense_results, 1):
            pid = res.passage.passage_id
            rrf_scores[pid] = rrf_scores.get(pid, 0.0) + (1.0 / (rrf_k + rank))

        for rank, res in enumerate(lexical_results, 1):
            pid = res.passage.passage_id
            rrf_scores[pid] = rrf_scores.get(pid, 0.0) + (1.0 / (rrf_k + rank))

        sorted_pids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for rank, (pid, score) in enumerate(sorted_pids, 1):
            passage = self.passage_id_to_passage[pid]
            results.append(
                RetrievalResult(
                    passage=passage,
                    score=score,
                    rank=rank,
                    retrieval_method="hybrid_rrf",
                    dense_score=dense_scores_map.get(pid),
                )
            )
        return results
