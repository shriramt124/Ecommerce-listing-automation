"""
AGENTIC STRATEGY 2: AI-POWERED TITLE OPTIMIZER
===============================================
Uses local Ollama LLM to make intelligent optimization decisions.

Usage:
    python3 main.py

First run: python3 ingest_keywords.py (to build the SentenceTransformers index)

Environment:
    ADKRUX_USE_AI=true (enable AI - default true)
    ADKRUX_OLLAMA_MODEL=gemma3:4b (Ollama model)
"""
   
import os
import re
import requests
import json

# Ensure AI is enabled
os.environ.setdefault('ADKRUX_USE_AI', 'true')

from agentic_optimizer import create_agentic_optimizer
from token_types import SIZES, COLORS, FRAGRANCE_WORDS
from agentic_llm import OllamaConfig, OllamaLLM, extract_json_object


def extract_truth_with_ai(title: str, optimizer) -> dict:
    """Use AI to automatically extract truth from the title."""
    
    print("\n   [Auto-Extract] Using AI to extract product attributes...")
    
    prompt = f"""You are an Amazon product title analyzer. Extract the key attributes from this product title.

PRODUCT TITLE: "{title}"

TASK: Extract ALL factual attributes you can find. Be precise and specific.

IMPORTANT INSTRUCTIONS:
1. For "product": Identify the SPECIFIC product type from the title (e.g., "Garbage Bags", "Dustbin Bags", "Phone Case", "Brake Pads"). NEVER use generic words like "Product", "Item", or "Thing".
2. For "color": Look for colors even if they're in parentheses like "(Black)" or "(White)".
3. For "brand": Extract the brand name if it appears at the start.
4. Be specific and literal - extract what you actually see in the title.

Respond ONLY with valid JSON:
{{
    "brand": "exact brand name if present, otherwise empty string",
    "product": "SPECIFIC product type (e.g. 'Garbage Bags', 'Phone Case', 'Handlebar'), NOT 'Product' or 'Item'",
    "size": "size if mentioned (Small/Medium/Large/XL/Universal/Mini etc.)",
    "color": "color if mentioned anywhere in title (check parentheses too)",
    "count": "quantity if mentioned (e.g., '120 Bags', 'Pack of 2')",
    "dimension": "dimensions if mentioned (e.g., '19 x 21 Inches')",
    "material": "material if mentioned (e.g., 'Plastic', 'Aluminium')",
    "fragrance": "fragrance if mentioned (e.g., 'Lavender')",
    "features": ["list of features like 'Perforated', 'Leak-Proof', 'With Lid'"],
    "compatibility": "what it's for (e.g., 'for Bikes', 'for Car', 'for Kitchen')"
}}

Only include fields you can actually find in the title. Leave empty if not present.

JSON:"""

    def _extract_pack_exact(raw_title: str) -> str:
        t = raw_title or ''
        m = re.search(r'(\b\d+\s*bags?\s*\(\s*\d+\s*bags?\s*[xX×*]\s*\d+\s*rolls?\s*\))', t, flags=re.IGNORECASE)
        if m:
            s = re.sub(r'\s+', ' ', m.group(1)).strip()
            s = s.replace('×', 'x').replace('*', 'x')
            s = re.sub(r'\bbags\b', 'Bags', s, flags=re.IGNORECASE)
            s = re.sub(r'\brolls\b', 'Rolls', s, flags=re.IGNORECASE)
            return s
        return ''

    try:
        # Prefer the pipeline's shared LLM instance if available.
        llm = getattr(optimizer, 'llm', None)
        if not isinstance(llm, OllamaLLM):
            llm = OllamaLLM(
                OllamaConfig(
                    model=os.getenv('ADKRUX_OLLAMA_MODEL', 'deepseek-v3.1:671b-cloud'),
                    base_url=os.getenv('ADKRUX_OLLAMA_URL', 'http://localhost:11434'),
                )
            )

        response = llm.generate(prompt, temperature=0.2, max_tokens=400)
        if response:
            result = extract_json_object(response)
            if result:
                # Clean up empty values
                truth = {k: v for k, v in result.items() if v and v != [] and v != ""}

                # Preserve exact pack math if present in title
                pack_exact = _extract_pack_exact(title)
                if pack_exact:
                    # Some models return count='1' for single item; ignore that if we have a real pack string
                    if str(truth.get('count', '')).strip() in {'1', '1 pc', '1 pcs', 'one'}:
                        truth.pop('count', None)
                    truth['count'] = pack_exact

                print(f"   [Auto-Extract] Found: {truth}")
                return truth
    except Exception as e:
        print(f"   [Auto-Extract] AI extraction failed: {e}")
    
    # Fallback to regex extraction
    print("   [Auto-Extract] Falling back to regex extraction...")
    return extract_truth_from_title(title)


