"""STRATEGY 2: KEYWORD INGESTION (SentenceTransformers index)

This script builds/updates a lightweight local embedding index (npz) used for
similarity search in Strategy 2.

Replaces the previous ChromaDB vector database.

Index output:
- strategy_2_keyword_optimizer/st_keywords_index/keywords_index.npz

Supported inputs:
- Excel exports (AdUnits/AdConv/searchTerm...)
- Amazon KeywordResearch CSV exports (rank-based columns)
"""

import os
import shutil
import sys
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import pandas as pd

import numpy as np

from embedder import encode_texts

# Configuration
DEFAULT_KEYWORDS_PATH = os.path.join(os.path.dirname(__file__), 'data (12).xlsx')
INDEX_DIR = os.path.join(os.path.dirname(__file__), 'st_keywords_index')
INDEX_PATH = os.path.join(INDEX_DIR, 'keywords_index.npz')
OLD_CHROMA_PATH = os.path.join(os.path.dirname(__file__), 'chroma_keywords_db')


def _dataset_id_from_path(path: str) -> str:
    base = os.path.basename(path)
    # keep it stable and filesystem-safe
    return base.replace(' ', '_').replace('/', '_')


def _score_keywordresearch_row(row: pd.Series) -> float:
    # Same logic as KeywordProcessor: rank-based score
    weights = {
        'Clicks Rank': 0.50,
        'Search Volume Rank': 0.50,
    }
    score = 0.0
    for col, w in weights.items():
        if col in row.index and pd.notna(row[col]):
            try:
                rank = float(row[col])
                if rank > 0:
                    score += w * (1.0 / rank)
            except Exception:
                pass
    return float(score)


def _iter_records_from_excel(path: str) -> Iterator[Tuple[str, Dict]]:
    df = pd.read_excel(path)
    for _, row in df.iterrows():
        keyword = str(row.get('searchTerm', '')).strip()
        if not keyword:
            continue
        ad_units = float(row['AdUnits']) if pd.notna(row.get('AdUnits')) else 0.0
        ad_conv = float(row['AdConv']) if pd.notna(row.get('AdConv')) else 0.0
        asin = str(row['ASIN']).strip() if pd.notna(row.get('ASIN')) else ""
        score = ad_units * (1 + ad_conv)
        yield keyword, {
            'keyword': keyword,
            'score': float(score),
            'ad_units': float(ad_units),
            'ad_conv': float(ad_conv),
            'asin': asin,
            'source_format': 'excel',
        }


def _iter_records_from_keywordresearch_csv(path: str, chunksize: int = 5000) -> Iterator[Tuple[str, Dict]]:
    # Chunked to support very large CSVs (100MB+)
    for chunk in pd.read_csv(path, chunksize=chunksize):
        if 'Keyword' not in chunk.columns:
            raise ValueError(f"CSV missing 'Keyword' column. Found: {chunk.columns.tolist()}")
        chunk = chunk.copy()
        chunk['score'] = chunk.apply(_score_keywordresearch_row, axis=1)
        for _, row in chunk.iterrows():
            keyword = str(row.get('Keyword', '')).strip()
            if not keyword:
                continue
            meta = {
                'keyword': keyword,
                'score': float(row.get('score', 0.0) or 0.0),
                'source_format': 'keywordresearch_csv',
            }
            # Keep a few useful fields if present (all optional)
            for col in [
                'Search Volume Rank', 'Clicks Rank', 'Add to Carts Rank', 'Purchases Rank', 'Sales Rank',
                'Suggested bid range', 'Top sub-category',
                'Organic Coverage Score', 'Advertising Coverage Score'
            ]:
                if col in row.index and pd.notna(row[col]):
                    val = row[col]
                    # ensure JSON-serializable primitives
                    if isinstance(val, (int, float, str, bool)):
                        meta[col] = val
                    else:
                        meta[col] = str(val)
            yield keyword, meta


def _iter_records(path: str) -> Iterator[Tuple[str, Dict]]:
    lower_path = path.lower()
    if lower_path.endswith('.csv'):
        return _iter_records_from_keywordresearch_csv(path)
    return _iter_records_from_excel(path)


