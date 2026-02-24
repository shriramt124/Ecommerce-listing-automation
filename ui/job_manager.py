"""
Job Manager
===========
Handles spawning listing_generator/run.py as a subprocess,
streaming stdout line by line over WebSocket.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class Job:
    job_id: str
    cmd: List[str]
    status: str = "pending"          # pending | running | done | error | stopped
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    output_dir: Optional[str] = None
    success_count: int = 0
    error_count: int = 0
    total: int = 0
    current: int = 0
    stage: str = ""
    current_asin: str = ""
    current_name: str = ""
    logs: List[str] = field(default_factory=list)
    _process: Optional[asyncio.subprocess.Process] = field(default=None, repr=False)
    _subscribers: List = field(default_factory=list, repr=False)


# In-memory job store
_jobs: Dict[str, Job] = {}


def build_command(params: dict) -> List[str]:
    """Convert UI params dict → run.py CLI args list."""
    cmd = [sys.executable, str(PROJECT_ROOT / "listing_generator" / "run.py")]

    cmd += ["--client", params["clientExcel"]]

    if params.get("outputDir"):
        cmd += ["--output", params["outputDir"]]

    # Run mode
    mode = params.get("mode", "full")
    if mode == "images_only":
        cmd.append("--images-only")
        cmd.append("--generate-images")
    elif mode == "search_terms_only":
        cmd.append("--search-terms-only")
        if params.get("analysisDir"):
            cmd += ["--analysis-dir", params["analysisDir"]]
    else:
        # Full or titles_only
        if params.get("generateImages") and mode != "titles_only":
            cmd.append("--generate-images")

    # Image type (only when images enabled)
    if params.get("generateImages") and mode not in ("search_terms_only", "titles_only"):
        img_type = params.get("imageType", "all")
        if img_type == "main":
            cmd.append("--main-image-only")
        elif img_type == "lifestyle":
            cmd.append("--lifestyle-image-only")
        elif img_type == "why_choose_us":
            cmd.append("--why-choose-us-only")
        elif img_type == "banner":
            cmd.append("--banner-image-only")

    # Keyword ingestion
    if params.get("browseNodes"):
        cmd += ["--browse-nodes", params["browseNodes"]]
    if params.get("ingestKeywords"):
        cmd.append("--ingest-keywords")

    # Analysis dir (for search-terms-only)
    if params.get("analysisDir") and mode != "search_terms_only":
        cmd += ["--analysis-dir", params["analysisDir"]]

    # Keyword index
    if params.get("keywordIndex"):
        cmd += ["--keyword-index", params["keywordIndex"]]

    # API config
    if params.get("geminiKey"):
        cmd += ["--gemini-key", params["geminiKey"]]
    if params.get("geminiModel"):
        cmd += ["--gemini-model", params["geminiModel"]]
        
    if params.get("llmProvider"):
        cmd += ["--llm-provider", params["llmProvider"]]
    if params.get("llmModel"):
        cmd += ["--llm-model", params["llmModel"]]
    if params.get("llmBaseUrl"):
        cmd += ["--llm-base-url", params["llmBaseUrl"]]
    if params.get("llmApiKey"):
        cmd += ["--llm-api-key", params["llmApiKey"]]
        
    # Category Filtering
    if params.get("ingestCategory"):
        cmd += ["--ingest-category", params["ingestCategory"]]
    if params.get("queryCategory"):
        cmd += ["--query-category", params["queryCategory"]]

    # Range
    skip = params.get("skip", 0)
    limit = params.get("limit")
    if skip and int(skip) > 0:
        cmd += ["--skip", str(skip)]
    if limit:
        cmd += ["--limit", str(limit)]

    return cmd


def build_cli_preview(params: dict) -> str:
    """Return a human-readable CLI command string for display."""
    cmd = build_command(params)
    # Relative-ify the python path
    parts = ["python3 listing_generator/run.py"]
    args = cmd[2:]  # skip python + script
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                parts.append(f"  {args[i]} {args[i+1]}")
                i += 2
            else:
                parts.append(f"  {args[i]}")
                i += 1
        else:
            parts.append(f"  {args[i]}")
            i += 1
    return " \\\n".join(parts)


async def start_job(params: dict) -> str:
    job_id = str(uuid.uuid4())[:8]
    cmd = build_command(params)
    job = Job(
        job_id=job_id,
        cmd=cmd,
        output_dir=params.get("outputDir"),
    )
    _jobs[job_id] = job
    asyncio.create_task(_run_job(job, params))
    return job_id


async def stop_job(job_id: str) -> bool:
    job = _jobs.get(job_id)
    if job and job._process and job.status == "running":
        try:
            job._process.terminate()
            job.status = "stopped"
            job.ended_at = datetime.now().isoformat()
            await _broadcast(job, {"type": "stopped"})
            return True
        except Exception:
            pass
    return False


async def _run_job(job: Job, params: dict):
    job.status = "running"
    job.started_at = datetime.now().isoformat()

    env = {**os.environ, "PYTHONUNBUFFERED": "1", "ADKRUX_TELEMETRY_IPC": "1"}
    if params.get("geminiKey"):
        env["GEMINI_API_KEY"] = params["geminiKey"]

    try:
        proc = await asyncio.create_subprocess_exec(
            *job.cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        job._process = proc

        from telemetry import emitter

        async for raw_line in proc.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip()
            
            # Intercept Telemetry IPC from subprocess
            if line.startswith("__TELEMETRY__:"):
                try:
                    telemetry_json = line.split("__TELEMETRY__:", 1)[1]
                    for q in emitter.queues:
                        q.put_nowait(telemetry_json)
                except Exception:
                    pass
                continue

            job.logs.append(line)

            # Parse structured info
            _parse_line(job, line)

            # Broadcast to all WebSocket subscribers
            await _broadcast(job, {"type": "log", "line": line})

            # Also broadcast progress if we updated it
            if job.current > 0:
                await _broadcast(job, {
                    "type": "progress",
                    "product": job.current,
                    "total": job.total,
                    "stage": job.stage,
                    "asin": job.current_asin,
                    "productName": job.current_name,
                })

        await proc.wait()
        job.status = "done" if proc.returncode == 0 else "error"
        job.ended_at = datetime.now().isoformat()
        await _broadcast(job, {
            "type": "done",
            "success": proc.returncode == 0,
            "excelPath": _find_excel(job),
            "successCount": job.success_count,
            "errorCount": job.error_count,
        })

    except Exception as e:
        job.status = "error"
        job.ended_at = datetime.now().isoformat()
        await _broadcast(job, {"type": "error", "message": str(e)})


def _parse_line(job: Job, line: str):
    """Extract structured progress from terminal lines."""
    # [N/M] Product name
    m = re.match(r'\s*\[(\d+)/(\d+)\]\s+(.+)', line)
    if m:
        job.current = int(m.group(1))
        job.total = int(m.group(2))
        job.current_name = m.group(3).strip()
        job.stage = "Starting"
        return

    # ASIN line: "ASIN: BXXXXXXXXX"
    m = re.search(r'ASIN:\s+([A-Z0-9]{10})', line)
    if m:
        job.current_asin = m.group(1)
        return

    # Stage lines (emoji prefix)
    stage_map = {
        "📸": "Image Generation",
        "🔍": "Keyword Discovery",
        "✅": "Complete",
        "❌": "Error",
        "🧑": "Keyword Judging",
        "📊": "Keyword Analysis",
        "🎨": "Scene Brainstorm",
        "🖼": "Image Generation",
        "🌍": "Lifestyle Images",
        "🏞": "Banner Image",
        "🌟": "Why Choose Us",
    }
    for emoji, stage_name in stage_map.items():
        if emoji in line:
            job.stage = stage_name
            break

    # Count successes
    if "✅ Product" in line and "complete" in line:
        job.success_count += 1

    # Count errors
    if "❌" in line and "Failed" in line:
        job.error_count += 1

    # Saved image
    m = re.search(r'✅ Saved:\s+(.+\.png)', line)
    if m:
        job.stage = "Image Saved"


async def _broadcast(job: Job, msg: dict):
    dead = []
    for ws in job._subscribers:
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            dead.append(ws)
    for ws in dead:
        job._subscribers.remove(ws)


def subscribe(job_id: str, ws):
    job = _jobs.get(job_id)
    if job:
        job._subscribers.append(ws)
        return job
    return None


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def get_all_jobs() -> List[Job]:
    return list(_jobs.values())


def _find_excel(job: Job) -> Optional[str]:
    if not job.output_dir:
        return None
    p = Path(job.output_dir) / "listing_output.xlsx"
    if p.exists():
        return str(p)
    return None
