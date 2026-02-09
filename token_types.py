"""
STRATEGY 2: TOKEN TYPES (V2 - WITH IMPLICATION RULES)
======================================================
Defines Token class, TokenType enum, and IMPLICATION RULES for concept-based optimization.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Set


class TokenType(Enum):
    """Types of tokens/concepts in an Amazon title."""
    BRAND = "brand"              # e.g., "Shalimar"
    PRODUCT = "product"          # e.g., "Garbage Bags"
    SIZE = "size"                # e.g., "Medium", "Large", "XL"
    COLOR = "color"              # e.g., "Black", "White", "Green"
    COUNT = "count"              # e.g., "120 Bags", "30x4 Rolls"
    DIMENSION = "dimension"      # e.g., "19 x 21 Inches"
    CAPACITY = "capacity"        # e.g., "30L", "32 Litres"
    MATERIAL = "material"        # e.g., "Plastic", "Paper"
    FRAGRANCE = "fragrance"      # e.g., "Lavender Fragrance"
    SCENT = "scent"              # e.g., "Scented" - REDUNDANT if FRAGRANCE exists!
    QUALITY_MARKER = "quality"   # e.g., "Premium", "Deluxe" - low value, evictable
    FEATURE = "feature"          # e.g., "Perforated Box", "Leak-Proof"
    USE_CASE = "use_case"        # e.g., "for Kitchen", "for Bathroom"
    SYNONYM = "synonym"          # e.g., "Dustbin Bag", "Trash Bag"
    SEPARATOR = "separator"      # e.g., "|", "-", "/"
    OTHER = "other"              # Unclassified
    COMPATIBILITY = "compatibility" # e.g., "for Honda", "Compatible with"
    POSITION = "position"        # e.g., "Front", "Rear"
    TECH_SPEC = "tech_spec"      # e.g., "12V", "BS6"
    PART_NUMBER = "part_number"  # e.g., OEM numbers
    BANNED = "banned"            # Promotional/policy-violating terms


class TokenOrigin(Enum):
    """Where the token came from."""
    BASE = "base"          # From original title
    KEYWORD = "keyword"    # Added from keyword database
    TRUTH = "truth"        # From product truth attributes


# ============================================================================
# CONCEPT TIERS (Priority levels for eviction)
# ============================================================================
class ConceptTier(Enum):
    """Priority tiers for concepts - lower tier = more evictable."""
    TIER_0 = 0  # Critical/Locked (Brand, Product, Critical Compatibility)
    TIER_1 = 1  # High Importance (Size, Color, Material, Count)
    TIER_2 = 2  # Medium Importance (Features, Tech Specs)
    TIER_3 = 3  # Low/Optional (Synonyms, redundant text)


# Map token types to their tiers
TOKEN_TIERS = {
    TokenType.BRAND: ConceptTier.TIER_0,
    TokenType.PRODUCT: ConceptTier.TIER_0,
    TokenType.COMPATIBILITY: ConceptTier.TIER_0, # Compatibility is critical for Auto
    
    TokenType.SIZE: ConceptTier.TIER_1,
    TokenType.COLOR: ConceptTier.TIER_1,
    TokenType.COUNT: ConceptTier.TIER_1,
    TokenType.MATERIAL: ConceptTier.TIER_1,
    TokenType.POSITION: ConceptTier.TIER_1,
    
    TokenType.DIMENSION: ConceptTier.TIER_2,
    TokenType.CAPACITY: ConceptTier.TIER_2,
    TokenType.FRAGRANCE: ConceptTier.TIER_2,
    TokenType.FEATURE: ConceptTier.TIER_2,
    TokenType.TECH_SPEC: ConceptTier.TIER_2,
    TokenType.PART_NUMBER: ConceptTier.TIER_2,
    
    TokenType.SCENT: ConceptTier.TIER_3,           # Low priority - often redundant
    TokenType.QUALITY_MARKER: ConceptTier.TIER_3,  # Low priority - vague
    TokenType.USE_CASE: ConceptTier.TIER_3,
    TokenType.SYNONYM: ConceptTier.TIER_3,
    TokenType.OTHER: ConceptTier.TIER_3,
    TokenType.SEPARATOR: ConceptTier.TIER_3,
    TokenType.BANNED: ConceptTier.TIER_3,
}


# ============================================================================
# IMPLICATION RULES (V2 KEY FEATURE!)
# ============================================================================
# If concept A exists, concept B becomes REDUNDANT and should be REMOVED
# Format: {concept_that_implies: [concepts_that_become_redundant]}

IMPLICATION_RULES = {
    # FRAGRANCE implies SCENT - "Lavender Fragrance" makes "Scented" redundant
    TokenType.FRAGRANCE: [TokenType.SCENT],
    
    # Specific features can imply generic ones (add more as needed)
    # TokenType.MATERIAL: [],  # example placeholder
}

SCENT_WORDS = ['scented', 'aromatic', 'fragrant', 'odor control', 'odour control']

# Words that indicate QUALITY_MARKER (low value, evictable)
QUALITY_MARKER_WORDS = ['premium', 'deluxe', 'superior', 'best', 'quality', 'pro', 'ultra', 'fancy', 'luxury']

# Words that indicate FRAGRANCE (implies SCENT)
FRAGRANCE_WORDS = ['lavender', 'rose', 'jasmine', 'lemon', 'citrus', 'fresh', 'mint', 'vanilla']


@dataclass
class Token:
    """
    Represents a concept in the title.
    
    V2 Changes:
    - Added tier field for priority-based eviction
    - Added redundant field to mark concepts for removal
    """
    text: str
    token_type: TokenType
    locked: bool = False
    value: float = 0.0
    cost: int = 0
    origin: TokenOrigin = TokenOrigin.BASE
    semantic_group: Optional[int] = None
    zone: str = "B"  # Default to Zone B
    normalized: str = field(default="", repr=False)
    tier: ConceptTier = ConceptTier.TIER_2  # Default tier
    redundant: bool = False  # If True, should be REMOVED
    
    def __post_init__(self):
        # Calculate cost (text length + 1 for space/separator)
        if self.cost == 0:
            self.cost = len(self.text) + 1
        # Normalize for matching
        if not self.normalized:
            self.normalized = self.text.lower().strip()
        # Set tier based on type
        if self.token_type in TOKEN_TIERS:
            self.tier = TOKEN_TIERS[self.token_type]
    
    def value_per_char(self) -> float:
        """Calculate value efficiency (used for eviction decisions)."""
        return self.value / max(self.cost, 1)
    
    def mark_redundant(self):
        """Mark this concept as redundant - should be removed."""
        self.redundant = True
        self.tier = ConceptTier.TIER_3
        self.value = 0
        self.locked = False
    
    def is_evictable(self) -> bool:
        """Check if this concept can be evicted."""
        return not self.locked and self.tier.value >= ConceptTier.TIER_2.value
    
    def __str__(self):
        lock_icon = "🔒" if self.locked else ""
        redundant_icon = "❌" if self.redundant else ""
        return f"{lock_icon}{redundant_icon}[{self.token_type.value}] {self.text} (v={self.value:.1f})"


# ============================================================================
# TRUTH-CRITICAL TYPES (These are LOCKED and cannot be removed)
# ============================================================================
TRUTH_CRITICAL_TYPES = {
    TokenType.BRAND,
    TokenType.PRODUCT,
    TokenType.SIZE,
    TokenType.COLOR,
    TokenType.COUNT,
    TokenType.COMPATIBILITY,
    TokenType.POSITION,
}

# ============================================================================
# ZONE DEFINITIONS
# ============================================================================
ZONE_A_TYPES = {
    TokenType.BRAND,
    TokenType.PRODUCT,
    TokenType.SIZE,
    TokenType.COLOR,
    TokenType.COUNT,
    TokenType.COMPATIBILITY,
    TokenType.POSITION,
}

ZONE_B_TYPES = {
    TokenType.DIMENSION,
    TokenType.CAPACITY,
    TokenType.FRAGRANCE,
    TokenType.FEATURE,
    TokenType.MATERIAL,
    TokenType.TECH_SPEC,
    TokenType.PART_NUMBER,
}

ZONE_C_TYPES = {
    TokenType.SCENT,           # If not removed by implication
    TokenType.QUALITY_MARKER,  # Usually removed
    TokenType.USE_CASE,
    TokenType.SYNONYM,
    TokenType.OTHER,
}


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================
MAX_CHARS = 200
ZONE_A_PERCENT = 0.40  # ~80 chars
ZONE_B_PERCENT = 0.40  # ~80 chars
ZONE_C_PERCENT = 0.20  # ~40 chars

SIMILARITY_THRESHOLD = 0.85
REPLACEMENT_MARGIN = 1.15  # candidate must be 15% better to replace
MAX_FEATURES = 3
MAX_SYNONYMS = 1  # Only 1 additional synonym allowed
MAX_QUALITY_MARKERS = 0  # Remove all quality markers by default

# Competitor brands to filter out
BANNED_BRANDS = ['newtone', 'competitor']

# Promotional/policy-violating words
BANNED_WORDS = [
    'bestseller', 'best seller', '#1', 'number one', 'free', 
    'offer', 'discount', 'sale', 'cheap', 'buy now', 'limited',
    'exclusive', 'guaranteed', 'certified', 'authentic'
]

# Size keywords
SIZES = ['small', 'medium', 'large', 'xl', 'xxl', 'mini', 'big', 'extra large']

# Color keywords
COLORS = [
    'black', 'white', 'red', 'blue', 'green', 'yellow', 'pink', 
    'purple', 'orange', 'brown', 'grey', 'gray', 'silver', 'gold'
]

# Materials
MATERIALS = ['aluminum', 'aluminium', 'steel', 'carbon fiber', 'plastic', 'rubber', 'leather', 'alloy', 'cnc']

# Positions
POSITIONS = ['front', 'rear', 'left', 'right', 'upper', 'lower', 'side']

# Tech Specs
TECH_SPECS = ['12v', 'waterproof', 'universal', 'adjustable']
