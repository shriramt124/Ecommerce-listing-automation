"""STRATEGY 2: KEYWORD DATABASE INTERFACE (SentenceTransformers)

This replaces the old ChromaDB-backed vector store with a lightweight local
embedding index backed by a `.npz` file.

Why:
- Avoid cross-dataset contamination unless explicitly filtered
- Use SentenceTransformers embeddings directly for similarity search
- Keep ingestion/query fully local (no sqlite vector DB)

Files created by ingestion:
- strategy_2_keyword_optimizer/st_keywords_index/keywords_index.npz

Env vars:
- ADKRUX_EMBED_MODEL: SentenceTransformer model (default: all-MiniLM-L6-v2)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from embedder import encode_texts


INDEX_DIR = os.path.join(os.path.dirname(__file__), "st_keywords_index")
INDEX_PATH = os.path.join(INDEX_DIR, "keywords_index.npz")


@dataclass(frozen=True)
class _IndexData:
    embeddings: np.ndarray  # (N, D), float32, L2-normalized
    keywords: np.ndarray  # (N,), str
    scores: np.ndarray  # (N,), float32
    ad_units: np.ndarray  # (N,), float32
    ad_conv: np.ndarray  # (N,), float32
    dataset_ids: np.ndarray  # (N,), str
    source_formats: np.ndarray  # (N,), str


class KeywordDB:
    """Query interface for the on-disk SentenceTransformer keyword index."""

    def __init__(self):
        self.index: Optional[_IndexData] = None
        self._load()

    def _load(self) -> None:
        if not os.path.exists(INDEX_PATH):
            print("   [KeywordDB] No index found. Run 'python3 ingest_keywords.py' first!")
            self.index = None
            return

        data = np.load(INDEX_PATH, allow_pickle=False)
        self.index = _IndexData(
            embeddings=np.asarray(data["embeddings"], dtype=np.float32),
            keywords=np.asarray(data["keywords"], dtype=str),
            scores=np.asarray(data["scores"], dtype=np.float32),
            ad_units=np.asarray(data["ad_units"], dtype=np.float32),
            ad_conv=np.asarray(data["ad_conv"], dtype=np.float32),
            dataset_ids=np.asarray(data["dataset_ids"], dtype=str),
            source_formats=np.asarray(data["source_formats"], dtype=str),
        )
        print(f"   [KeywordDB] Loaded SentenceTransformers index: {len(self.index.keywords)} keywords")

    def list_dataset_ids(self, max_scan: int = 50000) -> List[str]:
        if not self.index:
            return []
        # max_scan kept for backward compatibility; index is already in memory
        ds = self.index.dataset_ids[:max_scan]
        return sorted({d for d in ds if d})

    def get_all_keywords(self) -> List[Dict]:
        if not self.index:
            return []

        out: List[Dict] = []
        for kw, sc, au, ac, ds, sf in zip(
            self.index.keywords,
            self.index.scores,
            self.index.ad_units,
            self.index.ad_conv,
            self.index.dataset_ids,
            self.index.source_formats,
        ):
            out.append(
                {
                    "keyword": str(kw),
                    "score": float(sc),
                    "ad_units": float(au),
                    "ad_conv": float(ac),
                    "dataset_id": str(ds) if ds is not None else None,
                    "source_format": str(sf) if sf is not None else None,
                }
            )

        out.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return out

    def get_high_volume_keywords(self, min_units: float = 50) -> List[Dict]:
        return [kw for kw in self.get_all_keywords() if float(kw.get("ad_units", 0.0) or 0.0) >= min_units]

    def get_top_keywords(self, title: str, limit: int = 10, dataset_id: str = None) -> List[Dict]:
        """Return top-N keywords by cosine similarity using SentenceTransformers.

        - embeddings are L2-normalized, so dot() is cosine similarity
        - optionally filter by dataset_id
        """
        if not self.index:
            return []
        if not title or not str(title).strip():
            return []

        query_emb = encode_texts([str(title)])[0]  # (D,)

        # Apply dataset filter if requested
        if dataset_id:
            mask = self.index.dataset_ids == str(dataset_id)
            if not np.any(mask):
                return []
            emb = self.index.embeddings[mask]
            keywords = self.index.keywords[mask]
            scores = self.index.scores[mask]
            ad_units = self.index.ad_units[mask]
            ad_conv = self.index.ad_conv[mask]
            dataset_ids = self.index.dataset_ids[mask]
            source_formats = self.index.source_formats[mask]
        else:
            emb = self.index.embeddings
            keywords = self.index.keywords
            scores = self.index.scores
            ad_units = self.index.ad_units
            ad_conv = self.index.ad_conv
            dataset_ids = self.index.dataset_ids
            source_formats = self.index.source_formats

        # On some macOS numpy/Accelerate builds, matmul may emit spurious RuntimeWarnings
        # even when the numeric results are fine. Silence those to avoid confusing output.
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            sims = emb @ query_emb  # (N,)

        n = int(min(max(limit, 1), sims.shape[0]))
        # argpartition for speed, then exact sort
        idx = np.argpartition(-sims, n - 1)[:n]
        idx = idx[np.argsort(-sims[idx])]

        results: List[Dict] = []
        for i in idx.tolist():
            results.append(
                {
                    "keyword": str(keywords[i]),
                    "score": float(scores[i]),
                    "ad_units": float(ad_units[i]),
                    "ad_conv": float(ad_conv[i]),
                    "dataset_id": str(dataset_ids[i]) if dataset_ids[i] is not None else None,
                    "source_format": str(source_formats[i]) if source_formats[i] is not None else None,
                    "similarity": float(sims[i]),
                }
            )

        return results


if __name__ == "__main__":
    db = KeywordDB()

    print("\n--- Datasets ---")
    for ds in db.list_dataset_ids()[:20]:
        print(f"  - {ds}")

    print("\n--- Query Test ---")
    top = db.get_top_keywords("shalimar garbage bags medium 19 x 21 inches", limit=5)
    for i, kw in enumerate(top, 1):
        sim = kw.get("similarity", 0.0)
        print(f"  {i}. '{kw['keyword']}' | sim={sim:.3f} | score={kw['score']:.4f} | ds={kw.get('dataset_id')}")
