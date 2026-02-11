"""
IMAGE CREATOR
=============
Generates Amazon listing images using Gemini AI:
  1. Main product image (white background)
  2. Lifestyle image (country-specific scene)
  3. Why Choose Us comparison infographic

Wraps the existing Image_Creation module to reuse Gemini generation logic.
"""

from __future__ import annotations

import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load .env from Image_Creation folder (has Gemini + Groq keys)
_image_creation_env = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Image_Creation", ".env",
)
if os.path.exists(_image_creation_env):
    load_dotenv(_image_creation_env)

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

MAIN_IMAGE_PROMPT = """I am providing you the ORIGINAL product image from the Amazon listing.
Generate an IMPROVED, more professional version of THIS EXACT same product.

PRODUCT TITLE: {optimized_title}
BRAND: {brand}
PRODUCT TYPE: {product_type}

KEY FEATURES (from analysis):
{key_features}

COLORS: {colors}

CRITICAL RULES:
1. The product in your generated image MUST be the SAME product as in the reference image I provided.
2. Pure white (#FFFFFF) background — Amazon mandatory.
3. NO props, NO text overlays, NO logos, NO watermarks.
4. Product fills 80-85% of frame.
5. Professional studio lighting with soft shadows.
6. Colors MUST match the reference image exactly: {colors}
7. High resolution, 1024×1024 square.
8. Photorealistic quality — better than the original.
9. Same packaging, same labels, same shape as the reference.
10. DO NOT change the product design, only improve the photography quality.

Generate a BETTER version of the reference product image now."""


MAIN_IMAGE_PROMPT_NO_REF = """Generate a professional Amazon main product image.

PRODUCT TITLE: {optimized_title}
BRAND: {brand}
PRODUCT TYPE: {product_type}

KEY FEATURES (from analysis):
{key_features}

COLORS: {colors}

REQUIREMENTS:
1. Pure white (#FFFFFF) background — Amazon mandatory.
2. Show ONLY the product matching the title and features above.
3. NO props, NO text overlays, NO logos.
4. Product fills 80-85% of frame.
5. Professional studio lighting, crisp shadows.
6. Colors must match exactly: {colors}
7. High resolution, 1024×1024 square.
8. Photorealistic quality.
9. DO NOT add features not listed above.

Generate the product image now."""


LIFESTYLE_PROMPT = """I am providing you the ORIGINAL product image. Generate a lifestyle image showing THIS EXACT product in use.

PRODUCT TITLE: {optimized_title}

BULLET POINTS (actual listing content — use ONLY these features):
{bullets}

COUNTRY/MARKET: {country}

SCENE:
- Setting: {setting}
- Person: {person_description}
- Activity: {use_case}
- Mood: {mood}

CRITICAL RULES:
1. The product in the scene MUST look exactly like the reference image I provided.
2. Product MUST be clearly visible and in use.
3. {country_cultural_notes}
4. Natural lighting, warm atmosphere.
5. Show product being used as described in bullets above.
6. Professional quality, 1024×1024 square.
7. Person looks authentic for {country}.
8. NO text overlays or watermarks.
9. Only show features mentioned in bullets — do NOT invent new features.
10. The product design, colors, and packaging must match the reference.

Generate the lifestyle image now."""


WHY_CHOOSE_PROMPT = """I am providing you the ORIGINAL product image. Generate a professional Amazon-style comparison infographic featuring THIS EXACT product.

PRODUCT TITLE: {optimized_title}
BRAND: {brand}

DESCRIPTION (our actual product):
{description}

=== LAYOUT: PREMIUM SIDE-BY-SIDE COMPARISON (Amazon Infographic Style) ===

LEFT SIDE — "OUR BRAND" (OUR PRODUCT):
- Background: Premium white with subtle gradient, professional lighting
- Header: "OUR BRAND" in bold premium typography (gold/purple accent)
- Show the EXACT product from the reference image in perfect lighting
- Below the product, show FEATURE HIGHLIGHTS with ✓ checkmarks in vibrant green:
{our_features}

RIGHT SIDE — "COMPETITORS":
- Background: Neutral light gray (NOT ugly, just less premium feel)
- Header: "COMPETITORS" in standard gray typography
- Show a SIMILAR product type but with slightly less premium appearance:
  • Duller colors (NOT ugly, just less vibrant)
  • Standard packaging (NOT damaged, just plain)
  • Basic finish (NOT broken, just ordinary)
- Below it, show comparison points with neutral ○ or standard dash marks:
{competitor_issues}

=== CRITICAL DESIGN RULES (Amazon Premium Infographic Standards) ===
1. This is a PROFESSIONAL Amazon product infographic used by top brands (Anker, Apple, Samsung)
2. Competitor side shows a REAL alternative product — decent but less premium (like a budget brand)
3. DO NOT make competitor ugly/broken/damaged — show a real budget alternative
4. Use CLEAN professional typography, premium design, high-quality graphics
5. Elegant vertical divider line (thin, subtle) between the two sides
6. Our product MUST match the reference image EXACTLY in colors, design, branding
7. Colors for our product: {colors}
8. 1024×1024 square, photorealistic rendering, professional lighting
9. Think: How would Apple/Nike/Amazon Basics present this comparison?
10. ONLY use features from the description — NO hallucination or invented claims
11. Both sides should look professional — ours just MORE premium

Generate the premium comparison infographic now."""


