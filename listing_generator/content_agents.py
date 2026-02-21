"""
CONTENT AGENTS
==============
AI agents that generate Amazon listing content using ONLY real data:
  - BulletPointAgent:  5 × 200-char key features
  - DescriptionAgent:  800-1500 char product description
  - SearchTermsAgent:  200-char backend search terms (words NOT in title/bullets)

CRITICAL: These agents MUST NOT hallucinate. Every fact comes from:
  1. Image analysis (what AI sees)
  2. Keyword DB  (real Amazon search data)
  3. Client-supplied data (title, existing bullets, USP)
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_llm import GeminiLLM, extract_json_object
from agentic_llm import OllamaLLM


# ---------------------------------------------------------------------------
#  Bullet Point Agent
# ---------------------------------------------------------------------------

BULLET_POINT_PROMPT = """You are an Amazon listing expert writing KEY FEATURES (bullet points).

PRODUCT INFORMATION (source of truth — DO NOT INVENT anything beyond this):
- Title: "{title}"
- Brand: {brand}
- Product type: {product_type}
- Country/Marketplace: {country}
- Colors: {colors}
- Size: {size}
- Quantity: {quantity}
- Material: {material}
- AI-observed features: {ai_features}
- Existing bullet points: {existing_bullets}
- USP / More info: {usp}
- Manual / Product Details: {manual}

TOP KEYWORDS (from real Amazon search data — weave these naturally):
{keyword_list}

TASK: Write exactly 5 bullet points for an Amazon listing.

RULES:
1. Each bullet point MUST be ≤ 200 characters (HARD LIMIT).
2. Start each bullet with a SHORT CAPS PHRASE (2-4 words) followed by a colon, then details.
   Example: "HEAVY DUTY CONSTRUCTION: Made from thick, tear-resistant polyethylene..."
3. Include relevant keywords from the list naturally — do NOT keyword-stuff.
4. ONLY mention features/specs that appear in the data above. Do NOT invent features.
5. Cover different angles: material/quality, size/quantity, use cases, durability, value.
6. Write in {country} English style (UK spelling for UK, US spelling for US/AE).
7. Do NOT use superlatives like "best", "#1", "guaranteed". Amazon TOS prohibits these.

Respond ONLY with valid JSON:
{{
  "bullet_points": [
    "CAPS PHRASE: detail text here...",
    "CAPS PHRASE: detail text here...",
    "CAPS PHRASE: detail text here...",
    "CAPS PHRASE: detail text here...",
    "CAPS PHRASE: detail text here..."
  ]
}}

JSON:"""


# ---------------------------------------------------------------------------
#  Description Agent
# ---------------------------------------------------------------------------

DESCRIPTION_PROMPT = """You are an Amazon listing expert writing a PRODUCT DESCRIPTION.

PRODUCT INFORMATION (source of truth — DO NOT INVENT anything beyond this):
- Title: "{title}"
- Brand: {brand}
- Product type: {product_type}
- Country/Marketplace: {country}
- AI description from images: {ai_description}
- Key features: {key_features}
- Existing bullet points: {existing_bullets}
- Existing description: {existing_description}
- USP / More info: {usp}
- Manual / Product Details: {manual}

TOP KEYWORDS (from real Amazon search data — weave these naturally):
{keyword_list}

TASK: Write a compelling product description for Amazon.

RULES:
1. Length MUST be between 800 and 1500 characters (HARD LIMIT). Count carefully.
2. Start with a strong opening sentence about the product.
3. Organize into 2-3 SHORT paragraphs (use \\n\\n between paragraphs).
4. Include relevant keywords naturally throughout the text.
5. ONLY mention features/specs that appear in the data above. Do NOT invent anything.
6. Mention the brand name once or twice naturally.
7. End with a call to action or value statement.
8. Write in {country} English style.
9. Do NOT use superlatives like "best", "#1", "guaranteed".
10. Do NOT use HTML tags.
11. Make it DETAILED — cover material, usage, benefits, quantity, design.
12. AIM for 1000-1200 characters for the sweet spot.

Respond ONLY with valid JSON:
{{
  "description": "Your full description text here..."
}}

