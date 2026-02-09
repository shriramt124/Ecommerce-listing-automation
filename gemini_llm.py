"""Google Gemini LLM client — drop-in replacement for OllamaLLM.

Provides the same `.generate()` / `.test_connection()` interface so every agent
that currently uses OllamaLLM can switch to Gemini with zero code changes.

Requires: pip install google-genai
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from google import genai
from google.genai import types


@dataclass
class GeminiConfig:
    api_key: str
    model: str = "gemini-2.5-flash"          # best speed/quality for text tasks
    vision_model: str = "gemini-2.5-flash"   # same model handles vision too
    image_model: str = "gemini-3-pro-image-preview"  # for image generation only
    timeout_s: int = 120


class GeminiLLM:
    """Text generation via Google Gemini — same interface as OllamaLLM."""

    def __init__(self, config: GeminiConfig):
        self.config = config
        self.client = genai.Client(api_key=config.api_key)

    @staticmethod
    def _extract_text(resp) -> str:
        """Extract text from Gemini response, skipping thought_signature and other non-text parts."""
        try:
            # Iterate through parts and collect only text parts
            texts = []
            for candidate in resp.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        texts.append(part.text)
            return "\n".join(texts).strip()
        except Exception:
            # Fallback to resp.text (may print warning but still works)
            try:
                return (resp.text or "").strip()
            except Exception:
                return ""

    # ---- public interface (matches OllamaLLM) ----

    def test_connection(self) -> bool:
        """Quick health-check: try a trivial generation."""
        try:
            resp = self.client.models.generate_content(
                model=self.config.model,
                contents="Say OK",
                config=types.GenerateContentConfig(
                    max_output_tokens=5,
                    temperature=0.0,
                ),
            )
            return bool(resp.text)
        except Exception as e:
            print(f"   ❌ Gemini connection test failed: {e}")
            return False

    def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> Optional[str]:
        """Generate text — same signature as OllamaLLM.generate()."""
        try:
            resp = self.client.models.generate_content(
                model=self.config.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            text = self._extract_text(resp)
            return text if text else None
        except Exception as e:
            print(f"   ❌ Gemini generate error: {e}")
            return None

    # ---- vision helpers (used by ImageAnalyzer) ----

    def generate_with_image(
        self,
        prompt: str,
        image_bytes: bytes,
        *,
        temperature: float = 0.1,
        max_tokens: int = 1500,
        mime_type: str = "image/jpeg",
    ) -> Optional[str]:
        """Multimodal: text + single image."""
        try:
            resp = self.client.models.generate_content(
                model=self.config.vision_model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                            types.Part.from_text(text=prompt),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            text = self._extract_text(resp)
            return text if text else None
        except Exception as e:
            print(f"   ❌ Gemini vision error: {e}")
            return None

    def generate_with_images(
        self,
        prompt: str,
        images: list[bytes],
        *,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        mime_type: str = "image/jpeg",
    ) -> Optional[str]:
        """Multimodal: text + multiple images in one request."""
        try:
            parts = [
                types.Part.from_bytes(data=img, mime_type=mime_type)
                for img in images
            ]
            parts.append(types.Part.from_text(text=prompt))

            resp = self.client.models.generate_content(
                model=self.config.vision_model,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            text = self._extract_text(resp)
            return text if text else None
        except Exception as e:
            print(f"   ❌ Gemini multi-image error: {e}")
            return None


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a JSON object from model response.

    Identical to the one in agentic_llm.py so callers can import from either.
    """
    if not text:
        return None

    clean = text.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()

    start = clean.find("{")
    end = clean.rfind("}") + 1
    if start == -1 or end <= start:
        return None

    try:
        return json.loads(clean[start:end])
    except Exception:
        return None