# ---------------------------------------------------------------------------
# Country / Region details
# ---------------------------------------------------------------------------

REGION_MAP = {
    "AE": {
        "name": "UAE/Dubai",
        "setting": "Modern luxury Dubai apartment with Arabic design elements, marble floors, warm desert sunlight",
        "person": "Middle Eastern person in modern attire or traditional kandura/abaya",
        "cultural": "Include subtle Arabic architectural elements. Warm golden lighting.",
    },
    "UK": {
        "name": "United Kingdom",
        "setting": "Contemporary British home with clean modern decor, natural wood accents",
        "person": "British person in casual modern clothing",
        "cultural": "British style home interior. Soft natural light through windows.",
    },
    "US": {
        "name": "United States",
        "setting": "Modern American home with open floor plan, contemporary furniture",
        "person": "Diverse American person in casual wear",
        "cultural": "Contemporary American suburban home. Bright natural lighting.",
    },
    "IN": {
        "name": "India",
        "setting": "Contemporary Indian home with vibrant colors, traditional meets modern decor",
        "person": "Indian person in modern casual or traditional clothing",
        "cultural": "Warm, family-oriented Indian home atmosphere.",
    },
}

DEFAULT_REGION = {
    "name": "International",
    "setting": "Modern contemporary home with clean design",
    "person": "Person in modern casual clothing",
    "cultural": "Clean, modern, universal appeal.",
}


def _get_region(country: str) -> Dict[str, str]:
    """Map country code or name to region details."""
    c = (country or "").strip().upper()
    if c in REGION_MAP:
        return REGION_MAP[c]
    # Try matching by name
    cl = c.lower()
    for code, info in REGION_MAP.items():
        if cl in info["name"].lower() or info["name"].lower() in cl:
            return info
    return DEFAULT_REGION


