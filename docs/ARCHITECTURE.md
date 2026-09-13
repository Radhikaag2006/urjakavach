# UrjaKavach — Architecture

**SIH 2026 · PS 26117 · Team Smashers**
Sovereign On-Premise Agentic AI Workbench for MRPL

---

## Development architecture: MVP as a walking skeleton

We are **not** building layer-by-layer and integrating at the end. We build a
thin version of the *entire* pipeline that works end to end, then replace each
piece with a stronger one, keeping the system runnable at every moment.

```
Day 0 (done)   frontend -> API -> orchestrator -> [stub] -> tools -> deliverable   WORKS
Day 1          frontend -> API -> orchestrator -> [real models] -> tools           WORKS
Day 2          + knowledge-base grounding, + polish                                WORKS
```

The rule that protects us: **never leave the system broken for more than an
hour.** Every change goes from "working" to "working, but better."

This is why `USE_REAL_MODEL` exists. The stub is not dead code to be deleted —
it is the safety net. If the models misbehave 20 minutes before recording, flip
one flag and everything still runs.

---

## Runtime architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    ON-PREMISE / AIR-GAPPED FACILITY                  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ PRESENTATION LAYER                             frontend/        │  │
│  │ index.html · styles.css · app.js                                │  │
│  │ Vanilla HTML/CSS/JS - no build step, no CDN, works offline      │  │
│  └───────────────────────────┬────────────────────────────────────┘  │
│                              │ fetch() over localhost                 │
│  ┌───────────────────────────▼────────────────────────────────────┐  │
│  │ API LAYER                                      app/main.py      │  │
│  │ FastAPI · /api/health /api/tasks/* /api/logs /api/outputs/*     │  │
│  └───────────────────────────┬────────────────────────────────────┘  │
│                              │                                        │
│  ┌───────────────────────────▼────────────────────────────────────┐  │
│  │ AGENT ORCHESTRATION LAYER               app/orchestrator.py     │  │
│  │ plan -> route -> act -> verify -> iterate                       │  │
│  │ Logs EVERY step to the audit trail                              │  │
│  └──────┬──────────────────────────────────────┬──────────────────┘  │
│         │                                      │                      │
│  ┌──────▼───────────────────────┐   ┌──────────▼──────────────────┐  │
│  │ MODEL SERVING LAYER          │   │ TOOL LAYER      app/tools/  │  │
│  │ app/model_router.py          │   │                             │  │
│  │                              │   │ ocr_tool.py      Tesseract  │  │
│  │  reasoning -> :8080          │   │ sandbox_tool.py  subprocess │  │
│  │    Llama-3.2-3B-Instruct     │   │ docgen_tool.py   python-docx│  │
│  │  code      -> :8081          │   │ kb_tool.py       Chroma RAG │  │
│  │    Qwen2.5-Coder-1.5B        │   │                             │  │
│  │  ocr       -> local tool     │   └─────────────────────────────┘  │
│  │                              │                                     │
│  │  llama.cpp, OpenAI-compatible│   ┌─────────────────────────────┐  │
│  │  Falls back to stub on any   │   │ DATA / STORAGE              │  │
│  │  failure - never 500s        │   │ app/kb/      reference docs │  │
│  └──────────────────────────────┘   │ app/outputs/ generated docx │  │
│                                     │ app/logs/    audit trail    │  │
│                                     └─────────────────────────────┘  │
│                                                                      │
│   NO EGRESS. Nothing in this diagram makes an external network call. │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Why these choices

| Decision | Reason |
|---|---|
| **llama.cpp, not vLLM, for the demo** | vLLM needs a CUDA GPU. The team is on Macs. llama.cpp is Metal-accelerated on Mac and runs on Windows/Linux too. vLLM remains the stated production target on MRPL's GPU infrastructure — the abstraction boundary (an OpenAI-compatible HTTP endpoint) is identical, so it is genuinely a drop-in swap. |
| **Two model servers, not one** | The problem statement is about *multimodal, multi-model* routing. One model doing everything undercuts our own pitch. Two ports = two genuinely different models = a routing claim we can defend. |
| **Hand-rolled orchestrator, not LangGraph** | Same plan/route/act/verify loop, zero framework risk in a 2-day build. Contained in one file if we want to swap it later. |
| **Vanilla JS frontend, no framework** | No build step, no npm, nothing that can break for reasons unrelated to our demo. Also proves the offline claim. |
| **Tesseract for vision, not a VLM** | Real, working, fast, already proven. A multimodal GGUF model is the documented upgrade path, not a Day-2 gamble. |
| **JSON-lines log, not a database** | The audit trail is a demo centrepiece, not a scaling problem. A file is honest and inspectable. |
| **Stub fallback everywhere** | A teammate with no model installed can still run every flow. And no single component failure can take down the demo. |

---

## Request flow — Scenario 1 (document)

```
POST /api/tasks/document
  │
  ├─ plan            "read scanned report, draft approval note"
  ├─ route           vision subtask -> Tesseract
  ├─ tool:vision_ocr extract text from image                    [REAL]
  ├─ tool:knowledge_base  retrieve MRPL reference material       [REAL/skip]
  ├─ route           reasoning subtask -> Llama-3.2-3B :8080
  ├─ tool:reasoning  extract findings, grounded on plant docs    [REAL/stub]
  ├─ iterate_check   findings present? -> proceed
  ├─ tool:file_write build .docx approval note                   [REAL]
  └─ done
```

## Request flow — Scenario 2 (code)

```
POST /api/tasks/code
  │
  ├─ plan             "coding request: <prompt>"
  ├─ route            code subtask -> Qwen2.5-Coder :8081
  ├─ tool:code_gen    generate Python                            [REAL/stub]
  ├─ tool:code_sandbox execute in isolated subprocess            [REAL]
  ├─ iterate_check    passed? -> done.  failed? -> regenerate (up to 2x)
  └─ done
```

The iterate loop on the code flow is what makes this **agentic** rather than a
single model call: the system verifies its own output by executing it, and
retries on failure.

---

## Organisation-specific grounding (MRPL)

Three layers, cheapest first:

1. **Prompt grounding** (`app/prompts.py`) — every reasoning call carries MRPL
   domain context: tag conventions (PL-204B, PG-11, P-7), finding categories,
   severity vocabulary. Zero infrastructure cost, always on.
2. **RAG over plant documents** (`app/tools/kb_tool.py`, `app/kb/`) — retrieves
   from MRPL's own SOPs, approval workflow, and terminology glossary before the
   model answers. Degrades to empty string if not built, so it never blocks.
3. **Fine-tuning** — explicitly out of scope. Needs GPU time and a real dataset;
   RAG gets ~90% of the perceived effect at a fraction of the risk.

---

## What is real vs. simulated (state this honestly to judges)

| Component | Status |
|---|---|
| OCR / vision | **Real** — Tesseract |
| Sandboxed execution | **Real** — isolated subprocess, timeout-guarded |
| Document generation | **Real** — python-docx |
| Model routing | **Real** — two separate servers, different models |
| LLM inference | **Real** when `USE_REAL_MODEL=true`; deterministic stub otherwise |
| Knowledge base / RAG | **Real** — Chroma + sentence-transformers, offline |
| Audit logging | **Real** — append-only JSON-lines |
| Air-gapped operation | **Real** — zero external calls by design |
| vLLM serving | **Not in the demo** — llama.cpp stands in; vLLM is the production target |
| LangGraph | **Not in the demo** — equivalent loop hand-rolled |

Being precise about this line is a strength in front of judges, not a weakness.
It shows we know exactly what we built.
