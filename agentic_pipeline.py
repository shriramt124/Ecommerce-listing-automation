"""Modular agentic optimization pipeline.

Goal: reduce hallucinations by splitting responsibilities into independent agents with
validated, structured outputs passed step-by-step.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

from agentic_agents import (
    CategoryDetectorAgent,
    ConceptEvaluatorAgent,
    KeywordSelectorAgent,
    QueryPlannerAgent,
    TitleComposerAgent,
    TitleExtenderAgent,
)
from gemini_llm import GeminiConfig, GeminiLLM
from agentic_llm import OllamaConfig, OllamaLLM
from agentic_runlog import RunLogger
from keyword_db import KeywordDB
from parser import parser
from token_types import TokenType


def _normalize_pack_string(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s)
    s = s.replace("×", "x").replace("*", "x")
    s = re.sub(r"\bbag\b", "Bags", s, flags=re.IGNORECASE)
    s = re.sub(r"\bbags\b", "Bags", s, flags=re.IGNORECASE)
    s = re.sub(r"\broll\b", "Rolls", s, flags=re.IGNORECASE)
    s = re.sub(r"\brolls\b", "Rolls", s, flags=re.IGNORECASE)
    s = re.sub(r"\bx\b", "x", s, flags=re.IGNORECASE)
    return s.strip()


def extract_locked_truth_from_title(base_title: str) -> Dict[str, str]:
    locked: Dict[str, str] = {}
    t = base_title or ""

    pack_patterns = [
        r"(\b\d+\s*bags?\s*\(\s*\d+\s*bags?\s*[xX×*]\s*\d+\s*rolls?\s*\))",
        r"(\b\d+\s*bags?\s*\(\s*\d+\s*[xX×*]\s*\d+\s*rolls?\s*\))",
        r"(\b\d+\s*bags?\s*\(\s*\d+\s*rolls?\s*\))",
    ]
    for pat in pack_patterns:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            locked["count_exact"] = _normalize_pack_string(m.group(1))
            break

    dim = re.search(r"(\b\d+\s*[xX×]\s*\d+\s*(?:inches?|inch|cm|mm|feet?|ft)?\b)", t, flags=re.IGNORECASE)
    if dim:
        dim_str = re.sub(r"\s+", " ", dim.group(1)).strip()
        # Convert to short form units
        dim_str = re.sub(r"\s*Inches\b", " in", dim_str, flags=re.IGNORECASE)
        dim_str = re.sub(r"\s*Inch\b", " in", dim_str, flags=re.IGNORECASE)
        dim_str = re.sub(r"\s*Feet\b", " ft", dim_str, flags=re.IGNORECASE)
        dim_str = re.sub(r"\s*Foot\b", " ft", dim_str, flags=re.IGNORECASE)
        dim_str = re.sub(r"\s*Centimeters\b", " cm", dim_str, flags=re.IGNORECASE)
        dim_str = re.sub(r"\s*Millimeters\b", " mm", dim_str, flags=re.IGNORECASE)
        locked["dimension_exact"] = dim_str.strip()

    return locked


def enforce_locked_substrings(title: str, locked: Dict[str, str]) -> str:
    # First normalize common model artifacts so later regexes match reliably.
    out = re.sub(r"\bInch\s*es\b", "Inches", str(title or ""), flags=re.IGNORECASE)
    out = re.sub(r"\bRoll\s*s\b", "Rolls", out, flags=re.IGNORECASE)
    out = re.sub(r"\bBag\s*s\b", "Bags", out, flags=re.IGNORECASE)

    pack = locked.get("count_exact")
    if pack:
        # Remove duplicate pack patterns - look for the pack string appearing twice
        # Pattern: "120 Bags (30 Bags x 4 Rolls) (30 Bags x 4 Rolls)" or similar
        # Extract the parenthetical part
        paren_match = re.search(r"\(([^)]+)\)", pack)
        if paren_match:
            paren_part = paren_match.group(1)
            # Escape for regex
            paren_escaped = re.escape(paren_part)
            # Remove duplicate parenthetical: (XXX) (XXX) -> (XXX)
            out = re.sub(
                rf"\(({paren_escaped})\)\s*\(\1\)",
                rf"(\1)",
                out,
                flags=re.IGNORECASE
            )
            # Also handle case variations: (30 Bags x 4 Rolls) (30 Bags X 4 Rolls)
            out = re.sub(
                rf"\(\d+\s*Bags\s*[xX×]\s*\d+\s*Rolls\)\s*\(\d+\s*Bags\s*[xX×]\s*\d+\s*Rolls\)",
                lambda m: m.group(0).split(')')[0] + ')',
                out,
                flags=re.IGNORECASE
            )
        
        # Now ensure the locked pack string appears correctly
        if pack not in out:
            total_m = re.search(r"\b(\d+)\s*Bags\b", pack, flags=re.IGNORECASE)
            total = total_m.group(1) if total_m else None
            if total:
                out = re.sub(
                    rf"\b{re.escape(total)}\s*bags?\b\s*(?:,|-)\s*\d+\s*rolls?\b",
                    pack,
                    out,
                    flags=re.IGNORECASE,
                    count=1,
                )
                if pack not in out:
                    out = re.sub(
                        rf"\b{re.escape(total)}\s*bags?\b",
                        pack,
                        out,
                        flags=re.IGNORECASE,
                        count=1,
                    )

    dim = locked.get("dimension_exact")
    if dim and dim not in out:
        out = re.sub(
            r"\b\d+\s*[xX×]\s*\d+\s*(?:in\s*ch\s*es?|inches?|inch|cm|mm|feet?|ft)?\b",
            dim,
            out,
            flags=re.IGNORECASE,
            count=1,
        )

    # Final cleanup: convert any remaining long-form units to abbreviations
    out = re.sub(r"\s*Inches\b", " in", out, flags=re.IGNORECASE)
    out = re.sub(r"\s*Inch\b", " in", out, flags=re.IGNORECASE)
    out = re.sub(r"\s*Feet\b", " ft", out, flags=re.IGNORECASE)
    out = re.sub(r"\s*Foot\b", " ft", out, flags=re.IGNORECASE)
    out = re.sub(r"\s*Centimeters\b", " cm", out, flags=re.IGNORECASE)
    out = re.sub(r"\s*Millimeters\b", " mm", out, flags=re.IGNORECASE)
    
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"\b(in|ft|cm|mm)(?=[A-Za-z0-9])", r"\1 ", out)
    out = re.sub(r"\s+,", ",", out)
    return out


def _is_generic_value(value: str) -> bool:
    v = str(value or "").strip().lower()
    if not v:
        return True
    return v in {
        "product",
        "unknown",
        "unknown product",
        "unknown_product",
        "n/a",
        "na",
        "none",
        "general",
    }


def _clean_query_text(text: str) -> str:
    t = re.sub(r"[\[\]{}()\"']", " ", str(text or ""))
    t = t.replace("/", " ").replace("|", " ").replace("-", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _cap_words(text: str, max_words: int = 8) -> str:
    parts = _clean_query_text(text).split()
    return " ".join(parts[:max_words]).strip()


def get_vector_query_anchors(base_title: str, truth: Dict[str, Any], category_info: Dict[str, Any]) -> List[str]:
    title_lower = str(base_title or "").lower()
    compatibility_lower = str(truth.get("compatibility", "") or "").lower()
    search_priorities = category_info.get("search_priorities", []) or []
    priorities_text = " ".join([str(p).lower() for p in search_priorities])

    anchors = set()

    if re.search(r"\bcar\b", title_lower) or re.search(r"\bcar\b", compatibility_lower) or "car" in priorities_text:
        anchors.add("car")
    if re.search(r"\bvehicle\b", title_lower) or "vehicle" in compatibility_lower:
        anchors.add("car")

    if (
        re.search(r"\bbike\b", title_lower)
        or re.search(r"\bmotor(?:bike|cycle)\b", title_lower)
        or "bike" in compatibility_lower
        or "motorcycle" in compatibility_lower
        or "bike" in priorities_text
        or "motorcycle" in priorities_text
    ):
        anchors.add("bike")

    return sorted(anchors)


def build_vector_queries(
    base_title: str,
    truth: Dict[str, Any],
    category_info: Dict[str, Any],
    concepts: List[Dict[str, Any]] | None = None,
) -> List[str]:
    anchors = get_vector_query_anchors(base_title, truth, category_info)
    anchor_phrase = " ".join(anchors).strip()

    brand = str(truth.get("brand", "") or "").strip()
    product = str(truth.get("product", "") or "").strip()
    size = str(truth.get("size", "") or "").strip()
    dim = str(truth.get("dimension", "") or "").strip()
    color = str(truth.get("color", "") or "").strip()
    compatibility = str(truth.get("compatibility", "") or "").strip()
    locked_pack = str(truth.get("_locked", {}).get("count_exact", "") or "").strip()

    # Avoid poisoning retrieval with placeholders like truth={'product': 'Product'}
    if _is_generic_value(product):
        product = ""
    if _is_generic_value(brand):
        brand = ""

    # Pull additional query phrases from parsed concepts (helps capture synonyms like
    # "dustbin bag"/"trash bag" that are present in the title but not in truth.product).
    synonym_phrases: List[str] = []
    use_case_phrases: List[str] = []
    if concepts:
        for c in concepts:
            t = str(c.get("text", "") or "").strip()
            if not t:
                continue
            typ = str(c.get("type", "") or "").strip().lower()
            if typ in {"synonym"}:
                synonym_phrases.append(t)
            elif typ in {"use_case", "compatibility"}:
                use_case_phrases.append(t)

    search_priorities = category_info.get("search_priorities", []) or []

    queries: List[str] = []

    # Helper to add a query with basic cleanup + word cap
    def add(q: str) -> None:
        qn = _cap_words(q, max_words=8)
        if qn:
            queries.append(qn)

    core_phrases: List[str] = []
    if product:
        core_phrases.append(product)
    core_phrases.extend(synonym_phrases[:3])

    # Anchor-first combos (reduces cross-category drift)
    for core in core_phrases[:3]:
        if anchor_phrase:
            add(f"{anchor_phrase} {core}")
            if size:
                add(f"{anchor_phrase} {core} {size}")
            if color:
                add(f"{anchor_phrase} {core} {color}")

        if brand:
            add(f"{brand} {core}")
            if size:
                add(f"{brand} {core} {size}")
            if color:
                add(f"{brand} {core} {color}")
            if compatibility:
                add(f"{brand} {core} {compatibility}")

        if size:
            add(f"{core} {size}")
        if color:
            add(f"{color} {core} {size}" if size else f"{color} {core}")
        if dim:
            add(f"{core} {dim}")
            if size:
                add(f"{core} {size} {dim}")
        if locked_pack:
            add(f"{core} {locked_pack}")

        # Use-cases from title (e.g., 'for kitchen')
        for uc in use_case_phrases[:2]:
            add(f"{core} {uc}")
            if brand:
                add(f"{brand} {core} {uc}")

    for p in search_priorities[:6]:
        p = str(p).strip()
        if not p:
            continue
        add(p)
        for core in core_phrases[:2]:
            add(f"{p} {core}")
        if brand:
            add(f"{brand} {p}")

    seen = set()
    out: List[str] = []
    for q in queries:
        qn = _clean_query_text(q)
        if not qn:
            continue
        key = qn.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(qn)

    return out


def validate_title(title: str, truth: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []

    if len(title) > 200:
        issues.append(f"Too long: {len(title)} chars (max 200)")
    if len(title) < 160:
        issues.append(f"Too short: {len(title)} chars (should use 180-200 for SEO)")

    title_lower = title.lower()

    if truth.get("brand") and str(truth["brand"]).lower() not in title_lower:
        issues.append(f"Missing brand: {truth['brand']}")

    if truth.get("product"):
        product_words = str(truth["product"]).lower().split()
        if not any(w in title_lower for w in product_words if len(w) > 3):
            issues.append(f"Missing product: {truth['product']}")

    if truth.get("size"):
        size = str(truth["size"]).lower()
        if size not in title_lower and size.replace(" ", "") not in title_lower:
            issues.append(f"Missing size: {truth['size']}")

    if truth.get("color") and str(truth["color"]).lower() not in title_lower:
        issues.append(f"Missing color: {truth['color']}")

    banned_terms = ["#1", "best seller", "free", "discount", "sale", "cheap"]
    for term in banned_terms:
        if term in title_lower:
            issues.append(f"Policy violation: contains '{term}'")

    return {"is_valid": len(issues) == 0, "issues": issues, "char_count": len(title)}


class AgenticOptimizationPipeline:
    def __init__(self):
        self.enabled = os.getenv("ADKRUX_USE_AI", "true").lower() == "true"
        self.ollama_model = os.getenv("OLLAMA_MODEL", "deepseek-v3.1:671b-cloud")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        self.vector_debug = os.getenv("ADKRUX_VECTOR_DEBUG", "true").lower() == "true"
        self.ai_vector_rounds = int(os.getenv("ADKRUX_AI_VECTOR_ROUNDS", "1"))
        self.vector_limit_per_query = int(os.getenv("ADKRUX_VECTOR_LIMIT_PER_QUERY", "25"))
        self.vector_max_candidates = int(os.getenv("ADKRUX_VECTOR_MAX_CANDIDATES", "60"))

        self.llm = OllamaLLM(OllamaConfig(
            model=self.ollama_model,
            base_url=self.ollama_base_url,
            timeout_s=180,
        ))
        self.keyword_db = KeywordDB()

        self.category_agent = CategoryDetectorAgent(self.llm)
        self.concept_agent = ConceptEvaluatorAgent(self.llm)
        self.query_agent = QueryPlannerAgent(self.llm)
        self.selector_agent = KeywordSelectorAgent(self.llm)
        self.composer_agent = TitleComposerAgent(self.llm)
        self.extender_agent = TitleExtenderAgent(self.llm)

        self.logger = RunLogger(root_dir=os.path.join(os.path.dirname(__file__), "runs"))

        if self.enabled and not self.llm.test_connection():
            print("⚠️  Ollama connection failed — AI agents will be disabled.")
            self.enabled = False

    def _retrieve_keywords(
        self,
        base_title: str,
        truth: Dict[str, Any],
        category_info: Dict[str, Any],
        concepts: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        report: Dict[str, Any] = {"queries": [], "results_by_query": {}}

        queries = build_vector_queries(base_title, truth, category_info, concepts=concepts)
        anchors = get_vector_query_anchors(base_title, truth, category_info)

        for _ in range(max(self.ai_vector_rounds, 0)):
            more = self.query_agent.run(
                base_title=base_title,
                truth=truth,
                category_info=category_info,
                anchors=anchors,
                existing_queries=queries,
            )
            for q in more:
                if q.lower() not in {x.lower() for x in queries}:
                    queries.append(q)

        merged: Dict[str, Dict[str, Any]] = {}
        for q in queries:
            results = self.keyword_db.get_top_keywords(q, limit=self.vector_limit_per_query)
            report["results_by_query"][q] = results[:10]
            report["queries"].append(q)

            for r in results:
                kw = str(r.get("keyword", "") or "").strip()
                if not kw:
                    continue
                key = kw.lower()
                prev = merged.get(key)
                if not prev:
                    merged[key] = {**r, "hit_queries": [q]}
                else:
                    prev_sim = float(prev.get("similarity", 0.0) or 0.0)
                    new_sim = float(r.get("similarity", 0.0) or 0.0)
                    if new_sim > prev_sim:
                        keep_queries = prev.get("hit_queries", [])
                        merged[key] = {**r, "hit_queries": keep_queries}
                    if q not in prev.get("hit_queries", []):
                        prev.setdefault("hit_queries", []).append(q)

        candidates = list(merged.values())
        candidates.sort(
            key=lambda x: (
                float(x.get("similarity", 0.0) or 0.0),
                float(x.get("score", 0.0) or 0.0),
            ),
            reverse=True,
        )
        candidates = candidates[: self.vector_max_candidates]

        if self.vector_debug:
            print("   Vector queries used:")
            for q in queries[:20]:
                print(f"      - {q}")
            print(f"   Merged candidates: {len(candidates)}")
            for i, r in enumerate(candidates[:10], 1):
                sim = float(r.get("similarity", 0.0) or 0.0)
                sc = float(r.get("score", 0.0) or 0.0)
                au = float(r.get("ad_units", 0.0) or 0.0)
                print(f"      {i}. {r.get('keyword')} | sim={sim:.3f} | score={sc:.4f} | ad_units={au:.1f}")

        return candidates, report

    def optimize(self, base_title: str, truth: Dict[str, Any], pre_filtered_keywords: List[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
        """Optimize title using 6-agent pipeline.
        
        If pre_filtered_keywords are provided (from master_pipeline with volume-based ranking),
        use those instead of doing our own vector retrieval.
        """
        report: Dict[str, Any] = {
            "original_title": base_title,
            "original_length": len(base_title or ""),
            "steps": [],
            "agents_used": [],
        }

        if not self.enabled:
            return base_title, report

        self.logger.init_run(base_title)

        truth = dict(truth or {})
        truth["_locked"] = extract_locked_truth_from_title(base_title)
        locked_pack = truth.get("_locked", {}).get("count_exact")
        locked_dim = truth.get("_locked", {}).get("dimension_exact")
        if locked_pack and not truth.get("count"):
            truth["count"] = locked_pack
        if locked_dim and not truth.get("dimension"):
            truth["dimension"] = locked_dim

        self.logger.log("truth_locked", truth)

        tokens = parser.parse_title(base_title, truth)
        concepts: List[Dict[str, Any]] = []
        for t in tokens:
            if t.token_type != TokenType.SEPARATOR:
                concepts.append({"text": t.text, "type": t.token_type.value, "locked": t.locked})

        report["steps"].append(f"Parsed {len(concepts)} concepts")
        self.logger.log("concepts", {"concepts": concepts})

        category_info = self.category_agent.run(base_title, truth)
        report["agents_used"].append("CategoryDetector")
        report["category"] = category_info
        self.logger.log("category", category_info)

        needs_eval = ["premium", "scented", "deluxe", "superior", "quality"]
        evaluated: List[Dict[str, Any]] = []
        for c in concepts:
            text_lower = str(c.get("text", "")).lower()
            should = any(term in text_lower for term in needs_eval)
            if should:
                eval_result = self.concept_agent.run(
                    concept=str(c.get("text", "")),
                    concept_type=str(c.get("type", "")),
                    context={
                        "product": truth.get("product", ""),
                        "brand": truth.get("brand", ""),
                        "category": category_info.get("category", "general"),
                        "existing_concepts": [x.get("text", "") for x in concepts],
                    },
                )
                c["ai_evaluation"] = eval_result
                c["keep"] = bool(eval_result.get("keep", True))
            else:
                c["keep"] = True

            if c.get("keep"):
                evaluated.append(c)

        report["agents_used"].append("ConceptEvaluator")
        report["steps"].append(f"Kept {len(evaluated)} concepts")
        self.logger.log("concepts_kept", {"concepts": evaluated})

        # Use pre-filtered keywords if provided (from master_pipeline with volume ranking)
        if pre_filtered_keywords:
            candidates = pre_filtered_keywords
            report["steps"].append(f"Using {len(candidates)} pre-filtered keyword candidates (volume-ranked)")
            report["vector_retrieval"] = {"source": "master_pipeline_pre_filtered", "count": len(candidates)}
        else:
            candidates, retrieval_report = self._retrieve_keywords(base_title, truth, category_info, concepts=evaluated)
            report["steps"].append(f"Retrieved {len(candidates)} keyword candidates")
            report["vector_retrieval"] = {
                "queries": (retrieval_report.get("queries") or [])[:30],
                "top_preview": candidates[:15],
            }
        self.logger.log("retrieval", report["vector_retrieval"])

        existing_texts = [str(c.get("text", "")).lower() for c in evaluated]
        selected = self.selector_agent.run(
            existing_concepts=existing_texts,
            candidates=candidates,
            context={
                "product": truth.get("product", ""),
                "brand": truth.get("brand", ""),
                "category": category_info.get("category", "general"),
            },
        )
        report["agents_used"].append("KeywordSelector")
        report["selected_keywords"] = selected
        self.logger.log("selected_keywords", {"selected_keywords": selected})

        draft = self.composer_agent.run(
            original_title=base_title,
            truth=truth,
            concepts=evaluated,
            selected_keywords=selected,
            category_info=category_info,
        )
        report["agents_used"].append("TitleComposer")
        self.logger.log("draft", draft)

        optimized = str(draft.get("full_title", base_title) or base_title).strip()
        optimized = enforce_locked_substrings(optimized, truth.get("_locked", {}) or {})
        report["title_result"] = draft

        validation = validate_title(optimized, truth)
        report["validation"] = validation
        report["agents_used"].append("Validator")

        if len(optimized) < 170:
            extended = self.extender_agent.run(
                title=optimized,
                truth=truth,
                selected_keywords=selected,
                category_info=category_info,
                target_length=190,
            )
            optimized = enforce_locked_substrings(extended, truth.get("_locked", {}) or {})
            validation = validate_title(optimized, truth)
            report["validation"] = validation
            report["agents_used"].append("TitleExtender")

        report["optimized_title"] = optimized
        report["final_length"] = len(optimized)
        self.logger.log("final", report)

        return optimized, report
