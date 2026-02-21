"""
IMAGE ANALYZER
==============
Analyzes product images using Google Gemini vision model.
Extracts: brand, color, size, material, features, and generates ai_description.

CRITICAL: Only extracts what is VISIBLE. No guessing, no hallucination.
"""

import json
import os
import sys
import requests
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_llm import GeminiConfig, GeminiLLM, extract_json_object
from agentic_llm import OllamaConfig, OllamaLLM


def _read_image_bytes(image_path: str) -> bytes:
    """Read image file and return raw bytes."""
    with open(image_path, 'rb') as f:
        return f.read()


def _download_image(url: str, save_path: str, timeout: int = 30) -> bool:
    """Download an image from URL to local path."""
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(resp.content)
            return True
    except Exception as e:
        print(f"      ⚠️  Download failed for {url}: {e}")
    return False


SINGLE_IMAGE_PROMPT = """Analyze this product image and extract ONLY what you can CLEARLY SEE.

You MUST return a JSON object. Do NOT guess or invent any information.
If something is not visible, use null.

Extract:
{
    "brand": "brand name visible on packaging/product, or null",
    "product_type": "what type of product (e.g. 'phone holder', 'garbage bags')",
    "product_name": "full product name if readable on packaging",
    "colors": ["list of colors you SEE on the product"],
    "packaging_colors": ["colors of the packaging itself"],
    "size_info": "any size text visible (e.g. 'Large', '19x21 inches')",
    "quantity": "pack count if visible (e.g. '30 bags', '4 rolls')",
    "material_visible": "material if stated on packaging or clearly identifiable",
    "features_on_packaging": ["list of features/claims written ON the package"],
    "text_on_packaging": ["ALL readable text on the package"],
    "product_condition": "new/sealed/open/used",
    "image_angle": "front/back/side/top/closeup/lifestyle",
    "what_i_see": "A 2-3 sentence description of exactly what is visible in this image"
}

CRITICAL RULES:
- ONLY state what is VISIBLE in the image
- If you cannot read text clearly, say "partially readable" 
- Do NOT invent features, colors, or specs that aren't shown
- Return ONLY the JSON, no extra text"""


CONSOLIDATION_PROMPT = """Analyze a product based on {image_count} product image(s) and the listing data below.

IMAGE DATA:
{per_image_data}

LISTING DATA:
- Title: "{title}"
- Description: "{description}"
- USP: "{usp}"
- Existing Bullets:
{existing_bullets}

Return a single JSON object consolidating ALL information. Use ONLY verified facts from images and listing data.

{{
    "brand": "brand name or null",
    "product_type": "type of product",
    "product_name": "full name",
    "colors": ["product colors"],
    "size": "size info or null",
    "quantity": "pack count or null",
    "material": "material or null",
    "key_features": ["list of confirmed features from images AND existing bullets"],
    "usage": "what the product is used for",
    "target_audience": "who would buy this",
    "ai_description": "250-300 char vivid description of what you SEE in the images. Describe appearance, packaging, colors, shape.",
    "confidence": "high/medium/low"
}}

RULES:
- key_features: merge visible packaging text + existing bullet content
- ai_description: 250-300 chars, based on visible information only
- Do NOT invent features not visible or listed
- Return ONLY the JSON"""


