import os
import json
import uuid
import time
from . import config

SESSIONS_DIR = os.path.join(config.LOGS_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

def _get_path(session_id: str) -> str:
    # Basic path traversal protection
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
    return os.path.join(SESSIONS_DIR, f"{safe_id}.json")

def new_session(user_id: str = "default") -> str:
    session_id = str(uuid.uuid4())
    now = int(time.time())
    data = {
        "id": session_id,
        "user_id": user_id,
        "title": "New chat",
        "created_at": now,
        "updated_at": now,
        "document_context": None,
        "documents": [],
        "messages": []
    }
    with open(_get_path(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return session_id

def load(session_id: str) -> dict | None:
    path = _get_path(session_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _save(session_id: str, data: dict) -> None:
    data["updated_at"] = int(time.time())
    with open(_get_path(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def add_document_context(
    session_id: str,
    source_name: str,
    raw_text: str,
    findings: list[str],
    summary: str = "",
) -> dict:
    """Store or accumulate an OCR'd document and findings on the session.

    Multiple documents uploaded across different prompts or turns co-exist
    within the same session in the `documents` list.
    """
    data = load(session_id)
    if not data:
        return {}
    if "documents" not in data:
        data["documents"] = []
        if data.get("document_context"):
            data["documents"].append(data["document_context"])

    doc_record = {
        "source_name": source_name,
        "raw_text": raw_text,
        "findings": findings,
        "summary": summary,
        "stored_at": int(time.time()),
    }
    # Update existing if same source_name, else append
    existing_idx = next(
        (i for i, d in enumerate(data["documents"]) if d.get("source_name") == source_name),
        -1
    )
    if existing_idx >= 0:
        data["documents"][existing_idx] = doc_record
    else:
        data["documents"].append(doc_record)

    # Legacy/convenience pointer to the most recent document
    data["document_context"] = doc_record

    # Give the session a title from document if still generic
    if data.get("title") in ("New chat", None):
        import os as _os
        basename = _os.path.basename(source_name)
        data["title"] = f"Doc: {basename}"
    _save(session_id, data)
    return doc_record

def set_document_context(
    session_id: str,
    source_name: str,
    raw_text: str,
    findings: list[str],
    summary: str = "",
) -> None:
    """Alias for add_document_context for backwards compatibility."""
    add_document_context(session_id, source_name, raw_text, findings, summary)

def get_document_context(session_id: str) -> dict | None:
    """Return the most recently stored document context for this session, or None."""
    data = load(session_id)
    if not data:
        return None
    return data.get("document_context")

def get_all_documents(session_id: str) -> list[dict]:
    """Return all documents accumulated in this session."""
    data = load(session_id)
    if not data:
        return []
    docs = data.get("documents", [])
    if not docs and data.get("document_context"):
        return [data["document_context"]]
    return docs

def append_message(
    session_id: str,
    role: str,
    content: str,
    prompt: str | None = None,
    document: dict | None = None,
    documents: list[dict] | None = None,
    source: str | None = None,
    grounded: bool = False,
    code_result: dict | None = None,
    doc_result: dict | None = None,
) -> str:
    """Append a message to the session with optional code and document deliverables."""
    data = load(session_id)
    if not data:
        return ""
    
    message_id = str(uuid.uuid4())
    doc_list = documents if documents is not None else ([document] if document else [])
    single_doc = document if document is not None else (documents[0] if documents else None)
    
    msg = {
        "id": message_id,
        "role": role,
        "content": content,
        "prompt": prompt if prompt is not None else (content if role == "user" else None),
        "document": single_doc,
        "documents": doc_list,
        "source": source,
        "grounded": grounded,
        "code_result": code_result,
        "doc_result": doc_result,
        "timestamp": int(time.time()),
    }
    data["messages"].append(msg)
    
    # Auto-generate title from first user message if it's still "New chat"
    if data.get("title") == "New chat" and role == "user":
        title_text = prompt or content
        data["title"] = (title_text[:47] + "...") if len(title_text) > 50 else title_text
        
    _save(session_id, data)
    return message_id

def list_sessions(user_id: str = "default") -> list[dict]:
    sessions = []
    if not os.path.exists(SESSIONS_DIR):
        return []
    for filename in os.listdir(SESSIONS_DIR):
        if filename.endswith(".json"):
            session_id = filename[:-5]
            data = load(session_id)
            if data and (data.get("user_id") == user_id or (user_id == "default" and not data.get("user_id"))):
                sessions.append({
                    "id": data["id"],
                    "title": data.get("title", "Chat"),
                    "created_at": data.get("created_at", 0),
                    "updated_at": data.get("updated_at", data.get("created_at", 0)),
                    "has_document": data.get("document_context") is not None,
                })
    # Sort newest first
    sessions.sort(key=lambda x: x.get("updated_at", x.get("created_at", 0)), reverse=True)
    return sessions

def delete_session(session_id: str) -> None:
    path = _get_path(session_id)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
