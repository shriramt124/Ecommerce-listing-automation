"""Agent classes for the modular agentic pipeline.

Each agent has a single responsibility and returns a validated JSON structure.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from agentic_llm import OllamaLLM, extract_json_object
from agentic_validators import (
    validate_category_info,
    validate_concept_eval,
    validate_keyword_selection,
    validate_query_suggestions,
    validate_title_draft,
)


@dataclass
class AgentResult:
    ok: bool
    value: Dict[str, Any]
    errors: List[str]
    raw: Optional[str] = None


class BaseJsonAgent:
    def __init__(self, llm: OllamaLLM, *, name: str):
        self.llm = llm
        self.name = name

    def _run_json(
        self,
        prompt: str,
        *,
        temperature: float,
        max_tokens: int,
        validator,
        retries: int = 2,
    ) -> AgentResult:
        last_raw: Optional[str] = None
        last_errors: List[str] = []

        for attempt in range(retries + 1):
            raw = self.llm.generate(prompt, temperature=temperature, max_tokens=max_tokens)
            last_raw = raw
            obj = extract_json_object(raw or "")
            ok, errors = validator(obj)
            if ok and isinstance(obj, dict):
                return AgentResult(ok=True, value=obj, errors=[], raw=raw)

            last_errors = errors or ["invalid JSON output"]
            # Repair prompt on retry
            prompt = (
                prompt
                + "\n\nYour previous output was invalid. Fix it and output ONLY valid JSON matching the schema."
            )

        return AgentResult(ok=False, value={}, errors=last_errors, raw=last_raw)


class CategoryDetectorAgent(BaseJsonAgent):
    def __init__(self, llm: OllamaLLM):
        super().__init__(llm, name="CategoryDetector")

    def run(self, title: str, truth: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""You are an Amazon product categorization expert.

PRODUCT TITLE: \"{title}\"

PRODUCT TRUTH:
- Brand: {truth.get('brand', 'Unknown')}
- Product: {truth.get('product', 'Unknown')}
- Size: {truth.get('size', 'N/A')}
- Color: {truth.get('color', 'N/A')}
- Count: {truth.get('count', 'N/A')}

TASK: Analyze this product and identify:
1. Main category (e.g., home_storage, automotive, electronics, furniture)
2. Subcategory (e.g., garbage_bags, shock_absorbers, phone_cases)
3. Key attributes that drive purchase decisions
4. What customers typically search for FIRST when looking for this product

Respond ONLY with valid JSON:
{{
  \"category\": \"main category name\",
  \"subcategory\": \"specific product type\",
  \"key_attributes\": [\"attr1\", \"attr2\"],
  \"search_priorities\": [\"first\", \"second\", \"third\"],
  \"color_important\": true
}}

JSON:"""

        res = self._run_json(
            prompt,
            temperature=0.1,
            max_tokens=300,
            validator=validate_category_info,
            retries=2,
        )

        if res.ok:
            return res.value

        return {
            "category": "general",
            "subcategory": "unknown",
            "key_attributes": [],
            "search_priorities": [],
            "color_important": False,
        }


