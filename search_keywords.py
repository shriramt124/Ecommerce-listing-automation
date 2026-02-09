#!/usr/bin/env python3
"""
Quick keyword search tool - retrieves top keywords from vector DB
Usage: python search_keywords.py "your search query"
"""

import sys
from keyword_db import KeywordDB


def main():
    if len(sys.argv) < 2:
        print("Usage: python search_keywords.py 'your search query'")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    print(f"Searching for: {query}\n")
    
    db = KeywordDB()
    results = db.get_top_keywords(query, limit=50)
    
    if not results:
        print("No results found.")
        return
    
    print(f"Top {len(results)} keywords:\n")
    print(f"{'#':<4} {'Keyword':<40} {'Volume':<10} {'Similarity':<10}")
    print("-" * 70)
    
    for i, kw in enumerate(results, 1):
        keyword = kw.get('keyword', '')
        volume = kw.get('score', 0)
        similarity = kw.get('similarity', 0)
        print(f"{i:<4} {keyword:<40} {volume:<10.0f} {similarity:<10.3f}")


if __name__ == "__main__":
    main()
