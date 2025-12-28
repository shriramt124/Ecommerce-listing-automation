"""
AGENTIC STRATEGY 2: AI-POWERED TITLE OPTIMIZER
===============================================
Uses local Ollama LLM to make intelligent optimization decisions.
Replaces hardcoded rules with AI-driven logic.

Key AI Agents:
1. Category Detector - Identifies product category
2. Concept Evaluator - Decides keep/remove for each concept
3. Zone Builder - Builds optimal title with search-driven ordering
4. Title Validator - Final quality check

Environment:
- ADKRUX_USE_AI=true (enable AI)
- ADKRUX_OLLAMA_MODEL=gpt-oss:20b-cloud (default model)
"""

import os
import json
import re
import requests
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from token_types import Token, TokenType, TokenOrigin, ConceptTier, MAX_CHARS
from parser import parser
from keyword_db import KeywordDB


@dataclass
class ConceptWithRank:
    """A concept with its search ranking data."""
    text: str
    token_type: TokenType
    clicks_rank: float  # Lower = better (more clicks)
    search_rank: float  # Lower = better (more searches)
    priority_score: float  # Computed: higher = more important
    keep: bool = True
    reason: str = ""


class AgenticOptimizer:
    """
    AI-powered title optimizer using local Ollama.
    
    Philosophy:
    - First 40%: Decision zone (max info in search-optimal order)
    - Next 40%: SEO zone  (only product attrubute is allowed if high value) and only one time reperition is allowed of attributes in whole title
    - Last 20%: Details zone (features, fragrance, etc.)
    - No pipes (|) - natural phrasing
    - Color not forced to first 40% (visible in image)
    """
    
    def __init__(self):
        # Try local model first, then cloud
        self.model = os.getenv('ADKRUX_OLLAMA_MODEL', 'deepseek-v3.1:671b-cloud')
        self.base_url = os.getenv('ADKRUX_OLLAMA_URL', 'http://localhost:11434')
        self.api_url = f"{self.base_url}/api/generate"
        self.enabled = os.getenv('ADKRUX_USE_AI', 'true').lower() == 'true'
        
        # Keyword DB for search data
        self.keyword_db = KeywordDB()

        # Retrieval/debug controls
        self.vector_debug = os.getenv('ADKRUX_VECTOR_DEBUG', 'true').lower() == 'true'
        self.ai_vector_rounds = int(os.getenv('ADKRUX_AI_VECTOR_ROUNDS', '1'))
        self.vector_limit_per_query = int(os.getenv('ADKRUX_VECTOR_LIMIT_PER_QUERY', '25'))
        self.vector_max_candidates = int(os.getenv('ADKRUX_VECTOR_MAX_CANDIDATES', '60'))
        
        if self.enabled:
            print(f"   [Agentic] AI Optimizer enabled with model: {self.model}")
            if not self._test_connection():
                print(f"   [Agentic] ⚠️  Cannot connect to Ollama at {self.base_url}")
                self.enabled = False
    
    def _test_connection(self) -> bool:
        """Test Ollama connection."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def _call_ollama(self, prompt: str, temperature: float = 0.1, max_tokens: int = 500) -> Optional[str]:
        """Call Ollama API."""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                }
            }
            
            response = requests.post(self.api_url, json=payload, timeout=120)
            
            if response.status_code == 200:
                result = response.json()
                # Some cloud models return in 'thinking' field, others in 'response'
                text = result.get('response', '').strip()
                if not text:
                    # Try 'thinking' field (used by some cloud models)
                    text = result.get('thinking', '').strip()
                if not text:
                    # Try 'message' -> 'content' (chat format)
                    msg = result.get('message', {})
                    if isinstance(msg, dict):
                        text = msg.get('content', '').strip()
                return text
            else:
                print(f"   [Agentic] Ollama error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"   [Agentic] Ollama call failed: {e}")
            return None
    
    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """Extract JSON from AI response."""
        if not response:
            return None
        try:
            # Remove markdown code blocks if present
            clean = response.strip()
            if clean.startswith('```json'):
                clean = clean[7:]
            if clean.startswith('```'):
                clean = clean[3:]
            if clean.endswith('```'):
                clean = clean[:-3]
            clean = clean.strip()
            
            # Find JSON in response
            start = clean.find('{')
            end = clean.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(clean[start:end])
        except json.JSONDecodeError as e:
            print(f"   [Agentic] JSON parse error: {e}")
        return None

    def _normalize_pack_string(self, text: str) -> str:
        s = str(text or '').strip()
        if not s:
            return ''
        s = re.sub(r'\s+', ' ', s)
        # Normalize common separators
        s = s.replace('×', 'x').replace('*', 'x')
        # Normalize common casing in pack strings
        s = re.sub(r'\bbag\b', 'Bags', s, flags=re.IGNORECASE)
        s = re.sub(r'\bbags\b', 'Bags', s, flags=re.IGNORECASE)
        s = re.sub(r'\broll\b', 'Rolls', s, flags=re.IGNORECASE)
        s = re.sub(r'\brolls\b', 'Rolls', s, flags=re.IGNORECASE)
        s = re.sub(r'\bx\b', 'x', s, flags=re.IGNORECASE)
        return s.strip()

    def _extract_locked_truth_from_title(self, base_title: str) -> Dict[str, str]:
        """Extract exact substrings we should NOT allow the LLM to rewrite."""
        locked: Dict[str, str] = {}
        t = base_title or ''

        # Quantity pack patterns like: "120 Bags (30 Bags x 4 Rolls)"
        pack_patterns = [
            r'(\b\d+\s*bags?\s*\(\s*\d+\s*bags?\s*[xX×*]\s*\d+\s*rolls?\s*\))',
            r'(\b\d+\s*bags?\s*\(\s*\d+\s*[xX×*]\s*\d+\s*rolls?\s*\))',
            r'(\b\d+\s*bags?\s*\(\s*\d+\s*rolls?\s*\))',
        ]
        for pat in pack_patterns:
            m = re.search(pat, t, flags=re.IGNORECASE)
            if m:
                locked['count_exact'] = self._normalize_pack_string(m.group(1))
                break

        # Dimension like: 19 x 21 Inches / 19x21" / 19 X 21
        dim = re.search(r'(\b\d+\s*[xX×]\s*\d+\s*(?:inches?|inch|cm|mm)?\b)', t, flags=re.IGNORECASE)
        if dim:
            locked['dimension_exact'] = re.sub(r'\s+', ' ', dim.group(1)).strip()

        return locked

    def _enforce_locked_substrings(self, title: str, locked: Dict[str, str]) -> str:
        """Ensure critical locked substrings appear as-is (when present in original title)."""
        out = title

        # Enforce exact pack string
        pack = locked.get('count_exact')
        if pack:
            if pack not in out:
                total_m = re.search(r'\b(\d+)\s*Bags\b', pack, flags=re.IGNORECASE)
                total = total_m.group(1) if total_m else None
                if total:
                    # Replace a rewritten variant like "120 Bags, 30 Rolls" or "120 Bags 30 Rolls"
                    out = re.sub(
                        rf'\b{re.escape(total)}\s*bags?\b\s*(?:,|-)\s*\d+\s*rolls?\b',
                        pack,
                        out,
                        flags=re.IGNORECASE,
                        count=1,
                    )
                    # Replace a plain "120 Bags" with full pack if present
                    if pack not in out:
                        out = re.sub(
                            rf'\b{re.escape(total)}\s*bags?\b',
                            pack,
                            out,
                            flags=re.IGNORECASE,
                            count=1,
                        )

        # Enforce dimension
        dim = locked.get('dimension_exact')
        if dim and dim not in out:
            out = re.sub(
                r'\b\d+\s*[xX×]\s*\d+\s*(?:in\s*ch\s*es?|inches?|inch|cm|mm)?\b',
                dim,
                out,
                flags=re.IGNORECASE,
                count=1,
            )

        out = re.sub(r'\s+', ' ', out).strip()

        # Fix occasional model artifacts (word splitting)
        out = re.sub(r'\bInch\s*es\b', 'Inches', out, flags=re.IGNORECASE)
        out = re.sub(r'\bRoll\s*s\b', 'Rolls', out, flags=re.IGNORECASE)
        out = re.sub(r'\bBag\s*s\b', 'Bags', out, flags=re.IGNORECASE)

        # Ensure there is a separator between unit words and the next token
        out = re.sub(r'\b(Inches|Inch|cm|mm)(?=[A-Za-z0-9])', r'\1 ', out, flags=re.IGNORECASE)

        out = re.sub(r'\s+,', ',', out)
        return out

    def _build_vector_queries(self, base_title: str, truth: Dict, category_info: Dict) -> List[str]:
        anchors = self._get_vector_query_anchors(base_title, truth, category_info)
        anchor_phrase = ' '.join(anchors).strip()

        brand = str(truth.get('brand', '') or '').strip()
        product = str(truth.get('product', '') or '').strip()
        size = str(truth.get('size', '') or '').strip()
        dim = str(truth.get('dimension', '') or '').strip()
        color = str(truth.get('color', '') or '').strip()
        compatibility = str(truth.get('compatibility', '') or '').strip()
        locked_pack = str(truth.get('_locked', {}).get('count_exact', '') or '').strip()

        search_priorities = category_info.get('search_priorities', []) or []

        queries: List[str] = []
        # Anchor-first queries (prevents drift when product term is generic like "dustbin")
        if anchor_phrase and product:
            queries.append(f"{anchor_phrase} {product}")
        if anchor_phrase and product and size:
            queries.append(f"{anchor_phrase} {product} {size}")
        if brand and anchor_phrase and product:
            queries.append(f"{brand} {anchor_phrase} {product}")
        if brand and anchor_phrase and product and size:
            queries.append(f"{brand} {anchor_phrase} {product} {size}")
        if compatibility and product:
            queries.append(f"{product} {compatibility}")
        if brand and compatibility and product:
            queries.append(f"{brand} {product} {compatibility}")

        if brand and product and size:
            queries.append(f"{brand} {product} {size}")
        if product and size and dim:
            queries.append(f"{product} {size} {dim}")
        if brand and product:
            queries.append(f"{brand} {product}")
        if product and size:
            queries.append(f"{product} {size}")
        # Only allow a bare product query if we have no anchors; otherwise it can drift.
        if product and not anchor_phrase:
            queries.append(product)
        if product and color:
            if anchor_phrase:
                queries.append(f"{anchor_phrase} {product} {color}")
            queries.append(f"{product} {color}")
        if locked_pack and product:
            queries.append(f"{product} {locked_pack}")
        if base_title:
            queries.append(base_title)

        for p in search_priorities[:6]:
            p = str(p).strip()
            if not p:
                continue
            queries.append(p)
            if product:
                queries.append(f"{p} {product}")
            if brand:
                queries.append(f"{brand} {p}")

        # De-dup, keep order
        seen = set()
        out: List[str] = []
        for q in queries:
            qn = re.sub(r'\s+', ' ', q).strip()
            if not qn:
                continue
            key = qn.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(qn)
        return out

    def _get_vector_query_anchors(self, base_title: str, truth: Dict, category_info: Dict) -> List[str]:
        """Return disambiguating anchor tokens that should appear in retrieval queries when possible.

        This is intentionally conservative: anchors are only added when they already appear in the
        title/truth/category signals (to avoid injecting unrelated context).
        """
        title_lower = str(base_title or '').lower()
        compatibility_lower = str(truth.get('compatibility', '') or '').lower()
        search_priorities = category_info.get('search_priorities', []) or []
        priorities_text = ' '.join([str(p).lower() for p in search_priorities])

        anchors = set()

        # Vehicle anchors (strong disambiguators)
        if re.search(r'\bcar\b', title_lower) or re.search(r'\bcar\b', compatibility_lower) or 'car' in priorities_text:
            anchors.add('car')
        if re.search(r'\bvehicle\b', title_lower) or 'vehicle' in compatibility_lower:
            anchors.add('car')

        if (
            re.search(r'\bbike\b', title_lower)
            or re.search(r'\bmotor(?:bike|cycle)\b', title_lower)
            or 'bike' in compatibility_lower
            or 'motorcycle' in compatibility_lower
            or 'bike' in priorities_text
            or 'motorcycle' in priorities_text
        ):
            anchors.add('bike')

        # Keep stable ordering
        out = sorted(anchors)
        return out

    def _ai_suggest_vector_queries(self, base_title: str, truth: Dict, category_info: Dict, existing_queries: List[str]) -> List[str]:
        """Ask the LLM for broader/alternative retrieval queries (tool-like)."""
        anchors = self._get_vector_query_anchors(base_title, truth, category_info)
        anchor_phrase = ' '.join(anchors).strip()

        prompt = f"""You are helping retrieve Amazon search keywords from a vector database.

