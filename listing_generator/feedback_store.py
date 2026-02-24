import os
import json
import chromadb
from typing import List, Dict, Any, Optional

# Assuming we run from agentic_strategy_2 root, the embedder is one level up from this file's usage, 
# but this file runs inside listing_generator module.
import sys
from pathlib import Path

# Provide access to embedder from root
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from embedder import encode_texts
except ImportError:
    # Fallback if run directly
    def encode_texts(texts):
        import numpy as np
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        emb = model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(emb, dtype=np.float32)

DB_PATH = os.path.join(ROOT_DIR, "listing_feedback_db")

class FeedbackStore:
    """Stores and retrieves historically successful listings using ChromaDB."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=self.db_path)
        self.collection = self.client.get_or_create_collection(
            name="listing_feedback",
            metadata={"hnsw:space": "cosine"}
        )

    def save_good_example(self, 
                          asin: str, 
                          category: str, 
                          title: str, 
                          bullets: List[str], 
                          search_terms: str, 
                          truth_data: Dict[str, Any]) -> None:
        """Save a highly-rated listing into the memory vault."""
        
        if not category:
            category = "general"

        # The semantic key is the core product identity (title + top features)
        semantic_text = f"Category: {category}. Product: {title}"
        
        # Embed the semantic text
        embedding = encode_texts([semantic_text])[0].tolist()
        
        # We store the full listing as a JSON string in the metadata
        listing_data = {
            "title": title,
            "bullets": bullets,
            "search_terms": search_terms,
            "truth": truth_data
        }
        
        metadata = {
            "category": category,
            "asin": asin,
            "listing_json": json.dumps(listing_data)
        }

        self.collection.upsert(
            ids=[asin],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[semantic_text]
        )
        print(f"   [MemoryVault] Stored ASIN {asin} as a good example for '{category}'.")

    def get_similar_examples(self, product_context: str, category: str, n: int = 2) -> List[Dict[str, Any]]:
        """Retrieve top N historically successful listings for a specific category."""
        
        if not category:
            category = "general"
            
        print(f"   [MemoryVault] Querying for similar successful '{category}' listings...")
        
        # Check if we have anything in this category first
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
                where={"category": category}  # CRITICAL: Hard-filter by category
            )
            
            examples = []
            if results and results["metadatas"] and len(results["metadatas"][0]) > 0:
                for meta in results["metadatas"][0]:
                    if "listing_json" in meta:
                        try:
                            examples.append(json.loads(meta["listing_json"]))
                        except Exception:
                            pass
                
                print(f"   [MemoryVault] Retrieved {len(examples)} examples.")
                return examples
            else:
                print("   [MemoryVault] No matching examples found for this category.")
                return []
                
        except Exception as e:
            print(f"   [MemoryVault] Query failed (possibly empty category): {e}")
            return []