JSON:"""


# ---------------------------------------------------------------------------
#  Search Terms Agent
# ---------------------------------------------------------------------------

SEARCH_TERMS_PROMPT = """You are an Amazon backend search terms expert.

PRODUCT TITLE (already indexed by Amazon): "{title}"
BULLET POINTS (already indexed by Amazon): {bullets_text}

PRODUCT DETAILS:
  Product Type: {product_type}
  Brand: {brand}
  Material: {material}
  Color: {color}
  Size/Weight: {size}
  Target Audience: {target_audience}

TOP 50 MOST SEARCHED KEYWORDS FOR THIS PRODUCT (ranked by real Amazon search volume):
{keyword_list}

TASK: Generate backend search terms as COMMA-SEPARATED keyword phrases.
These are AI-suggested search terms based on keyword research data — include AS MANY relevant phrases as possible.

HOW TO DO THIS — READ CAREFULLY:
The keyword list above contains REAL customer search phrases for THIS product.
Your job is to pick the MOST RELEVANT keyword phrases and list them as search terms.

Step 1: Go through ALL 50 keyword phrases above — these are what customers ACTUALLY type. and skip those which are not relevant to the current product and title 
Step 2: Pick every phrase that is relevant to THIS specific product.
step 3: you can use the existing keywords in title and bullets and make sure the search terms and phrases are relevant to the product okay
Step 4: List them as COMMA-SEPARATED search phrases.
Step 6: Keep going until you've included ALL relevant phrases — aim for at least 300 characters.

EXAMPLE:
  If keyword data shows: "dumbbell set adjustable", "home gym weights", "rubber hex dumbbells",
  "exercise weights", "fitness training weights", "hand weights for women"

CRITICAL RULES:
1. Include AS MANY relevant phrases as possible — at least 300 characters, no upper limit.
2. Output format: lowercase comma-separated phrases (e.g. "phrase one, phrase two, phrase three").
3. Each phrase should be a meaningful 2-4 word search query from the keyword data above.
4. Do NOT just list individual disconnected words — keep phrases together.
6. Your phrases must come FROM the keyword data above that are relevant to the product  — do NOT invent random phrases.
7. No brand names (Amazon policy).
8. Every phrase must be relevant to THIS specific product.
9. MORE relevant phrases = BETTER. Do not stop at just a few.

Respond ONLY with valid JSON:
{{
  "search_terms": "phrase one, phrase two, phrase three, ..."
}}

