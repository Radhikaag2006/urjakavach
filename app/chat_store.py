"""
Chat session storage — simple JSON-file persistence for the
general-purpose chat feature. No database needed for a single-user
on-premise demo; each session is one JSON file under app/chat_history/,
gitignored the same way generated outputs and logs are.

Owner: chat feature (Track A/B).
"""
import json
import os
import time
import uuid

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "chat_history")
os.makedirs(SESSIONS_DIR, exist_ok=True)


def _path(session_id: str) -> str:
    safe = os.path.basename(session_id)  # prevent path traversal
    return os.path.join(SESSIONS_DIR, f"{safe}.json")


def new_session() -> str:
    session_id = str(uuid.uuid4())[:8]
    _save(session_id, {
        "id": session_id,
        "title": "New chat",
        "created_at": time.time(),
        "messages": [],
    })
    return session_id


def _save(session_id: str, data: dict) -> None:
    with open(_path(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load(session_id: str) -> dict | None:
    path = _path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def append_message(session_id: str, role: str, content: str) -> dict:
    data = load(session_id) or {
        "id": session_id,
        "title": "New chat",
        "created_at": time.time(),
        "messages": [],
    }
    data["messages"].append({
        "role": role,
        "content": content,
        "ts": time.time(),
    })
    if data["title"] == "New chat" and role == "user":
        data["title"] = content[:60]
    _save(session_id, data)
    return data


def list_sessions() -> list[dict]:
    sessions = []
    for fname in os.listdir(SESSIONS_DIR):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(SESSIONS_DIR, fname), "r", encoding="utf-8") as f:
            data = json.load(f)
        sessions.append({
            "id": data["id"],
            "title": data.get("title", "New chat"),
            "created_at": data.get("created_at", 0),
            "message_count": len(data.get("messages", [])),
        })
    sessions.sort(key=lambda s: s["created_at"], reverse=True)
    return sessions


def delete_session(session_id: str) -> None:
    path = _path(session_id)
    if os.path.exists(path):
        os.remove(path)