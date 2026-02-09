#!/usr/bin/env python3
"""Quick test: does Gemini produce an optimized title?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from gemini_llm import GeminiConfig, GeminiLLM

config = GeminiConfig(
    api_key=os.getenv("GEMINI_API_KEY", ""),
    model=os.getenv("GEMINI_TEXT_MODEL", "gemini-3-pro-preview"),
)
llm = GeminiLLM(config)

base_title = "Kakss Neoprene Dumbbells 1+1=2 KG Pack of 1 KG Each, Anti-Slip Coated Hand Weights for Home Gym & Fitness Training -Pink"

prompt = f"""You are an Amazon SEO title optimization expert.

ORIGINAL TITLE:
"{base_title}"

PRODUCT DATA:
- Brand: Kakss
- Product Type: Neoprene Dumbbells
- Colors: Pink
- Size/Weight: 1 KG Each
- Quantity: Pack of 2 (1+1=2 KG total)
- Material: Neoprene coated cast iron
- Usage: Home gym, fitness training, exercise
- Key Features: Anti-slip coating, hexagonal shape, printed weight markings

HIGH-VOLUME SEARCH KEYWORDS (from real Amazon UK data):
- dumbbells set (volume: 29300)
- weights (volume: 24559)
- adjustable dumbbells (volume: 14214)
- dumbbells (volume: 11166)
- weights dumbbells set (volume: 10733)
- dumbbells set women (volume: 6246)
- dumbells (volume: 5815)
- 5kg dumbbells pair (volume: 4039)
- 1kg dumbbells (volume: 1011)
- hand weights (volume: 1703)
- weights for women (volume: 2924)
- home gym equipment (volume: 2952)
- neoprene dumbbell set (volume: 592)

TASK: Rewrite the title to be 180-200 characters, optimized for Amazon SEO.

RULES:
1. Start with brand name: "Kakss"
2. Include the product type and ALL factual specs from the original title
3. ADD relevant search keywords from the list above that are NOT already in the title
4. Use natural comma-separated flow — no pipes (|)
5. DO NOT invent features not in the original title or product data
6. DO NOT use superlatives like "best", "#1", "guaranteed"
7. Target 180-200 characters (MUST be different from original and LONGER)
8. Keep all specific numbers, sizes, quantities from the original

Output ONLY the optimized title text (one line, no quotes):"""

print(f"Original title ({len(base_title)} chars):")
print(f"  {base_title}")
print(f"\nCalling Gemini (gemini-3-pro-preview)...")
raw = llm.generate(prompt, temperature=0.4, max_tokens=300)
print(f"\nRaw response:")
print(f"  '{raw}'")
print(f"\n  Length: {len(raw or '')} chars")

if raw:
    result = raw.strip().split("\n")[0].strip()
    if result.startswith('"') and result.endswith('"'):
        result = result[1:-1]
    if result.startswith("'") and result.endswith("'"):
        result = result[1:-1]
    import re
    result = re.sub(r"\s+", " ", result).strip()
    print(f"\nCleaned result ({len(result)} chars):")
    print(f"  {result}")
    print(f"\nDifferent from original: {result.strip() != base_title.strip()}")
    print(f"Length >= 100: {len(result) >= 100}")
