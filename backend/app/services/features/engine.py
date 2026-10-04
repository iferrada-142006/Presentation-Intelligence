"""
Feature Engine — derives semantic timeline events from stored measurements.

Takes raw frame-level data already in the DB (audio_features, video_features,
transcript_segments) and produces named events with start/end timestamps:

  pause         — sustained silence ≥ 1.5s (audio layer)
  wpm_sprint    — speech rate well above session average (audio layer)
  filler_cluster — ≥ 3 filler words in a 30-second window (speech layer)
  head_away      — head turned significantly off-axis for ≥ 2s (vision layer)
  face_absent    — face not detected for ≥ 5s (vision layer)
  movement_spike — body movement > 2.5σ above session mean (vision layer)

Design constraint: this layer only produces OBSERVATIONS. Descriptions are
factual ("3.2s silence at 0:42"), never interpretive ("nervousness at 0:42").
The LLM is free to interpret; the engine is not.
"""

import json
import logging
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models import AudioFeature, VideoFeature, TranscriptSegment
from app.services.speech.filler_words import FILLERS_ES, FILLERS_EN

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
_MIN_PAUSE_S = 1.5          # silence runs shorter than this are not events
_MIN_SPRINT_S = 4.0         # WPM sprint must last at least this long
_MIN_WPM_THRESHOLD = 165.0  # absolute floor; also uses mean+1.5σ, whichever is higher
_MIN_HEAD_AWAY_S = 2.0      # head-turned-away events need this duration
_MIN_FACE_ABSENT_S = 5.0    # face-not-detected events need this duration
_HEAD_YAW_THRESHOLD = 35.0  # degrees
_HEAD_PITCH_THRESHOLD = 25.0
_MOVEMENT_ZSCORE = 2.5      # body_movement z-score threshold for spike events
_FILLER_CLUSTER_WINDOW = 30.0
_MIN_FILLERS_IN_CLUSTER = 3

