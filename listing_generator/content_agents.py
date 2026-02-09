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
from agentic_llm import OpenAILLM


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

PRODUCT TITLE: "{title}"
BULLET POINTS: {bullets_text}

TOP KEYWORDS (from real Amazon search data):
{keyword_list}

TASK: Generate backend search terms for Amazon (max 200 characters total).

RULES:
1. Total length MUST be ≤ 200 characters (HARD LIMIT).
2. Use ONLY lowercase words separated by spaces. No commas, no punctuation.
3. Do NOT repeat any word that already appears in the title or bullet points above.
4. Include synonyms, alternate spellings, and related search terms.
5. Pull words from the keyword list that aren't already in the title/bullets.
6. No brand names (Amazon policy). No competitor names.
7. No offensive or misleading terms.
8. Do NOT repeat any word — each word should appear only ONCE.
9. Focus on words shoppers actually search for.

Example format: "heavy duty thick strong multipurpose household kitchen bathroom"

Respond ONLY with valid JSON:
{{
  "search_terms": "your search terms here..."
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
        for kw in sorted_kw[:20]:
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
        kw_lines = [f"  - {kw['keyword']} (search volume: {kw.get('score', 0):.0f})" for kw in sorted_kw[:15]]
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
    ) -> str:
        sorted_kw = sorted(keywords, key=lambda k: float(k.get('score', 0)), reverse=True)
        kw_lines = [f"  - {kw['keyword']}" for kw in sorted_kw[:25]]
        keyword_list = "\n".join(kw_lines) if kw_lines else "  (no keywords available)"

        bullets_text = " | ".join(b for b in bullets if b)

        prompt = SEARCH_TERMS_PROMPT.format(
            title=title,
            bullets_text=bullets_text or "(none)",
            keyword_list=keyword_list,
        )

        for attempt in range(3):
            temp = 0.2 + (attempt * 0.1)
            raw = self.llm.generate(prompt, temperature=temp, max_tokens=2000)
            obj = extract_json_object(raw or "")

            if obj and 'search_terms' in obj:
                terms = str(obj['search_terms']).strip().lower()
                # Remove punctuation except spaces
                terms = ''.join(c if c.isalnum() or c == ' ' else ' ' for c in terms)
                terms = ' '.join(terms.split())  # normalize spaces

                # Deduplicate words
                seen = set()
                unique = []
                for word in terms.split():
                    if word not in seen:
                        seen.add(word)
                        unique.append(word)
                terms = ' '.join(unique)

                # Enforce 200 char limit
                if len(terms) > 200:
                    words = terms.split()
                    trimmed = []
                    length = 0
                    for w in words:
                        if length + len(w) + 1 <= 200:
                            trimmed.append(w)
                            length += len(w) + 1
                        else:
                            break
                    terms = ' '.join(trimmed)

                if terms:
                    return terms

            prompt += f"\n\nAttempt {attempt+1} failed. Return valid JSON with 'search_terms' ≤ 200 chars."

        # Fallback: extract unique words from keywords not in title
        title_words = set(title.lower().split())
        fallback_words = []
        for kw in sorted_kw[:20]:
            for word in kw['keyword'].lower().split():
                if word not in title_words and word not in fallback_words and len(word) > 2:
                    fallback_words.append(word)
        return ' '.join(fallback_words[:30])[:200]
