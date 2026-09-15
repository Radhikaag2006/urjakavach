# UrjaKavach

**Sovereign On-Premise Agentic AI Workbench using Open-Weight Multimodal LLMs
for Confidential Industrial Work**

SIH 2026 · Problem Statement **26117** · Mangalore Refinery and Petrochemicals
Limited (MRPL) · Team **Smashers**

---

An agentic AI workbench that runs entirely inside a plant's own network. No
data leaves the facility. Two working scenarios:

1. **Scanned report → approval note** — OCR a scanned inspection report, ground
   the reading in MRPL's own SOPs, extract engineering findings, generate a real
   `.docx` approval note.
2. **Coding task → verified code** — generate Python for a plain-English
   request, then *execute it in an isolated sandbox* to verify it actually runs
   before returning it.

Every step is written to an append-only audit log.

---

## Quick start

```bash
python3 -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
pytest -v
python -m uvicorn app.main:app --reload --port 8000
```

Then open `frontend/index.html` in a browser.

Works immediately in **stub mode** with no model installed. To use real local
models, see [docs/SETUP.md](docs/SETUP.md) step 8.

---

## Documentation

| Doc | Read it when |
|---|---|
| [docs/SETUP.md](docs/SETUP.md) | Setting up your laptop — start here |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Understanding how the system fits together |
| [docs/TEAM_TRACKS.md](docs/TEAM_TRACKS.md) | What you own, git workflow, checkpoints |
| [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | Recording the demo video |

---

## Project layout

```
urjakavach/
├── app/
│   ├── config.py          ALL machine-specific settings live here
│   ├── main.py            FastAPI - HTTP layer only            [Track B]
│   ├── orchestrator.py    plan -> route -> act -> verify loop   [Track B]
│   ├── model_router.py    multi-model routing + stub fallback   [Track A]
│   ├── prompts.py         MRPL domain grounding                 [Track A]
│   ├── activity_log.py    append-only audit trail               [Track B]
│   ├── tools/
│   │   ├── ocr_tool.py        Tesseract OCR              REAL
│   │   ├── sandbox_tool.py    isolated execution         REAL
│   │   ├── docgen_tool.py     .docx generation           REAL
│   │   └── kb_tool.py         RAG retrieval              REAL
│   ├── kb/
│   │   ├── documents/         MRPL reference material
│   │   └── build_index.py     builds the vector index
│   ├── samples/           sample scanned report
│   ├── outputs/           generated .docx        (gitignored)
│   └── logs/              activity log           (gitignored)
├── frontend/
│   ├── index.html         structure                             [Track C]
│   ├── styles.css         VS Code dark theme                    [Track C]
│   └── app.js             fetch logic + rendering               [Track C]
├── tests/                 32 tests - must be green before any PR
├── scripts/
│   ├── start_models.sh    launch both model servers (Mac/Linux)
│   ├── start_models.ps1   launch both model servers (Windows)
│   └── smoke_test.py      pre-demo end-to-end check
└── docs/
```

---

## The two flags that matter

In `.env`:

```
USE_REAL_MODEL=false     # true = real llama.cpp models, false = deterministic stub
USE_KNOWLEDGE_BASE=true  # RAG grounding on MRPL reference docs
```

`USE_REAL_MODEL=false` is the **demo safety net**. If the models misbehave
before recording, flip it and everything still works. Real model calls also fall
back to the stub automatically if a server is unreachable — no single failure
can take down the demo.

---

## Before you push

```bash
pytest -v
```

Green, always. See [docs/TEAM_TRACKS.md](docs/TEAM_TRACKS.md) for branch naming
and the cross-platform rules.


## Security & Authentication
Role-based authentication is fully implemented. A custom login UI securely manages sessions, requiring Email, GitHub ID, or Phone Number along with a hashed password. User data and session management is handled via an encrypted JSON database (users.json), ensuring users only access their own private chat histories.

## Updates:
- **Profile Editing:** Logged-in users can update their Name, Profession, and Country via the Edit Profile button in the sidebar.
- **Animated UI:** Added 3D perspective animations and glowing effects to the authentication container.
- **Validation:** Enforces 6-character passwords and strictly 6-digit Employee Codes during registration.
- **Git Safety:** Explicitly ensured users.json is ignored via .gitignore to prevent leaking hashed passwords or PII.