class ConceptEvaluatorAgent(BaseJsonAgent):
    def __init__(self, llm: OllamaLLM):
        super().__init__(llm, name="ConceptEvaluator")

    def run(self, *, concept: str, concept_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""You are an Amazon keyword optimization expert.

CONCEPT TO EVALUATE: \"{concept}\" (Type: {concept_type})

PRODUCT CONTEXT:
- Product: {context.get('product', 'Unknown')}
- Brand: {context.get('brand', 'N/A')}
- Category: {context.get('category', 'general')}
- Current title concepts: {context.get('existing_concepts', [])}

TASK: Should this concept be KEPT in the title?

RULES:
- \"Premium\": Keep if product is high-end OR if \"premium\" is a common search term for this category
- \"Scented\": ALWAYS keep for fragrance products - it's a TOP search term even with specific fragrance mentioned
- Quality markers (Deluxe, Superior): Usually remove unless category-relevant
- Generic terms: Remove if they add no search value

Respond ONLY with valid JSON:
{{
  \"keep\": true,
  \"value_score\": 0.0,
  \"position\": \"zone_b\",
  \"reason\": \"brief\"
}}

JSON:"""

        res = self._run_json(
            prompt,
            temperature=0.1,
            max_tokens=220,
            validator=validate_concept_eval,
            retries=2,
        )

        if res.ok:
            return res.value

        return {"keep": True, "value_score": 0.5, "position": "zone_b", "reason": "default"}


class QueryPlannerAgent(BaseJsonAgent):
    def __init__(self, llm: OllamaLLM):
        super().__init__(llm, name="QueryPlanner")
        
        # Universal product synonyms dictionary
        self.category_synonyms = {
            'garbage_bags': ['garbage bags', 'trash bags', 'trash can liners', 'waste bags', 'dustbin bags', 'rubbish bags'],
            'phone_cases': ['phone cases', 'phone covers', 'phone protectors', 'phone sleeves', 'mobile cases'],
            'car_parts': ['car parts', 'auto parts', 'automotive parts', 'vehicle parts', 'car accessories'],
            'electronics': ['electronics', 'electronic devices', 'gadgets', 'tech products', 'electronic items'],
            'clothing': ['clothing', 'apparel', 'garments', 'wear', 'fashion items'],
            'furniture': ['furniture', 'home furniture', 'home decor', 'household items'],
            'kitchen': ['kitchen items', 'kitchen supplies', 'cooking items', 'kitchen utensils'],
            'bathroom': ['bathroom items', 'bathroom supplies', 'bath accessories'],
            'bedroom': ['bedroom items', 'bedroom accessories', 'sleep essentials'],
            'home_storage': ['storage items', 'storage solutions', 'organizers', 'storage containers'],
            'automotive': ['automotive parts', 'car accessories', 'vehicle parts', 'auto parts'],
            'health_beauty': ['health products', 'beauty items', 'personal care', 'cosmetic products'],
            'sports_fitness': ['sports equipment', 'fitness gear', 'exercise equipment', 'athletic items'],
            'toys_games': ['toys', 'games', 'play items', 'children products'],
            'books': ['books', 'reading materials', 'literature', 'publications'],
            'home_garden': ['home items', 'garden supplies', 'outdoor products', 'household goods'],
            'baby': ['baby products', 'infant items', 'baby gear', 'newborn products'],
            'office_products': ['office supplies', 'work items', 'business products', 'office equipment'],
        }

        # Common attributes across categories
        self.common_attributes = [
            'premium', 'deluxe', 'luxury', 'professional', 'heavy duty', 'durable',
            'waterproof', 'water resistant', 'eco friendly', 'biodegradable', 'reusable',
            'scented', 'unscented', 'large', 'medium', 'small', 'extra large', 'jumbo',
            'compact', 'portable', 'wireless', 'bluetooth', 'usb', 'rechargeable',
            'energy efficient', 'smart', 'automatic', 'manual', 'digital', 'analog'

        ]

        # Size and dimension patterns
        self.size_patterns = ['large', 'medium', 'small', 'extra large', 'jumbo', 'compact', 'mini', 'full size']
        self.material_patterns = ['plastic', 'metal', 'wood', 'fabric', 'leather', 'cotton', 'polyester', 'stainless steel']

    def _extract_product_attributes(self, title: str, truth: Dict[str, Any], category_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured product attributes from title and truth."""
        brand = str(truth.get("brand", "")).strip().lower()
        product = str(truth.get("product", "")).strip().lower()
        category = str(category_info.get("category", "general")).strip().lower()
        subcategory = str(category_info.get("subcategory", "unknown")).strip().lower()
        color = str(truth.get("color", "")).strip().lower()
        size = str(truth.get("size", "")).strip().lower()
        dimension = str(truth.get("dimension", "")).strip().lower()
        material = str(truth.get("material", "")).strip().lower()
        count = str(truth.get("count", "")).strip().lower()
        
        # Extract attributes from title concepts
        title_lower = title.lower()
        attributes = []
        
        # Common attribute patterns
        if "scented" in title_lower or "scent" in title_lower:
            attributes.append("scented")
        if "premium" in title_lower or "deluxe" in title_lower:
            attributes.append("premium")
        if "heavy duty" in title_lower:
            attributes.append("heavy duty")
        if "waterproof" in title_lower or "water resistant" in title_lower:
            attributes.append("waterproof")
        if "eco" in title_lower or "biodegradable" in title_lower:
            attributes.append("eco friendly")
        if "wireless" in title_lower:
            attributes.append("wireless")
        if "bluetooth" in title_lower:
            attributes.append("bluetooth")
        if "usb" in title_lower:
            attributes.append("usb")
        if "rechargeable" in title_lower:
            attributes.append("rechargeable")
        if "smart" in title_lower:
            attributes.append("smart")
        if "automatic" in title_lower:
            attributes.append("automatic")
        if "digital" in title_lower:
            attributes.append("digital")
        
        # Extract size descriptors if not in truth
        if not size:
            for size_word in self.size_patterns:
                if size_word in title_lower:
                    size = size_word
                    break
        
        # Extract material if not in truth
        if not material:
            for material_word in self.material_patterns:
                if material_word in title_lower:
                    material = material_word
                    break
        
        # Extract use cases/locations
        use_cases = []
        if "kitchen" in title_lower:
            use_cases.append("kitchen")
        if "bathroom" in title_lower:
            use_cases.append("bathroom")
        if "home" in title_lower:
            use_cases.append("home")
        if "office" in title_lower:
            use_cases.append("office")
        if "car" in title_lower:
            use_cases.append("car")
        if "outdoor" in title_lower:
            use_cases.append("outdoor")
        if "indoor" in title_lower:
            use_cases.append("indoor")
        if "bedroom" in title_lower:
            use_cases.append("bedroom")
        if "living room" in title_lower:
            use_cases.append("living room")
        
        # Generate synonyms based on category
        category_synonyms = self.category_synonyms.get(subcategory, 
                                                     self.category_synonyms.get(category, 
                                                                             [product or category or "products"]))
        
        return {
            'brand': brand,
            'product': product,
            'category': category,
            'subcategory': subcategory,
            'color': color,
            'size': size,
            'dimension': dimension,
            'material': material,
            'count': count,
            'attributes': attributes,
            'use_cases': use_cases,
            'category_synonyms': category_synonyms,
        }

    def _generate_systematic_queries(self, attrs: Dict[str, Any], existing_queries: List[str]) -> List[str]:
        """Generate systematic query combinations."""
        queries = []
        
        brand = attrs.get('brand', '')
        category = attrs.get('category', '')
        subcategory = attrs.get('subcategory', '')
        color = attrs.get('color', '')
        size = attrs.get('size', '')
        dimension = attrs.get('dimension', '')
        material = attrs.get('material', '')
        count = attrs.get('count', '')
        attributes = attrs.get('attributes', [])
        use_cases = attrs.get('use_cases', [])
        category_synonyms = attrs.get('category_synonyms', [category])
        
        existing_lower = {q.lower() for q in existing_queries}
        
        def add_query(query: str) -> None:
            """Add query if not duplicate and meets criteria."""
            if not query or len(query.split()) < 2:
                return
            query_clean = re.sub(r'\s+', ' ', query.strip().lower())
            if query_clean not in existing_lower and query_clean not in {q.lower() for q in queries}:
                queries.append(query_clean)
        
        # Rule 1: Core Brand + Category combinations
        for cat_syn in category_synonyms[:3]:  # Limit to avoid too many
            if brand and cat_syn:
                add_query(f"{brand} {cat_syn}")
        
        # Rule 2: Brand + Color + Category
        if brand and color and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{brand} {color} {cat_syn}")
                add_query(f"{color} {brand} {cat_syn}")
        
        # Rule 3: Category + Size/Dimension
        if size and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{cat_syn} {size} size")
                add_query(f"{cat_syn} {size}")
        
        if dimension and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{cat_syn} {dimension}")
                # Also try without spaces
                dim_no_space = re.sub(r'\s*([x×])\s*', r'\1', dimension.lower())
                if dim_no_space != dimension.lower():
                    add_query(f"{cat_syn} {dim_no_space}")
        
        # Rule 4: Color + Category + Size
        if color and size and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{color} {cat_syn} {size}")
        
        # Rule 5: Brand + Key Attributes + Category
        for attr in attributes[:3]:  # Limit attributes
            if brand and category_synonyms:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{brand} {attr} {cat_syn}")
                    add_query(f"{attr} {cat_syn}")
        
        # Rule 6: Category + Use Case
        for use_case in use_cases[:3]:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{cat_syn} {use_case}")
                add_query(f"{use_case} {cat_syn}")
        
        # Rule 7: Material + Category
        if material and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{material} {cat_syn}")
        
        # Rule 8: Long-tail variations
        if brand and color and size and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{brand} {color} {cat_syn} {size}")
        
        if brand and attributes and category_synonyms:
            for attr in attributes[:2]:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{brand} {cat_syn} {attr}")
        
        if color and attributes and category_synonyms:
            for attr in attributes[:2]:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{color} {attr} {cat_syn}")
        
        # Rule 9: Dimension + Material/Attribute combinations
        if dimension and (material or attributes) and category_synonyms:
            extra = material if material else attributes[0] if attributes else ""
            for cat_syn in category_synonyms[:2]:
                add_query(f"{cat_syn} {dimension} {extra}")
        
        # Rule 10: Category synonyms without brand (broader searches)
        for cat_syn in category_synonyms[1:4]:  # Skip first (probably already used)
            add_query(cat_syn)
            if size:
                add_query(f"{cat_syn} {size}")
            if color:
                add_query(f"{color} {cat_syn}")
            if material:
                add_query(f"{material} {cat_syn}")
        
        # Rule 11: Attribute-only queries for broader matching
        for attr in attributes[:2]:
            add_query(f"{attr} {category_synonyms[0]}")
        
        # Rule 12: Size + Material combinations
        if size and material:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{size} {material} {cat_syn}")
        
        # Rule 13: Color + Material combinations
        if color and material:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{color} {material} {cat_syn}")
        
        # Rule 14: Use case + Size combinations
        if use_cases and size:
            for use_case in use_cases[:2]:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{use_case} {size} {cat_syn}")
        
        # Rule 15: Count/Pack size related queries
        if count and category_synonyms:
            # Extract numbers from count
            numbers = re.findall(r'\d+', count)
            if numbers:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{numbers[0]} pack {cat_syn}")
                    add_query(f"{cat_syn} {numbers[0]} pack")
        
        return queries[:25]  # Increased limit for more comprehensive coverage

    def _enhance_with_ai(self, base_queries: List[str], attrs: Dict[str, Any], category_info: Dict[str, Any]) -> List[str]:
        """Use AI to enhance and add more sophisticated queries."""
        if not self.llm:
            return []
            
        # Prepare context for AI enhancement
        prompt = f"""You are helping retrieve Amazon search keywords from a vector database.

PRODUCT CONTEXT:
- Category: {category_info.get('category','general')} / {category_info.get('subcategory','unknown')}
- Brand: {attrs.get('brand', 'N/A')}
- Product Type: {attrs.get('product', 'Unknown')}
- Key Attributes: {attrs.get('attributes', [])}
- Use Cases: {attrs.get('use_cases', [])}

BASE SYSTEMATIC QUERIES:
{chr(10).join([f"- {q}" for q in base_queries[:10]])}

TASK: Propose 3-5 ADDITIONAL sophisticated search queries that:
1. Use customer language and synonyms
2. Include relevant long-tail variations
3. Cover search intents not in base queries
4. Stay within the same product category

STRICT RULES:
- Only suggest queries relevant to this specific product type
- Avoid generic terms like "best", "top", "quality"
- Focus on specific search intents customers might use
- Each query should be 2-5 words

Respond ONLY JSON:
{{"queries": ["query1", "query2", "query3"]}}

JSON:"""

        res = self._run_json(
            prompt,
            temperature=0.3,
            max_tokens=200,
            validator=validate_query_suggestions,
            retries=1,
        )

        if res.ok:
            ai_queries = res.value.get("queries", []) or []
            # Filter and clean AI queries
            enhanced = []
            for q in ai_queries:
                clean_q = re.sub(r'\s+', ' ', str(q).strip().lower())
                if clean_q and len(clean_q.split()) >= 2:
                    enhanced.append(clean_q)
            return enhanced

        return []

    def run(
        self,
        *,
        base_title: str,
        truth: Dict[str, Any],
        category_info: Dict[str, Any],
        anchors: List[str],
        existing_queries: List[str],
        max_new: int = 8,
    ) -> List[str]:
        """Enhanced query planning with systematic generation."""
        # Extract structured product attributes
        attrs = self._extract_product_attributes(base_title, truth, category_info)
        
        # Generate systematic queries first
        systematic_queries = self._generate_systematic_queries(attrs, existing_queries)
        
        # Enhance with AI for sophisticated variations
        ai_queries = self._enhance_with_ai(systematic_queries, attrs, category_info)
        
        # Combine and deduplicate
        all_queries = systematic_queries + ai_queries
        
        # Enforce anchor requirements if provided
        if anchors:
            filtered_queries = []
            for q in all_queries:
                if all(anchor in q for anchor in anchors):
                    filtered_queries.append(q)
            all_queries = filtered_queries
        
        # Remove duplicates and limit
        seen = set()
        unique_queries = []
        for q in all_queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)

        return unique_queries[:max_new]
        