PRODUCT TITLE: {base_title}
PRODUCT TRUTH: {json.dumps({k: v for k, v in truth.items() if not str(k).startswith('_')}, ensure_ascii=False)}
CATEGORY: {category_info.get('category','general')} / {category_info.get('subcategory','unknown')}

EXISTING QUERIES WE ALREADY TRIED:
{json.dumps(existing_queries, ensure_ascii=False, indent=2)}

TASK: Propose 3-6 NEW vector search queries that are BROADER but still relevant.

REQUIRED CONTEXT ANCHORS:
- Anchors: {anchors if anchors else []}
- If anchors are provided, EVERY query MUST include ALL anchors (e.g., include "{anchor_phrase}" in every query).

GUIDELINES:
- Use customer synonyms for the same product type (not new products)
- Try different ordering and shorter forms
- Include size/dimension as separate query sometimes
- Do NOT drift into other product categories
- Avoid 1-word queries; prefer 2-6 words with clear intent

Respond ONLY JSON:
{{"queries": ["q1", "q2", "q3"]}}

JSON:"""

        response = self._call_ollama(prompt, temperature=0.2, max_tokens=250)
        parsed = self._parse_json_response(response)
        if not parsed or 'queries' not in parsed:
            return []
        out: List[str] = []
        for q in parsed.get('queries', []) or []:
            qs = re.sub(r'\s+', ' ', str(q)).strip()
            if qs:
                out.append(qs)
        return out[:8]

    def _retrieve_keywords_multiquery(self, base_title: str, truth: Dict, category_info: Dict) -> Tuple[List[Dict], Dict]:
        """Multi-query vector retrieval with optional AI-guided query expansion."""
        retrieval_report: Dict[str, object] = {
            'queries': [],
            'results_by_query': {},
        }

        queries = self._build_vector_queries(base_title, truth, category_info)

        # Let AI propose broader queries (permission to "search anytime" within bounded rounds)
        for _ in range(max(self.ai_vector_rounds, 0)):
            more = self._ai_suggest_vector_queries(base_title, truth, category_info, queries)
            for q in more:
                if q.lower() not in {x.lower() for x in queries}:
                    queries.append(q)

        # Execute queries
        merged: Dict[str, Dict] = {}
        for q in queries:
            results = self.keyword_db.get_top_keywords(q, limit=self.vector_limit_per_query)
            retrieval_report['results_by_query'][q] = results[:10]  # keep small in report
            retrieval_report['queries'].append(q)

            for r in results:
                kw = str(r.get('keyword', '') or '').strip()
                if not kw:
                    continue
                key = kw.lower()
                prev = merged.get(key)
                if not prev:
                    merged[key] = {**r, 'hit_queries': [q]}
                else:
                    # Keep best similarity; accumulate queries
                    prev_sim = float(prev.get('similarity', 0.0) or 0.0)
                    new_sim = float(r.get('similarity', 0.0) or 0.0)
                    if new_sim > prev_sim:
                        keep_queries = prev.get('hit_queries', [])
                        merged[key] = {**r, 'hit_queries': keep_queries}
                    if q not in prev.get('hit_queries', []):
                        prev.setdefault('hit_queries', []).append(q)

        candidates = list(merged.values())
        # Sort primarily by similarity, secondarily by score
        candidates.sort(key=lambda x: (float(x.get('similarity', 0.0) or 0.0), float(x.get('score', 0.0) or 0.0)), reverse=True)
        candidates = candidates[: self.vector_max_candidates]

        if self.vector_debug:
            print("   Vector queries used:")
            for q in queries[:20]:
                print(f"      - {q}")
            print(f"   Merged candidates: {len(candidates)}")
            for i, r in enumerate(candidates[:10], 1):
                sim = float(r.get('similarity', 0.0) or 0.0)
                sc = float(r.get('score', 0.0) or 0.0)
                au = float(r.get('ad_units', 0.0) or 0.0)
                print(f"      {i}. {r.get('keyword')} | sim={sim:.3f} | score={sc:.4f} | ad_units={au:.1f}")

        return candidates, retrieval_report

    # =========================================================================
    # AGENT 1: CATEGORY DETECTOR
    # =========================================================================
    def detect_category(self, title: str, truth: Dict) -> Dict:
        """
        AI Agent 1: Detect product category and key characteristics.
        
        Returns:
        {
            "category": "home_storage",
            "subcategory": "garbage_bags",
            "key_attributes": ["scented", "medium", "kitchen"],
            "search_priorities": ["scent", "size", "room", "count"]
        }
        """
        print("\n   [Agent 1] Detecting category...")
        
        prompt = f"""You are an Amazon product categorization expert.

