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

import io
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image as PILImage, ImageOps
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

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
Generate a high-resolution, studio-quality version of THIS EXACT PRODUCT.
*** OUTPUT FORMAT: SQUARE (1:1) ASPECT RATIO ONLY ***

*** STRICT VISUAL LOYALTY REQUIRED ***
You must NOT redesign or "imagine" a new product. You must render the EXACT SAME object from the reference image, just with better lighting and sharpness.
- SAME Shape
- SAME Color (Visuals override text)
- SAME Label/Logo placement
- SAME Packaging

PRODUCT CONTEXT:
Title: {optimized_title}
Brand: {brand}
Type: {product_type}
Features: {key_features}
Colors: {colors}

CRITICAL EXECUTION RULES:
1. ASPECT RATIO: The output image MUST act as a 1024x1024 square. Do not produce wide/landscape images.
2. FIDELITY: The output must look like the reference image was photographed in a $10,000 studio.
3. BACKGROUND: Pure white (#FFFFFF). Amazon compliant.
4. FRAMING: Product fills 85% of the square canvas. Center aligned.
5. CORRECTION: Fix blur/noise, but preserve all physical details of the reference.
6. NO HALLUCINATIONS: Do not add extra buttons, change the handle shape, or alter the geometry.
7. NO WATERMARKS or text overlays.

Generate the definitive professional square image of this specific product."""


MAIN_IMAGE_PROMPT_NO_REF = """Generate a professional Amazon main product image.
*** OUTPUT FORMAT: SQUARE (1:1) ASPECT RATIO ONLY ***
*** STRICT ADHERENCE TO SPECS ***

PRODUCT TITLE: {optimized_title}
BRAND: {brand}
PRODUCT TYPE: {product_type}

KEY FEATURES (from analysis):
{key_features}

COLORS: {colors}

Requirements:
1. Pure white (#FFFFFF) background.
2. DISREGARD LANDSCAPE/PORTRAIT. Generate a SQUARE (1:1) image.
3. Realistic render of the product described above.
4. Colors MUST be exactly as specified: {colors}.
5. High-end commercial photography style.
6. 85% Frame fill within the square.
7. No text, logos (except brand on product), or props.

Generate the square product image now."""


LIFESTYLE_PROMPT = """I am providing you the ORIGINAL product image.
Generate a lifestyle image showing THIS EXACT PRODUCT being used.
*** OUTPUT FORMAT: SQUARE (1:1) ASPECT RATIO ONLY ***

*** STRICT VISUAL LOYALTY ***
The product in the scene MUST be identical to the reference image I provided.
- Do NOT change its color, shape, or size to match the "scene".
- The scene adapts to the product, not vice versa.
- CRITICAL: The brand name, logos, labels, and all text/markings visible on the original product MUST be clearly visible and readable in the lifestyle image too. The product should look EXACTLY like the main product photo — same branding, same stickers, same printing on the product.

CONTEXT:
Title: {optimized_title}
Brand: {brand}
Bullet Points:
{bullets}

MARKET: {country}
SCENE DETAILS:
- Setting: {setting}
- Person: {person_description}
- Activity: {use_case}
- Mood: {mood}

EXECUTION RULES:
1. FORMAT: Strict 1:1 Square image.with 1021×1024 dimensions.
2. INSERTION: Composite the reference product naturally into the scene.
3. VISIBILITY: Product must be the clear hero of the shot.
4. BRAND VISIBLE: The brand name "{brand}" and any logos/labels on the product MUST be clearly visible and legible — just like in the main product image. Do NOT remove or obscure branding.
5. AUTHENTICITY: {country_cultural_notes}
6. LIGHTING: Natural, matching the scene environment.
7. NO EXTRA TEXT: Do not add any overlaid text or watermarks. But keep all branding/text that is physically ON the product.
8. CONSISTENCY: If the reference product is Pink, the product in this image MUST BE PINK.

Generate the authentic lifestyle square shot now."""


WHY_CHOOSE_PROMPT = """I am providing you the ORIGINAL product image. Generate a professional Amazon-style comparison infographic.
*** OUTPUT FORMAT: SQUARE (1:1) ASPECT RATIO ONLY ***

*** STRICT VISUAL LOYALTY FOR "OUR BRAND" ***
The product shown under "OUR BRAND" must be the EXACT item from the reference image.

PRODUCT:
Title: {optimized_title}
Brand: {brand}
Description: {description}

LAYOUT: SPLIT SCREEN COMPARISON (Side-by-Side within a SQUARE)
--------------------------------
LEFT SIDE: "OUR BRAND" (Hero)
- Image: The EXACT reference product in perfect lighting.
- Vibe: Premium, High-End, Trustworthy.
- Features: Checked (✓) in Green.
{our_features}

RIGHT SIDE: "OTHERS" (Generic)
- Image: A standard, generic version of this product type (functional but ordinary).
- Vibe: Standard, Basic, Plain.
- Features: Crossed (X) in Red or muted Gray.
- Faults: Standard material, basic quality, plain design.

Visual Style:
- Clean, modern infographic.
- White/Light background for Our Brand.
- Grey/Dim background for Others.
- text should be readable.

Generate the square comparison image.

{competitor_issues}

=== CRITICAL DESIGN RULES (Amazon Premium Infographic Standards) ===
1. This is a PROFESSIONAL Amazon product infographic used by top brands (Anker, Apple, Samsung)
2. Competitor side shows a REAL alternative product — decent but basic (Standard Market Version)
3. DO NOT make competitor ugly/broken/damaged — just ordinary/average quality.
4. Use CLEAN professional typography, premium design, high-quality graphics
5. Elegant vertical divider line (thin, subtle) between the two sides
6. Our product MUST match the reference image EXACTLY in colors, design, branding
7. Colors for our product: {colors}
8. 1024×1024 square, photorealistic rendering, professional lighting
9. Think: How would Apple/Nike/Amazon Basics present this comparison? (Ours = Apple, Others = Generic)
10. ONLY use features from the description — NO hallucination or invented claims
11. Both sides should look professional — ours just MORE premium

Generate the premium comparison infographic now."""


BANNER_LIFESTYLE_PROMPT = """I am providing you the ORIGINAL product image as the reference.
Generate a premium HERO PRODUCT SHOT — wide landscape banner (1200×628px, 16:9 aspect ratio).

STYLE: Apple / Dyson / Anker product photography.
The product rests on a surface. A human hand or forearm gently touches it from the right side.
NO full-body action. NO exercise poses. NO person jumping or running.
This is a STUDIO-QUALITY close-up — the product is the undisputed star.

████████████████████████████████████████████████████████
  ZERO TEXT RULE
████████████████████████████████████████████████████████
ZERO rendered text in the image:
  ✗ No names, taglines, captions, labels, badges, or watermarks
  ✓ ONLY exception: text/logo physically printed ON the product itself
████████████████████████████████████████████████████████

*** PRODUCT VISUAL ACCURACY — CRITICAL ***
The product MUST match the reference image exactly:
- Same colors: {colors}
- Same shape, proportions, packaging, label
- REAL PHYSICAL SIZE: {weight_context}
  Render at true-to-life scale relative to the human hand.
  A 1kg dumbbell is SMALL (fits in one palm). A 16kg kettlebell is LARGE and heavy.
  DO NOT make the product bigger or smaller than real life.
- Do NOT reshape or redesign the product

PRODUCT:
Title: {optimized_title}
Brand: {brand}
Type: {product_type}

SCENE:
- Surface the product rests on: {surface}
- Background (soft bokeh): {background}
- Lighting: {lighting}
- Mood: {mood}
- Human element: One hand or forearm enters from the RIGHT side of frame,
  gently touching or steadying the product. Shows scale and human connection.

COMPOSITION (follow exactly):
1. 16:9 landscape, 1200×628px output
2. Product: LEFT-OF-CENTER, sharp, large, filling 40-55% of frame HEIGHT
3. Brand label/logo on product FACES the camera — must be clearly readable
4. Hand/arm enters from right — relaxed, natural
5. RIGHT THIRD of frame: clean, uncluttered background (Amazon ad text safe zone)
6. Depth-of-field: product tack-sharp, surface slightly focused, background beautiful bokeh
7. Lighting: clean, even on product label, cinematic warm fill on scene
8. NO person's face, NO full body, NO action poses

Generate the photorealistic hero product banner now.
ZERO text overlays. Brand label ON the product must be sharp and readable."""

# Banner target size
BANNER_SIZE: Tuple[int, int] = (1200, 628)


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

    def _brainstorm_lifestyle_scenarios(
        self,
        title: str,
        product_type: str,
        default_usage: str,
        country: str,
    ) -> List[Dict[str, str]]:
        """
        Use Gemini (Text) to brainstorm 4 DISTINCT usage scenarios/settings.
        Returns list of dicts: {"activity": "...", "setting": "...", "mood": "..."}
        """
        prompt = f"""You are an expert Art Director for Amazon photography.
PRODUCT: {title} ({product_type})
DEFAULT USAGE: {default_usage}
MARKET: {country}

TASK: Brainstorm 4 DISTINCT, REALISTIC lifestyle photography scenarios for this product.
Scenarios must be diverse (different rooms, different use-cases, different audiences).

Return ONLY valid JSON:
[
  {{ "activity": "Specific action (e.g. packing lunch)", "setting": "Specific location (e.g. sunlit kitchen)", "mood": "Energetic" }},
  {{ "activity": "...", "setting": "...", "mood": "..." }},
  {{ "activity": "...", "setting": "...", "mood": "..." }},
  {{ "activity": "...", "setting": "...", "mood": "..." }}
]
"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.7,
                    ),
                )
                if response.text:
                    scenarios = json.loads(response.text)
                    if isinstance(scenarios, list) and len(scenarios) >= 4:
                        return scenarios[:4]
            except Exception as e:
                print(f"         ⚠️  Brainstorming failed (attempt {attempt+1}): {e}")
                time.sleep(1)

        # Fallback scenarios if AI fails
        return [
            {"activity": f"Daily usage of {product_type}", "setting": "Modern Home Interior", "mood": "Natural"},
            {"activity": f"Key feature demonstration of {product_type}", "setting": "Close-up Environment", "mood": "Focused"},
            {"activity": f"Family enjoying {product_type}", "setting": "Living Space", "mood": "Warm"},
            {"activity": f"Active use of {product_type}", "setting": "Dynamic Setting", "mood": "Energetic"},
        ]

    def _brainstorm_banner_scenario(
        self,
        title: str,
        product_type: str,
        key_features: List[str],
        usage: str,
        country: str,
    ) -> Dict[str, str]:
        """
        Use Gemini (text) to design the SINGLE best cinematic banner scenario for this product.
        Returns a dict: {setting, action, mood, lighting, foreground, background}
        """
        features_text = "\n".join(f"- {f}" for f in key_features[:5]) if key_features else f"- {usage or 'daily use'}"
        prompt = f"""You are a senior product photographer and Art Director for a premium e-commerce brand.
Design the PERFECT hero product shot for a 1200×628px Amazon Sponsored Brand Ad.

STYLE: Think Apple product photography, Dyson ad, Anker ad.
The product rests on a surface. A hand gently touches it. Clean, blurred background.
NO full-body lifestyle scenes. NO action shots. NO exercise poses.
This is a STUDIO-QUALITY close-up hero shot.

PRODUCT: {title}
TYPE: {product_type}
MARKET: {country}
KEY FEATURES:
{features_text}
USAGE: {usage or 'everyday use'}

Design the SINGLE BEST surface and background for this product. Think:
- What surface makes the product look premium? (gym mat, marble counter, wooden desk, concrete floor, etc.)
- What background tells the product's story in soft focus? (blurred gym, blurred kitchen, blurred home)
- What lighting makes the product’s colors and label pop?
- What mood feels premium and aspirational for this product category?

Return ONLY valid JSON (no markdown, no explanation):
{{
  "surface": "Specific surface the product rests on (e.g. 'dark rubber gym mat, slightly textured')",
  "background": "Soft-focus blurred background behind (e.g. 'blurred home gym, dumbbell rack visible')",
  "lighting": "Lighting style (e.g. 'clean studio light from upper-left, warm fill from right')",
  "mood": "Premium mood (e.g. 'clean, aspirational, motivational')",
  "weight_context": "Realistic size note for Gemini (e.g. '1kg dumbbell: small, fits in one palm, about the size of a large apple')"
}}"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.8,
                    ),
                )
                if response.text:
                    scenario = json.loads(response.text)
                    if isinstance(scenario, dict) and "setting" in scenario:
                        print(f"         🎨 Banner scene: {scenario.get('mood','')}, {scenario.get('setting','')[:60]}")
                        return scenario
            except Exception as e:
                print(f"         ⚠️  Banner brainstorm failed (attempt {attempt+1}): {e}")
                time.sleep(1)

        # Hardcoded fallback
        return {
            "surface": f"Clean rubber mat or wooden surface",
            "background": f"Soft-focus blurred gym or home interior",
            "mood": "clean, aspirational, premium",
            "lighting": "clean studio light from upper-left, warm fill from right",
            "foreground": f"The {product_type}, sharp and close to camera",
            "weight_context": f"Show in realistic proportion to a human hand",
        }

    def generate_lifestyle_image(
        self,
        image_analysis: Dict[str, Any],
        country: str,
        output_path: Path,
        reference_image: str = None,
        scenario: Dict[str, str] = None,
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
            
        # Determine Scenario (Use-Case + Setting + Mood)
        if scenario:
            use_case = scenario.get("activity", image_analysis.get("usage") or "Daily Use")
            setting = scenario.get("setting", region["setting"])
            mood = scenario.get("mood", "Professional")
            print(f"         🎬 Scene: {use_case} @ {setting}")
        else:
            use_case = image_analysis.get("usage") or "daily use as described in bullets"
            setting = region["setting"]
            import random
            mood = random.choice(["positive, natural", "focused, professional", "warm, inviting", "energetic"])

        prompt = LIFESTYLE_PROMPT.format(
            optimized_title=image_analysis.get("optimized_title") or image_analysis.get("product_name") or "Product",
            brand=image_analysis.get("brand") or "Brand",
            bullets=bullets_text,
            country=region["name"],
            setting=setting,
            person_description=person_description,
            use_case=use_case,
            mood=mood,
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

    def _resize_to_banner(self, output_path: Path) -> bool:
        """Post-process a saved image to exact BANNER_SIZE (1200×628) using PIL center-crop."""
        if not HAS_PIL:
            print("         ⚠️  Pillow not installed — banner not resized. pip install Pillow")
            return True  # file still saved at original size
        try:
            with open(output_path, "rb") as f:
                raw = f.read()
            img = PILImage.open(io.BytesIO(raw))
            final = ImageOps.fit(img, BANNER_SIZE, method=PILImage.LANCZOS, centering=(0.5, 0.5))
            final.save(output_path, "PNG")
            print(f"         📌 Resized to {BANNER_SIZE[0]}×{BANNER_SIZE[1]}px")
            return True
        except Exception as e:
            print(f"         ⚠️  Banner resize failed: {e}")
            return True  # generation still succeeded even if resize failed

    def generate_banner_image(
        self,
        image_analysis: Dict[str, Any],
        country: str,
        output_path: Path,
        reference_image: str = None,
        bullets: List[str] = None,
        description: str = None,
    ) -> bool:
        """Generate a 1200×628px lifestyle banner — photorealistic, ZERO text overlays."""
        print(f"      🏞️  Generating lifestyle banner (1200×628)...")

        region = _get_region(country)

        target_audience = (image_analysis.get("target_audience") or "").strip()
        person_description = (
            f"{region['person'].split(' ')[0]} {target_audience}"
            if target_audience else region["person"]
        )

        bullet_list = bullets or image_analysis.get("bullets") or []
        if bullet_list:
            key_features = [b.split(".")[0][:90].strip() for b in bullet_list[:5] if b]
        else:
            raw_features = image_analysis.get("key_features") or image_analysis.get("features") or []
            key_features = [str(f)[:90].strip() for f in raw_features[:5]] if isinstance(raw_features, list) else ([str(raw_features)[:90]] if raw_features else [])

        usage = image_analysis.get("usage") or "daily use"
        product_type = image_analysis.get("product_type") or "product"
        title = image_analysis.get("optimized_title") or image_analysis.get("product_name") or "Product"
        colors = ", ".join(image_analysis.get("colors") or []) or "as shown in reference image"

        print(f"         🎨 Brainstorming best banner scene...")
        scenario = self._brainstorm_banner_scenario(
            title=title, product_type=product_type,
            key_features=key_features, usage=usage, country=region["name"],
        )

        prompt = BANNER_LIFESTYLE_PROMPT.format(
            optimized_title=title,
            brand=image_analysis.get("brand") or "Brand",
            product_type=product_type,
            colors=colors,
            surface=scenario.get("surface", "clean gym mat or wooden surface"),
            background=scenario.get("background", "soft-focus blurred interior"),
            lighting=scenario.get("lighting", "clean studio light, warm fill"),
            mood=scenario.get("mood", "clean, aspirational, premium"),
            weight_context=scenario.get("weight_context", f"Show {product_type} at realistic size relative to a human hand"),
        )

        ref_bytes = self._download_reference(reference_image)
        success = self._generate(prompt, Path(output_path), reference_image_bytes=ref_bytes)

        if success:
            self._resize_to_banner(Path(output_path))
            print(f"         ✅ Saved: {output_path}")
        else:
            print(f"         ❌ Failed to generate banner image")
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
        output_filenames: Dict[str, str] = None,
        pause_between: int = 3,
        banner_only: bool = False,
        lifestyle_only: bool = False,
        main_only: bool = False,
        why_choose_us_only: bool = False,
    ) -> Dict[str, bool]:
        """
        Generate product images using ONLY the analyzed content.

        Modes (mutually exclusive):
          banner_only        → only the 1200×628 Sponsored Brand Ad banner
          lifestyle_only     → only the 4 lifestyle images
          main_only          → only the main studio product image
          why_choose_us_only → only the Why Choose Us infographic
          (default)          → all image types
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        # Enrich image_analysis with the full listing content
        enriched_analysis = dict(image_analysis)
        enriched_analysis['optimized_title'] = optimized_title
        enriched_analysis['bullets'] = bullets
        enriched_analysis['description'] = description

        names = {
            "main_image": "main_product.png",
            "lifestyle_1": "lifestyle_1.png",
            "lifestyle_2": "lifestyle_2.png",
            "lifestyle_3": "lifestyle_3.png",
            "lifestyle_4": "lifestyle_4.png",
            "why_choose_us": "why_choose_us.png",
            "banner_image": "banner_1.png",
        }
        if output_filenames:
            names.update({k: v for k, v in output_filenames.items() if v})

        results: Dict[str, bool] = {}

        # ── Banner-only mode ─────────────────────────────────────────────
        if banner_only:
            print(f"      🏞️  Banner-only mode: generating 1200×628 Sponsored Brand Ad...")
            results["banner_image"] = self.generate_banner_image(
                enriched_analysis, country, out / names["banner_image"], reference_image,
                bullets=bullets, description=description,
            )
            print(f"      📸 Generated 1/1 banner image")
            return results

        # ── Main-image-only mode ─────────────────────────────────────────
        if main_only:
            print(f"      🖼️  Main-only mode: generating studio product image...")
            results["main_image"] = self.generate_main_image(
                enriched_analysis, out / names["main_image"], reference_image,
            )
            print(f"      📸 Generated 1/1 main image")
            return results

        # ── Why-choose-us-only mode ───────────────────────────────────────
        if why_choose_us_only:
            print(f"      🌟 Why-choose-us-only mode: generating infographic...")
            results["why_choose_us"] = self.generate_why_choose_us(
                enriched_analysis, out / names["why_choose_us"], reference_image,
            )
            print(f"      📸 Generated 1/1 why-choose-us infographic")
            return results

        # ── Lifestyle-only mode ──────────────────────────────────────────
        if lifestyle_only:
            print(f"      🌍 Lifestyle-only mode: brainstorming 4 distinct scenarios...")
            scenarios = self._brainstorm_lifestyle_scenarios(
                title=optimized_title,
                product_type=image_analysis.get("product_type", "Product"),
                default_usage=image_analysis.get("usage", ""),
                country=country,
            )
            print(f"      🌍 Generating 4 lifestyle images...")
            for i in range(1, 5):
                scenario = scenarios[i - 1] if i - 1 < len(scenarios) else None
                results[f"lifestyle_{i}"] = self.generate_lifestyle_image(
                    enriched_analysis, country, out / names[f"lifestyle_{i}"],
                    reference_image, scenario=scenario,
                )
                if i < 4:
                    time.sleep(pause_between)
            successes = sum(1 for v in results.values() if v)
            print(f"      📸 Generated {successes}/4 lifestyle images")
            return results

        # 1. Main image
        results["main_image"] = self.generate_main_image(
            enriched_analysis, out / names["main_image"], reference_image,
        )
        time.sleep(pause_between)

        # 2. Lifestyle image
        # Ask for 4 variations with DISTINCT scenarios
        print(f"      🌍 Brainstorming 4 distinct lifestyle scenarios...")
        
        scenarios = self._brainstorm_lifestyle_scenarios(
            title=optimized_title,
            product_type=image_analysis.get("product_type", "Product"),
            default_usage=image_analysis.get("usage", ""),
            country=country
        )
        
        print(f"      🌍 Generating lifestyle images (4 variations)...")
        for i in range(1, 5):
            # Use the i-1 th scenario (safe index access)
            scenario = scenarios[i-1] if i-1 < len(scenarios) else None
            
            results[f"lifestyle_{i}"] = self.generate_lifestyle_image(
                enriched_analysis, country, out / names[f"lifestyle_{i}"], 
                reference_image,
                scenario=scenario
            )
            time.sleep(pause_between)

        # 3. Why choose us
        results["why_choose_us"] = self.generate_why_choose_us(
            enriched_analysis, out / names["why_choose_us"], reference_image,
        )
        time.sleep(pause_between)

        # 4. Lifestyle banner (1200×628, no text) — pass full listing content
        results["banner_image"] = self.generate_banner_image(
            enriched_analysis, country, out / names["banner_image"], reference_image,
            bullets=bullets,
            description=description,
        )

        successes = sum(1 for v in results.values() if v)
        print(f"      📸 Generated {successes}/4 image types")
        return results