class ImageCreator:
    """Generates Amazon listing images using Google Gemini AI."""

    def __init__(self, gemini_api_key: str = None, model: str = None):
        if not HAS_GENAI:
            raise ImportError("google-genai package required. pip install google-genai")

        self.api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or os.getenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image-preview")

        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required. Set it in .env or pass directly.")

        self.client = genai.Client(api_key=self.api_key)

    def _generate(
        self,
        prompt: str,
        output_path: Path,
        reference_image_bytes: bytes = None,
        max_retries: int = 3,
    ) -> bool:
        """Core generation: prompt → image file."""
        for attempt in range(max_retries):
            try:
                # Build content parts
                parts = []
                if reference_image_bytes:
                    parts.append(types.Part.from_bytes(data=reference_image_bytes, mime_type="image/jpeg"))
                parts.append(types.Part.from_text(text=prompt))

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[types.Content(role="user", parts=parts)],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        temperature=0.7,
                    ),
                )

                for part in response.candidates[0].content.parts:
                    if hasattr(part, "inline_data") and part.inline_data:
                        image_data = part.inline_data.data
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, "wb") as f:
                            f.write(image_data)
                        return True

                # No image in response
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"         ⚠️  No image in response, retrying in {wait}s...")
                    time.sleep(wait)

            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                    wait = min(60, 2 ** (attempt + 2))
                    print(f"         ⚠️  Rate limit, waiting {wait}s...")
                    time.sleep(wait)
                elif attempt == max_retries - 1:
                    print(f"         ❌ Generation error: {err[:120]}")
                    return False
                else:
                    time.sleep(2)

        return False

    def _download_reference(self, image_source: str) -> Optional[bytes]:
        """Download or read a reference image, return bytes."""
        if not image_source:
            return None
        if image_source.startswith("http"):
            try:
                resp = requests.get(image_source, timeout=30)
                if resp.status_code == 200:
                    return resp.content
            except Exception:
                pass
        elif os.path.exists(image_source):
            with open(image_source, "rb") as f:
                return f.read()
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_main_image(
        self,
        image_analysis: Dict[str, Any],
        output_path: Path,
        reference_image: str = None,
    ) -> bool:
        """Generate an IMPROVED main product image based on the original from Excel input.
        
        If a reference image (from the input Excel) is available, Gemini receives it
        and is instructed to create a better version of the SAME product.
        """
        print(f"      🖼️  Generating main product image...")

        # Extract key features from bullets if available
        bullets = image_analysis.get('bullets', [])
        key_features = "\n".join(f"- {b[:100]}" for b in bullets[:5]) if bullets else "As shown in reference image"

        ref_bytes = self._download_reference(reference_image)

        # Use the reference-aware prompt when we have the original image
        prompt_template = MAIN_IMAGE_PROMPT if ref_bytes else MAIN_IMAGE_PROMPT_NO_REF

        prompt = prompt_template.format(
            optimized_title=image_analysis.get("optimized_title") or image_analysis.get("product_name") or "Product",
            brand=image_analysis.get("brand") or "Brand",
            product_type=image_analysis.get("product_type") or "product",
            key_features=key_features,
            colors=", ".join(image_analysis.get("colors", [])) or "as shown in reference",
        )

        if ref_bytes:
            print(f"         📷 Using original product image as reference")

        success = self._generate(prompt, Path(output_path), reference_image_bytes=ref_bytes)

        if success:
            print(f"         ✅ Saved: {output_path}")
        else:
            print(f"         ❌ Failed to generate main image")
        return success

    def generate_lifestyle_image(
        self,
        image_analysis: Dict[str, Any],
        country: str,
        output_path: Path,
        reference_image: str = None,
    ) -> bool:
        """Generate lifestyle image using actual bullet points."""
        print(f"      🌍 Generating lifestyle image for {country}...")

        region = _get_region(country)

        # Use actual bullets from the listing
        bullets = image_analysis.get('bullets', [])
        bullets_text = "\n".join(f"• {b}" for b in bullets[:5]) if bullets else "Daily use"

        # Use product's target audience to decide who to show, fall back to region default
        target_audience = (image_analysis.get("target_audience") or "").strip()
        if target_audience:
            person_description = f"{region['person'].split(' ')[0]} {target_audience}"
        else:
            person_description = region["person"]

        prompt = LIFESTYLE_PROMPT.format(
            optimized_title=image_analysis.get("optimized_title") or image_analysis.get("product_name") or "Product",
            bullets=bullets_text,
            country=region["name"],
            setting=region["setting"],
            person_description=person_description,
            use_case=image_analysis.get("usage") or "daily use as described in bullets",
            mood="positive, natural, authentic",
            country_cultural_notes=region["cultural"],
        )

        ref_bytes = self._download_reference(reference_image)
        success = self._generate(prompt, Path(output_path), reference_image_bytes=ref_bytes)

        if success:
            print(f"         ✅ Saved: {output_path}")
        else:
            print(f"         ❌ Failed to generate lifestyle image")
        return success

    def generate_why_choose_us(
        self,
        image_analysis: Dict[str, Any],
        output_path: Path,
        reference_image: str = None,
    ) -> bool:
        """Generate Why Choose Us using actual description and comparison points."""
        print(f"      📊 Generating 'Why Choose Us' infographic...")

        comparison = image_analysis.get("comparison_points", [])[:4]

        our_lines = []
        comp_lines = []
        for i, cp in enumerate(comparison, 1):
            our = cp.get("our_benefit", "Premium Quality")
            comp = cp.get("competitor_issue", "Standard option")
            our_lines.append(f"  {i}. ✓ {our}")
            comp_lines.append(f"  {i}. ○ {comp}")

        # Pad to 4
        while len(our_lines) < 4:
            our_lines.append(f"  {len(our_lines)+1}. ✓ Premium Quality")
            comp_lines.append(f"  {len(comp_lines)+1}. ○ Standard option")

        # Use actual description
        description = image_analysis.get('description', '')[:500] or "Premium product"

        prompt = WHY_CHOOSE_PROMPT.format(
            optimized_title=image_analysis.get("optimized_title") or image_analysis.get("product_name") or "Product",
            brand=image_analysis.get("brand") or "Brand",
            description=description,
            our_features="\n".join(our_lines),
            competitor_issues="\n".join(comp_lines),
            colors=", ".join(image_analysis.get("colors", [])) or "as shown",
        )

        ref_bytes = self._download_reference(reference_image)
        success = self._generate(prompt, Path(output_path), reference_image_bytes=ref_bytes)

        if success:
            print(f"         ✅ Saved: {output_path}")
        else:
            print(f"         ❌ Failed to generate infographic")
        return success

    def generate_all(
        self,
        image_analysis: Dict[str, Any],
        optimized_title: str,
        bullets: List[str],
        description: str,
        country: str,
        output_dir: str,
        reference_image: str = None,
        pause_between: int = 3,
    ) -> Dict[str, bool]:
        """
        Generate all three image types using ONLY the analyzed content.
        
        NO HALLUCINATION: All prompts use only data from:
        - image_analysis (from actual product images)
        - optimized_title (AI-generated from analysis)
        - bullets (AI-generated from analysis)
        - description (AI-generated from analysis)
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Enrich image_analysis with the full listing content
        enriched_analysis = dict(image_analysis)
        enriched_analysis['optimized_title'] = optimized_title
        enriched_analysis['bullets'] = bullets
        enriched_analysis['description'] = description

        results: Dict[str, bool] = {}

        # 1. Main image
        results["main_image"] = self.generate_main_image(
            enriched_analysis, out / "main_product.png", reference_image,
        )
        time.sleep(pause_between)

        # 2. Lifestyle image
        results["lifestyle"] = self.generate_lifestyle_image(
            enriched_analysis, country, out / "lifestyle.png", reference_image,
        )
        time.sleep(pause_between)

        # 3. Why choose us
        results["why_choose_us"] = self.generate_why_choose_us(
            enriched_analysis, out / "why_choose_us.png", reference_image,
        )

        successes = sum(1 for v in results.values() if v)
        print(f"      📸 Generated {successes}/3 images")
        return results