class ImageAnalyzer:
    """Analyzes product images using Google Gemini vision model."""

    def __init__(
        self,
        gemini_api_key: str = None,
        model: str = None,
        timeout: int = 120,
    ):
        api_key = gemini_api_key or os.getenv('GEMINI_API_KEY', '')
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY required for image analysis")

        vision_model = os.getenv('GEMINI_VISION_MODEL', 'gemini-3-pro-image-preview')
        self.llm = GeminiLLM(GeminiConfig(
            api_key=api_key,
            model=model or os.getenv('GEMINI_TEXT_MODEL', 'gemini-3-pro-preview'),
            vision_model=vision_model,
            timeout_s=timeout,
        ))
        # Separate Ollama LLM for text-only tasks (consolidation)
        self.text_llm = OllamaLLM(OllamaConfig(
            model=os.getenv('OLLAMA_MODEL', 'deepseek-v3.1:671b-cloud'),
            base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
            timeout_s=120,
        ))

    def analyze_single_image(self, image_path: str) -> Dict[str, Any]:
        """Analyze a single product image using Gemini vision."""
        if not os.path.exists(image_path):
            return {"error": f"File not found: {image_path}", "status": "ERROR"}

        image_bytes = _read_image_bytes(image_path)
        raw = self.llm.generate_with_image(
            SINGLE_IMAGE_PROMPT,
            image_bytes,
            temperature=0.1,
            max_tokens=2000,
        )
        if not raw:
            return {"error": "No response from Gemini vision", "status": "ERROR"}

        parsed = extract_json_object(raw)
        if parsed:
            parsed['image_path'] = image_path
            parsed['status'] = 'SUCCESS'
            return parsed

        return {"error": "Could not parse JSON", "raw": raw[:500], "status": "PARSE_ERROR"}

    def prepare_local_images(
        self,
        images: List[str],
        temp_dir: str,
    ) -> List[str]:
        """
        Ensure images are available locally.
        Downloads URLs, keeps local paths as-is.
        """
        os.makedirs(temp_dir, exist_ok=True)
        local_paths: List[str] = []

        for i, img in enumerate(images):
            if not img:
                continue
            if img.startswith('http://') or img.startswith('https://'):
                ext = img.split('.')[-1].split('?')[0][:4]
                if not ext or len(ext) > 4:
                    ext = 'jpg'
                save_path = os.path.join(temp_dir, f"img_{i}.{ext}")
                if not os.path.exists(save_path):
                    print(f"      ⬇️  Downloading image {i + 1}...")
                    if _download_image(img, save_path):
                        local_paths.append(save_path)
                else:
                    local_paths.append(save_path)
            elif os.path.exists(img):
                local_paths.append(img)
            else:
                print(f"      ⚠️  Image not found: {img}")

        return local_paths

    def analyze_product(
        self,
        product: Dict[str, Any],
        temp_dir: str,
    ) -> Dict[str, Any]:
        """
        Analyze all images of a product and produce consolidated analysis.
        """
        images = product.get('images', [])
        title = product.get('title', '')
        description = product.get('description', '')
        usp = product.get('usp', '')
        manual = product.get('manual', '')
        # Merge manual into description/usp context for richer analysis
        if manual:
            usp = f"{usp}\n{manual}".strip() if usp else manual
        existing_bullets = product.get('bullet_points', [])

        print(f"\n   📸 Image Analysis ({len(images)} images)...")

        if not images:
            print(f"      ⚠️  No images available")
            return {
                "brand": None,
                "product_type": None,
                "product_name": title,
                "colors": [],
                "key_features": [],
                "ai_description": f"Product: {title}" if title else "No image or title available.",
                "comparison_points": [],
                "confidence": "low",
                "status": "NO_IMAGES",
            }

        # Prepare local images
        local_paths = self.prepare_local_images(images, temp_dir)
        if not local_paths:
            print(f"      ❌ Could not obtain any images")
            return {
                "brand": None,
                "product_type": None,
                "product_name": title,
                "colors": [],
                "key_features": [],
                "ai_description": f"Product: {title}" if title else "No images available.",
                "comparison_points": [],
                "confidence": "low",
                "status": "DOWNLOAD_FAILED",
            }

        # Analyze each image individually
        per_image_results: List[Dict] = []
        for idx, img_path in enumerate(local_paths):
            print(f"      [{idx + 1}/{len(local_paths)}] Analyzing {os.path.basename(img_path)}...")
            result = self.analyze_single_image(img_path)
            if result.get('status') == 'SUCCESS':
                per_image_results.append(result)
            else:
                print(f"         ⚠️  {result.get('error', 'Unknown error')}")

        if not per_image_results:
            return {
                "brand": None,
                "product_type": None,
                "product_name": title or "Unknown Product",
                "colors": [],
                "key_features": [],
                "ai_description": f"Product: {title}" if title else "Detailed visual analysis failed.",
                "comparison_points": [],
                "confidence": "low",
                "status": "ALL_FAILED",
            }

        # Consolidate using text-only LLM call (with retries)
        print(f"      🔄 Consolidating {len(per_image_results)} image analyses...")

        per_image_text = ""
        for i, res in enumerate(per_image_results, 1):
            # Remove metadata keys before sending to LLM
            clean = {k: v for k, v in res.items() if k not in ('image_path', 'status')}
            per_image_text += f"\nImage {i}:\n{json.dumps(clean, indent=2)}\n"

        consolidation = CONSOLIDATION_PROMPT.format(
            image_count=len(per_image_results),
            per_image_data=per_image_text,
            title=title,
            description=description,
            usp=usp,
            existing_bullets="\n".join(f"  - {b}" for b in existing_bullets) if existing_bullets else "(none)",
        )

        MAX_CONSOLIDATION_RETRIES = 3
        prompt = consolidation
        for attempt in range(MAX_CONSOLIDATION_RETRIES):
            raw = self.text_llm.generate(prompt, temperature=0.15, max_tokens=3000)
            if raw:
                parsed = extract_json_object(raw)
                if parsed:
                    parsed['status'] = 'SUCCESS'
                    parsed['images_analyzed'] = len(per_image_results)
                    parsed['local_image_paths'] = local_paths
                    return parsed
                else:
                    print(f"      ⚠️  Consolidation attempt {attempt + 1}/{MAX_CONSOLIDATION_RETRIES} JSON parse failed.")
                    prompt = consolidation + (
                        f"\n\nAttempt {attempt + 1} returned INVALID JSON. "
                        "Return ONLY a valid JSON object — no markdown, no ```json blocks, no commentary."
                    )
            else:
                print(f"      ⚠️  Consolidation attempt {attempt + 1}/{MAX_CONSOLIDATION_RETRIES} returned empty response.")
                import time
                time.sleep(5)  # brief pause before retry on empty response

        # Fallback: merge ALL per-image results (not just the first)
        print(f"      ⚠️  Consolidation failed after {MAX_CONSOLIDATION_RETRIES} attempts, merging image data locally")
        fallback = self._merge_per_image_results(per_image_results, title)
        fallback['images_analyzed'] = len(per_image_results)
        fallback['local_image_paths'] = local_paths
        return fallback

    @staticmethod
    def _merge_per_image_results(
        results: List[Dict[str, Any]], title: str
    ) -> Dict[str, Any]:
        """Merge data from all per-image analyses into a single consolidated dict."""
        brand = None
        product_type = ""
        colors: List[str] = []
        features: List[str] = []
        texts: List[str] = []
        descriptions: List[str] = []
        size = ""
        quantity = ""
        material = ""

        for res in results:
            if not brand and res.get('brand'):
                brand = res['brand']
            if not product_type and res.get('product_type'):
                product_type = res['product_type']
            for c in (res.get('colors') or []):
                if c and c not in colors:
                    colors.append(c)
            for f in (res.get('features_on_packaging') or res.get('key_features') or []):
                if f and f not in features:
                    features.append(f)
            for t in (res.get('text_on_packaging') or []):
                if t and t not in texts:
                    texts.append(t)
            if res.get('what_i_see'):
                descriptions.append(res['what_i_see'])
            if not size:
                size = res.get('size_info') or res.get('size') or ''
            if not quantity:
                quantity = res.get('quantity') or ''
            if not material:
                material = res.get('material_visible') or res.get('material') or ''

        ai_desc = " ".join(descriptions)[:300] if descriptions else f"Product: {title}"

        return {
            "brand": brand,
            "product_type": product_type,
            "product_name": title,
            "colors": colors,
            "size": size,
            "quantity": quantity,
            "material": material,
            "key_features": features,
            "usage": "",
            "target_audience": "",
            "ai_description": ai_desc,
            "confidence": "low",
            "status": "FALLBACK_MERGE",
        }
