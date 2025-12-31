"""Run logging utilities.

Each optimization run can be persisted as JSON artifacts to help debug hallucinations.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


def _safe_slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip()).strip("-")
    if not s:
        return "run"
    return s[:max_len].lower()


@dataclass
class RunLogger:
    root_dir: str
    run_dir: Optional[str] = None

    def start(self, title: str) -> str:
        os.makedirs(self.root_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        slug = _safe_slug(title)
        self.run_dir = os.path.join(self.root_dir, f"{stamp}_{slug}")
        os.makedirs(self.run_dir, exist_ok=True)
        return self.run_dir

    def write_json(self, name: str, payload: Dict[str, Any]) -> None:
        if not self.run_dir:
            return
        path = os.path.join(self.run_dir, f"{name}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            # Never break optimization due to logging
            return
