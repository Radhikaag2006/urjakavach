"""
Whisper STT service — local speech-to-text for the voice assistant.

Loads the faster-whisper model once (module-level singleton) and reuses
it across requests; loading per-request would make every voice turn pay
a multi-second model-load cost. Runs on CPU, int8 quantized, so it works
without a GPU. Auto-detects Hindi vs English per the product requirement
(other languages are not tuned for and may come back inaccurate).

Owner: voice assistant feature.
"""
import io
import re

from faster_whisper import WhisperModel

from .. import config

_model: WhisperModel | None = None

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{2,}")


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            config.WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="int8",
        )
    return _model


def preload_model() -> None:
    """Force-load the model now instead of on the first request.

    Called once at app startup so the first real voice turn doesn't pay
    the multi-second model-load cost on top of transcription latency.
    """
    _get_model()


def _classify_language(text: str, whisper_language: str) -> str:
    """Refine Whisper's coarse hi/en tag using the actual transcript.

    Whisper's language-ID only ever returns a single language, so a
    Hinglish utterance (Hindi and English mixed in one sentence) gets
    collapsed to whichever of the two it leans towards — usually "hi" —
    which then made the reply prompt force pure Devanagari Hindi even
    though the user spoke a mix. Instead, look at the actual script mix
    in the transcribed text: if it contains a meaningful amount of both
    Devanagari and Latin-script words, call it "hinglish" so the chat
    prompt can reply in kind rather than forcing one language.
    """
    devanagari_chars = len(_DEVANAGARI_RE.findall(text))
    latin_words = len(_LATIN_WORD_RE.findall(text))

    if devanagari_chars >= 4 and latin_words >= 1:
        return "hinglish"
    if whisper_language == "hi" and devanagari_chars == 0 and latin_words >= 1:
        # Hindi speech transcribed entirely in Roman script - classic
        # "Hinglish typed in English letters" pattern.
        return "hinglish"
    return whisper_language


def transcribe_audio(audio_bytes: bytes) -> tuple[str, str]:
    """Transcribe raw audio bytes (webm/wav/etc.) to text.

    Returns (text, detected_language) where detected_language is
    "hi", "en", or "hinglish" (derived from the actual script mix in
    the transcript, see _classify_language); other Whisper detections
    are passed through as-is, callers should treat those as
    unsupported.
    Raises RuntimeError on failure so the caller can return a clean
    HTTP error instead of a stack trace.
    """
    if not audio_bytes:
        raise RuntimeError("No audio data received")

    try:
        model = _get_model()
        segments, info = model.transcribe(
            io.BytesIO(audio_bytes),
            language=None,
            task="transcribe",
            vad_filter=True,
        )
        text = "".join(seg.text for seg in segments).strip()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"Transcription failed: {e}") from e

    return text, _classify_language(text, info.language)
