"""AGENTIC STRATEGY 2: OPTIMIZER ENTRYPOINT

This file is intentionally minimal.

The project now uses a modular, step-by-step pipeline to reduce hallucinations:
- Category detection
- Concept evaluation
- Retrieval/query planning
- Keyword selection (must choose only from retrieved candidates)
- Title composition
- Validation (+ optional extension)

Public API:
- create_agentic_optimizer() -> object with optimize(title, truth)
"""

from __future__ import annotations

from agentic_pipeline import AgenticOptimizationPipeline


def create_agentic_optimizer() -> AgenticOptimizationPipeline:
    return AgenticOptimizationPipeline()
