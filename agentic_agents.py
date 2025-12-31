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
        retries: int = 3,
    ) -> AgentResult:
        last_raw: Optional[str] = None
        last_errors: List[str] = []

        for attempt in range(retries + 1):
            # Increase temperature on retries for better results
            attempt_temp = temperature + (attempt * 0.1)
            raw = self.llm.generate(prompt, temperature=attempt_temp, max_tokens=max_tokens)
            last_raw = raw
            
            # Debug: Check if LLM returned anything
            if not raw:
                last_errors = [f"LLM returned empty response (attempt {attempt + 1}/{retries + 1})"]
                continue
            
            obj = extract_json_object(raw or "")
            if not obj:
                last_errors = [f"Could not extract JSON from response (attempt {attempt + 1}/{retries + 1})"]
                continue
                
            ok, errors = validator(obj)
            if ok and isinstance(obj, dict):
                return AgentResult(ok=True, value=obj, errors=[], raw=raw)

            last_errors = errors or ["invalid JSON output"]
            # Repair prompt on retry with more explicit instructions
            prompt = (
                prompt
                + f"\n\nAttempt {attempt + 1} failed. Your output must be ONLY valid JSON, no explanations. Fix errors: {', '.join(last_errors[:3])}"
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

TASK: Analyze this product and provide SPECIFIC, ACTIONABLE categorization.

IMPORTANT: Be SPECIFIC, not generic. 
- Bad: "category": "home products", "subcategory": "general"
- Good: "category": "home_storage", "subcategory": "garbage_bags"

Examples of good categorization:
- Garbage Bags → category: "home_storage", subcategory: "garbage_bags"
- Phone Cases → category: "electronics_accessories", subcategory: "phone_cases"
- Brake Pads → category: "automotive", subcategory: "brake_parts"

Identify:
1. SPECIFIC main category (e.g., home_storage, automotive, electronics_accessories)
2. SPECIFIC subcategory that describes this exact product type
3. Key attributes customers care about MOST for this product
4. Top 3 search terms customers use when looking for this product (be specific, not generic)

Respond ONLY with valid JSON:
{{
  \"category\": \"specific_category_name\",
  \"subcategory\": \"specific_product_type\",
  \"key_attributes\": [\"most important attribute\", \"second most important\"],
  \"search_priorities\": [\"top search term 1\", \"top search term 2\", \"top search term 3\"],
  \"color_important\": true/false
}}

JSON:"""

        res = self._run_json(
            prompt,
            temperature=0.2,
            max_tokens=300,
            validator=validate_category_info,
            retries=3,
        )

        if res.ok:
            return res.value

        # Fallback with simpler, more direct prompt
        fallback_prompt = f"""What category is this product?

TITLE: "{title}"
PRODUCT TYPE: {truth.get('product', 'Unknown')}

Return JSON with category (like "home_storage", "automotive", "electronics") and subcategory:
{{"category": "...", "subcategory": "..."}}

JSON:"""
        
        fallback_res = self._run_json(
            fallback_prompt,
            temperature=0.3,
            max_tokens=150,
            validator=validate_category_info,
            retries=2,
        )
        
        if fallback_res.ok:
            category = fallback_res.value.get("category", "general")
            subcategory = fallback_res.value.get("subcategory", "unknown")
            return {
                "category": category,
                "subcategory": subcategory,
                "key_attributes": [],
                "search_priorities": [],
                "color_important": False,
            }

        # Final fallback - infer from product name
        title_lower = title.lower()
        product_lower = str(truth.get('product', '')).lower()
        if any(word in title_lower for word in ['garbage', 'trash', 'dustbin', 'waste']):
            return {
                "category": "home_storage",
                "subcategory": "garbage_bags", 
                "key_attributes": ["size", "color", "count"],
                "search_priorities": ["size", "count", "color"],
                "color_important": False,
            }
        elif any(word in title_lower for word in ['phone', 'case', 'cover']):
            return {
                "category": "electronics",
                "subcategory": "phone_cases",
                "key_attributes": ["model", "color", "protection"],
                "search_priorities": ["model", "color", "protection"],
                "color_important": True,
            }
        
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
        
        # Product type patterns for fallback extraction from title
        self.product_patterns = [
            (r'\b(garbage bags?)\b', 'garbage bags'),
            (r'\b(dustbin bags?)\b', 'dustbin bags'),
            (r'\b(trash bags?)\b', 'trash bags'),
            (r'\b(waste bags?)\b', 'waste bags'),
            (r'\b(bin bags?|bin liners?)\b', 'bin bags'),
            (r'\b(car trash bin)\b', 'car trash bin'),
            (r'\b(phone cases?|phone covers?|mobile cases?)\b', 'phone cases'),
            (r'\b(handlebar|handlebars)\b', 'handlebar'),
            (r'\b(shock absorber)\b', 'shock absorber'),
            (r'\b(brake pad|brake pads)\b', 'brake pads'),
            (r'\b(clutch lever)\b', 'clutch lever'),
            (r'\b(side mirror|rear mirror|rearview mirror)\b', 'mirror'),
            (r'\b(foot rest|footrest|foot peg)\b', 'foot rest'),
            (r'\b(seat cover|saddle cover)\b', 'seat cover'),
            (r'\b(mud guard|mudguard|fender)\b', 'mudguard'),
        ]

    def _extract_product_from_title(self, title: str) -> str:
        """Extract actual product type from title when truth.product is generic."""
        title_lower = title.lower()
        for pattern, product_name in self.product_patterns:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return product_name
        return ""

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
        
        # IMPORTANT: Detect and reject generic placeholder values for product
        generic_values = {"product", "products", "item", "items", "unknown", "n/a", "na", ""}
        if product in generic_values:
            # Try to extract actual product type from title
            product = self._extract_product_from_title(title)
        
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
        # If product was extracted successfully (not generic), use it with its synonyms
        category_synonyms = self.category_synonyms.get(subcategory, 
                                                     self.category_synonyms.get(category, None))
        
        # If no category synonyms found, build from product name
        if not category_synonyms:
            if product:
                # Use product and common variations
                category_synonyms = [product]
                # Add plural/singular variations
                if product.endswith('s'):
                    category_synonyms.append(product[:-1])  # Remove 's'
                else:
                    category_synonyms.append(product + 's')  # Add 's'
            else:
                # Last resort - use category name
                category_synonyms = [category] if category and category != "general" else []
        
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
        """Generate systematic query combinations with comprehensive attribute coverage."""
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
        
        # SYSTEMATIC COMBINATION RULES - Cover all logical combinations
        
        # COLOR + BRAND + CATEGORY combinations (User's specific request)
        if brand and color and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{brand} {color} {cat_syn}")
                add_query(f"{color} {brand} {cat_syn}")
                add_query(f"{brand} {cat_syn} {color}")
        
        # COLOR + CATEGORY combinations
        if color and category_synonyms:
            for cat_syn in category_synonyms[:3]:
                add_query(f"{color} {cat_syn}")
                add_query(f"{cat_syn} {color}")
        
        # SIZE + CATEGORY combinations
        if size and category_synonyms:
            for cat_syn in category_synonyms[:3]:
                add_query(f"{size} {cat_syn}")
                add_query(f"{cat_syn} {size}")
                add_query(f"{cat_syn} {size} size")
                add_query(f"{size} size {cat_syn}")
        
        # DIMENSION + CATEGORY combinations
        if dimension and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{cat_syn} {dimension}")
                # Also try dimension without spaces (e.g., "19x21")
                dim_no_space = re.sub(r'\s*([x×])\s*', r'\1', dimension.lower())
                if dim_no_space != dimension.lower():
                    add_query(f"{cat_syn} {dim_no_space}")
        
        # COLOR + SIZE + CATEGORY combinations (User's specific request)
        if color and size and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{color} {cat_syn} {size}")
                add_query(f"{size} {color} {cat_syn}")
                add_query(f"{cat_syn} {color} {size}")
                add_query(f"{cat_syn} {size} {color}")
        
        # BRAND + ATTRIBUTE + CATEGORY combinations
        for attr in attributes[:3]:
            if brand and category_synonyms:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{brand} {attr} {cat_syn}")
                    add_query(f"{attr} {brand} {cat_syn}")
                    add_query(f"{cat_syn} {brand} {attr}")
        
        # COLOR + ATTRIBUTE + CATEGORY combinations
        for attr in attributes[:3]:
            if color and category_synonyms:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{color} {attr} {cat_syn}")
                    add_query(f"{attr} {color} {cat_syn}")
        
        # BRAND + COLOR + SIZE + CATEGORY (comprehensive combination)
        if brand and color and size and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{brand} {color} {cat_syn} {size}")
                add_query(f"{color} {brand} {cat_syn} {size}")
                add_query(f"{brand} {cat_syn} {color} {size}")
                add_query(f"{brand} {color} {size} {cat_syn}")
                add_query(f"{color} {size} {brand} {cat_syn}")
        
        # COLOR + SIZE + CATEGORY combinations (missing from user expectation)
        if color and size and category_synonyms:
            for cat_syn in category_synonyms[:3]:
                add_query(f"{color} {cat_syn} {size}")
                add_query(f"{size} {color} {cat_syn}")
                add_query(f"{cat_syn} {color} {size}")
                add_query(f"{cat_syn} {size} {color}")
                add_query(f"{color} {size} {cat_syn}")
                add_query(f"{size} {cat_syn} {color}")
        
        # BRAND + ATTRIBUTE + CATEGORY combinations (missing from user expectation)
        for attr in attributes[:4]:  # Increased to include 'scented'
            if brand and category_synonyms:
                for cat_syn in category_synonyms[:3]:  # Increased coverage
                    add_query(f"{brand} {attr} {cat_syn}")
                    add_query(f"{attr} {brand} {cat_syn}")
                    add_query(f"{brand} {cat_syn} {attr}")
                    add_query(f"{cat_syn} {brand} {attr}")
        
        # MATERIAL + CATEGORY combinations
        if material and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{material} {cat_syn}")
                add_query(f"{cat_syn} {material}")
        
        # SIZE + MATERIAL + CATEGORY
        if size and material and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{size} {material} {cat_syn}")
                add_query(f"{material} {size} {cat_syn}")
        
        # COLOR + MATERIAL + CATEGORY
        if color and material and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{color} {material} {cat_syn}")
                add_query(f"{material} {color} {cat_syn}")
        
        # USE CASE + CATEGORY combinations
        for use_case in use_cases[:3]:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{use_case} {cat_syn}")
                add_query(f"{cat_syn} {use_case}")
        
        # USE CASE + SIZE + CATEGORY
        if use_cases and size:
            for use_case in use_cases[:2]:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{use_case} {size} {cat_syn}")
                    add_query(f"{size} {use_case} {cat_syn}")
        
        # DIMENSION + SIZE combinations
        if dimension and size and category_synonyms:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{cat_syn} {dimension} {size}")
                add_query(f"{cat_syn} {size} {dimension}")
        
        # ATTRIBUTE + CATEGORY combinations (without brand)
        for attr in attributes[:3]:
            for cat_syn in category_synonyms[:2]:
                add_query(f"{attr} {cat_syn}")
                add_query(f"{cat_syn} {attr}")
        
        # CATEGORY + COUNT/PACK size
        if count and category_synonyms:
            numbers = re.findall(r'\d+', count)
            if numbers:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{numbers[0]} {cat_syn}")
                    add_query(f"{cat_syn} {numbers[0]}")
                    add_query(f"{cat_syn} {numbers[0]} pack")
                    add_query(f"{numbers[0]} pack {cat_syn}")
        
        # LONG-TAIL combinations for broader coverage
        if brand and attributes and category_synonyms:
            for attr in attributes[:2]:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{brand} {cat_syn} {attr} {size}" if size else f"{brand} {cat_syn} {attr}")
        
        # DIMENSION + ATTRIBUTE combinations
        if dimension and attributes and category_synonyms:
            for attr in attributes[:2]:
                for cat_syn in category_synonyms[:2]:
                    add_query(f"{cat_syn} {dimension} {attr}")
        
        # CATEGORY SYNONYMS (broader searches without specific attributes)
        for cat_syn in category_synonyms[1:4]:
            add_query(cat_syn)
            if size:
                add_query(f"{cat_syn} {size}")
            if color:
                add_query(f"{color} {cat_syn}")
            if material:
                add_query(f"{material} {cat_syn}")
        
        return queries[:40]  # Increased limit to ensure all combinations are generated

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

TASK: Select the TOP {max_select} keywords for Amazon title optimization.

SELECTION CRITERIA (in priority order):
1. SEARCH VOLUME IS KING: Prioritize keywords with highest score (search volume proxy)
2. COMPLETE PHRASES WIN: Select multi-word phrases intact
   - "product medium size" is better than just "product" or "medium"
3. OVERLAP IS OKAY: High-volume phrases beat novelty
   - If title has "product" and candidate is "product medium size" with high score → SELECT IT
4. ZONE CLASSIFICATION for title composition:
   - ZONE_B (default): Most search phrases go here - high-volume terms customers search
   - ZONE_C: Variants/descriptors like fragrance, flavor, style, finish
   - Note: Zone A is for specs (size/dimension/count) which are extracted separately

ZONE EXAMPLES (generic patterns):
- ZONE_B: "product type size", "product for use case", "product with feature"
- ZONE_C: "lavender scented", "premium finish", "classic style", "mint flavor"

STRICT RULES:
- ONLY select from CANDIDATE KEYWORDS list
- Do NOT invent keywords
- Reject cross-category terms
- Do NOT reject high-volume keywords due to partial overlap with title

Respond ONLY JSON:
{{
  "selected_keywords": [
    {{"keyword": "keyword1", "zone": "ZONE_B|ZONE_C", "reason": "why selected"}}
  ],
  "rejected_count": 0,
  "rejection_reasons": []
}}

JSON:"""

        res = self._run_json(
            prompt,
            temperature=0.1,
            max_tokens=450,
            validator=validate_keyword_selection,
            retries=2,
        )

        # Build a lookup for scores from candidates
        score_lookup = {str(x.get("keyword", "")).strip().lower(): x.get("score", 0) for x in candidates}

        selected: List[Dict[str, Any]] = []
        if res.ok:
            for item in res.value.get("selected_keywords", []) or []:
                k = str(item.get("keyword", "")).strip()
                if not k:
                    continue
                if k.lower() not in allowed:
                    continue
                zone = str(item.get("zone", "ZONE_B")).strip().upper()
                if zone not in {"ZONE_A", "ZONE_B", "ZONE_C"}:
                    zone = "ZONE_B"
                selected.append({
                    "keyword": k,
                    "zone": zone,
                    "score": round(score_lookup.get(k.lower(), 0), 4),
                    "reason": str(item.get("reason", "")).strip()
                })

        # FALLBACK: If AI returned empty, auto-select top volume keywords
        if not selected and candidates:
            print("   [WARNING] KeywordSelector returned empty - auto-selecting top 10 by score")
            # Sort by score descending
            sorted_candidates = sorted(candidates, key=lambda x: float(x.get('score', 0) or 0), reverse=True)
            for kw in sorted_candidates[:min(10, max_select)]:
                k = str(kw.get("keyword", "")).strip()
                if k and k.lower() in allowed:
                    # Generic zone classification
                    zone = "ZONE_B"  # Default: search phrases go to Zone B
                    k_lower = k.lower()
                    
                    # Variants/descriptors -> Zone C
                    if any(word in k_lower for word in ["scent", "fragrance", "flavor", "aroma", "smell"]):
                        zone = "ZONE_C"
                    # Modifiers/accessories -> Zone C  
                    elif any(word in k_lower for word in ["style", "finish", "design", "pattern"]):
                        zone = "ZONE_C"
                    
                    selected.append({
                        "keyword": k,
                        "zone": zone,
                        "score": round(float(kw.get("score", 0) or 0), 4),
                        "reason": "auto-selected (high volume)"
                    })

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
        # Format keywords with zone hints AND score for volume-driven decisions
        keyword_list = [
            f"- {k.get('keyword','')} [{k.get('zone', 'ZONE_B')}] (score: {k.get('score', 0)})"
            for k in selected_keywords
        ]
        
        # Create TOP keywords list sorted by score
        top_keywords_text = ""
        if selected_keywords:
            sorted_kw = sorted(selected_keywords, key=lambda x: float(x.get('score', 0) or 0), reverse=True)
            top_3 = sorted_kw[:3]
            top_keywords_text = "\n".join([
                f"  #{i+1}: \"{kw.get('keyword', '')}\" (score: {kw.get('score', 0):.4f})"
                for i, kw in enumerate(top_3)
            ])
        else:
            top_keywords_text = "  (none - use original title concepts only)"

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

APPROVED KEYWORDS (with zone hints from retrieval):
{chr(10).join(keyword_list) if keyword_list else '- (none)'}

⭐ TOP KEYWORDS BY SEARCH VOLUME (MUST INCLUDE THESE IN TITLE):
{top_keywords_text}

TASK: Produce a single optimized title using ZONE-BASED COMPOSITION.

CRITICAL ANTI-HALLUCINATION RULES (VIOLATION = FAILURE):
1. NEVER invent words not in ORIGINAL TITLE or APPROVED KEYWORDS
2. NEVER change specific descriptors (e.g., "Lavender" → "Fresh", "Steel" → "Metal")
3. NEVER assume features not explicitly stated
4. If APPROVED KEYWORDS is empty, restructure ORIGINAL TITLE only

ZONE-BASED COMPOSITION STRATEGY:
Think of zones as logical sections that flow naturally with commas:

ZONE A (~40% chars): PURE PRODUCT INFORMATION (specs only, no keywords)
  * Brand + Product Type + Size + Dimension + Quantity + Color
  * Use LOCKED FACTS exactly ONCE (never repeat pack count or dimension)
  * Example: "Shalimar Garbage Bags, Medium 19 X 21 Inches, 120 Bags (30 Bags x 4 Rolls), Black"

ZONE B (~40% chars): HIGH-VOLUME SEARCH PHRASES (keywords, no spec repetition)
  * Insert TOP search keywords from APPROVED KEYWORDS
  * Include COMPLETE phrases from top keywords
  * Combine naturally: "Black Garbage Bags Medium Size with Perforated Box for Easy Dispensing"
  * DO NOT repeat specs already in Zone A
  * If Zone A has "Medium" and "120 Bags", Zone B should NOT repeat these
  * Add descriptive words like "Premium", "Heavy Duty" product relevant if in original or keywords do not assume features not stated

ZONE C (~20% chars): DESCRIPTORS (fragrance/style details)
  * Exact fragrance names: "Lavender Fragrance" or "with Lavender Fragrance"
  * Secondary keywords: "Scented Trash Bags"
  * Combine with "with" or commas naturally

NATURAL FLOW EXAMPLE:
✅ GOOD: "Brand Product, Size, Quantity, Color, Search Phrase with Feature, Descriptor"
"Shalimar Garbage Bags, Medium 19 X 21 Inches, 120 Bags (30x4), Black, Garbage Bags Medium Size with Perforated Box, Lavender Fragrance"

❌ BAD: "Brand Product Medium 19x21, 120 Bags (30x4) (30x4), Medium Garbage Bags..."
(Repeats pack count, repeats "Medium")

STRICT COMPOSITION RULES:
1. Each spec appears EXACTLY ONCE (no "120 Bags (30x4) (30x4)")
2. LOCKED FACTS copied exactly, used ONCE only
3. Flow with commas, NOT pipes (|)
4. Combine naturally - don't fragment
5. Brand appears ONCE at start
6. ONLY words from ORIGINAL TITLE or APPROVED KEYWORDS
7. Target 180-200 chars

ZONE INTEGRATION:
Don't create rigid barriers. Flow zones together:
"[Zone A: specs], [Zone B: keywords with features], [Zone C: descriptors]"

Output ONLY valid JSON:
{{
  "full_title": "...",
  "char_count": 0,
  "zone_a": "first ~40% of title",
  "zone_b": "middle ~40% of title",
  "zone_c": "final ~20% of title",
  "reasoning": {{"zone_a_rationale": "...", "zone_b_rationale": "...", "zone_c_rationale": "..."}}
}}

JSON:"""

        res = self._run_json(
            prompt,
            temperature=0.3,
            max_tokens=1000,
            validator=validate_title_draft,
            retries=4,
        )

        if not res.ok:
            # Fallback: return original title if AI completely fails
            print(f"   [WARNING] TitleComposer failed after retries. Errors: {res.errors}")
            return {"full_title": original_title, "error": "AI failed", "char_count": len(original_title)}

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
