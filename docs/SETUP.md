# Setup — every team member, every OS

Follow these in order. Steps 1–7 work identically on Mac, Windows and Linux.
Should take about 20 minutes, most of it downloads.

---

## 1. Clone the repo

```bash
git clone <repo-url>
cd urjakavach
```

## 2. Check Python 3.10+

```bash
python3 --version     # Mac / Linux
python --version      # Windows
```

Missing? Mac: `brew install python3` · Windows: python.org installer, **tick
"Add to PATH"** · Linux: `sudo apt install python3 python3-pip`

## 3. Virtual environment + dependencies

```bash
python3 -m venv venv

source venv/bin/activate      # Mac / Linux
venv\Scripts\activate         # Windows PowerShell

pip install -r requirements.txt
```

## 4. Install Tesseract (the OS binary, not just the pip package)

- **Mac:** `brew install tesseract`
- **Linux:** `sudo apt install tesseract-ocr`
- **Windows:** install the [UB-Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki), then add its folder to PATH

Verify — this must print a version, not "command not found":

```bash
tesseract --version
```

## 5. Create your local config

```bash
cp .env.example .env        # Mac / Linux
copy .env.example .env      # Windows
```

Leave `USE_REAL_MODEL=false` for now. The app works fully in stub mode — you do
not need a model installed to start contributing.

## 6. Run the tests

```bash
pytest -v
```

All tests must pass before you write any code. This is your baseline: if
something breaks later, you know it was your change.

## 7. Run the app

Terminal 1:
```bash
python -m uvicorn app.main:app --reload --port 8000
```

Then open `frontend/index.html` in your browser (double-click it).

Click both **Run Document Flow** and **Run Code Flow**. Both must work. You are
now set up.

---

## 8. Model layer — only when you are ready to use real models

### Install llama.cpp

- **Mac:** `brew install llama.cpp`
- **Windows:** download a prebuilt binary from [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases)
- **Linux:** release binary, or build with CMake

### Download the models

**Everyone must use the exact same files.** Different quantizations produce
different output and we will waste hours chasing a "bug" that is just a
different file.

Create a `models/` folder in the project root (it is gitignored) and download:

| Role | File | Approx size |
|---|---|---|
| Reasoning | `Llama-3.2-3B-Instruct-Q4_K_M.gguf` | ~2.0 GB |
| Code | `Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf` | ~1.1 GB |

Get them from the `bartowski` GGUF repos on Hugging Face. Download on your own
machine's normal internet connection.

### Start both servers

```bash
./scripts/start_models.sh ./models          # Mac / Linux
.\scripts\start_models.ps1 -ModelDir .\models   # Windows
```

Or manually, in two terminals:

```bash
llama-server -m models/Llama-3.2-3B-Instruct-Q4_K_M.gguf --port 8080
llama-server -m models/Qwen2.5-Coder-1.5B-Instruct-Q4_K_M.gguf --port 8081
```

**Test the servers directly before touching app code:**

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"say hello"}]}'
```

### Switch the app to real models

In `.env`: `USE_REAL_MODEL=true`, then restart uvicorn.

Check `/api/health` — `models` should show both as `"up"`.

---

## 9. Knowledge base — optional, for MRPL grounding

```bash
python -m app.kb.build_index
```

First run downloads the embedding model (~90 MB), then works offline forever.
Skip this and everything still runs — grounding just stays off.

---

## 10. Before every demo recording

```bash
python scripts/smoke_test.py
```

Exits 0 only if every flow works end to end. If it fails, do not record.

---

## Troubleshooting

**`uvicorn: command not found`** — use `python -m uvicorn ...` instead. The
script directory is not on your PATH.

**`ModuleNotFoundError`** — your venv is not activated, or pip installed into a
different Python. Run `python -m pip install -r requirements.txt`.

**`TesseractNotFoundError`** — step 4 was skipped, or Windows PATH was not
updated. Restart your terminal after installing.

**Frontend shows "backend not reachable"** — uvicorn is not running, or it is on
a different port. Check `http://localhost:8000/api/health` in a browser.

**Models show "unreachable" in /api/health** — `llama-server` is not running.
The app still works; it silently falls back to the stub.

**Code flow returns odd output in real mode** — the small code model sometimes
ignores instructions. Lower `MODEL_TEMPERATURE`, or set `USE_REAL_MODEL=false`
if you are close to recording.
