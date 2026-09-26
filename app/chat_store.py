import os
import json
import uuid
import time
from . import config

LOGS_DIR = config.LOGS_DIR
USERS_DIR = os.path.join(LOGS_DIR, "users")
INDEX_FILE = os.path.join(LOGS_DIR, "session_index.json")

os.makedirs(USERS_DIR, exist_ok=True)

def _load_index() -> dict:
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_index(index: dict):
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f)

def _get_path(session_id: str, user_id: str = None) -> str:
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
    
    if not user_id:
        index = _load_index()
        user_id = index.get(safe_id, "default")
    
    safe_user_id = "".join(c for c in user_id if c.isalnum() or c in "-_@.")
    user_sessions_dir = os.path.join(USERS_DIR, safe_user_id, "sessions")
    os.makedirs(user_sessions_dir, exist_ok=True)
    
    return os.path.join(user_sessions_dir, f"{safe_id}.json")

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
    
    # Save to index
    index = _load_index()
    index[session_id] = user_id
    _save_index(index)
    
    with open(_get_path(session_id, user_id), "w", encoding="utf-8") as f:
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
    user_id = data.get("user_id", "default")
    with open(_get_path(session_id, user_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def add_document_context(
    session_id: str,
    source_name: str,
    raw_text: str,
    findings: list[str],
    summary: str = "",
) -> dict:
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
    existing_idx = next(
        (i for i, d in enumerate(data["documents"]) if d.get("source_name") == source_name),
        -1
    )
    if existing_idx >= 0:
        data["documents"][existing_idx] = doc_record
    else:
        data["documents"].append(doc_record)

    data["document_context"] = doc_record

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
    add_document_context(session_id, source_name, raw_text, findings, summary)

def get_document_context(session_id: str) -> dict | None:
    data = load(session_id)
    if not data:
        return None
    return data.get("document_context")

def get_all_documents(session_id: str) -> list[dict]:
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
    
    if data.get("title") == "New chat" and role == "user":
        title_text = prompt or content
        data["title"] = (title_text[:47] + "...") if len(title_text) > 50 else title_text
        
    _save(session_id, data)
    return message_id

def list_sessions(user_id: str = "default") -> list[dict]:
    sessions = []
    safe_user_id = "".join(c for c in user_id if c.isalnum() or c in "-_@.")
    user_sessions_dir = os.path.join(USERS_DIR, safe_user_id, "sessions")
    
    if not os.path.exists(user_sessions_dir):
        return []
        
    for filename in os.listdir(user_sessions_dir):
        if filename.endswith(".json"):
            session_id = filename[:-5]
            data = load(session_id)
            if data:
                sessions.append({
                    "id": data["id"],
                    "title": data.get("title", "Chat"),
                    "created_at": data.get("created_at", 0),
                    "updated_at": data.get("updated_at", data.get("created_at", 0)),
                    "has_document": data.get("document_context") is not None,
                })
                
    sessions.sort(key=lambda x: x.get("updated_at", x.get("created_at", 0)), reverse=True)
    return sessions

def delete_session(session_id: str) -> None:
    path = _get_path(session_id)
    if os.path.exists(path):
        try:
            os.remove(path)
            index = _load_index()
            if session_id in index:
                del index[session_id]
                _save_index(index)
        except OSError:
            pass
