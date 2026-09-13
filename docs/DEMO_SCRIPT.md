# Demo video — narration script

Target: **3 to 4 minutes.** Run `python scripts/smoke_test.py` first. If it does
not exit clean, do not record.

---

## Before you hit record

- [ ] `scripts/smoke_test.py` passes
- [ ] Both model servers up (`/api/health` shows `"up"`) — or `USE_REAL_MODEL=false` deliberately
- [ ] Browser zoom at 110–125% so the terminal panel is readable on video
- [ ] Notifications silenced, unrelated tabs closed
- [ ] Sample report and a second upload image ready
- [ ] **Turn Wi-Fi off** — then say so on camera. Strongest possible proof.

---

## 0:00 — The problem (20s)

> "Refineries like MRPL generate confidential engineering work every day —
> inspection reports, P&IDs, operational code. None of it can go through cloud
> AI assistants, because that data cannot leave the facility. So today that work
> is done manually. UrjaKavach is a sovereign AI workbench that runs entirely
> inside the plant's own network."

**On screen:** the UI at rest. Point at the status bar: `on-premise · 0 external calls`.

> "My Wi-Fi is off right now. Everything you're about to see runs on this laptop."

---

## 0:20 — Scenario 1: scanned report to approval note (70s)

**On screen:** sidebar, `document_analysis.flow` selected, sample image visible.

> "Here's a scanned inspection report — an image, not text. Watch the terminal
> panel at the bottom: every step the agent takes is logged for audit."

**Click Run Document Flow.** Let the log fill. Then walk it:

> "It plans the task. It routes the vision subtask to the local OCR engine and
> extracts the text. It retrieves MRPL's own inspection SOP from the local
> knowledge base for grounding. Then it routes the *reasoning* subtask to a
> different model — a 3-billion parameter Llama running on this machine — which
> extracts the engineering findings."

Point at the findings list.

> "Note the equipment tags — PL-204B, PG-11 — preserved exactly from the source.
> It doesn't paraphrase plant data."

**Click the download link, open the .docx on screen.**

> "And this is a real Word document, generated locally, ready for engineer
> sign-off. Not a mockup — an actual deliverable."

---

## 1:30 — Scenario 2: code generation with verification (70s)

**Switch to `code_generation.flow`.**

> "Second scenario: engineers also write operational code, and that can't go to
> a cloud assistant either."

Type a prompt, **click Run Code Flow.**

> "Now watch the routing line — this task goes to a *different* model,
> Qwen2.5-Coder, on a different port. That's the model router picking the right
> specialist for the job."

Point at the sandbox output.

> "And here's the part that makes this agentic rather than just a chatbot: the
> system doesn't just print code and hope. It executes it in an isolated
> sandbox, checks that it actually ran, and only then returns it as verified.
> If it fails, it regenerates and tries again."

---

## 2:40 — The architecture claim (40s)

**On screen:** architecture diagram, or `/api/health` JSON.

> "Under the hood: a presentation layer, an API layer, an agentic orchestrator,
> two locally-served open-weight models with task-based routing, a tool layer,
> and an append-only audit log. Every step is recorded — which matters for a
> regulated industrial environment."

> "In production this serves through vLLM on MRPL's own GPU infrastructure. On
> this laptop it's llama.cpp — same open-weight models, same interface, so it's
> a drop-in swap."

---

## 3:20 — Close (20s)

> "Everything you've seen ran on one laptop, with the network disabled. No data
> left this machine. That's what makes it sovereign."

---

## Rules while recording

- **Never apologise for the model being slow.** Narrate through it: "while that
  runs, notice the log is already showing the routing decision."
- **Do not click anything you haven't rehearsed.** No live experiments.
- If something breaks, **stop and re-record** — don't try to recover on camera.
- Record the two scenarios as **separate takes** if it's easier, then cut
  together. A clean cut beats a shaky continuous take.

## If judges ask "is the AI real?"

Answer straight:

> "Yes — open-weight Llama and Qwen models running locally via llama.cpp. The
> OCR, sandbox execution, document generation and audit logging are all real
> implementations. We also ship a deterministic fallback mode so the system
> stays usable if a model is unavailable, which is a deployment requirement in
> an industrial setting, not a shortcut."

Never overclaim. Knowing exactly where your boundaries are reads as engineering
maturity.
