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
import uuid

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
from .agents.agent_store import agent_store
from .tools.registry import list_tools, get_tool, suggest_tools_for_intent

def get_current_user(authorization: str | None = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ")[1]
    user_id = auth.get_user_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id

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
    user_id: str = Depends(get_current_user),
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
        result = orchestrator.run_document_flow(
            image_path, source_name, session_id=session_id, user_id=user_id
        )
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

@app.post("/api/sandbox/execute")
def execute_code_in_sandbox(
    code: str = Form(...),
    user_id: str = Depends(get_current_user),
):
    """Execute code snippet directly in isolated sandbox and return stdout/stderr."""
    from .tools.sandbox_tool import run_in_sandbox
    if not code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty")
    res = run_in_sandbox(code)
    return JSONResponse(res)

@app.post("/api/chat")
def submit_chat_message(
    session_id: str | None = Form(None),
    message: str | None = Form(None),
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    agent_id: str | None = Form(None),
    user_id: str = Depends(get_current_user)
):
    """General-purpose chat — ask about uploaded docs/code or anything
    else. Grounded on the knowledge base when relevant, with
    per-session history persisted to disk."""
    clear_log()
    
    upload_list: list[UploadFile] = []
    if files:
        upload_list.extend([f for f in files if f and f.filename])
    if file and file.filename:
        if not any(f.filename == file.filename for f in upload_list):
            upload_list.append(file)
            
    has_files = len(upload_list) > 0
    clean_msg = (message or "").strip()
    
    if not clean_msg and not has_files:
        raise HTTPException(
            status_code=400, detail="Please provide a message prompt or attach a document"
        )
    if len(clean_msg) > 4000:
        raise HTTPException(
            status_code=400,
            detail="Message too long (max 4000 characters)",
        )
    if not clean_msg:
        clean_msg = "Please analyze and summarize the attached document(s)."

    if not session_id or chat_store.load(session_id) is None:
        session_id = chat_store.new_session(user_id)

    attachments = []
    MAX_UPLOAD_BYTES = 15 * 1024 * 1024
    for up_file in upload_list:
        content = up_file.file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413, detail=f"File {up_file.filename} too large (max 15MB)"
            )
        if len(content) > 0:
            safe_name = os.path.basename(up_file.filename)
            save_path = os.path.join(
                config.SAMPLES_DIR, f"chat_upload_{uuid.uuid4().hex[:6]}_{safe_name}"
            )
            with open(save_path, "wb") as f:
                f.write(content)
            attachments.append({
                "path": save_path,
                "type": up_file.content_type or "",
                "name": safe_name,
            })

    result = orchestrator.run_chat_flow(
        session_id,
        clean_msg,
        attachments=attachments,
        agent_id=agent_id,
    )
    return JSONResponse(result)


# --------------------------------------------------------------------
# Common Tools & Agent Onboarder Endpoints
# --------------------------------------------------------------------
class OnboardAgentRequest(BaseModel):
    name: str
    description: str
    use_case_ids: list[str] = []
    system_prompt: str
    skill_content: str
    tool_ids: list[str] = []
    model_type: str = "reasoning"
    department: str = "Custom Operations"
    starter_prompts: list[str] = []


class DraftSkillRequest(BaseModel):
    role_name: str
    description: str
    use_cases: list[str] = []
    guidelines: str = ""


@app.get("/api/tools")
def get_tools_catalog():
    """Return all registered tools and their capabilities."""
    return {"tools": list_tools()}


@app.get("/api/tools/suggest")
def suggest_tools(intent: str = ""):
    """Suggest tool IDs for a given intent or use case."""
    return {"suggested_tools": suggest_tools_for_intent(intent)}


@app.get("/api/agents")
def get_agents():
    """List all registered agents in the common pool."""
    return {
        "agents": agent_store.list_agents(),
        "use_cases": agent_store.list_all_use_cases(),
    }


@app.get("/api/agents/use-cases")
def get_use_cases_catalog():
    """Return distinct use cases with mapped agents (M:N directory)."""
    return {"use_cases": agent_store.list_all_use_cases()}


@app.get("/api/agents/search")
def search_agents(q: str = "", limit: int = 5):
    """Local air-gapped semantic search across use cases, agent names, and skills."""
    return {"results": agent_store.search_agents(q, top_k=limit)}


@app.get("/api/agents/{agent_id}")
def get_agent_detail(agent_id: str):
    ag = agent_store.get_agent(agent_id)
    if not ag:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ag


@app.post("/api/agents/onboard")
def onboard_agent(req: OnboardAgentRequest, user_id: str = Depends(get_current_user)):
    """Onboard a new customizable agent with custom skill and tool selection."""
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Agent name is required")
    if not req.description.strip():
        raise HTTPException(status_code=400, detail="Agent description is required")
    if not req.skill_content.strip():
        raise HTTPException(status_code=400, detail="Skill content (SKILL.md) is required")

    ag = agent_store.create_agent(
        name=req.name,
        description=req.description,
        use_case_ids=req.use_case_ids,
        system_prompt=req.system_prompt,
        skill_content=req.skill_content,
        tool_ids=req.tool_ids,
        model_type=req.model_type,
        department=req.department,
        starter_prompts=req.starter_prompts,
    )
    return {"status": "ok", "agent": ag}


@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, user_id: str = Depends(get_current_user)):
    success = agent_store.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete agent (built-in or not found)")
    return {"status": "ok", "deleted": agent_id}


@app.post("/api/agents/draft-skill")
def draft_skill(req: DraftSkillRequest):
    """Recursive Meta-Agent: uses local reasoning model to draft a comprehensive SKILL.md."""
    if not req.role_name.strip():
        raise HTTPException(status_code=400, detail="Role name is required")
    drafted_md = model_router.draft_skill_content(
        role_name=req.role_name,
        description=req.description,
        use_cases=req.use_cases,
        guidelines=req.guidelines,
    )
    return {"status": "ok", "skill_content": drafted_md}



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
@app.get("/api/download/{filename}")
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

# Serve frontend static assets (HTML, CSS, JS) at root
if os.path.exists(config.FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")

