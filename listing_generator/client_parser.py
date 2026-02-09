"""
CLIENT DATA PARSER
==================
Reads client Excel files (lqs-GMR_AE.xlsx, lqs-Kakks_uk.xlsx, etc.)
and extracts product records with ASIN, title, images, country, category.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def _safe_str(value: Any) -> str:
    """Safely convert a value to string, handling NaN and None."""
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _find_column(columns: List[str], candidates: List[str]) -> Optional[str]:
    """Find a column name by matching against multiple candidate names (case-insensitive)."""
    col_lower_map = {c.lower().strip(): c for c in columns}
    for candidate in candidates:
        key = candidate.lower().strip()
        if key in col_lower_map:
            return col_lower_map[key]
        # Partial match
        for col_key, col_original in col_lower_map.items():
            if key in col_key or col_key in key:
                return col_original
    return None


def parse_client_excel(excel_path: str) -> List[Dict[str, Any]]:
    """
    Parse a client Excel file and return a list of product records.

    Each record contains:
        asin, title, country, la_cat (browse node), images (list of URLs/paths),
        bullet_points (list), description, usp, and raw_row (dict).
    """
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"Client Excel not found: {excel_path}")

    print(f"\n📊 Reading client Excel: {path.name}")

    # Try multiple header rows (some files have header at row 1, 2, or 3)
    df = None
    for header_row in [0, 1, 2, 3]:
        try:
            candidate = pd.read_excel(str(path), header=header_row)
            cols_lower = [str(c).lower().strip() for c in candidate.columns]
            # Must have at least one recognizable column
            if any(kw in col for col in cols_lower for kw in ['asin', 'title', 'product', 'sku']):
                df = candidate
                df.columns = df.columns.astype(str).str.strip()
                df = df.dropna(how='all')
                print(f"   Found {len(df)} rows (header at row {header_row + 1})")
                break
        except Exception:
            continue

    if df is None:
        raise ValueError(f"Could not parse Excel file: {excel_path}. No recognizable columns found.")

    columns = list(df.columns)

    # Map standard fields
    col_asin = _find_column(columns, ['asin', 'ASIN', 'sku', 'SKU', 'product_id', 'client_id'])
    col_title = _find_column(columns, ['title', 'Title', 'product title', 'product_title', 'name'])
    col_country = _find_column(columns, ['country', 'Country', 'marketplace', 'market', 'region'])
    col_category = _find_column(columns, [
        'la-cat', 'la_cat', 'browse node', 'browse_node', 'category',
        'Category', 'sub-category', 'subcategory', 'node',
    ])
    col_desc = _find_column(columns, ['description', 'Description', 'descrp', 'product description'])
    col_usp = _find_column(columns, ['usp', 'USP', 'more info', 'More info eg USP', 'more_info'])

    # Find image columns (img1, img2, ... OR image1, image2, ...)
    image_cols: List[str] = []
    for col in columns:
        cl = col.lower()
        if cl.startswith('img') or cl.startswith('image') or 'image' in cl:
            image_cols.append(col)

    # Find bullet point columns
    bp_cols: List[str] = []
    for col in columns:
        cl = col.lower()
        if cl.startswith('bp') or cl.startswith('bullet') or cl.startswith('kf') or 'key feature' in cl:
            bp_cols.append(col)

    print(f"   Columns mapped: ASIN={col_asin}, Title={col_title}, Country={col_country}")
    print(f"   Category={col_category}, Images={len(image_cols)} cols, Bullets={len(bp_cols)} cols")

    products: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        asin = _safe_str(row.get(col_asin, '')) if col_asin else f"PRODUCT_{idx}"
        title = _safe_str(row.get(col_title, '')) if col_title else ""
        country = _safe_str(row.get(col_country, '')) if col_country else "UNKNOWN"
        la_cat = _safe_str(row.get(col_category, '')) if col_category else ""
        description = _safe_str(row.get(col_desc, '')) if col_desc else ""
        usp = _safe_str(row.get(col_usp, '')) if col_usp else ""

        if not asin and not title:
            continue  # Skip completely empty rows

        # Collect images
        images: List[str] = []
        for ic in image_cols:
            img = _safe_str(row.get(ic, ''))
            if img:
                if img.startswith('//'):
                    img = 'https:' + img
                images.append(img)

        # Collect existing bullet points
        bullet_points: List[str] = []
        for bc in bp_cols:
            bp = _safe_str(row.get(bc, ''))
            if bp:
                bullet_points.append(bp)

        # Raw row as dict for any extra data
        raw_row: Dict[str, Any] = {}
        for col in columns:
            val = _safe_str(row.get(col, ''))
            if val:
                raw_row[col] = val

        products.append({
            'asin': asin,
            'title': title,
            'country': country.upper(),
            'la_cat': la_cat,
            'description': description,
            'usp': usp,
            'images': images,
            'bullet_points': bullet_points,
            'raw_row': raw_row,
            'row_index': idx,
        })

    print(f"   ✅ Parsed {len(products)} products")
    return products
