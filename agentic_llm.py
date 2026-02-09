"""Lightweight LLM clients + JSON extraction helpers.

Supports OpenAI (GPT-5.1) as primary and Ollama as fallback.
Kept dependency-light so it works in minimal environments.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import requests

# ---------------------------------------------------------------------------
#  OpenAI GPT-5.1 Client (primary)
# ---------------------------------------------------------------------------

@dataclass
class OpenAIConfig:
    api_key: str = ""
    model: str = "gpt-5.1"
    timeout_s: int = 120
    reasoning_effort: str = "none"   # disable thinking


class OpenAILLM:
    """OpenAI chat-completions client matching the .generate() interface."""

    def __init__(self, config: OpenAIConfig | None = None):
        if config is None:
            config = OpenAIConfig()
        self.config = config
        if not self.config.api_key:
            self.config.api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.config.api_key:
            raise RuntimeError("OPENAI_API_KEY is required. Set it in .env or pass it explicitly.")

        from openai import OpenAI
        self._client = OpenAI(api_key=self.config.api_key, timeout=self.config.timeout_s)

    def test_connection(self) -> bool:
        try:
            resp = self._client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": "Say OK"}],
                max_completion_tokens=50,
                reasoning_effort=self.config.reasoning_effort,
            )
            return bool(resp.choices and resp.choices[0].message.content)
        except Exception as e:
            print(f"⚠️  OpenAI connection test failed: {e}")
            return False

    def generate(self, prompt: str, *, temperature: float = 0.1, max_tokens: int = 500) -> Optional[str]:
        try:
            resp = self._client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=max_tokens,
                temperature=temperature,
                reasoning_effort=self.config.reasoning_effort,
            )
            if resp.choices and resp.choices[0].message.content:
                return resp.choices[0].message.content.strip()
            return None
        except Exception as e:
            print(f"⚠️  OpenAI generate error: {e}")
            return None


# ---------------------------------------------------------------------------
#  Ollama Client (fallback)
# ---------------------------------------------------------------------------

@dataclass
class OllamaConfig:
    model: str = "deepseek-v3.1:671b-cloud"
    base_url: str = "http://localhost:11434"
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
