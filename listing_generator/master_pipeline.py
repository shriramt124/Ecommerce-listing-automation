"""
MASTER PIPELINE
===============
Orchestrates the full Amazon listing generation flow:

  Stage 1 → Parse client Excel → list of products
  Stage 2 → Ingest browse-node keywords (one-time)
  Stage 3 → For each product:
              a. Analyze images         (ImageAnalyzer)
              b. Retrieve keywords      (KeywordDB)
              c. Optimize title         (AgenticOptimizationPipeline)
              d. Generate bullet points (BulletPointAgent)
              e. Generate description   (DescriptionAgent)
              f. Generate search terms  (SearchTermsAgent)
              g. Generate images        (ImageCreator) — optional
  Stage 4 → Write output Excel + save images
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure parent dir (agentic_strategy_2) is on sys.path
_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from gemini_llm import GeminiConfig, GeminiLLM
from agentic_llm import OllamaConfig, OllamaLLM, extract_json_object
from agentic_pipeline import AgenticOptimizationPipeline
from keyword_db import KeywordDB
from parser import parser as title_parser

from listing_generator.client_parser import parse_client_excel
from listing_generator.browse_node_mapper import (
    ingest_browse_node_keywords,
    build_category_map,
    match_product_to_category,
)
from listing_generator.image_analyzer import ImageAnalyzer
from listing_generator.content_agents import BulletPointAgent, DescriptionAgent, SearchTermsAgent
from listing_generator.output_writer import (
    build_output_row,
    write_excel,
    save_product_images,
    write_analysis_json,
    load_existing_excel,
)


class ListingPipeline:
    """
    End-to-end Amazon listing generator.

    Usage:
        pipe = ListingPipeline(
            client_excel="input/lqs-GMR_AE.xlsx",
            browse_node_dir="input/Browse_Node_UK/",
            output_dir="output/",
        )
        pipe.run()
    """

    def __init__(
        self,
        client_excel: str,
        browse_node_dir: str = None,
        output_dir: str = None,
        *,
        generate_images: bool = False,
        images_only: bool = False,
        ingest_keywords: bool = False,
        gemini_api_key: str = None,
        gemini_model: str = None,
        limit: int = None,
        skip: int = 0,
        keyword_index_path: str = None,
        search_terms_only: bool = False,
        analysis_dir: str = None,
        banner_image_only: bool = False,
        lifestyle_image_only: bool = False,
        main_image_only: bool = False,
        why_choose_us_only: bool = False,
    ):
        self.client_excel = client_excel
        self.browse_node_dir = browse_node_dir
        self.generate_images_flag = generate_images
        self.images_only = images_only
        self.search_terms_only = search_terms_only
        self.analysis_dir = analysis_dir
        
        # If images_only is requested, force generate_images ON
        if self.images_only:
            self.generate_images_flag = True

        # If search_terms_only, disable images
        if self.search_terms_only:
            self.generate_images_flag = False
            
        self.ingest_keywords_flag = ingest_keywords
        self.limit = limit
        self.skip = skip
        self.keyword_index_path = keyword_index_path
        self.banner_image_only = banner_image_only
        self.lifestyle_image_only = lifestyle_image_only
        self.main_image_only = main_image_only
        self.why_choose_us_only = why_choose_us_only

        # Output directory with timestamp
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = output_dir or os.path.join(_PARENT_DIR, "listing_output", f"run_{ts}")

        # Gemini config (for vision/image tasks only)
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = gemini_model or os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")

        if not self.gemini_key:
            raise RuntimeError("GEMINI_API_KEY is required for vision/image tasks. Set it in .env or pass --gemini-key")

        # Ollama config (primary LLM for all text generation)
        self.ollama_model = os.getenv("OLLAMA_MODEL", "deepseek-v3.1:671b-cloud")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        # Will be initialized lazily
        self._llm: Optional[OllamaLLM] = None
        self._keyword_db: Optional[KeywordDB] = None
        self._title_pipeline: Optional[AgenticOptimizationPipeline] = None
        self._image_analyzer: Optional[ImageAnalyzer] = None
        self._bullet_agent: Optional[BulletPointAgent] = None
        self._desc_agent: Optional[DescriptionAgent] = None
        self._search_agent: Optional[SearchTermsAgent] = None
        self._image_creator = None  # Optional[ImageCreator]

    # ------------------------------------------------------------------
    # Lazy initialization
    # ------------------------------------------------------------------

    @property
    def llm(self) -> OllamaLLM:
        if self._llm is None:
            self._llm = OllamaLLM(OllamaConfig(
                model=self.ollama_model,
                base_url=self.ollama_base_url,
                timeout_s=180,
            ))
        return self._llm

    @property
    def keyword_db(self) -> KeywordDB:
        if self._keyword_db is None:
            self._keyword_db = KeywordDB(index_path=self.keyword_index_path)
        return self._keyword_db

    @property
    def title_pipeline(self) -> AgenticOptimizationPipeline:
        if self._title_pipeline is None:
            self._title_pipeline = AgenticOptimizationPipeline()
        return self._title_pipeline

    @property
    def image_analyzer(self) -> ImageAnalyzer:
        if self._image_analyzer is None:
            self._image_analyzer = ImageAnalyzer(
                gemini_api_key=self.gemini_key,
                model=self.gemini_model,
            )
        return self._image_analyzer

    @property
    def bullet_agent(self) -> BulletPointAgent:
        if self._bullet_agent is None:
            self._bullet_agent = BulletPointAgent(self.llm)
        return self._bullet_agent

    @property
    def desc_agent(self) -> DescriptionAgent:
        if self._desc_agent is None:
            self._desc_agent = DescriptionAgent(self.llm)
        return self._desc_agent

    @property
    def search_agent(self) -> SearchTermsAgent:
        if self._search_agent is None:
            self._search_agent = SearchTermsAgent(self.llm)
        return self._search_agent

    def _get_image_creator(self):
        """Lazy-load ImageCreator (requires google-genai)."""
        if self._image_creator is None:
            from listing_generator.image_creator import ImageCreator
            self._image_creator = ImageCreator(gemini_api_key=self.gemini_key)
        return self._image_creator

    # ------------------------------------------------------------------
    # Stage methods
    # ------------------------------------------------------------------

    def _stage_ingest(self) -> None:
        """Stage 0: Optionally ingest browse-node keywords."""
        if not self.ingest_keywords_flag:
            return
        if not self.browse_node_dir:
            print("   ⚠️  No browse-node directory specified, skipping ingestion.")
            return
        ingest_browse_node_keywords(self.browse_node_dir, reset=False)

    def _stage_parse(self) -> List[Dict[str, Any]]:
        """Stage 1: Parse client Excel."""
        return parse_client_excel(self.client_excel)

    def _load_cached_analysis(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Try to load cached image analysis from analysis_dir."""
        if not self.analysis_dir:
            return None

        asin = product.get("asin", "")
        if not asin:
            return None

        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in asin)
        json_path = os.path.join(self.analysis_dir, f"{safe_name}_analysis.json")

        if not os.path.isfile(json_path):
            print(f"      ⚠️  No cached analysis for {asin} at {json_path}")
            return None

        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            ia = data.get("image_analysis", {})
            if ia and ia.get("status") == "SUCCESS":
                print(f"      📂 Loaded cached image analysis for {asin}")
                return ia
            else:
                print(f"      ⚠️  Cached analysis for {asin} has no successful image_analysis")
                return None
        except Exception as e:
            print(f"      ⚠️  Failed to load cached analysis for {asin}: {e}")
            return None

    def _stage_image_analysis(
        self, product: Dict[str, Any], product_idx: int,
    ) -> Dict[str, Any]:
        """Stage 3a: Analyze product images (or load from cache)."""
        # Try cache first
        cached = self._load_cached_analysis(product)
        if cached is not None:
            return cached

        temp_dir = os.path.join(self.output_dir, "temp_images", f"product_{product_idx}")
        return self.image_analyzer.analyze_product(product, temp_dir)

    def _stage_keywords(
        self, product: Dict[str, Any], image_analysis: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, float], Dict[str, bool]]:
        """Stage 3b: 3-round agentic keyword discovery (from listing_pipeline).

        Round 1 — Wide sweep: LLM + programmatic queries → search_broad (no limit)
                  + product relevance embedding filter
        Round 2 — LLM judge: top 80 keywords judged relevant/not + gap-fill queries
        Round 3 — Synonym expansion (conditional): only if gap-fill found >=3 new in top 60

        Returns:
            (all_candidates, round1_queries, product_relevance, relevance_map)
        """
        title = product.get("title", "")
        title_lower = title.lower()

        # -- Product relevance embedding (single matmul, <1ms) --
        product_desc = self._build_product_description(product, image_analysis)
        product_relevance_threshold = 0.30
        print(f"   📐 Computing product relevance embedding...")
        product_relevance = self.keyword_db.compute_product_relevance(product_desc)
        total_rel = sum(1 for v in product_relevance.values() if v >= product_relevance_threshold)
        print(f"      {total_rel} keywords above relevance threshold ({product_relevance_threshold})")

        # ============================================================
        #  ROUND 1 — WIDE SWEEP
        # ============================================================
        print(f"\n   {'─'*50}")
        print(f"   🔍 ROUND 1: Wide Sweep — generating queries...")

        ai_queries = self._round1_generate_queries(product, image_analysis)
        fallback_queries = self._build_fallback_queries(product, image_analysis)

        # Dedup queries
        seen_q: set = set()
        round1_queries: List[str] = []
        for q in ai_queries + fallback_queries:
            ql = q.strip().lower()
            if ql and ql not in seen_q:
                seen_q.add(ql)
                round1_queries.append(q.strip())

        print(f"      LLM generated {len(ai_queries)} queries + {len(fallback_queries)} fallbacks "
              f"= {len(round1_queries)} unique")
        for i, q in enumerate(round1_queries[:8], 1):
            print(f"        {i}. \"{q}\"")
        if len(round1_queries) > 8:
            print(f"        ... +{len(round1_queries) - 8} more")

        # Sweep vector DB (NO limit cap — search_broad)
        merged: Dict[str, Dict[str, Any]] = {}
        for q in round1_queries:
            results = self.keyword_db.search_broad(q, min_similarity=0.25)
            for r in results:
                kw = str(r.get("keyword", "")).strip().lower()
                if not kw:
                    continue
                if kw not in merged:
                    merged[kw] = {**r, "hit_queries": [q], "hit_count": 1}
                else:
                    prev = merged[kw]
                    if float(r.get("similarity", 0)) > float(prev.get("similarity", 0)):
                        keep_hq = prev.get("hit_queries", [])
                        keep_hc = prev.get("hit_count", 0)
                        merged[kw] = {**r, "hit_queries": keep_hq, "hit_count": keep_hc}
                    if q not in prev.get("hit_queries", []):
                        merged[kw].setdefault("hit_queries", []).append(q)
                    merged[kw]["hit_count"] = merged[kw].get("hit_count", 0) + 1

        print(f"      Vector DB returned {len(merged)} unique keywords")

        # Attach product relevance + filter low relevance
        for kw in list(merged.keys()):
            pr = product_relevance.get(kw, 0.0)
            merged[kw]["product_relevance"] = pr
            if pr < product_relevance_threshold:
                del merged[kw]

        pool = sorted(merged.values(), key=lambda x: float(x.get("score", 0)), reverse=True)
        print(f"      After relevance filter: {len(pool)} keywords")
        vol_1k = sum(1 for x in pool if float(x.get("score", 0)) >= 1000)
        print(f"      Keywords with vol >= 1,000: {vol_1k}")

        # ============================================================
        #  ROUND 2 — LLM JUDGE + GAP FILL
        # ============================================================
        print(f"\n   {'─'*50}")
        print(f"   🧑‍⚖️ ROUND 2: LLM Judge + Gap Fill...")

        top_for_judge = pool[:80]
        relevance_map, gap_queries = self._round2_judge_and_gap_fill(
            product, image_analysis, top_for_judge,
        )

        relevant_count = sum(1 for v in relevance_map.values() if v)
        not_relevant_count = sum(1 for v in relevance_map.values() if not v)
        print(f"      LLM judged: {relevant_count} relevant, {not_relevant_count} not relevant")
        print(f"      Gap-fill queries generated: {len(gap_queries)}")

        # Remove NOT-relevant keywords
        removed_by_llm: List[str] = []
        for kw in list(merged.keys()):
            if kw in relevance_map and not relevance_map[kw]:
                del merged[kw]
                removed_by_llm.append(kw)

        if removed_by_llm:
            print(f"      Removed {len(removed_by_llm)} irrelevant keywords:")
            for kw in removed_by_llm[:10]:
                print(f"        ✗ {kw}")

        # Track pre-gap top 60 for convergence check
        pre_gap_top60 = set(
            kw for kw, _ in sorted(
                ((k, float(v.get("score", 0))) for k, v in merged.items()),
                key=lambda x: x[1], reverse=True,
            )[:60]
        )

        # Run gap-fill queries
        if gap_queries:
            new_gap_queries: List[str] = []
            for q in gap_queries:
                ql = q.strip().lower()
                if ql not in seen_q:
                    seen_q.add(ql)
                    new_gap_queries.append(q.strip())
            if new_gap_queries:
                print(f"      Running {len(new_gap_queries)} gap-fill queries...")
                new_added = 0
                for q in new_gap_queries:
                    gap_results = self.keyword_db.search_broad(q, min_similarity=0.25)
                    for r in gap_results:
                        kw = str(r.get("keyword", "")).strip().lower()
                        if not kw:
                            continue
                        pr = product_relevance.get(kw, 0.0)
                        if pr < product_relevance_threshold:
                            continue
                        if kw in relevance_map and not relevance_map[kw]:
                            continue
                        r["product_relevance"] = pr
                        r["round_discovered"] = 2
                        if kw not in merged:
                            merged[kw] = r
                            new_added += 1
                        else:
                            merged[kw]["hit_count"] = merged[kw].get("hit_count", 0) + 1
                print(f"      Gap-fill added {new_added} new keywords")

        # Check convergence
        pool = sorted(merged.values(), key=lambda x: float(x.get("score", 0)), reverse=True)
        post_gap_top60 = set(str(x.get("keyword", "")).lower() for x in pool[:60])
        new_in_top60 = post_gap_top60 - pre_gap_top60
        print(f"      New keywords in top 60: {len(new_in_top60)}")

        # ============================================================
        #  ROUND 3 — SYNONYM EXPANSION (conditional)
        # ============================================================
        run_round3 = len(new_in_top60) >= 3

        if run_round3:
            print(f"\n   {'─'*50}")
            print(f"   🔄 ROUND 3: Synonym Expansion (convergence not reached)...")
            found_kw_names = [str(x.get("keyword", "")) for x in pool[:40]]
            synonym_queries = self._round3_synonym_expansion(product, image_analysis, found_kw_names)

            new_syn_queries: List[str] = []
            for q in synonym_queries:
                ql = q.strip().lower()
                if ql not in seen_q:
                    seen_q.add(ql)
                    new_syn_queries.append(q.strip())

            if new_syn_queries:
                print(f"      Running {len(new_syn_queries)} synonym queries...")
                syn_added = 0
                for q in new_syn_queries:
                    syn_results = self.keyword_db.search_broad(q, min_similarity=0.25)
                    for r in syn_results:
                        kw = str(r.get("keyword", "")).strip().lower()
                        if not kw:
                            continue
                        pr = product_relevance.get(kw, 0.0)
                        if pr < product_relevance_threshold:
                            continue
                        if kw in relevance_map and not relevance_map[kw]:
                            continue
                        r["product_relevance"] = pr
                        r["round_discovered"] = 3
                        if kw not in merged:
                            merged[kw] = r
                            syn_added += 1
                        else:
                            merged[kw]["hit_count"] = merged[kw].get("hit_count", 0) + 1
                print(f"      Synonym expansion added {syn_added} new keywords")
        else:
            print(f"\n   ⏩ Skipping Round 3 (convergence reached — "
                  f"only {len(new_in_top60)} new in top 60)")

        # ============================================================
        #  FINAL ASSEMBLY
        # ============================================================
        print(f"\n   {'─'*50}")
        print(f"   📊 FINAL ASSEMBLY")

        # Tag round_discovered for round 1 keywords
        for data in merged.values():
            if "round_discovered" not in data:
                data["round_discovered"] = 1

        all_candidates = sorted(
            merged.values(),
            key=lambda x: float(x.get("score", 0)),
            reverse=True,
        )

        # Tag "already in title"
        for kw_data in all_candidates:
            kw_text = kw_data.get("keyword", "").lower()
            kw_words = set(kw_text.split())
            t_words = set(title_lower.split())
            overlap = len(kw_words & t_words) / len(kw_words) if kw_words else 0
            kw_data["in_title"] = overlap > 0.7 or kw_text in title_lower

        # Report
        new_kw = [k for k in all_candidates if not k.get("in_title")]
        in_title = [k for k in all_candidates if k.get("in_title")]
        r1 = sum(1 for k in all_candidates if k.get("round_discovered") == 1)
        r2 = sum(1 for k in all_candidates if k.get("round_discovered") == 2)
        r3 = sum(1 for k in all_candidates if k.get("round_discovered") == 3)

        print(f"      Total keywords: {len(all_candidates)} "
              f"({len(new_kw)} new, {len(in_title)} in title)")
        print(f"      By round: R1={r1}, R2={r2}, R3={r3}")
        print(f"      LLM calls used: {'3' if run_round3 else '2'}")
        print(f"\n      TOP 50 by volume:")
        for i, kw in enumerate(all_candidates[:50], 1):
            flag = "📌" if kw.get("in_title") else "🆕"
            vol = float(kw.get("score", 0))
            pr = float(kw.get("product_relevance", 0))
            hc = int(kw.get("hit_count", 0))
            rd = int(kw.get("round_discovered", 1))
            print(f"      {flag} {i:>2}. {kw['keyword']:<40s} "
                  f"vol={vol:>8.0f}  rel={pr:.2f}  hits={hc:>2}  R{rd}")

        return all_candidates, round1_queries, product_relevance, relevance_map

    # ------------------------------------------------------------------
    # Keyword discovery helper methods (ported from listing_pipeline)
    # ------------------------------------------------------------------

    def _build_product_description(
        self, product: Dict[str, Any], image_analysis: Dict[str, Any],
    ) -> str:
        """Build a rich product description for the relevance embedding."""
        parts: List[str] = []
        pt = (image_analysis.get("product_type") or "").strip()
        if pt:
            parts.append(pt)
        brand = (image_analysis.get("brand") or "").strip()
        if brand:
            parts.append(brand)
        size = (image_analysis.get("size") or "").strip()
        if size:
            parts.append(size)
        material = (image_analysis.get("material") or "").strip()
        if material:
            parts.append(material)
        colors = image_analysis.get("colors") or []
        if colors:
            parts.append(" ".join(colors))
        usage = (image_analysis.get("usage") or "").strip()
        if usage:
            parts.append(usage)
        audience = (image_analysis.get("target_audience") or "").strip()
        if audience:
            parts.append(audience)
        qty = (image_analysis.get("quantity") or "").strip()
        if qty:
            parts.append(qty)
        features = image_analysis.get("key_features") or []
        if features:
            parts.append(" ".join(features[:4]))
        manual = product.get("manual", "").strip()
        if manual:
            parts.append(manual[:200])
        return " ".join(parts)

    def _build_fallback_queries(
        self, product: Dict[str, Any], image_analysis: Dict[str, Any],
    ) -> List[str]:
        """Programmatic fallback queries that always run (no LLM needed)."""
        title = product.get("title", "")
        product_type = (image_analysis.get("product_type") or "").strip().lower()
        brand = (image_analysis.get("brand")
                 or product.get("raw_row", {}).get("Brand", "") or "").strip().lower()

        fb: List[str] = []
        if product_type:
            fb.append(product_type)
            if product_type.endswith("s"):
                fb.append(product_type[:-1])
            else:
                fb.append(product_type + "s")
        if brand and product_type:
            fb.append(f"{brand} {product_type}")
        if title:
            clean = title.lower()
            if brand:
                clean = clean.replace(brand, "").strip()
            clean = re.sub(r'[–—|/\\()\[\]{}]', ' ', clean)
            clean = re.sub(r'\s+', ' ', clean).strip()
            if clean and len(clean) > 10:
                fb.append(clean[:70])

        # Bullet points as queries
        for bp in (product.get("bullet_points") or [])[:3]:
            bp_text = str(bp).strip()
            if bp_text and len(bp_text) > 10:
                fb.append(bp_text[:80])

        # la_cat browse node
        la_cat = product.get("la_cat", "")
        if la_cat and la_cat.lower() != product_type:
            fb.append(la_cat)

        # Material/color combos
        material = (image_analysis.get("material") or "").strip().lower()
        if material and product_type:
            fb.append(f"{material} {product_type}")
        for color in (image_analysis.get("colors") or [])[:2]:
            if color and product_type:
                fb.append(f"{color.lower()} {product_type}")

        # Usage/audience
        usage = (image_analysis.get("usage") or "").strip()
        if usage:
            fb.append(usage[:60])
        audience = (image_analysis.get("target_audience") or "").strip()
        if audience and product_type:
            fb.append(f"{product_type} {audience[:40]}")

        return fb

    def _extract_title_used_rank_keywords(
        self,
        optimized_title: str,
        keywords: List[Dict[str, Any]],
        max_items: int = 12,
    ) -> str:
        """Return ranked keywords used in title (hybrid: deterministic + LLM refinement)."""
        title = (optimized_title or "").strip().lower()
        if not title or not keywords:
            return ""

        title_norm = re.sub(r"\s+", " ", title)
        seen: set = set()
        matched: List[Dict[str, Any]] = []
        by_keyword: Dict[str, Dict[str, Any]] = {}

        def _rank_key(item: Dict[str, Any]) -> int:
            rank = item.get("rank")
            try:
                r = int(rank)
                return r if r > 0 else 10**9
            except Exception:
                return 10**9

        for kw in sorted(keywords, key=_rank_key):
            phrase = str(kw.get("keyword", "") or "").strip().lower()
            if not phrase or phrase in seen:
                continue
            by_keyword[phrase] = kw

            pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
            if re.search(pattern, title_norm):
                matched.append(kw)
                seen.add(phrase)
                if len(matched) >= max_items:
                    break

        # LLM refinement: helps catch normalized variants while restricting to provided keyword list only.
        try:
            candidate_keywords = sorted(keywords, key=_rank_key)[:80]
            candidate_lines = []
            for kw in candidate_keywords:
                p = str(kw.get("keyword", "") or "").strip().lower()
                if not p:
                    continue
                r = kw.get("rank")
                r_text = str(r) if r not in (None, "", 0) else "N/A"
                candidate_lines.append(f"- {p} | rank={r_text}")

            if candidate_lines:
                prompt = f"""Find which ranked keywords are used in this Amazon title.

TITLE:
{optimized_title}

CANDIDATE KEYWORDS (use only these):
{chr(10).join(candidate_lines)}

Rules:
1) Return only keywords that appear in the title (exact phrase or obvious punctuation/spacing variant).
2) Do NOT invent new keywords.
3) Keep rank from the candidate list.
4) Max {max_items} items.

Return ONLY valid JSON:
{{
  "matched": [
    {{"keyword": "...", "rank": "..."}}
  ]
}}
JSON:"""

                raw = self.llm.generate(prompt, temperature=0.0, max_tokens=700)
                obj = extract_json_object(raw or "")
                for item in (obj.get("matched", []) if isinstance(obj, dict) else []):
                    phrase = str((item or {}).get("keyword", "") or "").strip().lower()
                    if not phrase:
                        continue
                    if phrase not in by_keyword:
                        continue
                    if phrase in seen:
                        continue
                    matched.append(by_keyword[phrase])
                    seen.add(phrase)
                    if len(matched) >= max_items:
                        break
        except Exception:
            pass

        # Final canonical formatting sorted by rank
        out = []
        for kw in sorted(matched, key=_rank_key)[:max_items]:
            phrase = str(kw.get("keyword", "") or "").strip().lower()
            rank = kw.get("rank")
            rank_text = str(rank) if rank not in (None, "", 0) else "N/A"
            out.append(f"{phrase} (rank {rank_text})")
        return "; ".join(out)

    def _round1_generate_queries(
        self, product: Dict[str, Any], image_analysis: Dict[str, Any],
    ) -> List[str]:
        """Round 1: LLM generates 30-40 structured search queries."""
        title = product.get("title", "")
        product_type = (image_analysis.get("product_type") or "").strip()
        brand = (image_analysis.get("brand")
                 or product.get("raw_row", {}).get("Brand", "") or "").strip()
        size = (image_analysis.get("size") or "").strip()
        material = (image_analysis.get("material") or "").strip()
        colors = ", ".join(image_analysis.get("colors") or [])
        usage = (image_analysis.get("usage") or "").strip()
        target_audience = (image_analysis.get("target_audience") or "").strip()
        key_features = ", ".join((image_analysis.get("key_features") or [])[:6])
        quantity = (image_analysis.get("quantity") or "").strip()
        la_cat = (product.get("la_cat") or "").strip()

        prompt = f"""You are an Amazon search expert. A customer wants to find this EXACT product on Amazon.

PRODUCT:
- Title: "{title}"
- Type: {product_type}
- Brand: {brand}
- Size/Weight: {size}
- Quantity: {quantity}
- Material: {material}
- Colors: {colors}
- Features: {key_features}
- Usage: {usage}
- Target Audience: {target_audience}
- Category: {la_cat}

Generate 30-40 Amazon search queries that REAL customers would type to find this product.

REQUIRED CATEGORIES (generate queries for EACH):
1. CORE PRODUCT: Just the product type, singular and plural forms
2. PRODUCT + SPEC: Product with size, weight, count, or dimensions
3. PRODUCT + MATERIAL: Product with material or coating
4. SYNONYMS: Alternative names customers use for this product type
5. USE-CASE: Product + where/how it's used
6. AUDIENCE: Product + who it's for
7. BRAND: Brand + product combinations
8. COLOR/STYLE: Product + color or visual attributes
9. MISSPELLINGS: Common typos customers make

ORDER: Generate from broadest (1-2 words) to most specific (3-5 words).

RULES:
- Each query 1-5 words (real search bar behavior)
- Only queries for THIS SPECIFIC product (correct size/weight/type)
- Short search phrases only, no full sentences
- No duplicates
- Include both singular and plural forms where natural

Return ONLY valid JSON:
{{"queries": ["query1", "query2", ...]}}

JSON:"""

        try:
            raw = self.llm.generate(prompt, temperature=0.4, max_tokens=2000)
            if raw:
                obj = extract_json_object(raw)
                if obj and "queries" in obj:
                    queries: List[str] = []
                    for q in obj["queries"]:
                        q = str(q).strip().lower()
                        if q and len(q) > 1 and len(q.split()) <= 7:
                            queries.append(q)
                    print(f"      🤖 LLM generated {len(queries)} search queries")
                    for q in queries[:8]:
                        print(f"         - {q}")
                    return queries
        except Exception as e:
            print(f"      ⚠️  LLM query generation failed: {e}")

        return []

    def _round2_judge_and_gap_fill(
        self, product: Dict[str, Any], image_analysis: Dict[str, Any],
        top_keywords: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, bool], List[str]]:
        """Round 2: LLM judges relevance of top keywords + generates gap queries."""
        title = product.get("title", "")
        product_type = (image_analysis.get("product_type") or "").strip()
        brand = (image_analysis.get("brand") or "").strip()
        size = (image_analysis.get("size") or "").strip()
        material = (image_analysis.get("material") or "").strip()
        la_cat = (product.get("la_cat") or "").strip()

        lines: List[str] = []
        for i, kw in enumerate(top_keywords, 1):
            keyword = kw.get("keyword", "")
            vol = float(kw.get("score", 0))
            sim = float(kw.get("product_relevance", kw.get("similarity", 0)))
            lines.append(f"  {i:>3}. {keyword:<45s} vol={vol:>8.0f}  sim={sim:.2f}")
        keyword_table = "\n".join(lines)

        prompt = f"""You are an Amazon keyword expert reviewing search keywords for a SPECIFIC product.

PRODUCT:
- Title: "{title}"
- Type: {product_type}
- Brand: {brand}
- Size/Weight: {size}
- Material: {material}
- Category: {la_cat}

Here are the TOP {len(top_keywords)} keywords found by search volume:
{keyword_table}

TWO TASKS:

TASK 1 — RELEVANCE JUDGMENT:
For each keyword above, mark it "relevant" or "not_relevant".
A keyword is NOT relevant if:
- It's for a DIFFERENT product category (e.g. "kettlebell" for a dumbbell product)
- It specifies a WRONG size/weight (e.g. "5kg dumbbells" for a 1kg product)
- It's for a different form factor (e.g. "adjustable dumbbells" for fixed neoprene dumbbells)
- It has nothing to do with this product

A keyword IS relevant if:
- It describes this product or a broader category it belongs to
- It's a synonym customers use for this type of product
- It matches the product's specs, material, use-case, or audience
- It's the product type without specific size (e.g. "dumbbells set" for any dumbbell)

TASK 2 — GAP ANALYSIS:
Look at what search angles are MISSING from the keywords found.
Generate 10-15 NEW search queries to find keywords we haven't covered yet.
Think about: synonyms, slang, abbreviations, different phrasings, use-cases not covered.

Return ONLY valid JSON:
{{
  "judgments": [
    {{"keyword": "keyword1", "relevant": true}},
    {{"keyword": "keyword2", "relevant": false, "reason": "wrong product type"}}
  ],
  "gap_queries": ["new query 1", "new query 2"]
}}

JSON:"""

        relevance_map: Dict[str, bool] = {}
        gap_queries: List[str] = []

        try:
            raw = self.llm.generate(prompt, temperature=0.1, max_tokens=4000)
            if raw:
                obj = extract_json_object(raw)
                if obj:
                    for j in (obj.get("judgments") or []):
                        kw = str(j.get("keyword", "")).strip().lower()
                        if kw:
                            relevance_map[kw] = bool(j.get("relevant", True))
                    for q in (obj.get("gap_queries") or []):
                        q = str(q).strip().lower()
                        if q and len(q) > 1 and len(q.split()) <= 7:
                            gap_queries.append(q)
        except Exception as e:
            print(f"      ⚠️  LLM judge failed: {e}")

        # Keywords not judged → assume relevant
        for kw_data in top_keywords:
            k = str(kw_data.get("keyword", "")).strip().lower()
            if k and k not in relevance_map:
                relevance_map[k] = True

        return relevance_map, gap_queries

    def _round3_synonym_expansion(
        self, product: Dict[str, Any], image_analysis: Dict[str, Any],
        found_keywords: List[str],
    ) -> List[str]:
        """Round 3: Generate synonym/misspelling/slang queries."""
        title = product.get("title", "")
        product_type = (image_analysis.get("product_type") or "").strip()
        found_str = "\n".join(f"  - {kw}" for kw in found_keywords[:30])

        prompt = f"""You are an Amazon search expert. We have already found the top keywords for this product.
Now we need to find ADDITIONAL keywords through synonyms, slang, misspellings, and alternative phrasings.

PRODUCT:
- Title: "{title}"
- Type: {product_type}

TOP KEYWORDS ALREADY FOUND:
{found_str}

Generate 10-15 search queries that would find keywords we HAVEN'T found yet.
Think about:
- Common misspellings (e.g. "dumbells" for "dumbbells", "excercise" for "exercise")
- Slang and informal terms customers use
- Alternative product names from different regions
- Different word orderings
- Related accessories or complementary product terms

RULES:
- Do NOT repeat the keywords already found above
- 1-5 words per query
- Focus on genuinely new search angles

Return ONLY valid JSON:
{{"queries": ["query1", "query2", ...]}}

JSON:"""

        try:
            raw = self.llm.generate(prompt, temperature=0.5, max_tokens=1000)
            if raw:
                obj = extract_json_object(raw)
                if obj and "queries" in obj:
                    queries: List[str] = []
                    for q in obj["queries"]:
                        q = str(q).strip().lower()
                        if q and len(q) > 1 and len(q.split()) <= 7:
                            queries.append(q)
                    return queries
        except Exception as e:
            print(f"      ⚠️  Synonym expansion failed: {e}")
        return []

    def _stage_title(
        self, product: Dict[str, Any], image_analysis: Dict[str, Any],
        keywords: List[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Stage 3c: Optimize title using the existing agentic pipeline."""
        base_title = product.get("title", "")
        
        # --- Synthesize title if missing (e.g. input is just ASIN/Images) ---
        if not base_title or len(base_title.strip()) < 5:
            print(f"      ⚠️  Title missing/too short. Synthesizing base title from image analysis...")
            
            # Extract components from image analysis
            brand_s = image_analysis.get("brand") or "Generic"
            p_type_s = image_analysis.get("product_type") or "Product"
            name_s = image_analysis.get("product_name") or ""
            
            # Start with Brand
            synth_parts = [brand_s]
            
            # Add Product Name or Type
            if name_s and len(name_s) > 3 and "unknown" not in name_s.lower():
                 synth_parts.append(name_s)
            elif p_type_s and "unknown" not in p_type_s.lower():
                 synth_parts.append(p_type_s)
            else:
                 synth_parts.append("Product")
                 
            # Add Specs to give the optimizer enough context
            if image_analysis.get("size"):
                synth_parts.append(str(image_analysis["size"]))
            if image_analysis.get("material"):
                synth_parts.append(str(image_analysis["material"]))
            if image_analysis.get("colors") and isinstance(image_analysis["colors"], list):
                if image_analysis["colors"]:
                    synth_parts.append(image_analysis["colors"][0])
            if image_analysis.get("quantity"):
                synth_parts.append(str(image_analysis["quantity"]))
                
            # Check features for "Pack" count if not in quantity
            features_text = " ".join((image_analysis.get("features_on_packaging") or []))
            if "pack" in features_text.lower() and "pack" not in " ".join(synth_parts).lower():
                # Try to extract pack size roughly if possible, or just leave it
                pass

            base_title = " ".join([p for p in synth_parts if p and p.lower() != "null"]).strip()
            print(f"      ✨ Synthesized Start Title: {base_title}")

        if not base_title:
            return "Product Title Unknown", {}

        # Build truth from image analysis + product data (FULL data for better optimization)
        # Use Excel Brand column as fallback for brand
        excel_brand = product.get("raw_row", {}).get("Brand", "") or ""
        analysis_brand = image_analysis.get("brand") or ""
        resolved_brand = analysis_brand or excel_brand

        truth = {
            "brand": resolved_brand,
            "product": image_analysis.get("product_type") or "",
            "size": image_analysis.get("size") or "",
            "color": ", ".join(image_analysis.get("colors") or []) or "",
            "count": image_analysis.get("quantity") or "",
            "material": image_analysis.get("material") or "",
            "usage": image_analysis.get("usage") or "",
            "key_features": image_analysis.get("key_features") or [],
            "ai_description": image_analysis.get("ai_description") or "",
            "target_audience": image_analysis.get("target_audience") or "",
            "product_name": image_analysis.get("product_name") or "",
            "manual": product.get("manual", ""),
        }

        print(f"   ✍️  Optimizing title...")
        # Pass the pre-filtered high-volume keywords to the agentic pipeline
        optimized, report = self.title_pipeline.optimize(base_title, truth, pre_filtered_keywords=keywords)

        # If the pipeline returned the same title, do a direct Gemini fallback
        if optimized.strip() == base_title.strip() or len(optimized) < 170:
            print(f"      ⚠️  Title unchanged or too short ({len(optimized)} chars), using direct optimization...")
            optimized = self._direct_title_optimize(base_title, image_analysis, keywords or [], product=product)

        print(f"      Original : {base_title[:80]}...")
        print(f"      Optimized: {optimized[:80]}...")
        print(f"      Length   : {len(optimized)} chars")

        return optimized, report

    def _direct_title_optimize(
        self, base_title: str, image_analysis: Dict[str, Any],
        keywords: List[Dict[str, Any]],
        product: Dict[str, Any] = None,
    ) -> str:
        """Fallback: directly ask Gemini to optimize the title with keyword data."""
        # Use brand from multiple sources
        brand = image_analysis.get("brand") or ""
        if not brand and product:
            brand = product.get("raw_row", {}).get("Brand", "") or ""
        product_type = image_analysis.get("product_type") or ""
        colors = ", ".join(image_analysis.get("colors") or [])
        size = image_analysis.get("size") or image_analysis.get("size_info") or ""
        quantity = image_analysis.get("quantity") or ""
        material = image_analysis.get("material") or image_analysis.get("material_visible") or ""
        usage = image_analysis.get("usage") or ""
        key_features = image_analysis.get("key_features") or image_analysis.get("features_on_packaging") or []

        # Also pull features from existing bullets if available
        existing_bullets = (product or {}).get("bullet_points", [])
        if existing_bullets and not key_features:
            key_features = existing_bullets[:5]

        # Deduplicate keywords and pick top unique ones
        seen = set()
        unique_kws = []
        for kw in keywords:
            k = str(kw.get("keyword", "")).strip().lower()
            if k and k not in seen:
                seen.add(k)
                unique_kws.append(kw)

        kw_text = "\n".join(
            f"- {kw['keyword']} (search volume score: {kw.get('score', 0)})"
            for kw in unique_kws[:20]
        )

        # Pass raw features to the LLM — it can identify title-worthy
        # features for ANY product category (no hardcoded feature dictionary)
        features_text = ", ".join(str(f) for f in key_features) if key_features else "(none)"
        ai_description = image_analysis.get("ai_description") or image_analysis.get("description") or ""

        brand_upper = brand.upper().strip() if brand else ""

        prompt = f"""You are a senior Amazon listing copywriter.

TASK — rewrite the title so it reads like a polished product description
while embedding as many high-volume search keywords as possible.

EXPERT EXAMPLES (study the rhythm):
• "KAKSS Neoprene Dumbbells Set, 1kg Pair (2 x 1kg), Pink Hex Dumbbells with Anti-Slip Coated Grip, Cast Iron Hand Weights for Home Gym Equipment and Fitness Training"
• "KAKSS Vinyl Kettlebell, 4kg Competition Kettlebell with Wide Handle, Cast Iron Kettlebells for Strength Training, HIIT and Core Workout"

ORIGINAL TITLE:
"{base_title}"

PRODUCT DATA (verified from images):
*** CRITICAL: VISUAL FACTS OVERRIDE ORIGINAL TITLE ***
If the Original Title contradicts these facts (e.g. wrong color, wrong count), you MUST use the facts below.
  Brand        : {brand_upper}
  Product Type : {product_type}
  Colors       : {colors}
  Size/Weight  : {size}
  Quantity     : {quantity}
  Material     : {material}
  Usage        : {usage}
  Key Features : {features_text}
  AI Description: {ai_description[:200] if ai_description else '(none)'}

HIGH-VOLUME SEARCH KEYWORDS (sorted by search volume — embed the top ones):
{kw_text if kw_text else '(none available)'}

STRATEGY: Look at the keywords above. The words that appear in the HIGHEST
volume keywords should appear in your title. see you do not necessary to pick up the Full phrase 
but if you feel some words form those can fit in our title that will makes sense then you have to use that 
but first priority is to use the phrase from the keyword list and if you feel some words from those keywords can be weaved into the title in a natural way then you can use that as well but do not forcefully use the words if they do not fit in the title
.

RULES:
1. Start with "{brand_upper}" (uppercase brand)
2. Natural comma-separated flow — NO pipes (|), NO keyword stuffing
3. Pattern: Brand + Material + Product Type + CleanWeight + Color + Feature + "with" phrase + "for" phrase
4. Weight must be clean: "1kg Pair (2 x 1kg)" NOT "1+1=2 KG"
5. Weave the highest-volume keywords into real product phrases
6. Extract title-worthy features from Key Features and AI Description (material, shape, finish, coating, grip, mechanism, etc.)
7. 180-200 characters, factually accurate
8. DO NOT invent features, DO NOT use superlatives

Output ONLY the optimized title text (one line, no quotes):"""

        raw = self.llm.generate(prompt, temperature=0.4, max_tokens=2000)
        if not raw:
            print(f"      ⚠️  Direct optimize: No response from LLM")
            return base_title

        result = raw.strip().split("\n")[0].strip()
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]
        if result.startswith("'") and result.endswith("'"):
            result = result[1:-1]

        import re
        result = re.sub(r"\s+", " ", result).strip()
        result = result.replace(" | ", ", ").replace("|", ",")

        # Hard cap 200
        if len(result) > 200:
            result = result[:197]
            last_sep = max(result.rfind(","), result.rfind(" "))
            if last_sep > 150:
                result = result[:last_sep].strip()

        # Accept if different from original and reasonable length
        if result.strip() != base_title.strip() and len(result) >= 100:
            print(f"      ✅ Direct optimize: Accepted ({len(result)} chars)")
            return result
        print(f"      ⚠️  Direct optimize: Rejected (len={len(result)}, same={result.strip() == base_title.strip()})")
        print(f"         Raw result: {result[:100]}...")
        return base_title

    def _stage_content(
        self,
        product: Dict[str, Any],
        image_analysis: Dict[str, Any],
        keywords: List[Dict[str, Any]],
        optimized_title: str,
        kw_queries: List[str] = None,
        product_relevance: Dict[str, float] = None,
        relevance_map: Dict[str, bool] = None,
    ) -> Tuple[List[str], str, str]:
        """Stage 3d-f: Generate bullets, description, search terms."""
        print(f"   📝 Generating content...")

        # Bullet points
        bullets = self.bullet_agent.run(product, image_analysis, keywords)
        print(f"      ✅ 5 bullet points generated")

        # Description
        description = self.desc_agent.run(product, image_analysis, keywords)
        print(f"      ✅ Description: {len(description)} chars")

        # Dedicated broader keyword retrieval for search terms
        if kw_queries and product_relevance is not None:
            search_kw = self._get_search_term_keywords(
                kw_queries, product_relevance, relevance_map or {},
                top_n=150,
            )
            print(f"      🔍 Dedicated search term keywords: {len(search_kw)} (top 150 by volume)")
        else:
            search_kw = keywords
            print(f"      ⚠️ No dedicated queries — using shared keyword pool ({len(search_kw)})")

        # Search terms (now with dedicated broader keyword pool)
        search_terms = self.search_agent.run(optimized_title, bullets, search_kw, image_analysis)
        print(f"      ✅ Search terms: {len(search_terms)} chars")

        return bullets, description, search_terms

    def _get_search_term_keywords(
        self,
        queries: List[str],
        product_relevance: Dict[str, float],
        relevance_map: Dict[str, bool],
        top_n: int = 150,
        relevance_threshold: float = 0.30,
    ) -> List[Dict[str, Any]]:
        """Run a dedicated broader sweep for search term keywords.

        Re-runs ALL the same queries from _stage_keywords against the vector DB
        with a slightly lower similarity floor to cast a wider net, then applies
        the same product relevance + LLM judge filters, and returns top N by volume.
        """
        merged: Dict[str, Dict[str, Any]] = {}

        for q in queries:
            results = self.keyword_db.search_broad(q, min_similarity=0.20)
            for r in results:
                kw = str(r.get("keyword", "")).strip().lower()
                if not kw:
                    continue

                # Product relevance filter
                pr = product_relevance.get(kw, 0.0)
                if pr < relevance_threshold:
                    continue

                # LLM judge filter — skip keywords explicitly marked NOT relevant
                if kw in relevance_map and not relevance_map[kw]:
                    continue

                r["product_relevance"] = pr

                if kw not in merged:
                    merged[kw] = r
                else:
                    # Keep highest similarity
                    if float(r.get("similarity", 0)) > float(merged[kw].get("similarity", 0)):
                        pr_old = merged[kw].get("product_relevance", 0)
                        merged[kw] = {**r, "product_relevance": pr_old}

        # Sort by volume descending, take top N
        candidates = sorted(
            merged.values(),
            key=lambda x: float(x.get("score", 0)),
            reverse=True,
        )

        return candidates[:top_n]

    def _generate_comparison_points(
        self,
        product: Dict[str, Any],
        image_analysis: Dict[str, Any],
        optimized_title: str,
        bullets: List[str],
        description: str,
    ) -> List[Dict[str, str]]:
        """Generate comparison points using ALL available content.

        Called AFTER title, bullets, description, search terms are ready
        and BEFORE image generation — so the comparison is based on the
        full picture of the product, not just raw image data.
        """
        print(f"   🆚 Generating comparison points...")

        brand = image_analysis.get("brand") or ""
        product_type = image_analysis.get("product_type") or ""
        key_features = image_analysis.get("key_features") or []
        material = image_analysis.get("material") or ""
        colors = image_analysis.get("colors") or []
        ai_desc = image_analysis.get("ai_description") or ""

        prompt = f"""You are a senior Amazon listing strategist creating a "Why Choose Us vs Competitors" comparison.

PRODUCT CONTEXT:
- Brand: {brand}
- Product Type: {product_type}
- Title: {optimized_title}
- Material: {material}
- Colors: {", ".join(colors)}
- Key Features (from images & listing): {json.dumps(key_features)}
- Bullet Points: {json.dumps(bullets)}
- Description: {description[:500]}
- What AI sees in images: {ai_desc}

TASK: Generate exactly 4 comparison points. Each point should highlight a REAL advantage
of THIS product that CUSTOMERS genuinely care about, paired with a common issue in
cheaper alternatives that shoppers actually complain about.

Think from the CUSTOMER'S perspective:
- What would make someone choose THIS product over a cheaper one?
- What do negative reviews of budget alternatives commonly say?
- Focus on: durability, comfort, safety, ease of use, value for money, design quality

Return ONLY this JSON:
{{
  "comparison_points": [
    {{"our_benefit": "specific advantage of THIS product", "competitor_issue": "real complaint about cheaper alternatives"}},
    {{"our_benefit": "...", "competitor_issue": "..."}},
    {{"our_benefit": "...", "competitor_issue": "..."}},
    {{"our_benefit": "...", "competitor_issue": "..."}}
  ]
}}

RULES:
- Each point must be 1 clear sentence, max 120 chars
- our_benefit must reference actual features/materials/design of THIS product
- competitor_issue must reflect real customer frustrations with budget options
- Do NOT be generic — be specific to this product category but if you got no information that is not specific then you can be generic
- Return ONLY valid JSON"""

        for attempt in range(3):
            raw = self.llm.generate(prompt, temperature=0.2, max_tokens=1500)
            if raw:
                parsed = extract_json_object(raw)
                if parsed and "comparison_points" in parsed:
                    points = parsed["comparison_points"]
                    if isinstance(points, list) and len(points) >= 3:
                        print(f"      ✅ {len(points)} comparison points generated")
                        return points[:4]
            if attempt < 2:
                prompt += f"\n\nAttempt {attempt+1} failed. Return ONLY valid JSON with 'comparison_points' array."

        print(f"      ⚠️  Comparison points generation failed, using defaults")
        return [
            {"our_benefit": "Premium build quality and materials", "competitor_issue": "Budget alternatives often feel flimsy"},
            {"our_benefit": "Designed for comfort and ease of use", "competitor_issue": "Cheaper options can be uncomfortable"},
            {"our_benefit": "Durable construction built to last", "competitor_issue": "Low-cost versions wear out quickly"},
            {"our_benefit": "Clear branding and quality packaging", "competitor_issue": "Generic products lack quality assurance"},
        ]

    def _stage_images(
        self,
        product: Dict[str, Any],
        image_analysis: Dict[str, Any],
        product_idx: int,
        optimized_title: str = "",
        bullets: List[str] = None,
        description: str = "",
    ) -> Dict[str, str]:
        """Stage 3g: Generate listing images using ALL analyzed content (no hallucination)."""
        if not self.generate_images_flag:
            return {}

        print(f"   🎨 Generating listing images...")
        creator = self._get_image_creator()

        asin = product.get("asin", f"PRODUCT_{product_idx}")
        safe_asin = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(asin))
        img_dir = os.path.join(self.output_dir, "images", safe_asin)

        ts = datetime.now().strftime("%Y_%m_%d_%H%M%S_%f")
        if self.banner_image_only:
            output_filenames = {"banner_image": f"banner_1_{ts}.png"}
        elif self.lifestyle_image_only:
            output_filenames = {
                "lifestyle_1": f"ls_1_{ts}.png",
                "lifestyle_2": f"ls_2_{ts}.png",
                "lifestyle_3": f"ls_3_{ts}.png",
                "lifestyle_4": f"ls_4_{ts}.png",
            }
        elif self.main_image_only:
            output_filenames = {"main_image": f"main_1_{ts}.png"}
        elif self.why_choose_us_only:
            output_filenames = {"why_choose_us": f"wcs_1_{ts}.png"}
        else:
            output_filenames = {
                "main_image": f"main_1_{ts}.png",
                "lifestyle_1": f"ls_1_{ts}.png",
                "lifestyle_2": f"ls_2_{ts}.png",
                "lifestyle_3": f"ls_3_{ts}.png",
                "lifestyle_4": f"ls_4_{ts}.png",
                "why_choose_us": f"wcs_1_{ts}.png",
                "banner_image": f"banner_1_{ts}.png",
            }

        # Use first available local image as reference
        ref_image = None
        local_paths = image_analysis.get("local_image_paths", [])
        if local_paths:
            ref_image = local_paths[0]
        elif product.get("images"):
            ref_image = product["images"][0]

        # Pass ALL generated content to prevent hallucination
        image_results = creator.generate_all(
            image_analysis=image_analysis,
            optimized_title=optimized_title,
            bullets=bullets or [],
            description=description,
            country=product.get("country", "US"),
            output_dir=img_dir,
            reference_image=ref_image,
            output_filenames=output_filenames,
            banner_only=self.banner_image_only,
            lifestyle_only=self.lifestyle_image_only,
            main_only=self.main_image_only,
            why_choose_us_only=self.why_choose_us_only,
            pause_between=3,
        )

        image_paths: Dict[str, str] = {}
        for key, fname in output_filenames.items():
            fpath = os.path.join(img_dir, fname)
            if image_results.get(key) and os.path.isfile(fpath):
                image_paths[key] = fpath

        return image_paths

    # ------------------------------------------------------------------
    # Main run
    # ------------------------------------------------------------------

    def run(self) -> str:
        """
        Execute the full listing generation pipeline.
        Returns the path to the output Excel file.
        """
        print("=" * 70)
        print("  AMAZON LISTING GENERATOR")
        print("=" * 70)
        print(f"  Client Excel  : {self.client_excel}")
        print(f"  Browse Nodes  : {self.browse_node_dir or '(none)'}")
        print(f"  Output Dir    : {self.output_dir}")
        print(f"  Generate Imgs : {self.generate_images_flag}")
        print(f"  Text LLM     : Ollama / {self.ollama_model}")
        print(f"  Vision LLM   : Gemini / {os.getenv('GEMINI_VISION_MODEL', 'gemini-3-pro-image-preview')}")
        print("=" * 70)

        os.makedirs(self.output_dir, exist_ok=True)

        # Stage 0: Keyword ingestion
        self._stage_ingest()

        # Stage 1: Parse products
        products = self._stage_parse()
        if not products:
            print("❌ No products found in Excel. Exiting.")
            return ""

        if self.limit:
            products = products[:self.limit]
            print(f"\n🔹 Limiting to first {self.limit} products ({len(products)} total).")

        # Stage 2: Build category map (if browse node dir provided)
        category_map: Dict[str, str] = {}
        if self.browse_node_dir:
            category_map = build_category_map(self.browse_node_dir)

        # Stage 3: Process each product
        # Load existing rows from previous run so they are preserved on resume
        existing_rows: List[Dict[str, Any]] = []
        if self.skip > 0:
            products = products[self.skip:]
            all_existing = load_existing_excel(self.output_dir)
            existing_rows = all_existing[:self.skip]
            discarded = len(all_existing) - len(existing_rows)
            if existing_rows:
                print(f"\n📂 Loaded {len(existing_rows)} existing rows from previous output.")
                if discarded > 0:
                    print(f"   🗑️  Discarded {discarded} extra rows (error/duplicate from previous crash).")
            else:
                print(f"\n⚠️  No existing output found in {self.output_dir} — starting fresh.")
            print(f"\n⏩ Skipping first {self.skip} products (resume mode).")

        output_rows: List[Dict[str, Any]] = list(existing_rows)
        total = len(products)
        output_excel = os.path.join(self.output_dir, "listing_output.xlsx")

        for idx, product in enumerate(products):
            display_idx = idx + self.skip
            display_num = display_idx + 1
            print(f"\n{'━' * 70}")
            print(f"  [{display_num}] {product.get('title', 'NO TITLE')[:60]}...")
            print(f"  ASIN: {product.get('asin', 'N/A')} | Country: {product.get('country', 'N/A')}")
            print(f"{'━' * 70}")

            try:
                if self.images_only:
                    print("   ⏩ IMAGES-ONLY MODE: Skipping text optimization...")
                    image_analysis = self._stage_image_analysis(product, display_idx)
                    keywords = [] # Not needed for image gen if we have description
                    optimized_title = product.get("title", "")
                    bullets = product.get("bullet_points", [])
                    description = product.get("description", "")
                    search_terms = ""
                elif self.search_terms_only:
                    print("   🔍 SEARCH-TERMS-ONLY MODE: Using cached analysis...")
                    # 3a. Load cached image analysis (no Gemini Vision call)
                    image_analysis = self._stage_image_analysis(product, display_idx)

                    # 3b. Keywords (needs image_analysis for relevance embedding)
                    keywords, kw_queries, product_relevance, relevance_map = self._stage_keywords(product, image_analysis)

                    # Skip title, bullets, description — use originals
                    optimized_title = product.get("title", "")
                    bullets = product.get("bullet_points", [])
                    description = product.get("description", "")

                    # Dedicated broader keyword retrieval for search terms
                    search_kw = self._get_search_term_keywords(
                        kw_queries, product_relevance, relevance_map,
                        top_n=150,
                    )
                    print(f"      🔍 Dedicated search term keywords: {len(search_kw)} (top 150 by volume)")

                    # Generate ONLY search terms
                    search_terms = self.search_agent.run(optimized_title, bullets, search_kw, image_analysis)
                    print(f"      ✅ Search terms: {len(search_terms)} chars")
                else:
                    # 3a. Image analysis
                    image_analysis = self._stage_image_analysis(product, display_idx)

                    # 3b. Keywords
                    keywords, kw_queries, product_relevance, relevance_map = self._stage_keywords(product, image_analysis)

                    # 3c. Title optimization (pass keywords for fallback)
                    optimized_title, title_report = self._stage_title(product, image_analysis, keywords)
                    if not optimized_title:
                        optimized_title = product.get("title", "")

                    # 3d-f. Content generation
                    bullets, description, search_terms = self._stage_content(
                        product, image_analysis, keywords, optimized_title,
                        kw_queries, product_relevance, relevance_map,
                )

                # 3f-2. Generate comparison points (skip in search-terms-only mode)
                if not self.search_terms_only:
                    comparison_points = self._generate_comparison_points(
                        product, image_analysis, optimized_title,
                        bullets, description,
                    )
                    # Inject into image_analysis so image creator can use them
                    image_analysis["comparison_points"] = comparison_points

                # 3g. Image generation using ALL analyzed content (no hallucination)
                if not self.search_terms_only:
                    image_paths = self._stage_images(
                    product, image_analysis, display_idx,
                    optimized_title=optimized_title,
                    bullets=bullets,
                    description=description,
                )
                else:
                    image_paths = {}

                # AI description from image analysis
                ai_description = image_analysis.get("ai_description", "")
                title_used_rank_keywords = self._extract_title_used_rank_keywords(
                    optimized_title,
                    keywords,
                )

                # Build output row
                row = build_output_row(
                    product=product,
                    optimized_title=optimized_title,
                    ai_description=ai_description,
                    bullets=bullets,
                    description=description,
                    search_terms=search_terms,
                    title_used_rank_keywords=title_used_rank_keywords,
                    image_paths=image_paths,
                )
                output_rows.append(row)

                # Save analysis JSON for debugging
                write_analysis_json(product, image_analysis, optimized_title, self.output_dir)

                print(f"   ✅ Product {display_num} complete")

            except Exception as e:
                print(f"   ❌ Error processing product {display_num}: {e}")
                import traceback
                traceback.print_exc()
                # Still add a partial row
                output_rows.append(build_output_row(
                    product=product,
                    optimized_title=product.get("title", ""),
                    ai_description="ERROR",
                    bullets=product.get("bullet_points", []),
                    description=product.get("description", ""),
                    search_terms="",
                ))

            # Incremental save after every product so progress is never lost
            try:
                write_excel(output_rows, output_excel)
                print(f"   💾 Progress saved ({len(output_rows)} rows)")
            except Exception as save_err:
                print(f"   ⚠️  Incremental save failed: {save_err}")

            # 15-second pause between products to avoid API rate limits
            if idx < total - 1:
                print(f"   ⏳ Waiting 15s before next product...")
                time.sleep(8)

        # Stage 4: Write final output
        print(f"\n{'=' * 70}")
        print(f"  WRITING OUTPUT")
        print(f"{'=' * 70}")

        write_excel(output_rows, output_excel)

        print(f"\n{'=' * 70}")
        print(f"  ✨ LISTING GENERATION COMPLETE")
        print(f"     New products processed: {total}")
        print(f"     Previously saved rows:  {len(existing_rows)}")
        print(f"     Total rows in Excel:    {len(output_rows)}")
        print(f"     Successful: {sum(1 for r in output_rows if r.get('ai descr') != 'ERROR')}")
        print(f"     Output: {output_excel}")
        print(f"{'=' * 70}")

        return output_excel
