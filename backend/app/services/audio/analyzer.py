"""
Audio analysis using librosa.

What we measure (observable):
  - RMS energy per frame → volume over time
  - Silence detection → frames below dynamic threshold
  - Pause extraction → consecutive silent frames ≥ min_pause_duration
  - Local WPM per window → derived from word timestamps in transcript

What we deliberately do NOT infer:
  - Emotions from energy/pitch
  - "Confidence" or "nervousness" from vocal features
  - Quality judgements from any single metric

Pitch (F0) is intentionally excluded from Phase 3.
It can be measured with librosa.pyin but interpreting it as
expressiveness or engagement is not methodologically defensible here.
It will be added in a later phase with explicit caveats.
"""

import logging
import numpy as np
import librosa
from dataclasses import dataclass, field
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Analysis parameters
WINDOW_SECONDS = 0.5       # RMS frame size
HOP_SECONDS = 0.25         # Frame hop (50% overlap for smooth curve)
MIN_PAUSE_SECONDS = 0.5    # Minimum silence duration to count as a pause
# Silence threshold: frames below (mean RMS * this factor) are silent
SILENCE_FACTOR = 0.15


class Pause(NamedTuple):
    start_seconds: float
    end_seconds: float
    duration_seconds: float


@dataclass
class AudioAnalysisResult:
    # Per-frame series (aligned to audio timeline)
    frame_times: list[float] = field(default_factory=list)
    frame_rms: list[float] = field(default_factory=list)
    frame_is_silence: list[int] = field(default_factory=list)
    frame_local_wpm: list[float] = field(default_factory=list)

    # Derived pause events
    pauses: list[Pause] = field(default_factory=list)

    # Aggregate metrics
    silence_threshold: float = 0.0
    total_duration_seconds: float = 0.0
    speech_duration_seconds: float = 0.0
    silence_duration_seconds: float = 0.0


