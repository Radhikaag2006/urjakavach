# Task: Add offline multilingual voice assistant to the app

## Context
This app is an offline/on-prem AI workbench. It currently has a working
text-based chat flow (user types → local LLM responds). We need to add
voice input and voice output on top of the existing chat flow, without
breaking it — text chat must keep working exactly as it does now.

Do NOT touch the database/conversation-storage layer in this task. We are
intentionally keeping conversation history in the existing JSON files for
now; a DB migration will happen separately later. Just make sure whatever
you build here still logs to the existing JSON structure the same way
normal text messages do.

## Requirements

- Input languages: Hindi and English (accuracy on other languages doesn't
  matter, don't optimize for them)
- Everything must run fully offline at runtime — no calls to any cloud
  STT/TTS/LLM API. Model weights may be downloaded once during setup.
- The existing local LLM chat endpoint should NOT be replaced — voice is
  a new input/output method feeding into the SAME chat logic that already
  exists for typed messages.

## Flow to implement

1. Frontend: mic button → record audio via `MediaRecorder` → send as a
   blob to a new backend endpoint.
   - While recording, replace the mic button's idle state with a
     Siri-style listening animation (a soft pulsing/wavy blob-shaped
     glow that reacts to the mic input level, similar to Apple Siri's
     visual) so the user has clear, unambiguous feedback that recording
     is active.
   - Place the MRPL logo centered inside/on top of that animated glow
     (same layout idea as Siri's orb, but branded with the MRPL logo
     instead of Apple's), so it reads as "MRPL is listening" rather than
     a generic recording indicator.
   - Animation states needed: idle (mic icon, no animation), listening
     (pulsing glow + logo, as above), processing (after recording stops,
     while waiting on `/api/transcribe`, show a distinct
     loading/thinking state so the user knows it's no longer recording
     but hasn't got a reply yet), and back to idle once the reply
     arrives. Don't leave the listening animation running after the user
     stops speaking or releases the mic button.
   - Keep this component self-contained (its own CSS/animation, no
     changes to unrelated UI) so it can be dropped in without touching
     the rest of the frontend layout.
2. Backend: new endpoint `POST /api/transcribe`
   - Accepts an audio file (webm/wav)
   - Runs it through `faster-whisper` (use the `small` model, CPU-friendly,
     `language=None` so it auto-detects Hindi vs English)
   - Returns JSON: `{ "text": "...", "detected_language": "hi" | "en" }`
3. Backend: feed `text` + `detected_language` into the EXISTING chat/LLM
   function, the same one already used for typed messages. Add a system
   prompt instruction so the reply is generated in the same language as
   `detected_language` (see prompt below — use it verbatim).
4. Backend: new endpoint `POST /api/synthesize`
   - Accepts `{ "text": "...", "language": "hi" | "en" }`
   - Picks a TTS model based on language: `facebook/mms-tts-hin` for Hindi,
     `facebook/mms-tts-eng` for English (via `transformers`)
   - Synthesizes audio, saves to a temp file, returns it as an audio
     response (or a URL to fetch it)
   - Deletes the temp file after it's served (don't accumulate files)
5. Frontend: on receiving the LLM's text reply, display it immediately
   (don't wait for audio). Separately call `/api/synthesize` with the
   reply text + detected_language, then play the returned audio via an
   `<audio>` element once ready.

## System prompt to use for language-matched replies

Add this to the existing system prompt (don't replace the whole thing,
append this block), and pass `detected_language` alongside the user's
message on every turn, not just once at the start of the conversation:

```
You will receive a user message along with its detected input language
(hi = Hindi, en = English).

Rules for your reply:
- Always reply in the SAME language as detected_language.
- If detected_language is "hi", reply entirely in Hindi using Devanagari script.
- If detected_language is "en", reply entirely in English.
- If the user's message mixes Hindi and English (Hinglish), match that mix
  in your reply rather than forcing pure Hindi or pure English.
- Do not translate or explain the language you are using — just respond
  naturally in it.
- Keep technical terms (proper nouns, product names, numbers) as-is
  regardless of language.
```

## Files to create/modify

- `backend/routes/transcribe.py` (or equivalent in current framework) —
  the `/api/transcribe` endpoint
- `backend/routes/synthesize.py` — the `/api/synthesize` endpoint
- `backend/services/whisper_service.py` — loads and runs faster-whisper
  once at startup (don't reload the model per-request)
- `backend/services/tts_service.py` — loads and runs the two MMS-TTS
  models once at startup
- Existing chat/LLM handler file — small edit to accept an optional
  `detected_language` param and append it to the prompt
- Frontend: a mic button component with recording logic, wired to call
  `/api/transcribe` then the existing chat-send function, then
  `/api/synthesize` for playback
- `requirements.txt` — add `faster-whisper`, `transformers` (if not
  already present)

## Acceptance criteria

- Speaking in English produces a transcribed English message, an
  English-language LLM reply (text visible immediately), and spoken
  English audio playback
- Speaking in Hindi produces a transcribed Hindi message (Devanagari or
  Romanized, whichever Whisper outputs), a Hindi-language LLM reply, and
  spoken Hindi audio playback
- Typing (existing text flow) still works completely unchanged
- No network calls happen at runtime once models are downloaded (verify
  by disconnecting network after first run and testing again)
- No leftover temp audio files accumulate on disk after repeated use

## Ask before assuming

If the current backend framework, existing chat function's signature, or
frontend framework aren't obvious from the codebase, ask before writing
code rather than guessing.
