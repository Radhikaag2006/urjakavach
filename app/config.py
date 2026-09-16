"""
Central configuration for UrjaKavach.

Everything machine-specific lives HERE and nowhere else, so the same
code runs unchanged on a Mac, Windows or Linux laptop. Override any
value with an environment variable (see .env.example).

Team note: if you find yourself hardcoding a path, a port or a model
name anywhere else in the codebase, it belongs in this file instead.
"""
import os
import sys
from dotenv import load_dotenv 

load_dotenv()

from dotenv import load_dotenv

# --------------------------------------------------------------------
# Paths — always derived, never hardcoded, so they work on every OS
# --------------------------------------------------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
SAMPLES_DIR = os.path.join(APP_DIR, "samples")
OUTPUTS_DIR = os.path.join(APP_DIR, "outputs")
LOGS_DIR = os.path.join(APP_DIR, "logs")
KB_DIR = os.path.join(APP_DIR, "kb")
KB_DOCUMENTS_DIR = os.path.join(KB_DIR, "documents")
KB_INDEX_DIR = os.path.join(KB_DIR, "index")

AGENTS_DATA_DIR = os.path.join(LOGS_DIR, "agents")

for _d in (OUTPUTS_DIR, LOGS_DIR, KB_DOCUMENTS_DIR, AGENTS_DATA_DIR):
    os.makedirs(_d, exist_ok=True)

# The interpreter running this process. NEVER hardcode "python3" —
# it does not exist on most Windows installs.
PYTHON_EXECUTABLE = sys.executable

# --------------------------------------------------------------------
# Model serving — two llama.cpp servers, one per task type
# --------------------------------------------------------------------
# Flip to "false" to fall back to the deterministic stub. This is the
# safety net: if the local models misbehave right before recording the
# demo, set USE_REAL_MODEL=false and everything still works.
USE_REAL_MODEL = os.getenv("USE_REAL_MODEL", "false").strip().lower() == "true"

REASONING_MODEL_URL = os.getenv(
    "REASONING_MODEL_URL", "http://localhost:8080/v1/chat/completions"
)
CODE_MODEL_URL = os.getenv(
    "CODE_MODEL_URL", "http://localhost:8081/v1/chat/completions"
)

REASONING_MODEL_NAME = os.getenv("REASONING_MODEL_NAME", "Llama-3.2-3B-Instruct")
CODE_MODEL_NAME = os.getenv("CODE_MODEL_NAME", "Qwen2.5-Coder-1.5B-Instruct")

MODEL_TIMEOUT_SEC = int(os.getenv("MODEL_TIMEOUT_SEC", "120"))
MODEL_MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", "384"))
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.2"))
# Optional explicit path to the Tesseract binary. Leave unset to rely on
# PATH (works on Mac/Linux usually; Windows PATH issues are common).
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")

# --------------------------------------------------------------------
# Knowledge base (organisation-specific grounding)
# --------------------------------------------------------------------
USE_KNOWLEDGE_BASE = os.getenv("USE_KNOWLEDGE_BASE", "true").lower() == "true"
KB_TOP_K = int(os.getenv("KB_TOP_K", "2"))

# --------------------------------------------------------------------
# Sandbox
# --------------------------------------------------------------------
SANDBOX_TIMEOUT_SEC = int(os.getenv("SANDBOX_TIMEOUT_SEC", "5"))

# --------------------------------------------------------------------
# API
# --------------------------------------------------------------------
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))


def describe() -> dict:
    """Used by /api/health so the UI (and the demo video) can show
    exactly what mode the system is running in."""
    return {
        "use_real_model": USE_REAL_MODEL,
        "reasoning_model": REASONING_MODEL_NAME if USE_REAL_MODEL else "deterministic-stub",
        "code_model": CODE_MODEL_NAME if USE_REAL_MODEL else "deterministic-stub",
        "knowledge_base": USE_KNOWLEDGE_BASE,
        "external_calls": 0,
    }
