"""Enhanced QueryPlannerAgent with systematic query generation.

This improved version replaces the AI-only approach with systematic query generation
that works consistently across all product categories.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from agentic_llm import OllamaLLM, extract_json_object
from agentic_validators import validate_query_suggestions


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


class ImprovedQueryPlannerAgent(BaseJsonAgent):
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
            anchor_phrase = " ".join(anchors).lower()
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


# Example usage for testing
if __name__ == "__main__":
    from agentic_llm import OllamaLLM, OllamaConfig
    
    # Example product
    title = "Shalimar Premium (Lavender Fragrance) Scented Garbage Bags | Medium 19 X 21 Inches | 120 Bags (30 Bags X 4 Rolls) | Dustbin Bag/Trash Bag | (Black) - Perforated Box for Easy Dispensing"
    
    truth = {
        "brand": "Shalimar",
        "product": "garbage bags",
        "color": "black",
        "size": "medium",
        "dimension": "19 X 21 inches",
        "count": "120 bags"
    }
    
    category_info = {
        "category": "home_storage",
        "subcategory": "garbage_bags",
        "search_priorities": ["garbage bags", "trash bags", "kitchen bags"],
        "key_attributes": ["scented", "medium size", "black"]
    }
    
    # Initialize agent (you'd need actual Ollama setup)
    # config = OllamaConfig(model="gemma3:4b", base_url="http://localhost:11434")
    # llm = OllamaLLM(config)
    # agent = ImprovedQueryPlannerAgent(llm)
    
    # For testing without LLM
    agent = ImprovedQueryPlannerAgent(None)
    
    queries = agent.run(
        base_title=title,
        truth=truth,
        category_info=category_info,
        anchors=[],
        existing_queries=[],
        max_new=10
    )
    
    print("Generated Queries:")
    for i, q in enumerate(queries, 1):
        print(f"{i:2d}. {q}")

