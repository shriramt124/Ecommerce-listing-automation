"""Lightweight Ollama client + JSON extraction helpers.

Kept dependency-free (stdlib + requests) so it works in minimal environments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass
class OllamaConfig:
    model: str
    base_url: str
    timeout_s: int = 120


class OllamaLLM:
    def __init__(self, config: OllamaConfig):
        self.config = config
        self.api_url = f"{self.config.base_url}/api/generate"

    def test_connection(self) -> bool:
        try:
            response = requests.get(f"{self.config.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, *, temperature: float = 0.1, max_tokens: int = 500) -> Optional[str]:
        try:
            payload = {
                "model": self.config.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            }

            response = requests.post(self.api_url, json=payload, timeout=self.config.timeout_s)
            if response.status_code != 200:
                return None

            result = response.json()
            text = (result.get("response") or "").strip()
            if not text:
                text = (result.get("thinking") or "").strip()
            if not text:
                msg = result.get("message")
                if isinstance(msg, dict):
                    text = (msg.get("content") or "").strip()
            return text.strip() if text else None
        except Exception:
            return None


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort extraction of a JSON object from a model response."""
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