PRODUCT TITLE: "{title}"

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
    "category": "main category name",
    "subcategory": "specific product type",
    "key_attributes": ["attr1", "attr2", "attr3"],
    "search_priorities": ["what customers search first", "second", "third"],
    "color_important": true/false (is color a key decision factor or visible in image?)
}}

JSON:"""

        response = self._call_ollama(prompt, temperature=0.1, max_tokens=300)
        result = self._parse_json_response(response)
        
        if result:
            print(f"      Category: {result.get('category')} / {result.get('subcategory')}")
            print(f"      Key attributes: {result.get('key_attributes', [])}")
            print(f"      Search priorities: {result.get('search_priorities', [])}")
            return result
        
        # Fallback
        return {
            "category": "general",
            "subcategory": "unknown",
            "key_attributes": [],
            "search_priorities": [],
            "color_important": False
        }

    # =========================================================================
    # AGENT 2: CONCEPT EVALUATOR
    # =========================================================================
    def evaluate_concept(self, concept: str, concept_type: str, context: Dict) -> Dict:
        """
        AI Agent 2: Evaluate if a concept should be kept and its value.
        
        Handles Premium, Scented, and other context-dependent decisions.
        """
        prompt = f"""You are an Amazon keyword optimization expert.

CONCEPT TO EVALUATE: "{concept}" (Type: {concept_type})

