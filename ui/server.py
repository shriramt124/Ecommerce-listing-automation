"""
FastAPI Server
==============
Serves the React frontend and provides REST + WebSocket API
for the Amazon Listing Generator UI dashboard.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from ui.job_manager import (
    start_job, stop_job, get_job, get_all_jobs,
    subscribe, build_cli_preview, PROJECT_ROOT
)
import sys
sys.path.append(str(PROJECT_ROOT))
from telemetry import emitter

# RL Memory Vault — lazy import so server starts even without chromadb
try:
    sys.path.insert(0, str(PROJECT_ROOT / "listing_generator"))
    from listing_generator.feedback_store import FeedbackStore
    _feedback_store = FeedbackStore()
except Exception as _fs_err:
    print(f"[server] FeedbackStore unavailable: {_fs_err}")
    _feedback_store = None

app = FastAPI(title="Amazon Listing Generator UI")

# Allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic models ─────────────────────────────────────────────────────────

class RunParams(BaseModel):
    clientExcel: str
    outputDir: Optional[str] = None
    mode: str = "full"                    # full | titles_only | images_only | search_terms_only
    generateImages: bool = False
    imageType: str = "all"                # all | main | lifestyle | why_choose_us | banner
    ingestKeywords: bool = False
    browseNodes: Optional[str] = None
    analysisDir: Optional[str] = None
    keywordIndex: Optional[str] = None
    geminiKey: Optional[str] = None
    geminiModel: Optional[str] = None
    llmProvider: str = "ollama"
    llmModel: Optional[str] = None
    llmBaseUrl: Optional[str] = None
    llmApiKey: Optional[str] = None
    ingestCategory: Optional[str] = None
    queryCategory: Optional[str] = None
    skip: int = 0
    limit: Optional[int] = None


class StopParams(BaseModel):
    jobId: str


class FeedbackRateParams(BaseModel):
    asin: str
    runId: str
    category: str = "general"
    action: str  # 'approve' | 'reject'


# ─── REST endpoints ───────────────────────────────────────────────────────────

@app.post("/api/run")
async def api_run(params: RunParams):
    if not Path(params.clientExcel).exists():
        raise HTTPException(400, f"Client Excel not found: {params.clientExcel}")

    # Auto-set output dir if not provided
    if not params.outputDir:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        params.outputDir = str(PROJECT_ROOT / "listing_output" / f"run_{ts}")

    job_id = await start_job(params.dict())
    return {"jobId": job_id, "outputDir": params.outputDir}


@app.post("/api/stop")
async def api_stop(body: StopParams):
    stopped = await stop_job(body.jobId)
    return {"stopped": stopped}


@app.get("/api/runs")
async def api_runs():
    runs = []

    # Live jobs first
    known_dirs = {job.output_dir for job in get_all_jobs()}
    for job in reversed(get_all_jobs()):
        runs.append({
            "id": job.job_id,
            "name": Path(job.output_dir).name if job.output_dir else job.job_id,
            "outputDir": job.output_dir,
            "startedAt": job.started_at,
            "endedAt": job.ended_at,
            "status": job.status,
            "total": job.total,
            "successCount": job.success_count,
            "errorCount": job.error_count,
        })

    # Scan output/ directory for all run folders on disk
    output_dir = PROJECT_ROOT / "listing_output"
    if output_dir.exists():
        for d in sorted(output_dir.iterdir(), reverse=True):
            if not d.is_dir() or str(d) in known_dirs or d.name.endswith('.xlsx'):
                continue
            analysis_dir = d / "analysis"
            product_count = len(list(analysis_dir.glob("*_analysis.json"))) if analysis_dir.exists() else 0
            excel = d / "listing_output.xlsx"
            runs.append({
                "id": d.name,
                "name": d.name,
                "outputDir": str(d),
                "startedAt": None,
                "endedAt": None,
                "status": "done" if excel.exists() else "partial",
                "total": product_count,
                "successCount": product_count,
                "errorCount": 0,
            })

    return runs


@app.get("/api/run/{run_id:path}")
async def api_run_detail(run_id: str):
    """Load output data for a run — from job memory or from disk."""
    job = get_job(run_id)
    output_dir = job.output_dir if job else None

    if not output_dir:
        candidate = PROJECT_ROOT / "listing_output" / run_id
        if candidate.is_dir():
            output_dir = str(candidate)

    if not output_dir or not Path(output_dir).exists():
        raise HTTPException(404, f"Run not found: {run_id}")

    od = Path(output_dir)
    excel_path = od / "listing_output.xlsx"
    analysis_dir = od / "analysis"
    images_dir = od / "images"

    IMG_SLOTS = [
        ("main_image",    lambda n: n.startswith("main") or "_main_" in n),
        ("lifestyle_1",   lambda n: n.startswith("ls_1") or "_ls_1_" in n or "lifestyle_1" in n),
        ("lifestyle_2",   lambda n: n.startswith("ls_2") or "_ls_2_" in n or "lifestyle_2" in n),
        ("lifestyle_3",   lambda n: n.startswith("ls_3") or "_ls_3_" in n or "lifestyle_3" in n),
        ("lifestyle_4",   lambda n: n.startswith("ls_4") or "_ls_4_" in n or "lifestyle_4" in n),
        ("why_choose_us", lambda n: n.startswith("wcs") or "why" in n or "choose" in n),
        ("banner_image",  lambda n: "banner" in n),
    ]

    products = []
    if analysis_dir.exists():
        for json_file in sorted(analysis_dir.glob("*_analysis.json")):
            try:
                data = json.loads(json_file.read_text())
                ia = data.get("image_analysis", {})
                asin = data.get("asin") or json_file.stem.replace("_analysis", "")

                # Match images to slots
                images = {}
                asin_img_dir = images_dir / asin
                if asin_img_dir.exists():
                    all_pngs = sorted(asin_img_dir.glob("*.png"))
                    unmatched = list(all_pngs)
                    for slot_key, matcher in IMG_SLOTS:
                        for img in all_pngs:
                            if matcher(img.name.lower()) and slot_key not in images:
                                images[slot_key] = f"/api/image/{_encode_path(str(img))}"
                                if img in unmatched:
                                    unmatched.remove(img)
                                break
                    # Assign any leftover PNGs to empty slots
                    slot_keys = [s for s, _ in IMG_SLOTS]
                    for img in unmatched:
                        for sk in slot_keys:
                            if sk not in images:
                                images[sk] = f"/api/image/{_encode_path(str(img))}"
                                break

                products.append({
                    "asin": asin,
                    "originalTitle": data.get("original_title", ""),
                    "optimizedTitle": data.get("optimized_title", ""),
                    "country": data.get("country", ""),
                    "laCategory": data.get("la_cat", ""),
                    "status": "done",
                    "brand": ia.get("brand", ""),
                    "productType": ia.get("product_type", ""),
                    "size": ia.get("size", ""),
                    "colors": ia.get("colors", []),
                    "keyFeatures": ia.get("key_features", []),
                    "usage": ia.get("usage", ""),
                    "targetAudience": ia.get("target_audience", ""),
                    "images": images,
                })
            except Exception as e:
                print(f"  ⚠️  Error parsing {json_file.name}: {e}")
                continue

    return {
        "outputDir": output_dir,
        "runName": od.name,
        "excelPath": f"/api/excel/{_encode_path(str(excel_path))}" if excel_path.exists() else None,
        "products": products,
    }


@app.get("/api/feedback/stats")
async def api_feedback_stats():
    """Return how many examples are stored in the Neural Memory Vault."""
    if not _feedback_store:
        return {"count": 0, "available": False}
    try:
        count = _feedback_store.collection.count()
        return {"count": count, "available": True}
    except Exception as e:
        return {"count": 0, "available": False, "error": str(e)}


@app.get("/api/keyword-categories")
async def api_keyword_categories():
    """Return the unique dataset/category IDs already ingested into the keyword vector index."""
    import numpy as np
    index_path = PROJECT_ROOT / "st_keywords_index" / "keywords_index.npz"
    if not index_path.exists():
        return {"categories": []}
    try:
        data = np.load(str(index_path), allow_pickle=False)
        ids = [str(x) for x in data["dataset_ids"].tolist()]
        unique = sorted(set(i for i in ids if i and i.strip()))
        return {"categories": unique}
    except Exception as e:
        return {"categories": [], "error": str(e)}


@app.post("/api/feedback/rate")
async def api_feedback_rate(params: FeedbackRateParams):
    """Save an approved listing to the Neural Memory Vault."""
    if params.action != 'approve':
        return {"status": "skipped", "reason": "action is not approve"}

    if not _feedback_store:
        raise HTTPException(503, "FeedbackStore not available (check ChromaDB installation)")

    # Find product analysis on disk
    output_dir = None
    job = get_job(params.runId)
    if job:
        output_dir = job.output_dir
    if not output_dir:
        candidate = PROJECT_ROOT / "listing_output" / params.runId
        if candidate.is_dir():
            output_dir = str(candidate)

    if not output_dir:
        raise HTTPException(404, f"Run not found: {params.runId}")

    analysis_path = Path(output_dir) / "analysis" / f"{params.asin}_analysis.json"
    if not analysis_path.exists():
        raise HTTPException(404, f"Analysis file not found for ASIN: {params.asin}")

    try:
        data = json.loads(analysis_path.read_text())
    except Exception as e:
        raise HTTPException(500, f"Failed to read analysis: {e}")

    title = data.get("optimized_title") or data.get("original_title", "")
    bullets = data.get("bullet_points", [])
    search_terms = data.get("search_terms", "")
    ia = data.get("image_analysis", {})
    keywords = data.get("keywords", [])
    manual = data.get("manual", "")

    truth_data = {
        "brand": ia.get("brand", ""),
        "product_type": ia.get("product_type", ""),
        "size": ia.get("size", ""),
        "colors": ia.get("colors", []),
        "key_features": ia.get("key_features", []),
    }

    # 1. Run the PatternExtractorAgent to deduce stylistic rules
    from agentic_agents import PatternExtractorAgent
    from agentic_llm import OllamaLLM
    from gemini_llm import GeminiLLM
    
    # We use Ollama so the entire RL training loop remains fully local
    model = os.getenv("OLLAMA_MODEL", "deepseek-v3.1:671b-cloud")
    llm = OllamaLLM(model=model)
    
    extractor = PatternExtractorAgent(llm)
    extracted_rules = extractor.run(
        approved_title=title,
        approved_bullets=bullets,
        keywords=keywords,
        image_analysis=ia,
        manual=manual,
    )

    _feedback_store.save_good_example(
        asin=params.asin,
        category=params.category,
        title=title,
        bullets=bullets,
        search_terms=search_terms if isinstance(search_terms, str) else ", ".join(search_terms or []),
        truth_data=truth_data,
        ai_rules=extracted_rules,  # Pass the new AI-deduced rules to the vault
    )

    return {"status": "saved", "asin": params.asin, "category": params.category}


@app.get("/api/cli-preview")
async def api_cli_preview(params_json: str):
    try:
        params = json.loads(params_json)
        return {"command": build_cli_preview(params)}
    except Exception as e:
        return {"command": f"# Error: {e}"}


@app.get("/api/files")
async def api_files(directory: str = str(PROJECT_ROOT), ext: str = ""):
    """Browse filesystem for file picker."""
    d = Path(directory)
    if not d.exists():
        raise HTTPException(404, "Directory not found")

    exts = [e.strip() for e in ext.split(",") if e.strip()] if ext else []
    items = []
    try:
        for p in sorted(d.iterdir()):
            if p.name.startswith("."):
                continue
            if p.is_dir():
                items.append({"name": p.name, "path": str(p), "isDir": True})
            elif not exts or any(p.name.endswith(e) for e in exts):
                items.append({"name": p.name, "path": str(p), "isDir": False, "size": p.stat().st_size})
    except PermissionError:
        pass
    return {"directory": str(d), "parent": str(d.parent), "items": items}


@app.get("/api/image/{encoded_path}")
async def api_image(encoded_path: str):
    path = _decode_path(encoded_path)
    if not Path(path).exists():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/png")


@app.get("/api/excel/{encoded_path}")
async def api_excel(encoded_path: str):
    path = _decode_path(encoded_path)
    if not Path(path).exists():
        raise HTTPException(404)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="listing_output.xlsx",
    )


# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    """Streams live AI Agent telemetry for the Neural Dashboard Visualizer."""
    await websocket.accept()
    queue = emitter.subscribe()
    try:
        while True:
            # Wait for events from the AI agents running in background threads
            msg = await queue.get()
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        pass
    finally:
        emitter.unsubscribe(queue)

@app.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket, jobId: str):
    await websocket.accept()
    job = subscribe(jobId, websocket)

    if not job:
        await websocket.send_text(json.dumps({"type": "error", "message": f"Job {jobId} not found"}))
        await websocket.close()
        return

    # Send buffered logs to new subscriber (catch-up)
    for line in job.logs:
        await websocket.send_text(json.dumps({"type": "log", "line": line}))

    # If job already finished, send done
    if job.status in ("done", "error", "stopped"):
        await websocket.send_text(json.dumps({"type": job.status}))
        await websocket.close()
        return

    # Keep connection alive until client disconnects
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in job._subscribers:
            job._subscribers.remove(websocket)
        
        # Auto-kill the job if no one is listening anymore
        if not job._subscribers and job.status == "running":
            await stop_job(jobId)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _encode_path(path: str) -> str:
    return base64.urlsafe_b64encode(path.encode()).decode()


def _decode_path(encoded: str) -> str:
    return base64.urlsafe_b64decode(encoded.encode()).decode()


# ─── Serve React build (production) ──────────────────────────────────────────

FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")