def extract_truth_from_title(title: str) -> dict:
    """Auto-extract truth attributes from the title using parser patterns."""
    truth = {}
    title_lower = title.lower()
    
    # Words that are product types, NOT brand names
    # These should never be detected as brands even if capitalized at start
    NON_BRAND_WORDS = {
        # Vehicle types
        'motorcycle', 'motorbike', 'bike', 'scooter', 'car', 'truck', 'auto', 'vehicle',
        'activa', 'scooty', 'moped', 'atv', 'utv',
        # Parts/categories
        'shock', 'absorber', 'suspension', 'handlebar', 'fork', 'brake', 'clutch',
        'mirror', 'indicator', 'light', 'seat', 'stand', 'guard', 'cover',
        # Home products  
        'garbage', 'dustbin', 'trash', 'waste', 'kitchen', 'bathroom', 'home',
        # Generic descriptors
        'universal', 'premium', 'heavy', 'duty', 'professional', 'original',
        'new', 'best', 'quality', 'super', 'ultra', 'extra', 'pack', 'set',
    }
    
    # Extract Brand (first capitalized word before common product terms)
    # Common pattern: "BrandName ProductType..."
    first_segment = title.split('|')[0].strip() if '|' in title else title.split()[0:3]
    if isinstance(first_segment, list):
        first_segment = ' '.join(first_segment)
    words = first_segment.split()
    if words and words[0][0].isupper():
        # Check if first word looks like a brand (not a size/color/non-brand word)
        first_word_lower = words[0].lower()
        if (first_word_lower not in SIZES 
            and first_word_lower not in COLORS
            and first_word_lower not in NON_BRAND_WORDS):
            truth['brand'] = words[0]
    
    # Extract Product (look for common product types)
    product_patterns = [
        r'\b(garbage bags?|dustbin bags?|trash bags?|waste bags?)\b',
        r'\b(car trash bin|car dustbin|dustbin)\b',
        r'\b(handlebar|fork|suspension)\b',
        # Automotive/motorcycle parts
        r'\b(shock absorber|shock riser|shock extender)\b',
        r'\b(brake pad|brake shoe|brake lever|brake disc)\b',
        r'\b(clutch lever|clutch plate|clutch cable)\b',
        r'\b(side mirror|rear mirror|rearview mirror)\b',
        r'\b(indicator|turn signal|blinker)\b',
        r'\b(foot rest|footrest|foot peg)\b',
        r'\b(seat cover|saddle cover)\b',
        r'\b(mud guard|mudguard|fender)\b',
        r'\b(crash guard|leg guard)\b',
    ]
    for pattern in product_patterns:
        match = re.search(pattern, title_lower)
        if match:
            truth['product'] = match.group(1).title()
            break
    
    # Extract Size
    for size in SIZES:
        if re.search(rf'\b{size}\b', title_lower):
            truth['size'] = size.title()
            break
    
    # Extract Color
    for color in COLORS:
        if re.search(rf'\b{color}\b', title_lower):
            truth['color'] = color.title()
            break
    
    # Extract Count (e.g., "120 Bags", "30 Bags X 4 Rolls")
    count_match = re.search(r'(\d+)\s*(bags?|pcs?|pieces?|rolls?|pack)', title_lower)
    if count_match:
        truth['count'] = count_match.group(0).title()
    
    # Extract Dimension (e.g., "19 X 21 Inches")
    dim_match = re.search(r'(\d+)\s*[xX×]\s*(\d+)\s*(inches?|cm)?', title, re.IGNORECASE)
    if dim_match:
        truth['dimension'] = dim_match.group(0)
    
    # Extract Fragrance
    for fragrance in FRAGRANCE_WORDS:
        if fragrance in title_lower:
            truth['fragrance'] = fragrance.title()
            break
    
    # Extract Capacity (e.g., "620 ml", "30L")
    cap_match = re.search(r'(\d+)\s*(ml|l|litres?|liters?|gallon)', title_lower)
    if cap_match:
        truth['capacity'] = cap_match.group(0)
    
    # Extract Features (common feature phrases)
    features = []
    feature_phrases = ['perforated box', 'easy dispensing', 'leak proof', 'leak-proof',
                       'heavy duty', 'star seal', 'push-top', 'one-touch', 'removable cover']
    for phrase in feature_phrases:
        if phrase in title_lower:
            features.append(phrase.title())
    if features:
        truth['features'] = features[:3]  # Max 3 features
    
    return truth


