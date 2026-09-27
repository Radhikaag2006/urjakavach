"""
MMS-TTS service — local text-to-speech for the voice assistant's spoken
replies.

Loads both the English and Hindi MMS-TTS models once (module-level
singletons) so repeated /api/synthesize calls don't pay model-load cost.
Writes each synthesized reply to a uniquely-named temp WAV file; the
caller (the API route) is responsible for deleting it after serving.

Owner: voice assistant feature.
"""
import os
import uuid

import scipy.io.wavfile

from .. import config

_MODEL_IDS = {
    "en": "facebook/mms-tts-eng",
    "hi": "facebook/mms-tts-hin",
}

_models: dict[str, object] = {}
_tokenizers: dict[str, object] = {}


def _get_model(language: str):
    if language not in _MODEL_IDS:
        raise RuntimeError(f"Unsupported TTS language: {language!r}")

    if language not in _models:
        from transformers import VitsModel, AutoTokenizer

        model_id = _MODEL_IDS[language]
        _tokenizers[language] = AutoTokenizer.from_pretrained(model_id)
        _models[language] = VitsModel.from_pretrained(model_id)

    return _models[language], _tokenizers[language]


def preload_models() -> None:
    """Force-load both TTS models now instead of on the first request.

    Called once at app startup so the first spoken reply of a session
    doesn't pay the multi-second model-load cost on top of synthesis.
    """
    for lang in _MODEL_IDS:
        _get_model(lang)


def synthesize_speech(text: str, language: str) -> str:
    """Synthesize `text` in `language` ("en" or "hi") to a temp WAV file.

    Returns the absolute path to the written file. Raises RuntimeError
    on failure.
    """
    import torch

    if not text.strip():
        raise RuntimeError("No text provided for synthesis")

    try:
        model, tokenizer = _get_model(language)
        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            output = model(**inputs).waveform
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Speech synthesis failed: {e}") from e

    os.makedirs(config.TTS_TMP_DIR, exist_ok=True)
    out_path = os.path.join(config.TTS_TMP_DIR, f"tts_{uuid.uuid4().hex}.wav")
    waveform = output.squeeze().cpu().numpy()
    scipy.io.wavfile.write(out_path, rate=model.config.sampling_rate, data=waveform)
    return out_path
