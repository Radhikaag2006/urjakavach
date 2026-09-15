import os
import json
import uuid
import hashlib
import time
import secrets
from . import config

USERS_FILE = os.path.join(config.LOGS_DIR, "users.json")
# In-memory token store: { token: {"user_id": user_id, "expires": timestamp} }
_TOKENS = {}

def _load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def register_user(identifier: str, password: str, name: str, profession: str, country: str, emp_code: str, github_id: str, role: str = "user") -> dict:
    users = _load_users()
    identifier = identifier.strip().lower()
    
    if len(password) <= 6:
        raise ValueError("Password must be more than 6 characters")
    if not emp_code.isdigit() or len(emp_code) != 6:
        raise ValueError("Employee code must be exactly 6 digits")
    
    # Check if exists
    for u_id, u_data in users.items():
        if u_data.get("identifier") == identifier:
            raise ValueError("User already exists")
            
    user_id = str(uuid.uuid4())
    salt = secrets.token_hex(8)
    
    users[user_id] = {
        "id": user_id,
        "identifier": identifier,
        "name": name,
        "profession": profession,
        "country": country,
        "emp_code": emp_code,
        "github_id": github_id,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "role": role,
        "created_at": int(time.time())
    }
    _save_users(users)
    return {"id": user_id, "identifier": identifier, "name": name, "role": role}


def update_user_info(user_id: str, data: dict) -> bool:
    users = _load_users()
    if user_id not in users:
        return False
    u = users[user_id]
    if 'name' in data:
        u['name'] = data['name']
    if 'profession' in data:
        u['profession'] = data['profession']
    if 'country' in data:
        u['country'] = data['country']
    _save_users(users)
    return True

def get_user_info(user_id: str) -> dict | None:
    users = _load_users()
    if user_id in users:
        u = users[user_id]
        return {"name": u.get("name", "User"), "profession": u.get("profession", "")}
    return None

def authenticate_user(identifier: str, password: str) -> str:
    users = _load_users()
    identifier = identifier.strip().lower()
    
    for u_id, u_data in users.items():
        if u_data.get("identifier") == identifier:
            expected_hash = _hash_password(password, u_data["salt"])
            if expected_hash == u_data["password_hash"]:
                # Generate token
                token = secrets.token_hex(16)
                # Token valid for 24 hours
                _TOKENS[token] = {"user_id": u_id, "expires": time.time() + 86400}
                return token
                
    raise ValueError("Invalid credentials")

def get_user_from_token(token: str) -> str | None:
    session = _TOKENS.get(token)
    if not session:
        return None
    if time.time() > session["expires"]:
        del _TOKENS[token]
        return None
    return session["user_id"]
