"""
BROWSE NODE KEYWORD MAPPER
===========================
Maps products to their keyword research CSV files from browse node folders,
and ingests those keywords into the vector database.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingest_keywords import ingest_keywords


def discover_keyword_files(browse_node_dir: str) -> List[str]:
    """
    Find all keyword research files (CSV + XLSX) in a browse node directory.
    Supports nested folder structures.
    """
    folder = Path(browse_node_dir)
    if not folder.exists():
        print(f"   ⚠️  Browse node directory not found: {browse_node_dir}")
        return []

    files = sorted(
        str(p) for p in folder.rglob('*')
        if p.is_file() and p.suffix.lower() in ('.csv', '.xlsx', '.xls')
    )
    print(f"   📂 Found {len(files)} keyword files in {folder.name}/")
    for f in files[:10]:
        print(f"      - {os.path.basename(f)}")
    if len(files) > 10:
        print(f"      ... and {len(files) - 10} more")

    return files


def extract_category_from_filename(file_path: str) -> str:
    """
    Extract category info from a keyword file's filename.
    Examples:
      KeywordResearch_Home_Home Storage_Waste_30_22-12-2025.csv
        → "Home > Home Storage > Waste"
      GB_AMAZON_magnet__dumbbell set 2kg_2025-12-24.xlsx
        → "dumbbell set 2kg"
    """
    basename = os.path.basename(file_path)
    name = os.path.splitext(basename)[0]

    # Handle Magnet/Browse Node format: GB_AMAZON_magnet__<keyword>_<date>
    if 'magnet__' in name.lower():
        # Extract the keyword part after 'magnet__'
        parts = name.split('magnet__', 1)
        if len(parts) > 1:
            keyword_part = parts[1]
            # Remove trailing date pattern like _2025-12-24
            import re
            keyword_part = re.sub(r'_\d{4}-\d{2}-\d{2}$', '', keyword_part)
            return keyword_part.strip()

    # Remove "KeywordResearch_" prefix
    if name.lower().startswith('keywordresearch_'):
        name = name[len('KeywordResearch_'):]

    # Split by underscore and filter out date/number parts
    parts = name.split('_')
    category_parts = []
    for part in parts:
        # Skip pure numbers, dates, and short numeric strings
        if part.isdigit():
            continue
        if len(part) <= 3 and part.isdigit():
            continue
        # Skip date-like patterns (22-12-2025, 18-56-04)
        if '-' in part and all(seg.isdigit() for seg in part.split('-')):
            continue
        category_parts.append(part.strip())

    return ' > '.join(category_parts) if category_parts else basename


def match_product_to_category(product: Dict[str, Any], csv_categories: Dict[str, str]) -> Optional[str]:
    """
    Try to match a product to a keyword CSV based on its la_cat or title.
    Returns the best matching CSV path, or None.
    """
    la_cat = str(product.get('la_cat', '') or '').lower()
    title = str(product.get('title', '') or '').lower()

    best_match = None
    best_score = 0

    for csv_path, category in csv_categories.items():
        cat_lower = category.lower()
        cat_words = set(cat_lower.replace('>', ' ').split())

        score = 0
        # Check overlap with la_cat
        if la_cat:
            la_words = set(la_cat.replace('>', ' ').replace(',', ' ').split())
            overlap = cat_words & la_words
            score += len(overlap) * 2

        # Check overlap with title
        title_words = set(title.split())
        overlap = cat_words & title_words
        score += len(overlap)

        if score > best_score:
            best_score = score
            best_match = csv_path

    return best_match


def ingest_browse_node_keywords(browse_node_dir: str, reset: bool = False) -> bool:
    """
    Ingest all keyword files (CSV + XLSX) from a browse node directory into the vector DB.
    """
    print(f"\n{'='*60}")
    print(f"  INGESTING BROWSE NODE KEYWORDS")
    print(f"{'='*60}")

    keyword_files = discover_keyword_files(browse_node_dir)
    if not keyword_files:
        print("   ❌ No keyword files found")
        return False

    return ingest_keywords(keyword_files, reset=reset)


def build_category_map(browse_node_dir: str) -> Dict[str, str]:
    """
    Build a mapping of file path → category string for all keyword files.
    """
    keyword_files = discover_keyword_files(browse_node_dir)
    category_map: Dict[str, str] = {}

    for file_path in keyword_files:
        category = extract_category_from_filename(file_path)
        category_map[file_path] = category
        print(f"   📋 {os.path.basename(file_path)} → {category}")

    return category_map
