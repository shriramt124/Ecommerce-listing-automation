#!/usr/bin/env python3
"""Quick audit script to analyze keyword DB and pipeline data."""
import numpy as np
import sys
sys.path.insert(0, '.')

from keyword_db import KeywordDB
db = KeywordDB()

# Test queries based on existing bullets
queries = [
    "neoprene dumbbells for women",
    "1kg dumbbells pair",
    "hand weights for home gym",
    "hexagonal dumbbells",
    "cast iron neoprene dumbbells",
    "dumbbells for fitness training",
    "anti slip dumbbells",
    "dumbbells set for home",
    "gym weights for women",
    "exercise weights",
]

print("=== KEYWORD SEARCH BY SMART QUERIES ===\n")
for q in queries:
    results = db.get_top_keywords(q, limit=3)
    top = results[0] if results else None
    if top:
        print(f'  "{q}" -> "{top["keyword"]}" (vol={top.get("score",0)}, sim={top.get("similarity",0):.3f})')

# Top volume keywords in DB
data = np.load('st_keywords_index/keywords_index.npz', allow_pickle=True)
keywords = data['keywords']
scores = data['scores']
seen = {}
for k, s in zip(keywords, scores):
    k_lower = str(k).lower()
    if k_lower not in seen or float(s) > seen[k_lower][1]:
        seen[k_lower] = (str(k), float(s))

top_volume = sorted(seen.values(), key=lambda x: x[1], reverse=True)[:20]
print(f'\n=== TOP 20 HIGHEST VOLUME KEYWORDS IN DB ===')
for i, (kw, vol) in enumerate(top_volume, 1):
    print(f'  {i}. "{kw}" (volume={vol})')

# Test what current _stage_keywords would produce for product 1
title = "Kakss Neoprene Dumbbells 1+1=2 KG Pack of 1 KG Each, Anti-Slip Coated Hand Weights for Home Gym & Fitness Training -Pink"
title_lower = title.lower()

all_queries = set()
all_queries.add(title[:80])
all_queries.add("Dumbbells")
all_queries.add("KAKSS Dumbbells")
# From existing bullets
all_queries.add("Dumbbells cast iron neoprene coating")
all_queries.add("Dumbbells hexagonal shape")
all_queries.add("hand weights exercise resistance training")

print(f'\n=== SIMULATED KEYWORD RETRIEVAL ({len(all_queries)} queries) ===')
merged = {}
for q in all_queries:
    results = db.get_top_keywords(str(q), limit=25)
    for r in results:
        kw = str(r.get("keyword", "")).strip().lower()
        if not kw:
            continue
        if kw not in merged or float(r.get("score", 0)) > float(merged[kw].get("score", 0)):
            merged[kw] = r

# Separate NEW vs existing
new_kw = []
for kw_data in merged.values():
    kw_text = kw_data.get("keyword", "").lower()
    if kw_text in title_lower:
        continue
    kw_words = set(kw_text.split())
    title_words = set(title_lower.split())
    overlap = len(kw_words & title_words) / len(kw_words) if kw_words else 0
    if overlap <= 0.7:
        new_kw.append(kw_data)

new_sorted = sorted(new_kw, key=lambda x: float(x.get("score", 0)), reverse=True)
print(f'\nTop NEW keywords (not in title) by volume:')
for i, kw in enumerate(new_sorted[:15], 1):
    print(f'  {i}. "{kw["keyword"]}" (vol={kw.get("score",0)}, sim={kw.get("similarity",0):.3f})')