def ingest_keywords(paths: List[str], reset: bool = False):
    """Load keywords from one or more files and store in the ST embedding index."""
    print("=" * 60)
    print("  STRATEGY 2: KEYWORD INGESTION (SentenceTransformers)")
    print("=" * 60)
    
    # Basic validation of inputs
    valid_paths = []
    for p in paths:
        if not p:
            continue
        if not os.path.isabs(p):
            # Allow running from repo root with workspace-relative paths like:
            #   agentic_strategy_2/KeywordResearch_....csv
            # If that doesn't exist, fall back to resolving relative to this script.
            if os.path.exists(p):
                p = os.path.abspath(p)
            else:
                p = os.path.join(os.path.dirname(__file__), p)
        if not os.path.exists(p):
            print(f"      -> Missing file: {p}")
            continue
        valid_paths.append(p)
    if not valid_paths:
        print("      -> No valid input files.")
        return False
    
    # Reset handling
    if reset:
        if os.path.exists(INDEX_DIR):
            shutil.rmtree(INDEX_DIR, ignore_errors=True)
            print(f"      -> Deleted existing ST index dir: {INDEX_DIR}")

        # User requested deleting the previous vector DB; do it on reset.
        if os.path.exists(OLD_CHROMA_PATH):
            shutil.rmtree(OLD_CHROMA_PATH, ignore_errors=True)
            print(f"      -> Deleted old ChromaDB dir: {OLD_CHROMA_PATH}")

    os.makedirs(INDEX_DIR, exist_ok=True)

    print(f"\n[1/3] Loading existing index (if any): {INDEX_PATH}")

    existing_keys = set()
    keywords: List[str] = []
    embeddings: List[np.ndarray] = []
    scores: List[float] = []
    ad_units: List[float] = []
    ad_conv: List[float] = []
    dataset_ids: List[str] = []
    source_formats: List[str] = []

    if os.path.exists(INDEX_PATH):
        data = np.load(INDEX_PATH, allow_pickle=False)
        keywords = [str(x) for x in data["keywords"].tolist()]
        scores = [float(x) for x in data["scores"].tolist()]
        ad_units = [float(x) for x in data["ad_units"].tolist()]
        ad_conv = [float(x) for x in data["ad_conv"].tolist()]
        dataset_ids = [str(x) for x in data["dataset_ids"].tolist()]
        source_formats = [str(x) for x in data["source_formats"].tolist()]
        embeddings = [np.asarray(x, dtype=np.float32) for x in data["embeddings"]]
        existing_keys = {f"{ds}::{kw.strip().lower()}" for kw, ds in zip(keywords, dataset_ids)}
        print(f"      -> Loaded existing index with {len(keywords)} keywords")
    else:
        print("      -> No existing index found")

    print(f"\n[2/3] Ingesting keywords and computing embeddings...")

    total_added = 0
    for input_path in valid_paths:
        dataset_id = _dataset_id_from_path(input_path)
        print(f"\n   -> Ingesting dataset: {dataset_id}")

        # Batch embed for speed
        batch_texts: List[str] = []
        batch_metas: List[Dict] = []

        def flush_embed_batch():
            nonlocal total_added, batch_texts, batch_metas
            if not batch_texts:
                return

            batch_emb = encode_texts(batch_texts)  # normalized
            for text, emb, meta in zip(batch_texts, batch_emb, batch_metas):
                key = f"{meta['dataset_id']}::{text.strip().lower()}"
                if key in existing_keys:
                    continue

                keywords.append(text)
                embeddings.append(np.asarray(emb, dtype=np.float32))
                scores.append(float(meta.get('score', 0.0) or 0.0))
                ad_units.append(float(meta.get('ad_units', 0.0) or 0.0))
                ad_conv.append(float(meta.get('ad_conv', 0.0) or 0.0))
                dataset_ids.append(str(meta.get('dataset_id') or ''))
                source_formats.append(str(meta.get('source_format') or ''))
                existing_keys.add(key)
                total_added += 1

            batch_texts, batch_metas = [], []

        for keyword, meta in _iter_records(input_path):
            meta = dict(meta)
            meta['dataset_id'] = dataset_id
            meta['source_file'] = os.path.basename(input_path)

            kw = str(keyword).strip()
            if not kw:
                continue

            # Defer dedupe check to flush so we can batch-embed efficiently
            batch_texts.append(kw)
            batch_metas.append(meta)

            if len(batch_texts) >= 256:
                flush_embed_batch()

        flush_embed_batch()
    
    print(f"\n[3/3] Writing index to disk...")

    # Stack embeddings into a matrix
    if embeddings:
        emb_matrix = np.vstack(embeddings).astype(np.float32)
    else:
        emb_matrix = np.zeros((0, 384), dtype=np.float32)

    np.savez_compressed(
        INDEX_PATH,
        embeddings=emb_matrix,
        keywords=np.asarray(keywords, dtype=str),
        scores=np.asarray(scores, dtype=np.float32),
        ad_units=np.asarray(ad_units, dtype=np.float32),
        ad_conv=np.asarray(ad_conv, dtype=np.float32),
        dataset_ids=np.asarray(dataset_ids, dtype=str),
        source_formats=np.asarray(source_formats, dtype=str),
    )

    print(f"\n" + "=" * 60)
    print(f"  SUCCESS: Added {total_added} keywords to ST index")
    print(f"  Index path: {INDEX_PATH}")
    print("=" * 60)
    
    return True


def test_query():
    """Test query to verify ingestion."""
    print("\n--- Testing Query ---")
    from keyword_db import KeywordDB

    db = KeywordDB()
    test_q = "garbage bags medium black"
    results = db.get_top_keywords(test_q, limit=5)
    print(f"Query: '{test_q}'")
    print("Top 5 matching keywords:")
    for i, r in enumerate(results, 1):
        print(
            f"  {i}. '{r['keyword']}' | sim={r.get('similarity', 0.0):.3f} | score={float(r.get('score', 0.0) or 0.0):.4f} | ds={r.get('dataset_id')}"
        )
    return results


if __name__ == "__main__":
    args = sys.argv[1:]
    reset = False
    if '--reset' in args:
        reset = True

    # Remaining args are treated as input file paths
    paths = [a for a in args if not a.startswith('--')]
    if not paths:
        paths = [DEFAULT_KEYWORDS_PATH]

    ok = ingest_keywords(paths, reset=reset)
    if ok:
        test_query()
