"""
STRATEGY 2: PARSER (V2 - CONCEPT-BASED)
========================================
Parses Amazon titles into typed CONCEPTS (not just tokens).
Handles parentheses content as single units.
Recognizes SCENT, QUALITY_MARKER, FRAGRANCE separately.
"""

import re
from typing import List, Dict, Optional, Tuple
from token_types  import (
    Token, TokenType, TokenOrigin, ConceptTier,
    SIZES, COLORS, BANNED_WORDS, SCENT_WORDS, QUALITY_MARKER_WORDS, FRAGRANCE_WORDS,
    MATERIALS, POSITIONS, TECH_SPECS
)
from normalizer import normalizer


class TitleParser:
    """
    V2 Parser: Extracts CONCEPTS from Amazon titles.
    
    Key improvements:
    - Recognizes parentheses content as single concept
    - Detects SCENT vs FRAGRANCE separately
    - Detects QUALITY_MARKER (Premium, Deluxe)
    - Understands that "(Lavender Fragrance)" is FRAGRANCE, not separate tokens
    """
    
    def __init__(self):
        # Precompile patterns
        self.dimension_pattern = re.compile(
            r'(\d+)\s*[xX×]\s*(\d+)\s*(Inches?|cm|Inch)?',
            re.IGNORECASE
        )
        self.count_pattern = re.compile(
            r'(\d+)\s*(Bags?|Pcs?|Pieces?|Rolls?|Pack|Count|Units?)',
            re.IGNORECASE
        )
        self.count_detail_pattern = re.compile(
            r'\((\d+)\s*[xX×]?\s*(\d+)?\s*(Bags?|Rolls?|Pcs?)?\)',
            re.IGNORECASE
        )
        self.capacity_pattern = re.compile(
            r'(\d+)\s*(L|Litres?|Liters?|ml|ML|Gallon)',
            re.IGNORECASE
        )
        self.fragrance_pattern = re.compile(
            r'(' + '|'.join(FRAGRANCE_WORDS) + r')\s*(Fragrance|Scent)?',
            re.IGNORECASE
        )
        self.parentheses_pattern = re.compile(r'\([^)]+\)')
    
    def parse_title(self, title: str, truth: Dict) -> List[Token]:
        """
        Parse a title string into a list of CONCEPT tokens.
        
        V2 Key: Handle parentheses content FIRST, then parse remaining.
        """
        tokens = []
        
        # STEP 1: Extract and process parentheses content first
        paren_concepts, title_without_parens = self._extract_parentheses_concepts(title, truth)
        tokens.extend(paren_concepts)
        
        # STEP 2: Split remaining title by separators
        segments = self._split_by_separators(title_without_parens)
        
        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue
            
            # Skip if it's just a separator
            if segment in ['|', '-', '/']:
                tokens.append(Token(
                    text=segment,
                    token_type=TokenType.SEPARATOR,
                    locked=False,
                    value=0
                ))
                continue
            
            # Classify the segment into concepts
            segment_tokens = self._classify_segment(segment, truth)
            tokens.extend(segment_tokens)
        
        # STEP 3: Mark truth-critical tokens as locked
        self._apply_truth_locks(tokens, truth)
        
        return tokens
    
    def _extract_parentheses_concepts(self, title: str, truth: Dict) -> Tuple[List[Token], str]:
        """
        Extract content in parentheses as single concepts.
        E.g., "(Lavender Fragrance)" becomes one FRAGRANCE concept.
        """
        tokens = []
        title_modified = title
        
        # Find all parentheses content
        matches = self.parentheses_pattern.findall(title)
        
        for match in matches:
            content = match.strip('()')
            content_lower = content.lower()
            
            # Check if it's a FRAGRANCE (e.g., "Lavender Fragrance")
            for fragrance in FRAGRANCE_WORDS:
                if fragrance in content_lower:
                    tokens.append(Token(
                        text=content,  # Strip parentheses
                        token_type=TokenType.FRAGRANCE,
                        locked=False,
                        value=40,
                        tier=ConceptTier.TIER_2
                    ))
                    # Remove from title to avoid double-processing
                    title_modified = title_modified.replace(match, '')
                    break
            else:
                # Check if it's a COLOR
                for color in COLORS:
                    if color in content_lower:
                        tokens.append(Token(
                            text=content,  # Strip parentheses
                            token_type=TokenType.COLOR,
                            locked=True,
                            value=70,
                            tier=ConceptTier.TIER_1
                        ))
                        title_modified = title_modified.replace(match, '')
                        break
        
        return tokens, title_modified
    
    def _split_by_separators(self, title: str) -> List[str]:
        """Split title by separators, keeping separators as separate items."""
        parts = re.split(r'(\s*\|\s*|\s*-\s*|\s*/\s*)', title)
        
        result = []
        for part in parts:
            part = part.strip()
            if part in ['|', '-', '/']:
                result.append(part)
            elif part:
                result.append(part)
        
        return result
    
    def _classify_segment(self, segment: str, truth: Dict) -> List[Token]:
        """
        Classify a segment into one or more concept tokens.
        
        V2: Splits segment if it contains multiple concepts.
        E.g., "Premium Scented Garbage Bags" -> [QUALITY_MARKER, SCENT, PRODUCT]
        """
        tokens = []
        segment_lower = segment.lower()
        
        # Try to identify multiple concepts in the segment
        remaining = segment
        
        # 1. Check for QUALITY_MARKER (Premium, Deluxe, etc.)
        for marker in QUALITY_MARKER_WORDS:
            if marker in segment_lower:
                # Split out the quality marker
                pattern = re.compile(rf'\b{marker}\b', re.IGNORECASE)
                match = pattern.search(remaining)
                if match:
                    tokens.append(Token(
                        text=match.group(),
                        token_type=TokenType.QUALITY_MARKER,
                        locked=False,
                        value=5,  # Very low value
                        tier=ConceptTier.TIER_3
                    ))
                    remaining = pattern.sub('', remaining).strip()

        # 1.5 Check for BRAND and extract it as its own concept
        # This prevents brand+product chunks from being classified as BRAND only.
        if truth.get('brand'):
            brand_text = str(truth['brand']).strip()
            if brand_text:
                brand_pattern = re.compile(rf'\b{re.escape(brand_text)}\b', re.IGNORECASE)
                match = brand_pattern.search(remaining)
                if match:
                    tokens.append(Token(
                        text=match.group(),
                        token_type=TokenType.BRAND,
                        locked=True,
                        value=100,
                        tier=ConceptTier.TIER_0
                    ))
                    remaining = brand_pattern.sub('', remaining).strip()
        
        # NEW: Check for SIZE at start of segment (e.g. "Medium 19 x 21")
        # This handles cases where Size and Dimension are in the same chunk
        first_word = remaining.split()[0] if remaining else ""
        if first_word.lower() in SIZES:
             tokens.append(Token(
                text=first_word,
                token_type=TokenType.SIZE,
                locked=True,
                value=75,
                tier=ConceptTier.TIER_1
            ))
             # Remove size word from start (case insensitive)
             remaining = remaining[len(first_word):].strip()

        # 2. Check for SCENT words (Scented, Aromatic, etc.)
        for scent in SCENT_WORDS:
            if scent in segment_lower:
                pattern = re.compile(rf'\b{scent}\b', re.IGNORECASE)
                match = pattern.search(remaining)
                if match:
                    tokens.append(Token(
                        text=match.group(),
                        token_type=TokenType.SCENT,
                        locked=False,
                        value=10,  # Low value - often redundant
                        tier=ConceptTier.TIER_3
                    ))
                    remaining = pattern.sub('', remaining).strip()
        
        # 3. Check for FRAGRANCE (if not already extracted from parentheses)
        for fragrance in FRAGRANCE_WORDS:
            if fragrance in segment_lower and 'fragrance' in segment_lower:
                pattern = re.compile(rf'\b{fragrance}\s*fragrance\b', re.IGNORECASE)
                match = pattern.search(remaining)
                if match:
                    tokens.append(Token(
                        text=match.group(),
                        token_type=TokenType.FRAGRANCE,
                        locked=False,
                        value=40,
                        tier=ConceptTier.TIER_2
                    ))
                    remaining = pattern.sub('', remaining).strip()
        
        # 4. Check for POSITIONS (Front, Rear, etc.)
        for pos in POSITIONS:
            if pos in segment_lower:
                pattern = re.compile(rf'\b{pos}\b', re.IGNORECASE)
                match = pattern.search(remaining)
                if match:
                    tokens.append(Token(
                        text=match.group(),
                        token_type=TokenType.POSITION,
                        locked=True,
                        value=65,
                        tier=ConceptTier.TIER_1
                    ))
                    remaining = pattern.sub('', remaining).strip()

        # 5. Check for MATERIALS (Aluminium, Steel, etc.)
        # Smart detection: if material is followed by descriptive nouns, keep phrase together
        descriptive_nouns = r'\b(bucket|bin|lid|cover|body|pedal|handle|frame|fork|tube|rod|bar|bracket|mount|clip|ring|plate|panel|door|drawer|container|tray|basket|rack)'
        
        for mat in MATERIALS:
            if mat in segment_lower:
                # Check if material is part of a descriptive phrase
                # Match: "material + 1-2 descriptive words"
                phrase_pattern = re.compile(
                    rf'\b({mat})\s+(?:(?:\w+\s+)?{descriptive_nouns})',
                    re.IGNORECASE
                )
                phrase_match = phrase_pattern.search(remaining)
                
                if phrase_match:
                    # Keep the whole phrase together as FEATURE
                    tokens.append(Token(
                        text=phrase_match.group(),
                        token_type=TokenType.FEATURE,
                        locked=True,
                        value=65,
                        tier=ConceptTier.TIER_1
                    ))
                    remaining = phrase_pattern.sub('', remaining).strip()
                else:
                    # Extract as standalone material
                    standalone_pattern = re.compile(rf'\b{mat}\b', re.IGNORECASE)
                    standalone_match = standalone_pattern.search(remaining)
                    if standalone_match:
                        tokens.append(Token(
                            text=standalone_match.group(),
                            token_type=TokenType.MATERIAL,
                            locked=True,
                            value=60,
                            tier=ConceptTier.TIER_1
                        ))
                        remaining = standalone_pattern.sub('', remaining).strip()
        
        # 6. Check for TECH_SPECS (BS6, 12V, etc.)
        for spec in TECH_SPECS:
            if spec in segment_lower:
                pattern = re.compile(rf'\b{spec}\b', re.IGNORECASE)
                match = pattern.search(remaining)
                if match:
                    tokens.append(Token(
                        text=match.group(),
                        token_type=TokenType.TECH_SPEC,
                        locked=False,  # Not strictly locked, but high value
                        value=55,
                        tier=ConceptTier.TIER_2
                    ))
                    remaining = pattern.sub('', remaining).strip()

        # 7. Check for COMPATIBILITY (Heuristic: "for" + Capitalized Word)
        # E.g., "for Honda", "for Suzuki Gixxer", "for Motorcycles & Scooters"
        # Updated pattern to capture "for X & Y" and "for X, Y & Z" patterns
        # The pattern now allows: ampersand (&), comma (,), and "and" between items
        comp_pattern = re.compile(
            r'\b(for|compatible with)\s+'
            r'([A-Z][a-zA-Z0-9\-\.\']*'  # First word (capitalized)
            r'(?:\s+[A-Z][a-zA-Z0-9\-\.\']*)*'  # Additional capitalized words
            r'(?:\s*[&,]\s*[A-Z][a-zA-Z0-9\-\.\']*(?:\s+[A-Z][a-zA-Z0-9\-\.\']*)*)*'  # & X or , X patterns
            r'(?:\s+and\s+[A-Z][a-zA-Z0-9\-\.\']*(?:\s+[A-Z][a-zA-Z0-9\-\.\']*)*)?'  # optional "and X"
            r')'
        )
        match = comp_pattern.search(remaining)
        if match:
             # Verify it's not a Position (e.g. "for Front") or Feature
             matched_text = match.group(0)
             target = match.group(2).lower()
             # Avoid misclassifying feature phrases like "for Easy Dispensing" as compatibility.
             excluded_target_words = {
                 'easy', 'dispensing', 'install', 'installation', 'use', 'usage', 'clean', 'cleaning',
                 'kitchen', 'bathroom', 'home', 'office', 'premium', 'quality'
             }
             target_words = set(re.split(r'\s+', target.strip()))
             if (
                 target not in POSITIONS
                 and not (target_words & excluded_target_words)
             ):
                tokens.append(Token(
                    text=matched_text,
                    token_type=TokenType.COMPATIBILITY,
                    locked=True,
                    value=95,  # Very high importance for auto parts
                    tier=ConceptTier.TIER_0
                ))
                remaining = comp_pattern.sub('', remaining).strip()

        # 8. Extract common multi-word FEATURE phrases inside the remaining chunk.
        # This helps ensure we can keep 2-3 distinct features instead of one long feature blob.
        feature_phrases = [
            'perforated box',
            'easy dispensing',
            'leak proof',
            'leak-proof',
            'heavy duty',
            'heavy-duty',
            'star seal',
            'odor control',
            'odour control',
        ]

        remaining_lower = remaining.lower()
        found_features = []
        for phrase in feature_phrases:
            idx = remaining_lower.find(phrase)
            if idx != -1:
                found_features.append((idx, phrase))

        # Extract in appearance order
        for _, phrase in sorted(found_features, key=lambda x: x[0]):
            # Remove phrase (case-insensitive) from remaining, but preserve nice surface form
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            if pattern.search(remaining):
                surface = ' '.join([w.capitalize() for w in phrase.replace('-', ' ').split()])
                # Keep hyphenated display for leak-proof / heavy-duty
                if '-' in phrase:
                    surface = phrase.title()
                tokens.append(Token(
                    text=surface,
                    token_type=TokenType.FEATURE,
                    locked=False,
                    value=35,
                    tier=ConceptTier.TIER_2
                ))
                remaining = pattern.sub('', remaining).strip()
                remaining_lower = remaining.lower()

        # 4. Process remaining content
        remaining = remaining.strip()
        if remaining:
            # If only a connector word remains, drop it.
            if remaining.lower() in {'for', 'with', 'and', 'or'}:
                return tokens
            token = self._classify_single_segment(remaining, truth)
            if token:
                tokens.append(token)
        
        return tokens if tokens else [self._classify_single_segment(segment, truth)]
    
    def _classify_single_segment(self, segment: str, truth: Dict) -> Token:
        """Classify a single segment into a Token."""
        segment_lower = segment.lower()
        
        # Check for BANNED words
        for banned in BANNED_WORDS:
            if banned in segment_lower:
                return Token(
                    text=segment,
                    token_type=TokenType.BANNED,
                    locked=False,
                    value=-50,
                    tier=ConceptTier.TIER_3
                )
        
        # Check for BRAND
        if truth.get('brand') and truth['brand'].lower() in segment_lower:
            return Token(
                text=segment,
                token_type=TokenType.BRAND,
                locked=True,
                value=100,
                tier=ConceptTier.TIER_0
            )
        
        # Check for DIMENSION
        if self.dimension_pattern.search(segment):
            return Token(
                text=segment,
                token_type=TokenType.DIMENSION,
                locked=False,
                value=60,
                tier=ConceptTier.TIER_2
            )
        
        # Check for COUNT
        if self.count_pattern.search(segment) or self.count_detail_pattern.search(segment):
            return Token(
                text=segment,
                token_type=TokenType.COUNT,
                locked=True,
                value=80,
                tier=ConceptTier.TIER_1
            )
        
        # Check for SIZE
        for size in SIZES:
            if size in segment_lower:
                return Token(
                    text=segment,
                    token_type=TokenType.SIZE,
                    locked=True,
                    value=75,
                    tier=ConceptTier.TIER_1
                )
        
        # Check for SYNONYM
        synonyms = ['dustbin bag', 'trash bag', 'waste bag', 'bin bag', 'bin liner']
        for syn in synonyms:
            if syn in segment_lower:
                val = 30
                if 'dustbin' in syn: 
                    val = 35  # Prefer Dustbin over Trash based on user pref
                return Token(
                    text=segment,
                    token_type=TokenType.SYNONYM,
                    locked=False,
                    value=val,
                    tier=ConceptTier.TIER_3
                )
        
        # Check for PRODUCT
        if truth.get('product'):
            product_words = truth['product'].lower().split()
            if any(pw in segment_lower for pw in product_words if len(pw) > 3):
                return Token(
                    text=segment,
                    token_type=TokenType.PRODUCT,
                    locked=True,
                    value=90,
                    tier=ConceptTier.TIER_0
                )
        
        # Check for USE_CASE
        # Keep this broad and category-agnostic.
        if (
            segment_lower.startswith('for ')
            or any(w in segment_lower for w in ['kitchen', 'bathroom', 'car', 'office', 'home'])
        ):
            return Token(
                text=segment,
                token_type=TokenType.USE_CASE,
                locked=False,
                value=25,
                tier=ConceptTier.TIER_3
            )
        
        # Check for FEATURE
        feature_indicators = [
            # common packaging/bags
            'perforated', 'leak', 'leakproof', 'proof', 'heavy duty', 'easy', 'dispensing', 'strong', 'thick', 'star seal',
            # general product features
            'durable', 'portable', 'compact', 'mini', 'removable', 'washable', 'easy clean', 'easy-clean',
            # car trash bin specifics
            'push-top', 'push top', 'one-touch', 'one touch', 'spring-loaded', 'spring loaded',
            'cup holder', 'door pocket', 'universal fit', 'no screws', 'no glue',
            'storage box', 'coin', 'keys'
        ]
        for indicator in feature_indicators:
            if indicator in segment_lower:
                return Token(
                    text=segment,
                    token_type=TokenType.FEATURE,
                    locked=False,
                    value=35,
                    tier=ConceptTier.TIER_2
                )
        
        # Default: OTHER
        return Token(
            text=segment,
            token_type=TokenType.OTHER,
            locked=False,
            value=10,
            tier=ConceptTier.TIER_3
        )
    
    def _apply_truth_locks(self, tokens: List[Token], truth: Dict):
        """Mark tokens that match truth as locked."""
        for token in tokens:
            if token.token_type == TokenType.BRAND:
                if truth.get('brand') and truth['brand'].lower() in token.text.lower():
                    token.locked = True
                    token.tier = ConceptTier.TIER_0
            
            if token.token_type == TokenType.SIZE:
                if truth.get('size') and truth['size'].lower() in token.text.lower():
                    token.locked = True
                    token.tier = ConceptTier.TIER_1
            
            if token.token_type == TokenType.COLOR:
                if truth.get('color') and truth['color'].lower() in token.text.lower():
                    token.locked = True
                    token.tier = ConceptTier.TIER_1


# Singleton instance
parser = TitleParser()