PRODUCT CONTEXT:
- Product: {context.get('product', 'Unknown')}
- Brand: {context.get('brand', 'N/A')}
- Category: {context.get('category', 'general')}
- Current title concepts: {context.get('existing_concepts', [])}

TASK: Should this concept be KEPT in the title?

RULES:
- "Premium": Keep if product is high-end OR if "premium" is a common search term for this category
- "Scented": ALWAYS keep for fragrance products - it's a TOP search term even with specific fragrance mentioned
- Quality markers (Deluxe, Superior): Usually remove unless category-relevant
- Generic terms: Remove if they add no search value

Respond ONLY with valid JSON:
{{
    "keep": true/false,
    "value_score": 0.0 to 1.0 (how valuable is this concept?),
    "position": "zone_a" / "zone_b" / "zone_c" (where should it appear?),
    "reason": "brief explanation"
}}

JSON:"""

        response = self._call_ollama(prompt, temperature=0.1, max_tokens=200)
        result = self._parse_json_response(response)
        
        if result:
            return result
        
        # Fallback: keep by default
        return {"keep": True, "value_score": 0.5, "position": "zone_b", "reason": "default"}

    # =========================================================================
    # AGENT 3: KEYWORD RANKER
    # =========================================================================
    def rank_keywords(self, concepts: List[str], keywords_from_db: List[Dict], context: Dict) -> List[Dict]:
        """
        AI Agent 3: Rank keywords by search value and relevance.
        
        Uses vector DB results + AI reasoning to prioritize keywords.
        """
        print("\n   [Agent 3] Ranking keywords by search value...")
        
        # Format keywords with their scores
        kw_list = []
        for kw in keywords_from_db[:20]:  # Top 20 from vector DB
            kw_list.append({
                "keyword": kw.get('keyword', ''),
                "similarity": round(kw.get('similarity', 0), 3),
                "score": round(kw.get('score', 0), 4),
                "ad_units": round(float(kw.get('ad_units', 0) or 0.0), 1),
                "ad_conv": round(float(kw.get('ad_conv', 0) or 0.0), 4),
                "dataset_id": kw.get('dataset_id'),
                "hit_queries": kw.get('hit_queries', [])[:3],
            })
        
        prompt = f"""You are an Amazon search optimization expert.

PRODUCT: {context.get('product', 'Unknown')}
BRAND: {context.get('brand', 'N/A')}
CATEGORY: {context.get('category', 'general')}

CURRENT CONCEPTS IN TITLE:
{concepts}

CANDIDATE KEYWORDS FROM VECTOR DATABASE (similarity + score + which queries found them):
{json.dumps(kw_list, indent=2)}

TASK: Select the TOP 15 keywords that:
1. Add NEW search value (not already in title)
2. Are highly relevant to this product
3. Would help customers find this product
4. Have good scores (higher = better search volume)

IMPORTANT:
- Prefer keywords that are specific to this product type in the vector query context and has higher score
- Reject obvious cross-category leakage

DO NOT select keywords that:
- Are just rearrangements of existing words
- Are for different products
- Add no new search terms

Respond ONLY with valid JSON:
{{
    "selected_keywords": [
        {{"keyword": "keyword1", "reason": "why selected"}},
        {{"keyword": "keyword2", "reason": "why selected"}}
    ],
    "rejected_count": number of rejected keywords,
    "rejection_reasons": ["common reasons for rejection"]
}}