# Frame intervals (must match production settings)
_AUDIO_HOP = 0.25
_AUDIO_WINDOW = 0.5
_VIDEO_HOP = 0.5


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tc(seconds: float) -> str:
    """Format seconds as m:ss for display."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def _group(timestamps: list[float], max_gap: float) -> list[tuple[float, float]]:
    """Group a sorted list of timestamps into (start, end) intervals."""
    if not timestamps:
        return []
    ts = sorted(timestamps)
    groups: list[list[float]] = [[ts[0], ts[0]]]
    for t in ts[1:]:
        if t - groups[-1][1] <= max_gap:
            groups[-1][1] = t
        else:
            groups.append([t, t])
    return [(g[0], g[1]) for g in groups]


def _evt(
    layer: str,
    event_type: str,
    start: float,
    end: float,
    magnitude: float,
    description: str,
) -> dict:
    return {
        "layer": layer,
        "event_type": event_type,
        "start_seconds": round(start, 2),
        "end_seconds": round(end, 2),
        "duration_seconds": round(end - start, 2),
        "magnitude": round(float(magnitude), 3),
        "description": description,
    }


# ── Detectors ─────────────────────────────────────────────────────────────────

def _pauses(rows: list[AudioFeature]) -> list[dict]:
    silence_ts = [r.timestamp_seconds for r in rows if r.is_silence]
    groups = _group(silence_ts, max_gap=_AUDIO_HOP + 0.05)
    events = []
    for start_t, end_t in groups:
        start = max(0.0, start_t - _AUDIO_HOP)
        end = end_t + _AUDIO_HOP
        dur = end - start
        if dur >= _MIN_PAUSE_S:
            events.append(_evt(
                "audio", "pause", start, end, dur,
                f"Silencio de {dur:.1f}s en {_tc(start)}",
            ))
    return events


def _wpm_sprints(rows: list[AudioFeature]) -> list[dict]:
    wpm_data = [(r.timestamp_seconds, r.local_wpm)
                for r in rows if r.local_wpm is not None and r.local_wpm > 0]
    if not wpm_data:
        return []
    vals = [v for _, v in wpm_data]
    mean_wpm = float(np.mean(vals))
    std_wpm = float(np.std(vals))
    threshold = max(_MIN_WPM_THRESHOLD, mean_wpm + 1.5 * std_wpm)

    sprint_ts = [t for t, v in wpm_data if v >= threshold]
    groups = _group(sprint_ts, max_gap=1.0)
    events = []
    for start_t, end_t in groups:
        dur = end_t - start_t + _AUDIO_HOP
        if dur >= _MIN_SPRINT_S:
            sprint_vals = [v for t, v in wpm_data if start_t <= t <= end_t]
            peak = round(float(np.max(sprint_vals)), 0)
            events.append(_evt(
                "audio", "wpm_sprint", start_t, end_t + _AUDIO_HOP, peak,
                f"{peak:.0f} PPM (ref: {mean_wpm:.0f} PPM promedio) por {dur:.1f}s en {_tc(start_t)}",
            ))
    return events


def _filler_clusters(segments: list[TranscriptSegment], language: str = "es") -> list[dict]:
    filler_set = FILLERS_ES if language == "es" else FILLERS_EN

    # Collect filler timestamps from words_json
    filler_ts: list[float] = []
    for seg in segments:
        if not seg.words_json:
            continue
        words = seg.words_json if isinstance(seg.words_json, list) else json.loads(seg.words_json)
        prev_word: Optional[str] = None
        for w in words:
            word = w.get("word", "").strip().lower().rstrip(".,!?")
            bigram = f"{prev_word} {word}" if prev_word else ""
            if bigram.strip() in filler_set or word in filler_set:
                t = float(w.get("start", seg.start_seconds))
                filler_ts.append(t)
            prev_word = word

    if not filler_ts:
        return []

    # Sliding window: count fillers in each 30s window
    filler_ts.sort()
    events = []
    i = 0
    reported: set[int] = set()
    while i < len(filler_ts):
        window_start = filler_ts[i]
        window_end = window_start + _FILLER_CLUSTER_WINDOW
        indices_in_window = [j for j in range(i, len(filler_ts)) if filler_ts[j] <= window_end]
        count = len(indices_in_window)
        if count >= _MIN_FILLERS_IN_CLUSTER:
            key = round(window_start)
            if key not in reported:
                reported.add(key)
                events.append(_evt(
                    "speech", "filler_cluster",
                    window_start, filler_ts[indices_in_window[-1]], float(count),
                    f"{count} muletillas en {_FILLER_CLUSTER_WINDOW:.0f}s desde {_tc(window_start)}",
                ))
            # Advance past this cluster
            i = indices_in_window[-1] + 1
        else:
            i += 1

    return events


def _head_away(rows: list[VideoFeature]) -> list[dict]:
    """Frames where head is significantly off-axis (face detected but turned away)."""
    away_ts = [
        r.timestamp_seconds for r in rows
        if r.face_detected
        and r.head_yaw is not None
        and r.head_pitch is not None
        and (abs(r.head_yaw) > _HEAD_YAW_THRESHOLD or abs(r.head_pitch) > _HEAD_PITCH_THRESHOLD)
    ]
    groups = _group(away_ts, max_gap=_VIDEO_HOP + 0.1)
    events = []
    for start_t, end_t in groups:
        dur = end_t - start_t + _VIDEO_HOP
        if dur >= _MIN_HEAD_AWAY_S:
            # Compute representative yaw for this interval
            yaws = [
                abs(r.head_yaw) for r in rows
                if r.face_detected and r.head_yaw is not None
                and start_t <= r.timestamp_seconds <= end_t
            ]
            max_yaw = max(yaws) if yaws else 0.0
            events.append(_evt(
                "vision", "head_away",
                start_t, end_t + _VIDEO_HOP, max_yaw,
                f"Cabeza girada {max_yaw:.0f}° durante {dur:.1f}s en {_tc(start_t)}",
            ))
    return events


def _face_absence(rows: list[VideoFeature]) -> list[dict]:
    absent_ts = [r.timestamp_seconds for r in rows if not r.face_detected]
    groups = _group(absent_ts, max_gap=_VIDEO_HOP + 0.1)
    events = []
    for start_t, end_t in groups:
        dur = end_t - start_t + _VIDEO_HOP
        if dur >= _MIN_FACE_ABSENT_S:
            events.append(_evt(
                "vision", "face_absent",
                start_t, end_t + _VIDEO_HOP, dur,
                f"Cara no detectada durante {dur:.1f}s en {_tc(start_t)}",
            ))
    return events


def _movement_spikes(rows: list[VideoFeature]) -> list[dict]:
    movement_data = [
        (r.timestamp_seconds, r.body_movement)
        for r in rows if r.body_movement is not None
    ]
    if len(movement_data) < 5:
        return []
    vals = [v for _, v in movement_data]
    mean_m = float(np.mean(vals))
    std_m = float(np.std(vals))
    if std_m < 1e-6:
        return []

    spike_ts = [t for t, v in movement_data if (v - mean_m) / std_m > _MOVEMENT_ZSCORE]
    groups = _group(spike_ts, max_gap=_VIDEO_HOP + 0.1)
    events = []
    for start_t, end_t in groups:
        spike_vals = [v for t, v in movement_data if start_t <= t <= end_t]
        peak = max(spike_vals)
        zscore = (peak - mean_m) / std_m
        events.append(_evt(
            "vision", "movement_spike",
            start_t, end_t + _VIDEO_HOP, zscore,
            f"Movimiento corporal elevado ({zscore:.1f}σ) en {_tc(start_t)}",
        ))
    return events


# ── Public API ────────────────────────────────────────────────────────────────

def run(presentation_id: int, db: Session, language: str = "es") -> list[dict]:
    """
    Derive all timeline events for a presentation from stored features.
    Returns sorted list of event dicts ready for bulk insert.
    """
    audio_rows = (
        db.query(AudioFeature)
        .filter(AudioFeature.presentation_id == presentation_id)
        .order_by(AudioFeature.timestamp_seconds)
        .all()
    )
    video_rows = (
        db.query(VideoFeature)
        .filter(VideoFeature.presentation_id == presentation_id)
        .order_by(VideoFeature.timestamp_seconds)
        .all()
    )
    segments = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.presentation_id == presentation_id)
        .order_by(TranscriptSegment.start_seconds)
        .all()
    )

    events: list[dict] = []
    events.extend(_pauses(audio_rows))
    events.extend(_wpm_sprints(audio_rows))
    events.extend(_filler_clusters(segments, language))
    events.extend(_head_away(video_rows))
    events.extend(_face_absence(video_rows))
    events.extend(_movement_spikes(video_rows))

    events.sort(key=lambda e: e["start_seconds"])
    logger.info(
        f"Feature engine: {len(events)} events "
        f"({sum(1 for e in events if e['layer']=='audio')} audio, "
        f"{sum(1 for e in events if e['layer']=='speech')} speech, "
        f"{sum(1 for e in events if e['layer']=='vision')} vision)"
    )
    return events
