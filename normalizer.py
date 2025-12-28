"""
STRATEGY 2: NORMALIZER
=======================
Normalizes text for consistent matching: units, plurals, spelling variants.
"""

import re


class Normalizer:
    """Text normalization utilities."""
    
    # Spelling variants (UK → US)
    SPELLING_MAP = {
        'colour': 'color',
        'grey': 'gray',
        'litre': 'liter',
        'litres': 'liters',
        'centre': 'center',
        'metre': 'meter',
        'metres': 'meters',
        'centimetre': 'centimeter',
        'centimetres': 'centimeters',
    }
    
    # Unit normalization patterns
    UNIT_PATTERNS = [
        (r'(\d+)\s*[lL](?:iters?)?', r'\1L'),      # 30 L, 30 liters → 30L
        (r'(\d+)\s*[mM][lL]', r'\1ml'),            # 750 ml, 750ML → 750ml
        (r'(\d+)\s*[gG](?:rams?)?', r'\1g'),       # 500 g, 500 grams → 500g
        (r'(\d+)\s*[kK][gG]', r'\1kg'),            # 2 kg, 2KG → 2kg
        (r'(\d+)\s*[pP][cC][sS]?', r'\1 Pcs'),     # 10 pcs → 10 Pcs
        (r'(\d+)\s*[cC][mM]', r'\1cm'),            # 30 cm → 30cm
        (r'(\d+)\s*[iI]nch(?:es)?', r'\1 Inches'), # 21 inch, 21 inches → 21 Inches
    ]
    
    # Dimension pattern normalization: "19 X 21" → "19x21"
    DIMENSION_PATTERN = re.compile(r'(\d+)\s*[xX×]\s*(\d+)')
    
    def normalize(self, text: str) -> str:
        """
        Full normalization pipeline.
        Returns lowercase normalized string for matching.
        """
        result = text.lower().strip()
        
        # Apply spelling normalization
        result = self.normalize_spelling(result)
        
        # Apply unit normalization
        result = self.normalize_units(result)
        
        # Normalize dimensions
        result = self.normalize_dimensions(result)
        
        # Clean up whitespace
        result = ' '.join(result.split())
        
        return result
    
    def normalize_spelling(self, text: str) -> str:
        """Convert UK spellings to US."""
        result = text
        for uk, us in self.SPELLING_MAP.items():
            result = re.sub(rf'\b{uk}\b', us, result, flags=re.IGNORECASE)
        return result
    
    def normalize_units(self, text: str) -> str:
        """Normalize unit representations."""
        result = text
        for pattern, replacement in self.UNIT_PATTERNS:
            result = re.sub(pattern, replacement, result)
        return result
    
    def normalize_dimensions(self, text: str) -> str:
        """Normalize dimension format: 19 X 21 → 19x21"""
        return self.DIMENSION_PATTERN.sub(r'\1x\2', text)
    
    def normalize_plural(self, word: str) -> str:
        """Get singular form for matching."""
        word = word.lower()
        
        # Common plurals
        if word.endswith('bags'):
            return word[:-1]  # bags → bag
        if word.endswith('liners'):
            return word[:-1]  # liners → liner
        if word.endswith('rolls'):
            return word[:-1]  # rolls → roll
        if word.endswith('pieces'):
            return word[:-1]  # pieces → piece
        if word.endswith('ies'):
            return word[:-3] + 'y'  # batteries → battery
        if word.endswith('es') and len(word) > 3:
            return word[:-2]  # boxes → box
        if word.endswith('s') and not word.endswith('ss'):
            return word[:-1]
        
        return word
    
    def are_same_concept(self, word1: str, word2: str) -> bool:
        """Check if two words are the same concept (singular/plural)."""
        w1 = self.normalize_plural(word1.lower())
        w2 = self.normalize_plural(word2.lower())
        return w1 == w2 or word1.lower() == word2.lower()
    
    def extract_number(self, text: str) -> int:
        """Extract first number from text."""
        match = re.search(r'\d+', text)
        return int(match.group()) if match else 0


# Singleton instance
normalizer = Normalizer()