JSON:"""

        response = self._call_ollama(prompt, temperature=0.1, max_tokens=400)
        result = self._parse_json_response(response)
        
        if result and 'selected_keywords' in result:
            print(f"      Selected {len(result['selected_keywords'])} keywords")
            for kw in result['selected_keywords']:
                print(f"         ✓ {kw.get('keyword')} - {kw.get('reason', '')}")
            return result['selected_keywords']

        # Fallback (LLM JSON parse can fail): pick top keywords by score/similarity
        product = str(context.get('product', '') or '').lower()
        category = str(context.get('category', '') or '').lower()
        existing = ' '.join(concepts).lower()

        # Simple cross-category bans
        bans = set()
        if 'bike' in category or 'automotive' in category:
            bans.update({'garbage', 'trash', 'dustbin', 'kitchen', 'scented', 'fragrance'})
        if 'home' in category or 'storage' in category:
            bans.update({'shock', 'absorber', 'handlebar', 'fork', 'bike', 'motorbike'})

        selected: List[Dict] = []
        for kw in keywords_from_db:
            k = str(kw.get('keyword', '') or '').strip()
            if not k:
                continue
            kl = k.lower()
            if any(b in kl for b in bans):
                continue
            if kl in existing or kl.replace(' ', '') in existing.replace(' ', ''):
                continue
            if product and product not in existing and product not in kl and len(selected) < 2:
                # still allow some broad keywords even if product term missing
                pass
            selected.append({"keyword": k, "reason": "fallback: high similarity/score"})
            if len(selected) >= 5:
                break

        if selected:
            print(f"      Selected {len(selected)} keywords (fallback)")
            for kw in selected:
                print(f"         ✓ {kw.get('keyword')} - {kw.get('reason', '')}")
            return selected

        return []

    # =========================================================================
    # AGENT 4: ZONE BUILDER (CORE AI AGENT)
    # =========================================================================
    def build_optimized_title(self, truth: Dict, concepts: List[Dict], keywords: List[Dict], category_info: Dict, original_title: str = "") -> Dict:
        """
        AI Agent 4: Build the complete optimized title with 3 zones.
        
        This is the CORE AI agent that replaces rule-based zone building.
        """
        print("\n   [Agent 4] Building optimized title...")
        
        # Format concepts for prompt - these are from ORIGINAL title only
        concept_list = []
        for c in concepts:
            concept_list.append(f"- {c.get('text', '')} ({c.get('type', 'unknown')})")
        
        # Format selected keywords from vector DB
        keyword_list = []
        for kw in keywords:
            keyword_list.append(f"- {kw.get('keyword', '')}")
        
        # Get brand - handle empty brand
        brand = truth.get('brand', '').strip()
        if not brand or brand == 'N/A':
            brand = ""

        locked = truth.get('_locked', {}) or {}
        locked_count = locked.get('count_exact', '')
        locked_dimension = locked.get('dimension_exact', '')

        has_scented = False
        if truth.get('fragrance'):
            has_scented = True
        for c in concepts:
            if 'scented' in str(c.get('text', '')).lower():
                has_scented = True
                break
        
        prompt = f"""You are an expert Amazon title optimization AI. Your goal is to REORGANIZE and OPTIMIZE titles for maximum search visibility.

ORIGINAL TITLE (for reference):
"{original_title}"

PRODUCT INFORMATION (extracted from original):
- Brand: {brand if brand else "(No brand)"}
- Product Type: {truth.get('product', 'Unknown Product')}
- Size: {truth.get('size', '')}
- Color: {truth.get('color', '')}
- Count/Quantity: {truth.get('count', '')}
- Dimensions: {truth.get('dimension', '')}
- Material: {truth.get('material', '')}
- Features: {truth.get('features', [])}

⚠️ LOCKED FACTS (COPY EXACTLY - DO NOT REWRITE):
- Pack string: "{locked_count}" ← USE THIS EXACT FORMAT
- Dimension: "{locked_dimension}"

IS SCENTED/FRAGRANCE PRODUCT: {has_scented}

CATEGORY: {category_info.get('category', 'general')} / {category_info.get('subcategory', 'unknown')}
TOP SEARCH TERMS: {category_info.get('search_priorities', [])}

CONCEPTS FROM ORIGINAL TITLE (use these!):
{chr(10).join(concept_list)}

HIGH-VALUE KEYWORDS FROM VECTOR DB (customers search these):
{chr(10).join(keyword_list) if keyword_list else "- No additional keywords"}

===== YOUR TASK =====
Create an OPTIMIZED Amazon title with EXACTLY these zones:

ZONE A (First ~80 chars = 40%): CLICK DECISION ZONE
- This is what users see in search results - it must CONVINCE them to click
- Include: Brand (if any) + Product Type + Key Differentiators (size, quantity, dimension)
- Order by WHAT CUSTOMERS SEARCH MOST for this category
- Use LOCKED strings exactly as provided
- COLOR: Only include here if it's a key differentiator, otherwise save for end

ZONE B (Next ~80 chars = 40%): SEO OPTIMIZATION ZONE  
- Add SYNONYMS of the product type that are in VECTOR DB results
- Rearrange existing concepts into searchable phrases
- ⚠️ DO NOT repeat brand name - brand appears ONLY in Zone A
- ⚠️ DO NOT invent features/compatibility not in original
- You MAY repeat: product attrubutes like size, dimension, count only 1 time if it aids searchability according vector keywords

ZONE C (Last ~40 chars = 20%): ADDITIONAL DETAILS + COLOR
- Put COLOR here if not already in Zone A
- Any remaining attributes from original title
- Keep it simple - don't pad with invented words and do not invent any keyword okay

===== CRITICAL RULES =====
1. ONLY USE WORDS/CONCEPTS FROM ORIGINAL TITLE OR VECTOR DB - never invent features, specs, or compatibility
2. NO PIPES (|) - use commas, spaces, hyphens naturally
3. LOCKED STRINGS MUST BE EXACT - copy "{locked_count}" and "{locked_dimension}" character by character
4. BRAND APPEARS ONLY ONCE (in Zone A) - never repeat brand anywhere else
5. If fragrance/scented product: include "Scented" early in Zone A and what fragrance in Zone B
6. COLOR PLACEMENT: If color not in Zone A, put it at the VERY END of title
7. DO NOT ADD:
   - Compatibility not in original (no "for Truck, SUV" unless original says so)
   - Features not in original (no "Heavy Duty" unless original says so)
   - New product variants (no "Travel Bag" if original says "Dustbin")
