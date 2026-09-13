"""
UrjaKavach — Sovereign On-Premise Agentic AI Workbench
API layer (FastAPI).

Run:
    uvicorn app.main:app --reload --port 8000
    (or: python -m uvicorn app.main:app --reload --port 8000)

Then open frontend/index.html in a browser.

Owner: Track B. Keep this file thin — it should only handle HTTP
concerns (parsing requests, shaping responses). All real logic belongs
in orchestrator.py and the tools.
"""
import os

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from . import model_router
from . import orchestrator
from .activity_log import read_log, clear_log
from .tools.kb_tool import kb_status

app = FastAPI(title="UrjaKavach Prototype API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """Shows exactly what mode the system is in. The UI renders this,
    and it is what backs the '0 external calls' claim in the demo."""
    return {
        "status": "ok",
        "mode": "on-premise",
        **config.describe(),
        "models": model_router.model_health(),
        "knowledge_base_status": kb_status(),
    }


@app.post("/api/tasks/document")
def submit_document_task(
    use_sample: bool = Form(True),
    file: UploadFile | None = File(None),
):
    """OCR -> findings -> approval note.

    Defaults to the bundled sample so the demo works with one click; a
    real scanned image can be uploaded instead."""
    clear_log()

    if file is not None and not use_sample:
        MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB

        content = file.file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large (max 15MB)")
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        upload_path = os.path.join(config.SAMPLES_DIR, f"upload_{file.filename}")
        with open(upload_path, "wb") as f:
            f.write(content)
        image_path = upload_path
        source_name = file.filename
    else:
        image_path = os.path.join(config.SAMPLES_DIR, "inspection_report.png")
        source_name = "inspection_report.png (sample scanned report)"

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")

    try:
        result = orchestrator.run_document_flow(image_path, source_name)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return JSONResponse(result)


@app.post("/api/tasks/code")
def submit_code_task(prompt: str = Form(...)):
    """Generate code, execute it in a sandbox, return verified output."""
    clear_log()
    if not prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt must not be empty")
    if len(prompt) > 2000:
        raise HTTPException(status_code=400, detail="Prompt too long (max 2000 characters)")
    result = orchestrator.run_code_flow(prompt)
    return JSONResponse(result)


@app.get("/api/logs")
def get_logs():
    return {"logs": read_log()}


@app.get("/api/outputs/{filename}")
def get_output(filename: str):
    # Prevent path traversal — filename must be a bare name
    if os.path.basename(filename) != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = os.path.join(config.OUTPUTS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Output not found")
    return FileResponse(path, filename=filename)


# Serve sample images so the frontend can preview "what was scanned"
app.mount("/samples", StaticFiles(directory=config.SAMPLES_DIR), name="samples")
