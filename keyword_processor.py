"""
STRATEGY 2: KEYWORD PROCESSOR
==============================
Loads, filters, and processes keywords from the database.
Applies truth constraints and strips conflicting attributes.
"""

import pandas as pd
import os
import re
from typing import List, Dict, Tuple
from token_types import BANNED_BRANDS, SIZES, COLORS


class KeywordProcessor:
    """
    Processes keywords from Excel/CSV (used mainly for truth-safe cleanup).
    Applies filtering, scoring, and truth-constrained stripping.
    """
    
    def __init__(self, keywords_path: str = None):
        if keywords_path is None:
            keywords_path = os.path.join(os.path.dirname(__file__), 'data (12).xlsx')

        self.keywords_path = keywords_path
        self.keywords = self._load_keywords(keywords_path)
        print(f"   [KeywordProcessor] Loaded {len(self.keywords)} keywords")
    
    def _load_keywords(self, keywords_path: str) -> pd.DataFrame:
        """Load keywords from Excel (AdUnits/AdConv) or KeywordResearch CSV (rank-based)."""
        try:
            lower_path = keywords_path.lower()

            if lower_path.endswith('.csv'):
                # KeywordResearch CSVs can be very large (100MB+). They are typically rank-sorted,
                # so reading the top rows is enough for optimization.
                df = pd.read_csv(keywords_path, nrows=20000)

                # Normalize column names we expect
                if 'Keyword' not in df.columns:
                    raise ValueError(f"CSV missing 'Keyword' column. Found: {df.columns.tolist()}")

                # Score from ranks (lower rank => higher score)
                df['score'] = df.apply(self._score_keywordresearch_row, axis=1)
                df = df.sort_values('score', ascending=False).reset_index(drop=True)
                return df

            # Default: Excel
            df = pd.read_excel(keywords_path)

            # Calculate composite score: volume × (1 + conversion)
            if 'AdUnits' in df.columns and 'AdConv' in df.columns:
                df['score'] = df['AdUnits'] * (1 + df['AdConv'])
            else:
                # Fallback if schema differs
                df['score'] = 0.0

            df = df.sort_values('score', ascending=False).reset_index(drop=True)
            return df
        except Exception as e:
            print(f"   [KeywordProcessor] Error loading keywords: {e}")
            return pd.DataFrame()

    def _score_keywordresearch_row(self, row: pd.Series) -> float:
        """Compute a stable score for Amazon KeywordResearch CSV rows."""
        # Score from rank columns (lower rank is better)
        # NOTE: For agentic_strategy_2 we only use Clicks + Search Volume ranks.
        weights = {
            'Clicks Rank': 0.30,
            'Search Volume Rank': 0.70,
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
    
    def get_top_keywords(self, limit: int = 20) -> List[Dict]:
        """Get top keywords by score."""
        result = []

        for _, row in self.keywords.head(limit).iterrows():
            if 'searchTerm' in row.index:
                term = str(row['searchTerm'])
                ad_units = float(row['AdUnits']) if 'AdUnits' in row.index and pd.notna(row['AdUnits']) else 0.0
                ad_conv = float(row['AdConv']) if 'AdConv' in row.index and pd.notna(row['AdConv']) else 0.0
            else:
                term = str(row['Keyword'])
                ad_units = 0.0
                ad_conv = 0.0

            result.append({
                'term': term,
                'ad_units': ad_units,
                'ad_conv': ad_conv,
                'score': float(row['score'])
            })
        
        return result
    
    def filter_keywords(self, truth: Dict, banned_brands: List[str] = None) -> List[Dict]:
        """
        Filter keywords based on truth and policy rules.
        
        Args:
            truth: Product truth attributes
            banned_brands: List of competitor brand names to filter out
        
        Returns:
            Filtered list of keywords
        """
        if banned_brands is None:
            banned_brands = BANNED_BRANDS
        
        filtered = []
        
        for _, row in self.keywords.iterrows():
            raw_term = str(row['searchTerm']) if 'searchTerm' in row.index else str(row['Keyword'])
            term = raw_term.lower()
            
            # Skip if contains competitor brand
            if any(brand.lower() in term for brand in banned_brands):
                continue
            
            # Strip conflicting attributes and get cleaned term
            cleaned_term = self.strip_conflicting_attributes(term, truth)
            
            if cleaned_term and len(cleaned_term) > 2:
                filtered.append({
                    'original_term': raw_term,
                    'cleaned_term': cleaned_term,
                    'ad_units': float(row['AdUnits']) if 'AdUnits' in row.index and pd.notna(row.get('AdUnits')) else 0.0,
                    'ad_conv': float(row['AdConv']) if 'AdConv' in row.index and pd.notna(row.get('AdConv')) else 0.0,
                    'score': float(row['score'])
                })
        
        # Sort by score
        filtered.sort(key=lambda x: x['score'], reverse=True)
        
        return filtered
    
    def strip_conflicting_attributes(self, keyword: str, truth: Dict) -> str:
        """
        Strip attribute values from keyword that conflict with truth.
        
        Example:
            keyword: "garbage bag medium black"
            truth: {size: "Large", color: "White"}
            result: "garbage bag" (stripped "medium" and "black")
        """
        keyword_lower = keyword.lower()
        words_to_remove = set()
        
        # Check SIZE conflict
        if truth.get('size'):
            truth_size = truth['size'].lower()
            for size in SIZES:
                if size in keyword_lower and size != truth_size:
                    words_to_remove.add(size)
        
        # Check COLOR conflict
        if truth.get('color'):
            truth_color = truth['color'].lower()
            for color in COLORS:
                if color in keyword_lower and color != truth_color:
                    words_to_remove.add(color)
        
        # Remove conflicting words
        if words_to_remove:
            result_words = []
            for word in keyword.split():
                if word.lower() not in words_to_remove:
                    result_words.append(word)
            return ' '.join(result_words).strip()
        
        return keyword
    
    def extract_template(self, keywords: List[Dict]) -> str:
        """
        Extract dominant template from top keywords.
        E.g., "PRODUCT + SIZE + COLOR" pattern
        """
        # Count attribute patterns
        patterns = {}
        
        for kw in keywords[:20]:
            term = kw.get('cleaned_term', kw.get('term', ''))
            pattern = self._detect_pattern(term)
            
            if pattern:
                patterns[pattern] = patterns.get(pattern, 0) + kw['score']
        
        # Return highest weighted pattern
        if patterns:
            return max(patterns.items(), key=lambda x: x[1])[0]
        
        return "PRODUCT"
    
    def _detect_pattern(self, term: str) -> str:
        """Detect the attribute pattern in a keyword."""
        term_lower = term.lower()
        components = []
        
        # Check for product words
        product_words = ['garbage', 'dustbin', 'trash', 'bag', 'bags', 'liner']
        if any(pw in term_lower for pw in product_words):
            components.append('PRODUCT')
        
        # Check for size
        if any(size in term_lower for size in SIZES):
            components.append('SIZE')
        
        # Check for color
        if any(color in term_lower for color in COLORS):
            components.append('COLOR')
        
        if components:
            return ' + '.join(components)
        
        return None
    
    def get_keyword_score(self, keyword: str) -> float:
        """Get the score for a specific keyword."""
        keyword_lower = keyword.lower().strip()
        
        for _, row in self.keywords.iterrows():
            if str(row['searchTerm']).lower().strip() == keyword_lower:
                return float(row['score'])
        
        return 0.0
    
    def find_best_synonym(self, concept: str, truth: Dict) -> Tuple[str, float]:
        """
        Find the highest-scoring keyword that represents a concept.
        
        Args:
            concept: The concept to find (e.g., "garbage bag")
            truth: Truth attributes for validation
        
        Returns:
            (best_keyword, score) or (None, 0) if not found
        """
        best_term = None
        best_score = 0
        
        for _, row in self.keywords.iterrows():
            term = str(row['searchTerm']).lower()
            
            # Check if term contains the concept
            if concept.lower() in term:
                # Validate against truth
                cleaned = self.strip_conflicting_attributes(term, truth)
                if cleaned and len(cleaned) > 2:
                    score = float(row['score'])
                    if score > best_score:
                        best_score = score
                        best_term = cleaned
        
        return best_term, best_score


# Singleton factory
_processor_instance = None

def get_keyword_processor(keywords_path: str = None) -> KeywordProcessor:
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = KeywordProcessor(keywords_path)
    return _processor_instance
