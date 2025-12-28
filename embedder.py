"""Shared SentenceTransformers embedder utilities.

We keep model loading in one place so:
- Strategy 2 keyword search and semantic grouping share the same model
- The model loads once per process

Env vars:
- ADKRUX_EMBED_MODEL: SentenceTransformer model name (default: all-MiniLM-L6-v2)
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Sequence

import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_EMBED_MODEL = os.getenv("ADKRUX_EMBED_MODEL", "all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformer:
    return SentenceTransformer(DEFAULT_EMBED_MODEL)


def encode_texts(texts: Sequence[str]) -> np.ndarray:
    """Encode texts into L2-normalized float32 embeddings."""
    model = get_embedder()
    # normalize_embeddings avoids manual cosine norm and makes dot() = cosine.
    emb = model.encode(
        list(texts),
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(emb, dtype=np.float32)