def analyze(audio_path: str, transcript_segments: list[dict]) -> AudioAnalysisResult:
    """
    Run full audio analysis on a WAV file.

    Args:
        audio_path: Path to 16kHz mono WAV (as extracted by ffmpeg stage).
        transcript_segments: List of segment dicts with 'words' containing
                             word-level timestamps from the speech stage.
    """
    logger.info(f"Loading audio: {audio_path}")
    y, sr = librosa.load(audio_path, sr=16000, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    logger.info(f"Audio loaded: {duration:.1f}s @ {sr}Hz")

    # ── RMS energy per frame ────────────────────────────────────────────────
    hop_length = int(HOP_SECONDS * sr)
    frame_length = int(WINDOW_SECONDS * sr)

    rms = librosa.feature.rms(
        y=y,
        frame_length=frame_length,
        hop_length=hop_length,
    )[0]  # shape: (n_frames,)

    frame_times = librosa.frames_to_time(
        np.arange(len(rms)), sr=sr, hop_length=hop_length
    )

    # ── Dynamic silence threshold ────────────────────────────────────────────
    # Use a percentile-based threshold: frames in the lower X% of energy
    # are considered silence. More robust than a fixed value across videos.
    voiced_rms = rms[rms > 0]
    if len(voiced_rms) == 0:
        silence_threshold = 0.001
    else:
        # 15th percentile of voiced energy as threshold
        silence_threshold = float(np.percentile(voiced_rms, 15) * SILENCE_FACTOR + np.percentile(voiced_rms, 15) * 0.1)
        # Simpler: mean * factor
        silence_threshold = float(np.mean(voiced_rms) * SILENCE_FACTOR)

    logger.info(f"Silence threshold (dynamic): {silence_threshold:.5f}")

    frame_is_silence = (rms < silence_threshold).astype(int).tolist()

    # ── Local WPM per frame ─────────────────────────────────────────────────
    # Flatten all word timestamps from transcript
    all_words = []
    for seg in transcript_segments:
        for w in (seg.get("words") or []):
            if isinstance(w, dict):
                all_words.append(w)

    frame_local_wpm = _compute_local_wpm(
        frame_times=frame_times.tolist(),
        window_seconds=WINDOW_SECONDS * 4,  # wider window for WPM (2s)
        all_words=all_words,
    )

    # ── Pause detection ─────────────────────────────────────────────────────
    pauses = _detect_pauses(
        frame_times=frame_times.tolist(),
        frame_is_silence=frame_is_silence,
        hop_seconds=HOP_SECONDS,
        min_pause_seconds=MIN_PAUSE_SECONDS,
    )
    logger.info(f"Detected {len(pauses)} pauses ≥ {MIN_PAUSE_SECONDS}s")

    # ── Aggregate durations ─────────────────────────────────────────────────
    silence_frames = sum(frame_is_silence)
    silence_duration = silence_frames * HOP_SECONDS
    speech_duration = max(0.0, duration - silence_duration)

    result = AudioAnalysisResult(
        frame_times=[float(t) for t in frame_times.tolist()],
        frame_rms=[float(v) for v in rms.tolist()],
        frame_is_silence=frame_is_silence,
        frame_local_wpm=frame_local_wpm,
        pauses=pauses,
        silence_threshold=silence_threshold,
        total_duration_seconds=float(duration),
        speech_duration_seconds=float(speech_duration),
        silence_duration_seconds=float(silence_duration),
    )
    return result


def _compute_local_wpm(
    frame_times: list[float],
    window_seconds: float,
    all_words: list[dict],
) -> list[float]:
    """Count words within a sliding window centered on each frame."""
    local_wpm = []
    half = window_seconds / 2
    for t in frame_times:
        t_start = max(0.0, t - half)
        t_end = t + half
        count = sum(
            1 for w in all_words
            if w.get("start", 0) >= t_start and w.get("end", 0) <= t_end
        )
        # Convert count in window to words/minute
        wpm = round((count / window_seconds) * 60, 1) if window_seconds > 0 else 0.0
        local_wpm.append(wpm)
    return local_wpm


def _detect_pauses(
    frame_times: list[float],
    frame_is_silence: list[int],
    hop_seconds: float,
    min_pause_seconds: float,
) -> list[Pause]:
    """
    Extract pauses as contiguous silence runs ≥ min_pause_seconds.

    A 'pause' here is a period where the RMS energy is below the dynamic
    silence threshold. This includes breathing, intentional dramatic pauses,
    and hesitation gaps. The caller is responsible for contextual interpretation.
    """
    pauses = []
    in_pause = False
    pause_start = 0.0

    for i, (t, is_sil) in enumerate(zip(frame_times, frame_is_silence)):
        if is_sil and not in_pause:
            in_pause = True
            pause_start = t
        elif not is_sil and in_pause:
            in_pause = False
            duration = t - pause_start
            if duration >= min_pause_seconds:
                pauses.append(Pause(
                    start_seconds=round(pause_start, 3),
                    end_seconds=round(t, 3),
                    duration_seconds=round(duration, 3),
                ))

    # Close an open pause at end of audio
    if in_pause and frame_times:
        duration = frame_times[-1] - pause_start
        if duration >= min_pause_seconds:
            pauses.append(Pause(
                start_seconds=round(pause_start, 3),
                end_seconds=round(frame_times[-1], 3),
                duration_seconds=round(duration, 3),
            ))

    return pauses


def compute_audio_metrics(result: AudioAnalysisResult) -> list[tuple]:
    """
    Derive aggregate metrics from AudioAnalysisResult.
    Returns list of (metric_name, value, unit, confidence).
    """
    rms = result.frame_rms
    pauses = result.pauses
    duration = result.total_duration_seconds

    # Energy statistics
    voiced_rms = [v for v, s in zip(rms, result.frame_is_silence) if s == 0 and v > 0]
    energy_mean = float(np.mean(voiced_rms)) if voiced_rms else 0.0
    energy_std = float(np.std(voiced_rms)) if voiced_rms else 0.0
    # Coefficient of variation: normalized measure of energy variability
    energy_cv = round(energy_std / energy_mean, 4) if energy_mean > 0 else 0.0

    # Pause statistics
    pause_count = len(pauses)
    pause_durations = [p.duration_seconds for p in pauses]
    avg_pause_duration = round(float(np.mean(pause_durations)), 3) if pause_durations else 0.0
    max_pause_duration = round(float(np.max(pause_durations)), 3) if pause_durations else 0.0
    pause_rate_per_min = round((pause_count / duration) * 60, 2) if duration > 0 else 0.0

    # Silence ratio
    silence_ratio = round(result.silence_duration_seconds / duration, 4) if duration > 0 else 0.0

    # Local WPM variability (speech rate stability)
    voiced_wpm = [w for w, s in zip(result.frame_local_wpm, result.frame_is_silence) if s == 0 and w > 0]
    wpm_std = round(float(np.std(voiced_wpm)), 2) if voiced_wpm else 0.0

    return [
        ("pause_count",         pause_count,          "count",    0.85),
        ("avg_pause_duration",  avg_pause_duration,   "seconds",  0.85),
        ("max_pause_duration",  max_pause_duration,   "seconds",  0.85),
        ("pause_rate_per_min",  pause_rate_per_min,   "count/min",0.85),
        ("silence_ratio",       silence_ratio,        "ratio",    0.90),
        ("energy_cv",           energy_cv,            "ratio",    0.80),
        ("wpm_std",             wpm_std,              "wpm",      0.75),
    ]
