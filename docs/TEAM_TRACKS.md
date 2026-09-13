# Team tracks — who owns what

Three tracks run **in parallel**. File ownership is deliberately split so two
people rarely touch the same file, which keeps merge conflicts near zero.

---

## Track A — Model layer

**Owns:** `app/model_router.py` · `app/prompts.py` · `app/kb/` · `scripts/start_models.*`

Does **not** need a Mac. llama.cpp runs on Windows and Linux too — and if you
have an Nvidia GPU, your dev loop will be faster than the Mac users'.

**Day 1**
1. Install llama.cpp, download both GGUF files, get `llama-server` answering a
   raw `curl` on :8080 and :8081. **Do not touch app code until this works.**
2. Set `USE_REAL_MODEL=true`, run `pytest tests/test_model_router.py -v`.
3. Tune `app/prompts.py` until findings extraction preserves equipment tags
   (PL-204B, PG-11) and returns one finding per line.
4. Verify the activity log shows **two different model names** on the ROUTE
   lines — that is the multi-model proof for the video.

**Day 2 (stretch)** — build the knowledge base (`python -m app.kb.build_index`),
confirm `grounded: true` comes back on the document flow.

**Definition of done:** both flows produce good output with `USE_REAL_MODEL=true`,
*and* still work when you flip it to `false`.

---

## Track B — Backend / orchestration

**Owns:** `app/main.py` · `app/orchestrator.py` · `app/tools/*` · `app/activity_log.py` · `tests/`

**Day 1**
1. Run `pytest -v` — all green before you change anything.
2. Harden the tools: error paths, edge cases (empty OCR result, huge image,
   code that loops forever, malformed upload).
3. Add a test for every bug you fix. The suite is the contract between tracks.
4. Keep `main.py` thin — HTTP concerns only, logic goes in the orchestrator.

**Day 2** — tighten the iterate loop, make log wording legible on camera
(it will be read at 1080p from three feet away).

**Definition of done:** `pytest -v` fully green, `scripts/smoke_test.py` passes
against a running server in both model modes.

---

## Track C — Frontend / demo

**Owns:** `frontend/*` · `docs/DEMO_SCRIPT.md` · the PPT · the video

Zero OS dependency — it is HTML/CSS/JS in a browser.

**Day 1**
1. Run both flows in the UI, list everything that looks wrong or unclear.
2. Make the terminal panel unmistakable — it is the single most important
   element on screen, because it is what visually proves multi-step agency.
3. Check every error path actually renders (stop the backend mid-demo and
   confirm you get a readable error, not a frozen button).

**Day 2** — align UI wording with the PPT and the narration script, then own
the recording.

**Definition of done:** a full demo run recorded, watchable, with no dead air
and no unexplained pauses.

---

## The two Mac owners (cross-cutting)

Whoever has a Mac additionally owns **final integration on real demo hardware**:

- Set up llama.cpp on the Mac on **Day 1 morning**, not Day 2. Discovering a
  hardware problem on Day 2 is how teams lose.
- Pull `main` several times a day — integration problems should surface at
  hour 5, not hour 20.
- Review PRs for cross-platform mistakes (see below).
- Run the **Day 1 evening full-team integration test** and own the Day 2 dry run
  and recording.
- Check RAM: both models running together must not thrash on the presenting
  laptop. If they do, drop to smaller quantizations — never drop routing.

---

## Git workflow

```bash
git checkout -b track-a/real-model-call
# ... work ...
pytest -v                    # must be green before you push
git push -u origin track-a/real-model-call
# open PR -> a Mac owner reviews and merges
```

**Rules**
- Branch prefix by track: `track-a/`, `track-b/`, `track-c/`.
- **Small, frequent PRs.** Do not batch a whole layer into one giant PR.
- `pytest -v` green is required before opening a PR.
- Never commit: `.env`, `*.gguf`, `venv/`, generated `.docx` or `.log` files.
  (`.gitignore` covers these — do not override it.)
- Anything machine-specific belongs in `app/config.py` + `.env`, nowhere else.

## Cross-platform rules — everyone, every PR

These are what actually cause "works on my machine" bugs:

1. Use `config.PYTHON_EXECUTABLE`, never a hardcoded `"python3"` — it does not
   exist on most Windows installs.
2. Use `os.path.join` / `pathlib`, never hand-typed `/` or `\` separators.
3. Read every URL, port and path from `app/config.py`, never inline.
4. Open text files with `encoding="utf-8"` explicitly — Windows defaults differ.

---

## Daily checkpoints

| When | What | Who |
|---|---|---|
| Day 1, 12:00 | Model servers answering curl; tests green | All tracks |
| Day 1, 18:00 | Real models wired in, both flows work | Track A + B |
| Day 1, 21:00 | **Full-team integration test on the Mac** | Everyone |
| Day 2, 12:00 | Day-1 failures fixed, smoke test passes | All tracks |
| Day 2, 15:00 | Rough demo recorded once, end to end | Track C |
| Day 2, 19:00 | **Build frozen.** Final recording. | Mac owners |

After the freeze, no code changes except to fix something that visibly breaks on
camera. The biggest risk in the last hours is breaking something that already
worked.
