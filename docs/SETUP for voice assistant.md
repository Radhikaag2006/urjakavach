# Setup guide — offline voice assistant (MRPL workbench)

Follow this once on each teammate's machine to get the voice pipeline
(Whisper STT + local LLM + MMS-TTS) running.

## 1. Prerequisites

- Python 3.10+ installed
- Git access to this repo
- ~10 GB free disk space (model weights for Whisper, the LLM, and TTS
  models all get cached locally)
- Internet connection for this setup step only — after models are
  downloaded once, no internet is needed to run the app

## 2. Clone and install dependencies

```bash
git clone <repo-url>
cd <repo-folder>

python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate

pip install -r requirements.txt
```

`requirements.txt` should include (add if missing):
```
faster-whisper
transformers
torch
```

## 3. Download models (one-time, needs internet)

Run the app once, or run this small script, so the models get pulled
and cached locally (default cache location: `~/.cache/huggingface`):

```bash
python -c "
from faster_whisper import WhisperModel
WhisperModel('small', device='cpu', compute_type='int8')

from transformers import VitsModel, AutoTokenizer
VitsModel.from_pretrained('facebook/mms-tts-hin')
AutoTokenizer.from_pretrained('facebook/mms-tts-hin')
VitsModel.from_pretrained('facebook/mms-tts-eng')
AutoTokenizer.from_pretrained('facebook/mms-tts-eng')
"
```

This downloads:
- Whisper `small` model (~500 MB) — speech-to-text
- MMS-TTS Hindi + English models (~100–200 MB each) — text-to-speech

Your local LLM (Llama/Qwen per the project stack) should already have
its own separate setup/download step — follow the existing instructions
for that if not already done on this machine.

## 4. Verify offline operation

After the download step above completes:

```bash
# Turn off wifi / disconnect network, then:
python -m pytest tests/test_voice_pipeline.py   # if tests exist
# or just run the app and test mic input manually
```

If transcription, LLM reply, and TTS playback all still work with no
network connection, offline setup is confirmed.

## 5. Run the app

```bash
# backend
python app.py          # or however the existing backend is started

# frontend (separate terminal, if applicable)
npm install
npm run dev
```

Open the app, click the mic button, and speak in Hindi or English —
you should see the Siri-style listening animation while recording, a
processing state while it transcribes and generates a reply, and then
the reply both as text and as spoken audio.

## Troubleshooting

- **Slow first response**: the first transcription/synthesis after
  startup is slower because models are loading into memory — this is
  normal, subsequent requests are faster.
- **Model download fails / times out**: check you're not behind a
  restrictive proxy/firewall during this one-time step; the models come
  from Hugging Face.
- **Mic button does nothing**: check browser permissions — the site
  needs microphone access granted (browser will prompt on first click).
- **Out of disk space**: model cache lives in `~/.cache/huggingface`;
  safe to delete and re-download if needed.
