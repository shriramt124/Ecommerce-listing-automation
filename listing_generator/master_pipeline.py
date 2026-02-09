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

import os
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
from agentic_llm import OpenAIConfig, OpenAILLM
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
        ingest_keywords: bool = False,
        gemini_api_key: str = None,
        gemini_model: str = None,
        limit: int = None,
    ):
        self.client_excel = client_excel
        self.browse_node_dir = browse_node_dir
        self.generate_images_flag = generate_images
        self.ingest_keywords_flag = ingest_keywords
        self.limit = limit

        # Output directory with timestamp
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = output_dir or os.path.join(_PARENT_DIR, "listing_output", f"run_{ts}")

        # Gemini config (for vision/image tasks only)
        self.gemini_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = gemini_model or os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")

        if not self.gemini_key:
            raise RuntimeError("GEMINI_API_KEY is required for vision/image tasks. Set it in .env or pass --gemini-key")

        # OpenAI config (primary LLM for all text generation)
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-5.1")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")

        # Will be initialized lazily
        self._llm: Optional[OpenAILLM] = None
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
    def llm(self) -> OpenAILLM:
        if self._llm is None:
            self._llm = OpenAILLM(OpenAIConfig(
                api_key=self.openai_api_key,
                model=self.openai_model,
            ))
        return self._llm

    @property
    def keyword_db(self) -> KeywordDB:
        if self._keyword_db is None:
            self._keyword_db = KeywordDB()
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

    def _stage_image_analysis(
        self, product: Dict[str, Any], product_idx: int,
    ) -> Dict[str, Any]:
        """Stage 3a: Analyze product images."""
        temp_dir = os.path.join(self.output_dir, "temp_images", f"product_{product_idx}")
        return self.image_analyzer.analyze_product(product, temp_dir)

    def _stage_keywords(
        self, product: Dict[str, Any], image_analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Stage 3b: Retrieve relevant keywords from vector DB.
        
        STRATEGY: Prioritize high-volume keywords NOT already in the title.
        """
        title = product.get("title", "")
        title_lower = title.lower()
        product_type = image_analysis.get("product_type", "")
        brand = image_analysis.get("brand", "")

        # Build multiple queries for broad coverage
        queries = set()
        if title:
            queries.add(title[:80])
        if product_type:
            queries.add(product_type)
        if brand and product_type:
            queries.add(f"{brand} {product_type}")
        # Add key features as queries
        for feat in (image_analysis.get("key_features") or [])[:3]:
            if feat:
                queries.add(f"{product_type} {feat}" if product_type else feat)

        # --- NEW: Extract queries from EXISTING BULLET POINTS ---
        existing_bullets = product.get("bullet_points", [])
        for bp in existing_bullets:
            bp_text = str(bp).strip()
            if bp_text and len(bp_text) > 10:
                # Use bullet point text as a query (truncated)
                queries.add(bp_text[:80])
                # Also combine product_type + bullet for focused results
                if product_type:
                    queries.add(f"{product_type} {bp_text[:50]}")

        # --- NEW: Use Brand from Excel raw_row ---
        excel_brand = product.get("raw_row", {}).get("Brand", "") or ""
        if excel_brand and not brand:
            brand = excel_brand
        if excel_brand and product_type:
            queries.add(f"{excel_brand} {product_type}")

        # --- NEW: Use la_cat (browse node) for better category coverage ---
        la_cat = product.get("la_cat", "")
        if la_cat and la_cat != product_type:
            queries.add(la_cat)
            if brand:
                queries.add(f"{brand} {la_cat}")

        # --- NEW: Add usage/audience queries from image analysis ---
        usage = image_analysis.get("usage", "")
        if usage:
            queries.add(usage[:60])
        target_audience = image_analysis.get("target_audience", "")
        if target_audience and product_type:
            queries.add(f"{product_type} {target_audience[:40]}")

        # --- NEW: Add material + product_type combo ---
        material = image_analysis.get("material", "")
        if material and product_type:
            queries.add(f"{material} {product_type}")

        # --- NEW: Add color + product_type (customers search by color) ---
        colors = image_analysis.get("colors") or []
        for color in colors[:2]:
            if color and product_type:
                queries.add(f"{color} {product_type}")

        # --- NEW: LLM-generated queries for smarter coverage ---
        # Let the LLM think like a customer: "what would people search for?"
        llm_queries = self._generate_llm_queries(product_type, brand, image_analysis)
        for q in llm_queries:
            queries.add(q)

        # Merge results from all queries
        merged: Dict[str, Dict[str, Any]] = {}
        for q in queries:
            results = self.keyword_db.get_top_keywords(str(q), limit=25)
            for r in results:
                kw = str(r.get("keyword", "")).strip().lower()
                if not kw:
                    continue
                # Keep highest similarity + score for each keyword
                if kw not in merged:
                    merged[kw] = r
                else:
                    # If duplicate, keep the one with higher score (search volume)
                    if float(r.get("score", 0)) > float(merged[kw].get("score", 0)):
                        merged[kw] = r

        # CRITICAL: Separate keywords into "already in title" vs "new"
        already_in_title = []
        new_keywords = []
        
        for kw_data in merged.values():
            kw_text = kw_data.get("keyword", "").lower()
            # Check if keyword is substantially present in title
            if kw_text in title_lower:
                already_in_title.append(kw_data)
            else:
                # Check for partial word matches (e.g., "dumbbell" matches "dumbbells")
                kw_words = set(kw_text.split())
                title_words = set(title_lower.split())
                overlap = len(kw_words & title_words) / len(kw_words) if kw_words else 0
                if overlap > 0.7:  # 70% of keyword words already in title
                    already_in_title.append(kw_data)
                else:
                    new_keywords.append(kw_data)

        # Sort NEW keywords by search volume (score), not similarity
        new_keywords_sorted = sorted(
            new_keywords,
            key=lambda x: float(x.get("score", 0)),
            reverse=True,
        )

        # Sort existing keywords by similarity (for context)
        existing_sorted = sorted(
            already_in_title,
            key=lambda x: float(x.get("similarity", 0)),
            reverse=True,
        )

        # PRIORITIZE: New high-volume keywords first, then existing for context
        candidates = new_keywords_sorted[:40] + existing_sorted[:20]

        print(f"   🔑 Retrieved {len(candidates)} keyword candidates ({len(new_keywords_sorted)} new, {len(existing_sorted)} existing)")
        print(f"      Top NEW keywords by search volume:")
        for i, kw in enumerate(new_keywords_sorted[:5], 1):
            score = float(kw.get("score", 0))
            sim = float(kw.get("similarity", 0))
            print(f"      {i}. {kw['keyword']} (volume={score:.0f}, sim={sim:.3f})")

        return candidates

    def _generate_llm_queries(
        self, product_type: str, brand: str, image_analysis: Dict[str, Any],
    ) -> List[str]:
        """Ask the LLM to think like a customer and generate search queries.

        This replaces hundreds of lines of hardcoded category dictionaries with
        a single generic LLM call that works for ANY product category.
        """
        material = image_analysis.get("material", "")
        colors = ", ".join(image_analysis.get("colors") or [])
        usage = image_analysis.get("usage", "")
        target_audience = image_analysis.get("target_audience", "")
        key_features = image_analysis.get("key_features") or []

        prompt = f"""You are an Amazon search expert. Given this product, generate 8-12 search
queries that REAL CUSTOMERS would type into the Amazon search bar to find it.

Product Type : {product_type}
Brand        : {brand}
Material     : {material}
Colors       : {colors}
Usage        : {usage}
Audience     : {target_audience}
Features     : {'; '.join(key_features[:4])}

Think about:
- What words do customers use? (e.g. "dumbbells for women", "hand weights")
- Audience variations (for men, for women, for beginners, for home)
- Material/feature combos ("neoprene dumbbells", "cast iron kettlebell")
- Use-case phrases ("home gym equipment", "fitness training weights")
- Common synonyms customers might search

Return ONLY a JSON array of query strings, 2-6 words each:
["query 1", "query 2", ...]

JSON:"""

        try:
            raw = self.llm.generate(prompt, temperature=0.3, max_tokens=500)
            if raw:
                import json as _json
                # Extract JSON array from response
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                queries = _json.loads(raw)
                if isinstance(queries, list):
                    clean = [str(q).strip().lower() for q in queries if isinstance(q, str) and len(str(q).strip()) > 3]
                    print(f"      🤖 LLM generated {len(clean)} search queries")
                    for q in clean[:5]:
                        print(f"         - {q}")
                    return clean[:12]
        except Exception as e:
            print(f"      ⚠️  LLM query generation failed: {e}")

        return []

    def _stage_title(
        self, product: Dict[str, Any], image_analysis: Dict[str, Any],
        keywords: List[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Stage 3c: Optimize title using the existing agentic pipeline."""
        base_title = product.get("title", "")
        if not base_title:
            return "", {}

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
    ) -> Tuple[List[str], str, str]:
        """Stage 3d-f: Generate bullets, description, search terms."""
        print(f"   📝 Generating content...")

        # Bullet points
        bullets = self.bullet_agent.run(product, image_analysis, keywords)
        print(f"      ✅ 5 bullet points generated")

        # Description
        description = self.desc_agent.run(product, image_analysis, keywords)
        print(f"      ✅ Description: {len(description)} chars")

        # Search terms
        search_terms = self.search_agent.run(optimized_title, bullets, keywords)
        print(f"      ✅ Search terms: {len(search_terms)} chars")

        return bullets, description, search_terms

    def _stage_images(
        self,
        product: Dict[str, Any],
        image_analysis: Dict[str, Any],
        product_idx: int,
        optimized_title: str = "",
        bullets: List[str] = None,
        description: str = "",
    ) -> Dict[str, bool]:
        """Stage 3g: Generate listing images using ALL analyzed content (no hallucination)."""
        if not self.generate_images_flag:
            return {}

        print(f"   🎨 Generating listing images...")
        creator = self._get_image_creator()

        img_dir = os.path.join(self.output_dir, "images", f"product_{product_idx}")

        # Use first available local image as reference
        ref_image = None
        local_paths = image_analysis.get("local_image_paths", [])
        if local_paths:
            ref_image = local_paths[0]
        elif product.get("images"):
            ref_image = product["images"][0]

        # Pass ALL generated content to prevent hallucination
        return creator.generate_all(
            image_analysis=image_analysis,
            optimized_title=optimized_title,
            bullets=bullets or [],
            description=description,
            country=product.get("country", "US"),
            output_dir=img_dir,
            reference_image=ref_image,
            pause_between=3,
        )

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
        print(f"  Text LLM     : OpenAI / {self.openai_model}")
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
        output_rows: List[Dict[str, Any]] = []
        total = len(products)

        for idx, product in enumerate(products):
            print(f"\n{'━' * 70}")
            print(f"  [{idx + 1}/{total}] {product.get('title', 'NO TITLE')[:60]}...")
            print(f"  ASIN: {product.get('asin', 'N/A')} | Country: {product.get('country', 'N/A')}")
            print(f"{'━' * 70}")

            try:
                # 3a. Image analysis
                image_analysis = self._stage_image_analysis(product, idx)

                # 3b. Keywords
                keywords = self._stage_keywords(product, image_analysis)

                # 3c. Title optimization (pass keywords for fallback)
                optimized_title, title_report = self._stage_title(product, image_analysis, keywords)
                if not optimized_title:
                    optimized_title = product.get("title", "")

                # 3d-f. Content generation
                bullets, description, search_terms = self._stage_content(
                    product, image_analysis, keywords, optimized_title,
                )

                # 3g. Image generation using ALL analyzed content (no hallucination)
                image_results = self._stage_images(
                    product, image_analysis, idx,
                    optimized_title=optimized_title,
                    bullets=bullets,
                    description=description,
                )

                # Build image file paths for embedding in Excel
                img_dir = os.path.join(self.output_dir, "images", f"product_{idx}")
                image_paths = {}
                if image_results:
                    for img_key, img_file in [
                        ("main_image", "main_product.png"),
                        ("lifestyle", "lifestyle.png"),
                        ("why_choose_us", "why_choose_us.png"),
                    ]:
                        fpath = os.path.join(img_dir, img_file)
                        if image_results.get(img_key) and os.path.isfile(fpath):
                            image_paths[img_key] = fpath

                # AI description from image analysis
                ai_description = image_analysis.get("ai_description", "")

                # Build output row
                row = build_output_row(
                    product=product,
                    optimized_title=optimized_title,
                    ai_description=ai_description,
                    bullets=bullets,
                    description=description,
                    search_terms=search_terms,
                    image_paths=image_paths,
                )
                output_rows.append(row)

                # Save analysis JSON for debugging
                write_analysis_json(product, image_analysis, optimized_title, self.output_dir)

                print(f"   ✅ Product {idx + 1} complete")

            except Exception as e:
                print(f"   ❌ Error processing product {idx + 1}: {e}")
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

            # Brief pause between products
            if idx < total - 1:
                time.sleep(1)

        # Stage 4: Write output
        print(f"\n{'=' * 70}")
        print(f"  WRITING OUTPUT")
        print(f"{'=' * 70}")

        output_excel = os.path.join(self.output_dir, "listing_output.xlsx")
        write_excel(output_rows, output_excel)

        print(f"\n{'=' * 70}")
        print(f"  ✨ LISTING GENERATION COMPLETE")
        print(f"     Products processed: {total}")
        print(f"     Successful: {sum(1 for r in output_rows if r.get('ai descr') != 'ERROR')}")
        print(f"     Output: {output_excel}")
        print(f"{'=' * 70}")

        return output_excel
