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

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from . import config
from . import model_router
from . import orchestrator
from .activity_log import read_log, clear_log
from .tools.kb_tool import kb_status
from . import chat_store
from . import auth

def get_current_user(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]
    user_id = auth.get_user_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id
from . import chat_store

app = FastAPI(title="UrjaKavach Prototype API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/auth/register")
def register(
    identifier: str = Form(...), 
    password: str = Form(...),
    name: str = Form(...),
    profession: str = Form(...),
    country: str = Form(...),
    emp_code: str = Form(...),
    github_id: str = Form(...)
):
    try:
        user = auth.register_user(identifier, password, name, profession, country, emp_code, github_id)
        return {"status": "ok", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login")
def login(identifier: str = Form(...), password: str = Form(...)):
    try:
        token = auth.authenticate_user(identifier, password)
        return {"status": "ok", "token": token}
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/api/auth/me")
def get_me(user_id: str = Depends(get_current_user)):
    user_info = auth.get_user_info(user_id)
    if not user_info:
        raise HTTPException(status_code=404, detail="User not found")
    return user_info


from pydantic import BaseModel
class ProfileUpdate(BaseModel):
    name: str | None = None
    profession: str | None = None
    country: str | None = None

@app.put("/api/auth/me")
def update_me(profile: ProfileUpdate, user_id: str = Depends(get_current_user)):
    success = auth.update_user_info(user_id, profile.dict(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "ok"}

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
    session_id: str | None = Form(None),
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
        result = orchestrator.run_document_flow(image_path, source_name,session_id=session_id)
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

@app.post("/api/chat")
def submit_chat_message(
    session_id: str | None = Form(None),
    message: str = Form(...),
    file: UploadFile | None = File(None),
    user_id: str = Depends(get_current_user)
):
    """General-purpose chat — ask about uploaded docs/code or anything
    else. Grounded on the knowledge base when relevant, with
    per-session history persisted to disk."""
    clear_log()
    if not message.strip():
        raise HTTPException(
            status_code=400, detail="Message must not be empty"
        )
    if len(message) > 4000:
        raise HTTPException(
            status_code=400,
            detail="Message too long (max 4000 characters)",
        )

    if not session_id or chat_store.load(session_id) is None:
        session_id = chat_store.new_session(user_id)

    attachment_path = None
    attachment_type = None
    if file is not None:
        MAX_UPLOAD_BYTES = 15 * 1024 * 1024
        content = file.file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413, detail="File too large (max 15MB)"
            )
        if len(content) > 0:
            attachment_path = os.path.join(
                config.SAMPLES_DIR, f"chat_upload_{file.filename}"
            )
            with open(attachment_path, "wb") as f:
                f.write(content)
            attachment_type = file.content_type or ""

    result = orchestrator.run_chat_flow(
        session_id, message, attachment_path, attachment_type
    )
    return JSONResponse(result)


@app.get("/api/chat/sessions")
def list_chat_sessions(user_id: str = Depends(get_current_user)):
    return {"sessions": chat_store.list_sessions(user_id)}


@app.get("/api/chat/sessions/{session_id}")
def get_chat_session(session_id: str, user_id: str = Depends(get_current_user)):
    data = chat_store.load(session_id)
    if data is None or data.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    return data


@app.delete("/api/chat/sessions/{session_id}")
def delete_chat_session(session_id: str, user_id: str = Depends(get_current_user)):
    data = chat_store.load(session_id)
    if data and data.get("user_id") == user_id:
        chat_store.delete_session(session_id)
    return {"deleted": session_id}


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