class KeywordSelectorAgent(BaseJsonAgent):
    def __init__(self, llm: OllamaLLM):
        super().__init__(llm, name="KeywordSelector")

        

    def run(
        self,
        *,
        existing_concepts: List[str],
        candidates: List[Dict[str, Any]],
        context: Dict[str, Any],
        max_select: int = 15,
    ) -> List[Dict[str, Any]]:
        # Only provide a bounded list to the model
        short = []
        for kw in candidates[:25]:
            short.append(
                {
                    "keyword": kw.get("keyword", ""),
                    "similarity": round(float(kw.get("similarity", 0) or 0.0), 3),
                    "score": round(float(kw.get("score", 0) or 0.0), 4),
                    "ad_units": round(float(kw.get("ad_units", 0) or 0.0), 1),
                    "ad_conv": round(float(kw.get("ad_conv", 0) or 0.0), 4),
                    "hit_queries": (kw.get("hit_queries") or [])[:3],
                }
            )

        allowed = {str(x.get("keyword", "")).strip().lower() for x in short if str(x.get("keyword", "")).strip()}

        prompt = f"""You are an Amazon search optimization expert.

PRODUCT: {context.get('product', 'Unknown')}
BRAND: {context.get('brand', 'N/A')}
CATEGORY: {context.get('category', 'general')}

CURRENT CONCEPTS IN TITLE:
{existing_concepts}

CANDIDATE KEYWORDS (ONLY choose from this list):
{json.dumps(short, indent=2)}

TASK: Select the TOP {max_select} keywords that:
1. Add NEW search value (not already in title)
2. Are highly relevant to this product
3. Would help customers find this product

STRICT RULES:
- You MUST ONLY select keywords that appear in the CANDIDATE KEYWORDS list.
- Do NOT invent any keyword.
- Reject cross-category leakage.

Respond ONLY JSON:
{{
  \"selected_keywords\": [
    {{\"keyword\": \"keyword1\", \"reason\": \"why\"}}
  ],
  \"rejected_count\": 0,
  \"rejection_reasons\": []
}}

JSON:"""

        res = self._run_json(
            prompt,
            temperature=0.1,
            max_tokens=450,
            validator=validate_keyword_selection,
            retries=2,
        )

        selected: List[Dict[str, Any]] = []
        if res.ok:
            for item in res.value.get("selected_keywords", []) or []:
                k = str(item.get("keyword", "")).strip()
                if not k:
                    continue
                if k.lower() not in allowed:
                    continue
                selected.append({"keyword": k, "reason": str(item.get("reason", "")).strip()})

        return selected[:max_select]