def get_sample_truth() -> dict:
    """Sample truth attributes for testing."""
    return {
        'brand': 'Shalimar',
        'product': 'Garbage Bags',
        'size': 'Medium',
        'color': 'Black',
        'count': '120 Bags',
        'count_detail': '30x4 Rolls',
        'dimension': '19 x 21 Inches',
        'fragrance': 'Lavender',
        'features': ['Perforated Box', 'Easy Dispensing', 'Leak Proof']
    }


def get_sample_title() -> str:
    """Sample title for testing."""
    return (
        "Shalimar Premium (Lavender Fragrance) Scented Garbage Bags | "
        "Medium 19 X 21 Inches | 120 Bags (30 Bags X 4 Rolls) | "
        "Dustbin Bag/Trash Bag | (Black) - Perforated Box for Easy Dispensing"
    )


def main():
    """Main entry point - supports both interactive and command-line modes."""
    import sys
    
    # Check if title provided via command line
    if len(sys.argv) > 1:
        # Command-line mode: python3 main.py "Your Title Here"
        title = sys.argv[1]
        print(f"Optimizing: {title}")
        
        # Minimal truth (AI will extract from title)
        truth = {'product': 'Product'}
        
        optimizer = create_agentic_optimizer()
        optimized, _ = optimizer.optimize(title, truth)
        print(f"\nResult: {optimized}")
        return optimized
    
    # Interactive mode
    print("=" * 70)
    print("  AGENTIC STRATEGY 2: AI-POWERED TITLE OPTIMIZER")
    print("  (Using Ollama LLM for intelligent optimization)")
    print("=" * 70)
    
    # Initialize AI optimizer
    optimizer = create_agentic_optimizer()
    
    # =========================================================================
    # INPUT: Base Title
    # =========================================================================
    print("\n--- ENTER YOUR PRODUCT TITLE ---")
    print("(Enter your current Amazon product title, or press Enter for sample)")
    base_title = input("\nTitle: ").strip()
    
    using_sample = False
    if not base_title:
        using_sample = True
        base_title = get_sample_title()
        print(f"\n[Using sample title for testing]")
        print(f"   {base_title}")
    
    # =========================================================================
    # AUTO-EXTRACT TRUTH FROM TITLE USING AI
    # =========================================================================
    print("\n--- EXTRACTING PRODUCT ATTRIBUTES ---")
    
    if using_sample:
        truth = get_sample_truth()
        print(f"   Using sample truth: {truth}")
    else:
        truth = extract_truth_with_ai(base_title, optimizer)
    
    # =========================================================================
    # RUN AI-POWERED OPTIMIZATION
    # =========================================================================
    optimized_title, report = optimizer.optimize(base_title, truth)
    
    # =========================================================================
    # OUTPUT RESULTS
    # =========================================================================
    print("\n" + "=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)
    
    original_len = len(base_title)
    final_len = len(optimized_title)
    
    print(f"\n📌 ORIGINAL TITLE ({original_len} chars):")
    print(f"   {base_title}")
    
    print(f"\n✨ OPTIMIZED TITLE ({final_len} chars):")
    print(f"   {optimized_title}")
    
    # Show character usage
    print(f"\n📊 CHARACTER USAGE:")
    print(f"   Original: {original_len} chars")
    print(f"   Optimized: {final_len} chars")
    if final_len > original_len:
        print(f"   📈 Added {final_len - original_len} more characters for better SEO")
    elif final_len < original_len:
        print(f"   📉 Saved {original_len - final_len} characters")
    
    # Status
    print("\n" + "-" * 70)
    if 180 <= final_len <= 200:
        print("Status: ✅ PERFECT - Within target range (180-200 chars)!")
    elif final_len < 180:
        print(f"Status: ⚠️ SHORT - {180 - final_len} chars below minimum")
    else:
        print(f"Status: ⚠️ LONG - {final_len - 200} chars over maximum")
    
    print("=" * 70)
    
    return optimized_title


if __name__ == "__main__":
    main()
