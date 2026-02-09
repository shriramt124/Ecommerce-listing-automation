"""Run logging utility for saving intermediate agent outputs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict


class RunLogger:
    """Logs agent outputs to JSON files for debugging and analysis."""
    
    def __init__(self, root_dir: str = "runs"):
        self.root_dir = root_dir
        self.run_dir: str | None = None
        
    def init_run(self, title: str) -> None:
        """Initialize a new run directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create safe directory name from title
        safe_title = "".join(c if c.isalnum() or c in ('-', '_') else '-' for c in title.lower()[:50])
        self.run_dir = os.path.join(self.root_dir, f"{timestamp}_{safe_title}")
        os.makedirs(self.run_dir, exist_ok=True)
        
    def log(self, name: str, data: Dict[str, Any]) -> None:
        """Save data to a JSON file in the run directory."""
        if not self.run_dir:
            return
            
        filepath = os.path.join(self.run_dir, f"{name}.json")
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save log {name}: {e}")
