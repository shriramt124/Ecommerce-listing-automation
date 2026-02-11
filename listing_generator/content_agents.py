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
    """Generates Amazon backend search terms — words NOT already in title/bullets."""

    def __init__(self, llm):
        self.llm = llm

    def run(
        self,
        title: str,
        bullets: List[str],
        keywords: List[Dict[str, Any]],
        image_analysis: Dict[str, Any] = None,
    ) -> str:
        sorted_kw = sorted(keywords, key=lambda k: float(k.get('score', 0)), reverse=True)
        # Give the LLM all top 50 keyword phrases to work with
        kw_lines = [f"  - {kw['keyword']} (volume: {float(kw.get('score',0)):.0f})" for kw in sorted_kw[:50]]
        keyword_list = "\n".join(kw_lines) if kw_lines else "  (no keywords available)"

        bullets_text = " | ".join(b for b in bullets if b)

        # Build set of words already in title + bullets (for post-processing cleanup)
        already_indexed = set()
        for w in title.lower().split():
            clean = ''.join(c for c in w if c.isalnum())
            if clean and len(clean) > 1:
                already_indexed.add(clean)
        for b in bullets:
            for w in b.lower().split():
                clean = ''.join(c for c in w if c.isalnum())
                if clean and len(clean) > 1:
                    already_indexed.add(clean)

        ia = image_analysis or {}
        prompt = SEARCH_TERMS_PROMPT.format(
            title=title,
            bullets_text=bullets_text or "(none)",
            keyword_list=keyword_list,
            product_type=ia.get('product_type', ''),
            brand=ia.get('brand', ''),
            material=ia.get('material', ''),
            color=', '.join(ia.get('colors') or []) or '',
            size=ia.get('size', ''),
            target_audience=ia.get('target_audience', ''),
        )

        for attempt in range(3):
            temp = 0.2 + (attempt * 0.1)
            raw = self.llm.generate(prompt, temperature=temp, max_tokens=2000)
            obj = extract_json_object(raw or "")

            if obj and 'search_terms' in obj:
                terms = str(obj['search_terms']).strip().lower()
                # Clean: allow alphanumeric, spaces, and commas only
                terms = ''.join(c if c.isalnum() or c in (' ', ',') else ' ' for c in terms)
                # Normalize: split into comma-separated phrases, clean each
                raw_phrases = [p.strip() for p in terms.split(',') if p.strip()]

                # Filter out phrases where ALL words are already in title/bullets
                filtered_phrases = []
                for phrase in raw_phrases:
                    phrase_words = phrase.split()
                    new_words = [w for w in phrase_words if ''.join(c for c in w if c.isalnum()) not in already_indexed]
                    if new_words:  # at least one new word in this phrase
                        filtered_phrases.append(phrase)

                # Deduplicate phrases
                seen_phrases = set()
                unique_phrases = []
                for phrase in filtered_phrases:
                    if phrase not in seen_phrases:
                        seen_phrases.add(phrase)
                        unique_phrases.append(phrase)

                terms = ', '.join(unique_phrases)

                if terms:
                    return terms

            prompt += f"\n\nAttempt {attempt+1} failed. Return valid JSON with 'search_terms' key. Include as many relevant keyword phrases as possible."

        # Fallback: use keyword phrases directly (comma-separated), skip if all words in title/bullets
        fallback_phrases = []
        seen_fb = set()
        for kw in sorted_kw[:50]:
            phrase = kw['keyword'].lower().strip()
            if phrase in seen_fb:
                continue
            seen_fb.add(phrase)
            phrase_words = phrase.split()
            new_words = [w for w in phrase_words if ''.join(c for c in w if c.isalnum()) not in already_indexed]
            if new_words:
                fallback_phrases.append(phrase)
        return ', '.join(fallback_phrases)


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
