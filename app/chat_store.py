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

def new_session(user_id: str) -> str:
    session_id = str(uuid.uuid4())
    data = {
        "id": session_id,
        "user_id": user_id,
        "title": "New chat",
        "created_at": int(time.time()),
        "messages": []
    }
    with open(_get_path(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f)
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

def append_message(session_id: str, role: str, content: str) -> None:
    data = load(session_id)
    if not data:
        return
    data["messages"].append({"role": role, "content": content})
    
    # Auto-generate title from first user message if it's "New chat"
    if data["title"] == "New chat" and role == "user":
        # First 50 chars of first message
        data["title"] = (content[:47] + "...") if len(content) > 50 else content
        
    with open(_get_path(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f)

def list_sessions(user_id: str) -> list[dict]:
    sessions = []
    for filename in os.listdir(SESSIONS_DIR):
        if filename.endswith(".json"):
            session_id = filename[:-5]
            data = load(session_id)
            if data and data.get("user_id") == user_id:
                # Return summary without all messages for the list view
                sessions.append({
                    "id": data["id"],
                    "title": data.get("title", "Chat"),
                    "created_at": data.get("created_at", 0)
                })
    # Sort newest first
    sessions.sort(key=lambda x: x["created_at"], reverse=True)
    return sessions

def delete_session(session_id: str) -> None:
    path = _get_path(session_id)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