JSON:"""


class BulletPointAgent:
    """Generates 5 Amazon bullet points from real product data + keywords."""

    def __init__(self, llm):
        self.llm = llm

    def run(
        self,
        product: Dict[str, Any],
        image_analysis: Dict[str, Any],
        keywords: List[Dict[str, Any]],
    ) -> List[str]:
        # Build keyword list string — sort by search volume for better prioritization
        sorted_kw = sorted(keywords, key=lambda k: float(k.get('score', 0)), reverse=True)
        kw_lines = []
        for kw in sorted_kw[:50]:
            vol = float(kw.get('score', 0))
            kw_lines.append(f"  - {kw['keyword']} (search volume: {vol:.0f})")
        keyword_list = "\n".join(kw_lines) if kw_lines else "  (no keywords available)"

        existing_bullets = product.get('bullet_points', [])
        bullets_str = "\n".join(f"  {i+1}. {b}" for i, b in enumerate(existing_bullets)) if existing_bullets else "  (none)"

        prompt = BULLET_POINT_PROMPT.format(
            title=product.get('title', ''),
            brand=image_analysis.get('brand') or product.get('raw_row', {}).get('Brand', '') or 'Unknown',
            product_type=image_analysis.get('product_type') or 'Unknown',
            country=product.get('country', 'US'),
            colors=', '.join(image_analysis.get('colors') or []) or 'N/A',
            size=image_analysis.get('size') or 'N/A',
            quantity=image_analysis.get('quantity') or 'N/A',
            material=image_analysis.get('material') or 'N/A',
            ai_features=', '.join((image_analysis.get('key_features') or [])[:8]) or 'N/A',
            existing_bullets=bullets_str,
            usp=product.get('usp', '') or 'N/A',
            manual=product.get('manual', '') or 'N/A',
            keyword_list=keyword_list,
        )

        for attempt in range(3):
            temp = 0.2 + (attempt * 0.1)
            raw = self.llm.generate(prompt, temperature=temp, max_tokens=2000)
            obj = extract_json_object(raw or "")

            if obj and 'bullet_points' in obj:
                bullets = obj['bullet_points']
                if isinstance(bullets, list) and len(bullets) >= 3:
                    # Enforce 200 char limit
                    clean = []
                    for b in bullets[:5]:
                        b = str(b).strip()
                        if len(b) > 200:
                            b = b[:197] + "..."
                        clean.append(b)
                    # Pad to 5 if needed
                    while len(clean) < 5:
                        clean.append("")
                    return clean

            prompt += f"\n\nAttempt {attempt+1} failed. Return ONLY valid JSON with exactly 5 bullet points."

        # Fallback: return existing bullets padded to 5
        fallback = list(existing_bullets[:5])
        while len(fallback) < 5:
            fallback.append("")
        return fallback


class DescriptionAgent:
    """Generates Amazon product description from real product data + keywords."""

    def __init__(self, llm):
        self.llm = llm

    def run(
        self,
        product: Dict[str, Any],
        image_analysis: Dict[str, Any],
        keywords: List[Dict[str, Any]],
    ) -> str:
        sorted_kw = sorted(keywords, key=lambda k: float(k.get('score', 0)), reverse=True)
        kw_lines = [f"  - {kw['keyword']} (search volume: {kw.get('score', 0):.0f})" for kw in sorted_kw[:50]]
        keyword_list = "\n".join(kw_lines) if kw_lines else "  (no keywords available)"

        key_features = image_analysis.get('key_features') or []
        features_str = ", ".join(key_features[:6]) if key_features else "N/A"

        existing_bullets = product.get('bullet_points', [])
        bullets_str = "\n".join(f"  {i+1}. {b}" for i, b in enumerate(existing_bullets)) if existing_bullets else "  (none)"

        prompt = DESCRIPTION_PROMPT.format(
            title=product.get('title', ''),
            brand=image_analysis.get('brand') or product.get('raw_row', {}).get('Brand', '') or 'Unknown',
            product_type=image_analysis.get('product_type') or 'Unknown',
            country=product.get('country', 'US'),
            ai_description=image_analysis.get('ai_description', '') or 'N/A',
            key_features=features_str,
            existing_bullets=bullets_str,
            existing_description=product.get('description', '')[:300] or 'N/A',
            usp=product.get('usp', '') or 'N/A',
            manual=product.get('manual', '') or 'N/A',
            keyword_list=keyword_list,
        )

        for attempt in range(3):
            temp = 0.2 + (attempt * 0.1)
            raw = self.llm.generate(prompt, temperature=temp, max_tokens=2000)
            obj = extract_json_object(raw or "")

            if obj and 'description' in obj:
                desc = str(obj['description']).strip()
                if len(desc) >= 600:  # Accept 600+ (allow some slack below 800)
                    # Enforce 1500 char max
                    if len(desc) > 1500:
                        # Truncate at last sentence before 1500
                        cut = desc[:1500]
                        last_period = cut.rfind('.')
                        if last_period > 800:
                            desc = cut[:last_period + 1]
                        else:
                            desc = cut
                    return desc

            prompt += f"\n\nAttempt {attempt+1} failed. Return valid JSON with 'description' that is 800-1500 characters long. Current was too short."

        # Fallback
        return product.get('description', '') or image_analysis.get('ai_description', '') or ''


class SearchTermsAgent:
    """Generates Amazon backend search terms using LLM-powered keyword chaining.
    
    Strategy: Keywords from vector DB are category-relevant but may include
    other product variants (wrong weight/size/color). The LLM must:
    1. Filter OUT keywords with specs that don't match THIS product
    2. Chain the remaining keywords into meaningful phrases ≤200 chars
    3. Weave in product-specific attributes (brand, material, color, size)
    """

    def __init__(self, llm):
        self.llm = llm

    def _extract_product_attributes(
        self,
        title: str,
        bullets: List[str],
        image_analysis: Dict[str, Any],
    ) -> str:
        """Pull every distinguishing product attribute from all available data."""
        ia = image_analysis or {}
        attrs: List[str] = []

        brand = ia.get('brand') or ''
        if brand and brand.lower() not in ('unknown', 'n/a', ''):
            attrs.append(f"Brand: {brand}")

        material = ia.get('material') or ''
        if material and material.lower() not in ('unknown', 'n/a', ''):
            attrs.append(f"Material: {material}")

        colors = ia.get('colors') or []
        if colors:
            attrs.append(f"Colors: {', '.join(colors)}")

        size = ia.get('size') or ''
        if size and size.lower() not in ('unknown', 'n/a', ''):
            attrs.append(f"Size/Weight: {size}")

        quantity = ia.get('quantity') or ''
        if quantity and quantity.lower() not in ('unknown', 'n/a', ''):
            attrs.append(f"Quantity/Pack: {quantity}")

        product_type = ia.get('product_type') or ''
        if product_type and product_type.lower() not in ('unknown', 'n/a', ''):
            attrs.append(f"Product type: {product_type}")

        key_features = ia.get('key_features') or []
        if key_features:
            attrs.append(f"Key features: {', '.join(key_features[:6])}")

        usp = ia.get('usp') or ''
        if usp and usp.lower() not in ('unknown', 'n/a', ''):
            attrs.append(f"USP: {usp}")

        # Extract distinguishing words from bullets (material, finish, use-case hints)
        if bullets:
            bullet_text = ' '.join(bullets[:5])
            attrs.append(f"Bullet highlights: {bullet_text[:300]}")

        return "\n".join(attrs) if attrs else "No additional attributes available."

    def run(
        self,
        title: str,
        bullets: List[str],
        keywords: List[Dict[str, Any]],
        image_analysis: Dict[str, Any] = None,
    ) -> str:
        MAX_CHARS = 200

        # Keywords come from a dedicated broader sweep (up to 150) already
        # sorted by volume. Let LLM filter variant mismatches.
        sorted_kw = sorted(keywords, key=lambda k: float(k.get('score', 0)), reverse=True)
        top_pool = sorted_kw[:150]

        if not top_pool:
            return ""

        # Build keyword list for the LLM
        kw_lines = []
        for i, kw in enumerate(top_pool, 1):
            phrase = str(kw.get('keyword', '')).strip()
            vol = float(kw.get('score', 0))
            kw_lines.append(f"{i}. {phrase} (vol: {vol:.0f})")
        keyword_list = "\n".join(kw_lines)

        # Extract rich product context from image analysis + bullets
        product_attributes = self._extract_product_attributes(title, bullets, image_analysis or {})

        prompt = f"""You are an Amazon backend search term expert with deep listing optimization experience.

