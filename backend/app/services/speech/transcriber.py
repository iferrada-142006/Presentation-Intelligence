"""
Speech-to-text using faster-whisper.

Design notes:
- Model is loaded once at worker startup and reused across jobs (avoids 1-2s reload cost).
- Word-level timestamps are always requested — they're needed for WPM per segment,
  pause detection, and timeline event anchoring in later phases.
- Language detection is automatic when language="auto"; we allow forcing "es" or "en".
- We store raw segment data in transcript_segments.words_json so downstream stages
  can reprocess without re-transcribing.
"""

import logging
from faster_whisper import WhisperModel
from app.config import settings

logger = logging.getLogger(__name__)


def load_model() -> WhisperModel:
    """Load and return the faster-whisper model. Call once at worker startup."""
    logger.info(f"Loading faster-whisper model: {settings.whisper_model}")
    model = WhisperModel(
        settings.whisper_model,
        device="cpu",
        compute_type="int8",          # int8 quantization: faster + less RAM on CPU
        download_root=settings.models_dir,
    )
    logger.info("Model loaded.")
    return model


def transcribe(audio_path: str, model: WhisperModel, language: str = "es") -> dict:
    """
    Transcribe audio and return structured result.

    Returns:
        {
            "language": str,
            "language_probability": float,
            "duration_seconds": float,
            "segments": [
                {
                    "start": float,
                    "end": float,
                    "text": str,
                    "words": [{"word": str, "start": float, "end": float, "probability": float}]
                }
            ]
        }
    """
    detect_language = language == "auto"
    transcribe_language = None if detect_language else language

    segments_iter, info = model.transcribe(
        audio_path,
        language=transcribe_language,
        word_timestamps=True,
        vad_filter=True,             # skip silence before transcribing
        vad_parameters={"min_silence_duration_ms": 500},
    )

    logger.info(
        f"Detected language: {info.language} "
        f"(p={info.language_probability:.2f}), "
        f"duration: {info.duration:.1f}s"
    )

    segments = []
    for seg in segments_iter:
        words = []
        if seg.words:
            words = [
                {
                    "word": w.word.strip(),
                    "start": float(round(w.start, 3)),
                    "end": float(round(w.end, 3)),
                    "probability": float(round(w.probability, 3)),
                }
                for w in seg.words
                if w.word.strip()
            ]
        segments.append({
            "start": float(round(seg.start, 3)),
            "end": float(round(seg.end, 3)),
            "text": seg.text.strip(),
            "avg_logprob": float(round(seg.avg_logprob, 3)),
            "words": words,
        })

    return {
        "language": info.language,
        "language_probability": float(round(info.language_probability, 3)),
        "duration_seconds": float(round(info.duration, 2)),
        "segments": segments,
    }
