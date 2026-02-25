import os
import json
import chromadb
from typing import List, Dict, Any, Optional

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from embedder import encode_texts
except ImportError:
    def encode_texts(texts):
        import numpy as np
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        emb = model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(emb, dtype=np.float32)

DB_PATH = os.path.join(ROOT_DIR, "listing_feedback_db")


class FeedbackStore:
    """Stores and retrieves historically successful listings using ChromaDB.

    Improvement over v1:
    - Saves structured per-field patterns (title, bullets, search_terms)
      separately, so the LLM can get focused examples for each task.
    - Injects rejection signals when available ("avoid these patterns").
    - Each example is tagged with its category for strict filtering.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(
            name="listing_feedback",
            metadata={"hnsw:space": "cosine"}
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Save
    # ─────────────────────────────────────────────────────────────────────────

    def save_good_example(self,
                          asin: str,
                          category: str,
                          title: str,
                          bullets: List[str],
                          search_terms: str,
                          truth_data: Dict[str, Any],
                          ai_rules: Dict[str, str] = None) -> None:
        """Save an approved listing into the memory vault with structured patterns.

        Structured patterns extracted and stored:
          title_pattern    — length bucket + keyword position observations
          bullet_pattern   — avg bullet length + feature-benefit flag
          search_terms_len — char count of the search terms string
          ai_rules         — deep stylistic rules extracted by PatternExtractorAgent
        """
        if not category:
            category = "general"

        if ai_rules:
            print(f"   [MemoryVault] 🧠 Learned AI Rules: {ai_rules}")

        # Build structured pattern observations
        title_len = len(title)
        title_words = title.split()
        brand = truth_data.get("brand", "")
        starts_with_brand = title.lower().startswith(brand.lower()) if brand else False

        # Bullet patterns
        bullet_lengths = [len(b) for b in bullets] if bullets else [0]
        avg_bullet_len = sum(bullet_lengths) / max(len(bullet_lengths), 1)
        feature_benefit_bullets = sum(1 for b in bullets if ":" in b[:30]) if bullets else 0

        patterns = {
            "title_chars": title_len,
            "title_char_bucket": (
                "short (<100)" if title_len < 100
                else "medium (100-150)" if title_len < 150
                else "long (150+)"
            ),
            "title_starts_with_brand": starts_with_brand,
            "title_word_count": len(title_words),
            "bullet_count": len(bullets) if bullets else 0,
            "avg_bullet_len": round(avg_bullet_len),
            "feature_benefit_bullets": feature_benefit_bullets,
            "search_terms_chars": len(search_terms) if search_terms else 0,
        }

        # Embed AI-extracted strategic rules into the saved pattern data
        if ai_rules:
            if ai_rules.get("title_rule"):
                patterns["ai_title_rule"] = ai_rules["title_rule"]
            if ai_rules.get("bullet_rule"):
                patterns["ai_bullet_rule"] = ai_rules["bullet_rule"]

        # The semantic key for retrieval: product identity
        semantic_text = f"Category: {category}. Product: {title}"
        embedding = encode_texts([semantic_text])[0].tolist()

        listing_data = {
            "title": title,
            "bullets": bullets,
            "search_terms": search_terms,
            "truth": truth_data,
            "patterns": patterns,    # ← NEW: structured per-field analysis
        }

        metadata = {
            "category": category,
            "asin": asin,
            "listing_json": json.dumps(listing_data),
            # Queryable fields for future filtering
            "title_chars": title_len,
            "avg_bullet_len": round(avg_bullet_len),
            "feature_benefit_bullets": feature_benefit_bullets,
        }

        self.collection.upsert(
            ids=[asin],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[semantic_text]
        )
        print(f"   [MemoryVault] ✅ Stored ASIN {asin} for '{category}' | "
              f"title={title_len}ch | bullets={len(bullets)} | "
              f"fb_bullets={feature_benefit_bullets} | st={len(search_terms)}ch")

    # ─────────────────────────────────────────────────────────────────────────
    # Retrieve
    # ─────────────────────────────────────────────────────────────────────────

    def get_similar_examples(self, product_context: str, category: str, n: int = 2) -> List[Dict[str, Any]]:
        """Retrieve top N historically successful listings for a category.

        Returns structured examples ready for LLM prompt injection, including:
        - The approved title, bullets, and search terms
        - Pattern observations so the model understands WHY they were good
        """
        if not category:
            category = "general"

        print(f"   [MemoryVault] Querying for similar '{category}' listings...")

        try:
            count = self.collection.count()
            if count == 0:
                print("   [MemoryVault] Vault is empty. No examples to inject.")
                return []
        except Exception:
            return []

        embedding = encode_texts([product_context])[0].tolist()

        try:
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n,
                where={"category": category}   # CRITICAL: hard-filter by category
            )

            examples = []
            if results and results["metadatas"] and len(results["metadatas"][0]) > 0:
                for meta in results["metadatas"][0]:
                    if "listing_json" in meta:
                        try:
                            data = json.loads(meta["listing_json"])
                            patterns = data.get("patterns", {})

                            # Build a structured prompt-ready example
                            examples.append({
                                "title": data.get("title", ""),
                                "bullets": data.get("bullets", []),
                                "search_terms": data.get("search_terms", ""),
                                # Structured pattern notes injected into the prompt
                                "pattern_notes": {
                                    "title_length": f"{patterns.get('title_chars', '?')} chars ({patterns.get('title_char_bucket', '?')})",
                                    "bullet_count": patterns.get("bullet_count", "?"),
                                    "feature_benefit_bullets": patterns.get("feature_benefit_bullets", 0),
                                    "search_terms_chars": patterns.get("search_terms_chars", "?"),
                                    "avg_bullet_length": f"{patterns.get('avg_bullet_len', '?')} chars",
                                    "title_starts_with_brand": patterns.get("title_starts_with_brand", False),
                                    "strategic_title_rule": patterns.get("ai_title_rule", ""),
                                    "strategic_bullet_rule": patterns.get("ai_bullet_rule", ""),
                                },
                            })
                        except Exception:
                            pass

            if examples:
                print(f"   [MemoryVault] Retrieved {len(examples)} structured examples.")
            else:
                print("   [MemoryVault] No matching examples found for this category.")
            return examples

        except Exception as e:
            print(f"   [MemoryVault] Query failed (possibly empty category): {e}")
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Utilities
    # ─────────────────────────────────────────────────────────────────────────

    def count(self) -> int:
        """Return total number of examples stored."""
        try:
            return self.collection.count()
        except Exception:
            return 0

    def clear_category(self, category: str) -> int:
        """Delete all examples for a specific category. Returns count deleted."""
        try:
            results = self.collection.get(where={"category": category})
            ids = results.get("ids", [])
            if ids:
                self.collection.delete(ids=ids)
                print(f"   [MemoryVault] Deleted {len(ids)} examples for '{category}'.")
            return len(ids)
        except Exception as e:
            print(f"   [MemoryVault] clear_category failed: {e}")
            return 0