8. YOU CAN ADD:
   - SYNONYMS of product type from vector DB if we are getting in vector db so add and pick smartly (Dustbin = Trash Can = Garbage Bin)
   - Rearrangements of existing words into better phrases in a way that phrase matches with most searched vector query
   - Generic use cases IF they make sense ("for Car" is fine if it's a car product)
9. TARGET 180-200 chars - but QUALITY over QUANTITY - better to be 170 high-value than 200 padded words


===== OUTPUT FORMAT =====
Return ONLY valid JSON:
{{
    "full_title": "Complete optimized title (180-200 chars)",
    "char_count": 195,
    "zone_a": "First ~80 chars",
    "zone_b": "Next ~80 chars",
    "zone_c": "Last ~40 chars",
    "reasoning": {{
        "zone_a_order": "Why this order for decision zone",
        "repetitions": ["What terms were repeated and why"],
        "premium_decision": "Kept or removed Premium and why",
        "color_placement": "Where color was placed and why"
    }}
}}

Generate the title now:"""

        response = self._call_ollama(prompt, temperature=0.2, max_tokens=800)
        result = self._parse_json_response(response)
        
        if result:
            # Get full title - try full_title first, then construct from zones
            title = result.get('full_title', '')
            
            if not title and result.get('zone_a'):
                # Construct from zones
                zones = []
                if result.get('zone_a'):
                    zones.append(result['zone_a'])
                if result.get('zone_b'):
                    zones.append(result['zone_b'])
                if result.get('zone_c'):
                    zones.append(result['zone_c'])
                title = ', '.join(zones)
            
            if title:
                # Clean up common issues
                title = title.replace(' | ', ', ').replace('|', ',')
                title = re.sub(r'\s+', ' ', title).strip()
                
                result['full_title'] = title
                
                print(f"      Generated title ({len(title)} chars):")
                print(f"      Zone A: {result.get('zone_a', 'N/A')}")
                print(f"      Zone B: {result.get('zone_b', 'N/A')}")
                print(f"      Zone C: {result.get('zone_c', 'N/A')}")
                
                if 'reasoning' in result:
                    print(f"      Reasoning:")
                    for key, value in result['reasoning'].items():
                        print(f"         - {key}: {value}")
                
                return result
        
        # Fallback: Build a better title from truth + keywords
        fallback_parts = []
        if truth.get('brand'):
            fallback_parts.append(truth['brand'])
        if truth.get('product'):
            fallback_parts.append(truth['product'])
        if truth.get('size'):
            fallback_parts.append(truth['size'])
        if truth.get('dimension'):
            fallback_parts.append(truth['dimension'])
        if truth.get('color'):
            fallback_parts.append(truth['color'])
        if truth.get('count'):
            fallback_parts.append(str(truth['count']))
        if truth.get('material'):
            fallback_parts.append(truth['material'])
        if truth.get('compatibility'):
            fallback_parts.append(truth['compatibility'])
        
        # Add some keywords
        if keywords:
            for kw in keywords[:3]:
                kw_text = kw.get('keyword', '')
                if kw_text and len(' '.join(fallback_parts + [kw_text])) < 180:
                    fallback_parts.append(kw_text.title())
        
        # Add features if still have room
        if truth.get('features'):
            for feat in truth['features'][:3]:
                if len(' '.join(fallback_parts + [feat])) < 195:
                    fallback_parts.append(feat)
        
        fallback_title = ' '.join(fallback_parts)
        # Clean up
        fallback_title = fallback_title.replace(' | ', ', ').replace('|', ',')
        fallback_title = re.sub(r'\s+', ' ', fallback_title).strip()
        
        print(f"      ⚠️  AI failed, using fallback title ({len(fallback_title)} chars): {fallback_title[:60]}...")
        
        return {"full_title": fallback_title, "error": "AI failed - using fallback"}

    # =========================================================================
    # AGENT 5: TITLE VALIDATOR
    # =========================================================================
    def validate_title(self, title: str, truth: Dict) -> Dict:
        """
        AI Agent 5: Validate the generated title.
        
        Checks:
        - Length (max 200 chars)
        - Truth alignment (all critical info present)
        - No policy violations
        """
        print("\n   [Agent 5] Validating title...")
        
        issues = []
        
        # Length check
        if len(title) > 200:
            issues.append(f"Too long: {len(title)} chars (max 200)")
        
        # Title too short - not using full potential
        if len(title) < 160:
            issues.append(f"Too short: {len(title)} chars (should use 180-200 for SEO)")
        
        # Truth alignment
        title_lower = title.lower()
        
        if truth.get('brand') and truth['brand'].lower() not in title_lower:
            issues.append(f"Missing brand: {truth['brand']}")
        
        if truth.get('product'):
            product_words = truth['product'].lower().split()
            if not any(w in title_lower for w in product_words if len(w) > 3):
                issues.append(f"Missing product: {truth['product']}")
        
        if truth.get('size') and truth['size'].lower() not in title_lower:
            # Check for variants
            size = truth['size'].lower()
            if size not in title_lower and size.replace(' ', '') not in title_lower:
                issues.append(f"Missing size: {truth['size']}")
        
        if truth.get('color') and truth['color'].lower() not in title_lower:
            issues.append(f"Missing color: {truth['color']}")
        
        # Policy check (no promotional terms)
        banned_terms = ['#1', 'best seller', 'free', 'discount', 'sale', 'cheap']
        for term in banned_terms:
            if term in title_lower:
                issues.append(f"Policy violation: contains '{term}'")
        
        is_valid = len(issues) == 0
        
        if is_valid:
            print(f"      ✅ Title is valid ({len(title)} chars)")
        else:
            print(f"      ❌ Title has issues:")
            for issue in issues:
                print(f"         - {issue}")
        
        return {
            "is_valid": is_valid,
            "issues": issues,
            "char_count": len(title)
        }

    # =========================================================================
    # AGENT 6: TITLE EXTENDER (for short titles)
    # =========================================================================
    def extend_title(self, title: str, truth: Dict, keywords: List[Dict], category_info: Dict, target_length: int = 190) -> str:
        """
        AI Agent 6: Extend a short title to use more character budget.
        
        Adds relevant keywords and synonyms to maximize search coverage.
        """
        if len(title) >= target_length:
            return title
        
        print(f"\n   [Agent 6] Extending title from {len(title)} to ~{target_length} chars...")
        
        chars_to_add = target_length - len(title)
        
        # Get category info for context
        category = category_info.get('category', 'general')
        search_priorities = category_info.get('search_priorities', [])
        key_attributes = category_info.get('key_attributes', [])
        product = truth.get('product', '')
        brand = truth.get('brand', '')
        
        # Format keywords
        kw_list = [kw.get('keyword', '') for kw in keywords[:5]]
        
        prompt = f"""TASK: Add {chars_to_add} more characters to this Amazon product title.

PRODUCT CATEGORY: {category}
PRODUCT TYPE: {product}
BRAND: {brand}

CURRENT TITLE ({len(title)} chars):
{title}

ATTRIBUTES FROM ORIGINAL TITLE:
{', '.join(key_attributes) if key_attributes else 'see title above'}

⚠️ STRICT RULES - READ CAREFULLY:
1. ONLY add words/phrases that are SYNONYMS of what's already in the title
2. DO NOT invent features (no "Heavy Duty", "long lasting" etc unless in original)
3. DO NOT add compatibility not mentioned (no "Truck, SUV" unless in original)
4. DO NOT create new product variants (no "Travel Bag" if original says "Dustbin")
5. DO NOT repeat brand name
6. If color exists, put it at the END

YOU CAN ADD:
- SYNONYMS: of product type from vector DB if showing in results
- Rearrangements of existing words into phrases but according to the 40-40-20 rule keeping mind and also zones
- Simple connectors: "for", "with", "and"

RULES:
- Keep existing title exactly as is at the start
- Add content at the END using commas
- Final title MUST be under 200 characters
- NO PIPES (|)
- QUALITY over QUANTITY - don't pad with irrelevant words
- 

Output ONLY the extended title (nothing else):"""

        response = self._call_ollama(prompt, temperature=0.3, max_tokens=250)
        
        if response:
            # Clean the response
            extended = response.strip()
            
            # Take only the first line if multiple lines
            if '\n' in extended:
                extended = extended.split('\n')[0].strip()
            
            # Remove quotes if present
            if extended.startswith('"') and extended.endswith('"'):
                extended = extended[1:-1]
            if extended.startswith("'") and extended.endswith("'"):
                extended = extended[1:-1]
            
            # Clean up
            extended = re.sub(r'\s+', ' ', extended).strip()
            extended = extended.replace(' | ', ', ').replace('|', ',')
            
            # Truncate if over 200
            if len(extended) > 200:
                # Try to cut at a reasonable point
                extended = extended[:197]
                # Find last comma or space
                last_comma = extended.rfind(',')
                last_space = extended.rfind(' ')
                cut_point = max(last_comma, last_space)
                if cut_point > 150:
                    extended = extended[:cut_point].strip()
            
            # Validate it's reasonable
            if len(extended) > len(title) and len(extended) <= 200:
                print(f"      Extended to {len(extended)} chars")
                return extended
            else:
                print(f"      Extension result: {len(extended)} chars - keeping original")
        
        return title

    # =========================================================================
    # MAIN OPTIMIZATION PIPELINE
    # =========================================================================
    def optimize(self, base_title: str, truth: Dict) -> Tuple[str, Dict]:
        """
        Run the complete agentic optimization pipeline.
        
        Steps:
        1. Parse title into concepts
        2. Detect category (AI Agent 1)
        3. Evaluate concepts - keep/remove (AI Agent 2)
        4. Get keywords from vector DB
        5. Rank keywords (AI Agent 3)
        6. Build optimized title (AI Agent 4)
        7. Validate (AI Agent 5)
        """
        print("\n" + "="*60)
        print("  AGENTIC TITLE OPTIMIZER")
        print("="*60)
        print(f"\nOriginal: {base_title}")
        print(f"Length: {len(base_title)} chars")
        
        report = {
            'original_title': base_title,
            'original_length': len(base_title),
            'steps': [],
            'agents_used': []
        }
        
        if not self.enabled:
            print("\n⚠️  AI is disabled. Enable with ADKRUX_USE_AI=true")
            return base_title, report

        # Lock exact facts from the original title so the LLM doesn't rewrite them
        truth = dict(truth or {})
        truth['_locked'] = self._extract_locked_truth_from_title(base_title)
        locked_pack = truth.get('_locked', {}).get('count_exact')
        locked_dim = truth.get('_locked', {}).get('dimension_exact')
        # Prefer locked exact values when truth is missing/weak
        if locked_pack and not truth.get('count'):
            truth['count'] = locked_pack
        if locked_dim and not truth.get('dimension'):
            truth['dimension'] = locked_dim
        
        # STEP 1: Parse title into concepts
        print("\n[Step 1] Parsing title...")
        tokens = parser.parse_title(base_title, truth)
        concepts = []
        for t in tokens:
            if t.token_type != TokenType.SEPARATOR:
                concepts.append({
                    'text': t.text,
                    'type': t.token_type.value,
                    'locked': t.locked
                })
        print(f"   Extracted {len(concepts)} concepts")
        report['steps'].append(f"Parsed {len(concepts)} concepts")
        
        # STEP 2: Detect category (AI Agent 1)
        category_info = self.detect_category(base_title, truth)
        report['agents_used'].append('Category Detector')
        report['category'] = category_info
        
        # STEP 3: Evaluate key concepts (AI Agent 2)
        print("\n[Step 3] Evaluating concepts...")
        evaluated_concepts = []
        
        # Find concepts that need AI evaluation (Premium, Scented, etc.)
        needs_evaluation = ['premium', 'scented', 'deluxe', 'superior', 'quality']
        
        for c in concepts:
            text_lower = c['text'].lower()
            
            # Check if this concept needs AI evaluation
            should_evaluate = any(term in text_lower for term in needs_evaluation)
            
            if should_evaluate:
                eval_result = self.evaluate_concept(
                    c['text'], 
                    c['type'],
                    {
                        'product': truth.get('product', ''),
                        'brand': truth.get('brand', ''),
                        'category': category_info.get('category', 'general'),
                        'existing_concepts': [x['text'] for x in concepts]
                    }
                )
                c['ai_evaluation'] = eval_result
                c['keep'] = eval_result.get('keep', True)
                print(f"   AI evaluated '{c['text']}': keep={c['keep']} ({eval_result.get('reason', '')})")
            else:
                c['keep'] = True
            
            if c['keep']:
                evaluated_concepts.append(c)
        
        report['agents_used'].append('Concept Evaluator')
        report['steps'].append(f"Evaluated concepts, keeping {len(evaluated_concepts)}")
        
        # STEP 4: Get keywords from vector DB
        print("\n[Step 4] Searching keyword database...")

        db_keywords, retrieval_report = self._retrieve_keywords_multiquery(base_title, truth, category_info)
        print(f"   Found {len(db_keywords)} merged candidates from vector DB")
        report['steps'].append(f"Retrieved {len(db_keywords)} merged keyword candidates")
        report['vector_retrieval'] = {
            'queries': retrieval_report.get('queries', [])[:30],
            'top_preview': db_keywords[:15],
        }
        
        # STEP 5: Rank keywords (AI Agent 3)
        existing_concept_texts = [c['text'].lower() for c in evaluated_concepts]
        selected_keywords = self.rank_keywords(
            existing_concept_texts,
            db_keywords,
            {
                'product': truth.get('product', ''),
                'brand': truth.get('brand', ''),
                'category': category_info.get('category', 'general')
            }
        )
        report['agents_used'].append('Keyword Ranker')
        report['selected_keywords'] = selected_keywords
        
        # STEP 6: Build optimized title (AI Agent 4)
        title_result = self.build_optimized_title(
            truth,
            evaluated_concepts,
            selected_keywords,
            category_info,
            original_title=base_title
        )
        report['agents_used'].append('Zone Builder')
        
        optimized_title = title_result.get('full_title', base_title)
        optimized_title = self._enforce_locked_substrings(optimized_title, truth.get('_locked', {}) or {})
        report['title_result'] = title_result
        
        # STEP 7: Validate (AI Agent 5)
        validation = self.validate_title(optimized_title, truth)
        report['agents_used'].append('Title Validator')
        report['validation'] = validation
        
        # STEP 8: Extend if too short (AI Agent 6)
        if len(optimized_title) < 170:
            optimized_title = self.extend_title(
                optimized_title, 
                truth, 
                selected_keywords,
                category_info,
                target_length=190
            )
            report['agents_used'].append('Title Extender')
            optimized_title = self._enforce_locked_substrings(optimized_title, truth.get('_locked', {}) or {})
            # Re-validate after extension
            validation = self.validate_title(optimized_title, truth)
            report['validation'] = validation
        
        # If validation still fails, try to fix
        if not validation['is_valid'] and validation['issues']:
            print("\n[Step 8b] Title has remaining issues...")
            report['needs_refinement'] = True
        
        # Final output
        print("\n" + "="*60)
        print("  OPTIMIZATION COMPLETE")
        print("="*60)
        print(f"\n✨ OPTIMIZED TITLE ({len(optimized_title)} chars):")
        print(f"   {optimized_title}")
        print(f"\n📊 Agents used: {len(report['agents_used'])}")
        for agent in report['agents_used']:
            print(f"   - {agent}")
        
        report['optimized_title'] = optimized_title
        report['final_length'] = len(optimized_title)
        
        return optimized_title, report


# Factory function
def create_agentic_optimizer() -> AgenticOptimizer:
    """Create an agentic optimizer instance."""
    return AgenticOptimizer()


# Test function
def test_agentic_optimizer():
    """Test the agentic optimizer with sample products."""
    
    optimizer = create_agentic_optimizer()
    
    # Test case 1: Shalimar Garbage Bags
    print("\n" + "="*80)
    print("TEST CASE 1: Shalimar Garbage Bags")
    print("="*80)
    
    title1 = "Shalimar Premium (Lavender Fragrance) Scented Garbage Bags | Medium 19 X 21 Inches | 120 Bags (30 Bags X 4 Rolls) | Dustbin Bag/Trash Bag | (Black) - Perforated Box for Easy Dispensing"
    
    truth1 = {
        'brand': 'Shalimar',
        'product': 'Garbage Bags',
        'size': 'Medium',
        'color': 'Black',
        'count': '120 Bags (30 x 4 Rolls)',
        'dimension': '19 x 21 Inches',
        'features': ['Lavender Fragrance', 'Scented', 'Perforated Box', 'Easy Dispensing']
    }
    
    optimized1, report1 = optimizer.optimize(title1, truth1)
    
    print("\n\n" + "="*80)
    print("COMPARISON:")
    print("="*80)
    print(f"\nORIGINAL ({len(title1)} chars):")
    print(f"   {title1}")
    print(f"\nOPTIMIZED ({len(optimized1)} chars):")
    print(f"   {optimized1}")
    
    # Expected ideal output for reference
    ideal = "Shalimar Scented Garbage Bags Medium 19x21\" 120(30bags x 4rolls), Premium Black Dustbin Bags Medium Size for Kitchen with Lavender Fragrance"
    print(f"\nIDEAL REFERENCE ({len(ideal)} chars):")
    print(f"   {ideal}")


if __name__ == "__main__":
    test_agentic_optimizer()