class TitleComposerAgent(BaseJsonAgent):
    def __init__(self, llm: OllamaLLM):
        super().__init__(llm, name="TitleComposer")

    def run(
        self,
        *,
        original_title: str,
        truth: Dict[str, Any],
        concepts: List[Dict[str, Any]],
        selected_keywords: List[Dict[str, Any]],
        category_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        concept_list = [f"- {c.get('text','')} ({c.get('type','unknown')})" for c in concepts]
        keyword_list = [f"- {k.get('keyword','')}" for k in selected_keywords]

        brand = str(truth.get("brand", "") or "").strip()
        if brand in {"N/A", "Unknown"}:
            brand = ""

        locked = truth.get("_locked", {}) or {}
        locked_count = str(locked.get("count_exact", "") or "")
        locked_dimension = str(locked.get("dimension_exact", "") or "")

        has_scented = bool(truth.get("fragrance")) or any(
            "scented" in str(c.get("text", "")).lower() for c in concepts
        )

        prompt = f"""You are an expert Amazon title optimization AI.

ORIGINAL TITLE (reference):
\"{original_title}\"

PRODUCT INFORMATION (from original):
- Brand: {brand if brand else '(No brand)'}
- Product Type: {truth.get('product', 'Unknown Product')}
- Size: {truth.get('size', '')}
- Color: {truth.get('color', '')}
- Count/Quantity: {truth.get('count', '')}
- Dimensions: {truth.get('dimension', '')}
- Material: {truth.get('material', '')}
- Features: {truth.get('features', [])}

LOCKED FACTS (copy EXACTLY, do not rewrite):
- Pack string: \"{locked_count}\"
- Dimension: \"{locked_dimension}\"

IS SCENTED/FRAGRANCE PRODUCT: {has_scented}

CATEGORY: {category_info.get('category', 'general')} / {category_info.get('subcategory', 'unknown')}
TOP SEARCH TERMS: {category_info.get('search_priorities', [])}

CONCEPTS FROM ORIGINAL TITLE (you may reuse/reorder):
{chr(10).join(concept_list)}

APPROVED KEYWORDS (ONLY choose from these if you add anything new):
{chr(10).join(keyword_list) if keyword_list else '- (none)'}

TASK: Produce a single optimized title.

STRICT RULES:
1. ONLY use words/concepts from ORIGINAL TITLE or APPROVED KEYWORDS.
2. Do NOT invent features/specs/compatibility.
3. NO pipes (|).
4. Brand appears ONLY ONCE.
5. Locked strings must be copied exactly if non-empty.
6. Target 180-200 chars, but do not pad.

PRIORITIZATION GUIDANCE (general, category-agnostic):
- Prefer *what customers search first*: core product terms + high-intent descriptors (as hinted by APPROVED KEYWORDS and TOP SEARCH TERMS).
- Put factual, high-precision attributes (size, pack/count, dimension) earlier than "variant" descriptors.
- Treat variant descriptors (fragrance/flavor/style) as lower-priority SEO unless APPROVED KEYWORDS strongly revolve around them; if included, place them later (end of title) rather than near the beginning.
- If a generic quality marker (e.g., Premium) adds no retrieval-backed search value, keep it later or omit it.

Output ONLY valid JSON:
{{
  \"full_title\": \"...\",
  \"char_count\": 0,
  \"zone_a\": \"...\",
  \"zone_b\": \"...\",
  \"zone_c\": \"...\",
  \"reasoning\": {{}}
}}

JSON:"""

        res = self._run_json(
            prompt,
            temperature=0.2,
            max_tokens=900,
            validator=validate_title_draft,
            retries=2,
        )

        if not res.ok:
            return {"full_title": original_title, "error": "AI failed"}

        title = str(res.value.get("full_title", "") or "").strip()
        title = title.replace(" | ", ", ").replace("|", ",")
        title = re.sub(r"\s+", " ", title).strip()
        res.value["full_title"] = title
        res.value["char_count"] = len(title)
        return res.value


class TitleExtenderAgent:
    def __init__(self, llm: OllamaLLM):
        self.llm = llm

    def run(
        self,
        *,
        title: str,
        truth: Dict[str, Any],
        selected_keywords: List[Dict[str, Any]],
        category_info: Dict[str, Any],
        target_length: int = 190,
    ) -> str:
        if len(title) >= target_length:
            return title

        chars_to_add = target_length - len(title)

        category = category_info.get("category", "general")
        search_priorities = category_info.get("search_priorities", [])
        key_attributes = category_info.get("key_attributes", [])
        product = truth.get("product", "")
        brand = truth.get("brand", "")
        kw_list = [kw.get("keyword", "") for kw in selected_keywords[:5]]

        prompt = f"""TASK: Add ~{chars_to_add} more characters to this Amazon product title.

PRODUCT CATEGORY: {category}
PRODUCT TYPE: {product}
BRAND: {brand}

CURRENT TITLE ({len(title)} chars):
{title}

ATTRIBUTES FROM ORIGINAL TITLE:
{', '.join(key_attributes) if key_attributes else 'see title above'}

APPROVED KEYWORDS (optional):
{kw_list}

STRICT RULES:
1. ONLY add synonyms/rephrasings of what's already in the title OR items from APPROVED KEYWORDS.
2. DO NOT invent features (no "Heavy Duty" etc unless already present).
3. DO NOT add compatibility not mentioned.
4. DO NOT repeat brand.
5. NO pipes.

Output ONLY the extended title (one line):"""

        raw = self.llm.generate(prompt, temperature=0.25, max_tokens=260)
        if not raw:
            return title

        extended = raw.strip().split("\n")[0].strip()
        if extended.startswith('"') and extended.endswith('"'):
            extended = extended[1:-1]
        if extended.startswith("'") and extended.endswith("'"):
            extended = extended[1:-1]

        extended = re.sub(r"\s+", " ", extended).strip()
        extended = extended.replace(" | ", ", ").replace("|", ",")

        # Hard cap 200
        if len(extended) > 200:
            extended = extended[:197]
            last_comma = extended.rfind(",")
            last_space = extended.rfind(" ")
            cut_point = max(last_comma, last_space)
            if cut_point > 150:
                extended = extended[:cut_point].strip()

        if len(extended) > len(title) and len(extended) <= 200:
            return extended

        return title