═══ THIS PRODUCT ═══
TITLE: "{title}"

PRODUCT SPECIFICATIONS (from image analysis & listing data):
{product_attributes}

═══ KEYWORD POOL (from database, sorted by search volume) ═══
{keyword_list}

═══ YOUR TASK ═══
Create a backend search term string (max {MAX_CHARS} characters) by:
1. SELECTING only keywords that match THIS EXACT product (use specs above to filter out wrong variants)
2. CHAINING selected keywords into meaningful search phrases using ONLY words from the keyword pool

═══ CRITICAL: VARIANT FILTERING ═══
The keyword pool above comes from a category-level database. It contains keywords for
the ENTIRE category, including OTHER product variants that are NOT this product.

You MUST EXCLUDE keywords that specify a DIFFERENT:
- Weight/size: If this product is 3kg → EXCLUDE "2kg dumbbells", "4kg weights", "1kg", "5kg", "10kg"
  (Only include THIS product's weight: 3kg)
- Color: If this product is black → EXCLUDE "pink dumbbells", "red weights"
  (Only include THIS product's color)
- Material: If this product is neoprene → EXCLUDE "cast iron dumbbells" (unless it actually is cast iron)
- Gender: If product is unisex → you CAN include both "women" and "men" terms
- Count: If this is a pair → EXCLUDE "single dumbbell", "set of 6"

KEEP keywords that are:
✓ Generic (no conflicting spec): "dumbbells set", "hand weights", "gym equipment"
✓ Matching THIS product's specs: "3kg dumbbells", "neoprene weights"  
✓ Describing features/use: "non slip grip", "home gym", "exercise weights"
✓ Alternate spellings: "dumb bells", "dumbells", "dumbell"
✓ Brand-related: brand name + product type

═══ HOW TO CHAIN ═══
After filtering, chain the remaining keywords into flowing mini-phrases (2-5 words each):
- Start from highest volume keywords
- Connect related words into phrases a customer would actually search
- ONLY use words that appear in the KEYWORD POOL above.
  Do NOT inject brand, material, color, or any word that isn't already in a keyword.
  If the keyword pool contains "neoprene dumbbells" → use it. If it doesn't → don't add "neoprene".
- Words CAN repeat to form different meaningful phrases, but limit any single word
  to at most 2-3 occurrences. The output should NOT look spammy or overly repetitive.
- No commas, no punctuation — just space-separated flowing phrases
- All lowercase

GOOD example (for a 3kg neoprene dumbbell, assuming keyword pool contains "neoprene dumbbells", "kakss dumbbells" etc.):
"dumbbells set 3kg pair neoprene dumbbells hexagonal non slip grip weights women home gym equipment exercise dumbbell 3kg weights ladies dumb bells hand weights fitness dumbell set gym"

Notice:
- ONLY 3kg appears (the actual product weight). NO 2kg/4kg/1kg/5kg.
- "neoprene" and "kakss" appear ONLY because they were in the keyword pool.
- "dumbbells" appears 2-3x max, forming different phrases each time — not spammy.
- These are BACKEND search terms (hidden, not customer-facing) — focus on maximizing keyword coverage for Amazon's indexing algorithm.

BAD example 1:
"dumbbells set 3kg weights women 2kg 4kg 1kg 5kg dumbbells pair"
↑ WRONG — includes 2kg, 4kg, 1kg, 5kg which are DIFFERENT products!

BAD example 2:
"dumbbells set dumbbells weights dumbbells pair dumbbells women dumbbells gym dumbbells"
↑ WRONG — "dumbbells" repeated 6 times, looks spammy and wastes character space!

CRITICAL: Must be ≤ {MAX_CHARS} characters total. Only lowercase.

Return ONLY valid JSON:
{{
  "search_terms": "your chained search term string here"
}}

JSON:"""

        for attempt in range(3):
            temp = 0.15 + (attempt * 0.1)
            raw = self.llm.generate(prompt, temperature=temp, max_tokens=1000)
            obj = extract_json_object(raw or "")

            if obj and 'search_terms' in obj:
                terms = str(obj['search_terms']).strip().lower()
                # Clean: keep only alphanumeric and spaces
                terms = ''.join(c if c.isalnum() or c == ' ' else ' ' for c in terms)
                terms = ' '.join(terms.split())  # normalize whitespace

                # Enforce 200 char limit — cut at last full word
                if len(terms) > MAX_CHARS:
                    cut = terms[:MAX_CHARS]
                    last_space = cut.rfind(' ')
                    if last_space > MAX_CHARS * 0.7:
                        terms = cut[:last_space].strip()
                    else:
                        terms = cut.strip()

                if len(terms) >= 50:  # sanity check
                    return terms

            prompt += f"\n\nAttempt {attempt+1} failed. Return ONLY valid JSON with 'search_terms'. Must be ≤ {MAX_CHARS} chars, lowercase, meaningful phrases. EXCLUDE keywords with specs that don't match this product."

        # Fallback: chain keyword phrases directly
        return self._fallback_chain(top_pool, MAX_CHARS)

    def _fallback_chain(
        self, sorted_kw: List[Dict[str, Any]], max_chars: int,
    ) -> str:
        """Fallback: chain top keyword phrases directly, keeping meaningful groups."""
        chain_parts: List[str] = []
        current_len = 0

        for kw in sorted_kw:
            phrase = str(kw.get('keyword', '')).strip().lower()
            phrase = ''.join(c if c.isalnum() or c == ' ' else ' ' for c in phrase)
            phrase = ' '.join(phrase.split())
            if not phrase:
                continue

            test_len = current_len + len(phrase) + (1 if chain_parts else 0)
            if test_len > max_chars:
                break

            chain_parts.append(phrase)
            current_len = test_len

        return ' '.join(chain_parts)


# ---------------------------------------------------------------------------
#  How To Sell Agent
# ---------------------------------------------------------------------------

HOW_TO_SELL_PROMPT = """You are a senior Amazon marketplace strategist.

PRODUCT: {title}
BRAND: {brand}
PRODUCT TYPE: {product_type}
MATERIAL: {material}
TARGET AUDIENCE: {target_audience}
KEY FEATURES: {key_features}

COMPETITIVE ADVANTAGES (from image analysis):
{comparison_points}

TOP SEARCH KEYWORDS (what customers search for):
{keyword_list}

TASK: Write a concise "How To Sell" strategy for this SPECIFIC product.
This should be actionable advice for the seller in 3-5 bullet points.

Cover:
1. PRIMARY SELLING ANGLE — what makes this product stand out (based on the competitive advantages above)
2. TARGET CUSTOMER — who to market to, based on the search keywords and audience data
3. KEY DIFFERENTIATORS — what to emphasize in ads and A+ content vs competitors
4. PRICING STRATEGY HINT — positioning (budget-friendly starter, mid-range, premium)
5. SEASONAL/TREND NOTE — if relevant (e.g. "New Year fitness resolution season")

Be SPECIFIC to this product. Do NOT give generic e-commerce advice.
Keep total response under 500 characters.

Respond ONLY with valid JSON:
{{
  "how_to_sell": "• Point 1\n• Point 2\n• Point 3\n• Point 4\n• Point 5"
}}

JSON:"""


class HowToSellAgent:
    """Generates product-specific selling strategy from real data."""

    def __init__(self, llm):
        self.llm = llm

    def run(
        self,
        product: Dict[str, Any],
        image_analysis: Dict[str, Any],
        keywords: List[Dict[str, Any]],
        optimized_title: str,
    ) -> str:
        sorted_kw = sorted(keywords, key=lambda k: float(k.get('score', 0)), reverse=True)
        kw_lines = [f"  - {kw['keyword']} (volume: {float(kw.get('score',0)):.0f})" for kw in sorted_kw[:50]]
        keyword_list = "\n".join(kw_lines) if kw_lines else "  (none)"

        # Build comparison points text
        comp_points = image_analysis.get('comparison_points') or []
        comp_lines = []
        for cp in comp_points[:4]:
            our = cp.get('our_benefit', '')
            their = cp.get('competitor_issue', '')
            if our:
                comp_lines.append(f"  ✅ Us: {our}")
            if their:
                comp_lines.append(f"  ❌ Them: {their}")
        comparison_text = "\n".join(comp_lines) if comp_lines else "  (none available)"

        key_features = image_analysis.get('key_features') or []

        prompt = HOW_TO_SELL_PROMPT.format(
            title=optimized_title,
            brand=image_analysis.get('brand') or product.get('raw_row', {}).get('Brand', '') or '',
            product_type=image_analysis.get('product_type', ''),
            material=image_analysis.get('material', ''),
            target_audience=image_analysis.get('target_audience', ''),
            key_features=', '.join(key_features[:5]) or 'N/A',
            comparison_points=comparison_text,
            keyword_list=keyword_list,
        )

        for attempt in range(3):
            temp = 0.2 + (attempt * 0.1)
            raw = self.llm.generate(prompt, temperature=temp, max_tokens=1000)
            obj = extract_json_object(raw or "")

            if obj and 'how_to_sell' in obj:
                text = str(obj['how_to_sell']).strip()
                if len(text) >= 50:
                    if len(text) > 500:
                        text = text[:497] + "..."
                    return text

            prompt += f"\n\nAttempt {attempt+1} failed. Return valid JSON with 'how_to_sell' ≤ 500 chars."

        return ""
