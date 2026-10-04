"""
Rubric Engine — scores presentations across 5 formal dimensions.

Each dimension has:
  - A transparent scoring formula (piecewise linear from documented anchors)
  - A primary metric that drives the score
  - Evidence text citing the actual measured value
  - A level label (0–4) with fixed anchors

Design rules:
  - Scores are deterministic: same metrics → same score, always
  - Reference ranges are documented and justified below each dimension
  - No psychological inference: "score 45 on verbal rhythm" not "monotone delivery"
  - If data is insufficient to score a dimension, it is skipped (not scored 0)

Dimensions:
  verbal_rhythm      — speech rate vs. 120–150 PPM reference range
  filler_density     — filler word rate per minute
  silence_management — proportion of silence and pause characteristics
  vocal_dynamics     — volume variability (energy coefficient of variation)
  visual_presence    — head orientation toward camera (Phase 5+ only)
"""

from dataclasses import dataclass
from typing import Optional

RUBRIC_VERSION = "v1.0"

LEVEL_LABELS = {
    0: "Insuficiente",
    1: "En desarrollo",
    2: "Adecuado",
    3: "Competente",
    4: "Ejemplar",
}

DIMENSION_META = {
    "verbal_rhythm": {
        "label": "Ritmo Verbal",
        "description": "Velocidad media del habla respecto al rango de referencia 120–150 PPM.",
    },
    "filler_density": {
        "label": "Densidad de Muletillas",
        "description": "Frecuencia de palabras de relleno por minuto.",
    },
    "silence_management": {
        "label": "Gestión del Silencio",
        "description": "Proporción de tiempo en silencio y duración media de pausas.",
    },
    "vocal_dynamics": {
        "label": "Dinámica Vocal",
        "description": "Variabilidad de volumen medida como CV de energía RMS.",
    },
    "visual_presence": {
        "label": "Presencia Visual",
        "description": "Proporción de tiempo con cabeza orientada hacia la cámara (|yaw|<20° y |pitch|<20°).",
    },
}


@dataclass
class DimensionResult:
    dimension: str
    score: float           # 0–100
    level: int             # 0–4
    level_label: str
    primary_metric: str
    primary_value: float
    evidence: str
    rubric_version: str = RUBRIC_VERSION


# ── Scoring primitives ────────────────────────────────────────────────────────

def _level(score: float) -> int:
    if score >= 86: return 4
    if score >= 71: return 3
    if score >= 51: return 2
    if score >= 26: return 1
    return 0


def _piecewise(value: float, points: list[tuple[float, float]]) -> float:
    """Piecewise linear interpolation. Points must be sorted by x."""
    if value <= points[0][0]:
        return float(points[0][1])
    if value >= points[-1][0]:
        return float(points[-1][1])
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= value <= x1:
            t = (value - x0) / (x1 - x0) if x1 != x0 else 0.0
            return round(y0 + t * (y1 - y0), 1)
    return float(points[-1][1])


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


# ── Dimension scorers ─────────────────────────────────────────────────────────

def _verbal_rhythm(metrics: dict, events: list[dict]) -> Optional[DimensionResult]:
    """
    Reference: 120–150 PPM is widely cited for professional presentations.
    Optimal center: 130–145 PPM (clear articulation + information density balance).
    WPM std penalty: high variability (>50 PPM std) suggests poor rhythm control.
    Sprint event penalty: each sprint = pacing loss.
    """
    wpm = metrics.get("avg_wpm")
    if wpm is None:
        return None

    # Tent function: score peaks at 130–145, falls on both sides
    if wpm <= 145:
        base = _piecewise(wpm, [
            (0, 5), (70, 20), (95, 45), (110, 65), (120, 80), (130, 93), (145, 100),
        ])
    else:
        base = _piecewise(wpm, [
            (145, 100), (155, 92), (170, 78), (190, 58), (215, 35), (250, 15),
        ])

    # Adjustments
    std = metrics.get("wpm_std") or 0.0
    std_adj = 0.0
    if std < 15:
        std_adj = +3   # very stable rhythm
    elif std > 50:
        std_adj = -8
    elif std > 35:
        std_adj = -4

    sprint_count = sum(1 for e in events if e.get("event_type") == "wpm_sprint")
    sprint_adj = _clamp(-sprint_count * 3, -12, 0)

    score = _clamp(base + std_adj + sprint_adj)
    lv = _level(score)

    evidence = (
        f"{wpm:.0f} PPM (referencia: 120–150 PPM)"
        + (f" · variabilidad: {std:.0f} PPM σ" if std else "")
        + (f" · {sprint_count} sprint{'s' if sprint_count != 1 else ''} detectado{'s' if sprint_count != 1 else ''}" if sprint_count else "")
    )

    return DimensionResult("verbal_rhythm", score, lv, LEVEL_LABELS[lv], "avg_wpm", float(wpm), evidence)


def _filler_density(metrics: dict, events: list[dict]) -> Optional[DimensionResult]:
    """
    Reference: < 2/min is unnoticeable; > 6/min becomes disruptive.
    The confidence of filler detection is 0.7 (Whisper normalizes speech).
    Score is conservative: we penalize less than measurement alone would suggest.
    """
    rate = metrics.get("filler_rate_per_min")
    if rate is None:
        return None

    base = _piecewise(rate, [
        (0, 98), (1, 92), (2, 82), (3.5, 70), (5, 55), (7, 38), (10, 22), (15, 10),
    ])

    cluster_count = sum(1 for e in events if e.get("event_type") == "filler_cluster")
    cluster_adj = _clamp(-cluster_count * 4, -12, 0)

    score = _clamp(base + cluster_adj)
    lv = _level(score)

    total = metrics.get("filler_count") or 0
    evidence = (
        f"{rate:.1f} muletillas/min ({total:.0f} totales)"
        + (f" · {cluster_count} cluster{'s' if cluster_count != 1 else ''}" if cluster_count else "")
        + " [confianza de detección: 0.7]"
    )

    return DimensionResult("filler_density", score, lv, LEVEL_LABELS[lv], "filler_rate_per_min", float(rate), evidence)


def _silence_management(metrics: dict, events: list[dict]) -> Optional[DimensionResult]:
    """
    Reference: 5–20% silence is normal and allows listeners to process.
    < 3%: no pauses at all (rushed delivery, no breathing room).
    > 30%: excessive hesitation or very long pauses.
    Average pause duration: 1–2s is natural; > 4s average is disruptive.
    """
    silence_ratio = metrics.get("silence_ratio")
    if silence_ratio is None:
        return None

    pct = silence_ratio * 100

    # U-shaped: both too little and too much are penalized
    # Optimal: 8–18%
    if pct <= 18:
        base = _piecewise(pct, [
            (0, 45), (3, 60), (6, 78), (10, 92), (14, 97), (18, 100),
        ])
    else:
        base = _piecewise(pct, [
            (18, 100), (22, 90), (28, 72), (35, 50), (45, 30), (60, 15),
        ])

    # Avg pause duration adjustment
    avg_pause = metrics.get("avg_pause_duration") or 0.0
    pause_adj = 0.0
    if avg_pause > 4.0:
        pause_adj = -10
    elif avg_pause > 3.0:
        pause_adj = -5
    elif 1.0 <= avg_pause <= 2.5:
        pause_adj = +3  # natural pause rhythm

    score = _clamp(base + pause_adj)
    lv = _level(score)

    pause_count = metrics.get("pause_count") or 0
    evidence = (
        f"{pct:.1f}% de silencio (referencia: 5–20%)"
        + (f" · pausa media: {avg_pause:.1f}s" if avg_pause else "")
        + (f" · {pause_count:.0f} pausa{'s' if pause_count != 1 else ''} ≥ 0.5s" if pause_count else "")
    )

    return DimensionResult("silence_management", score, lv, LEVEL_LABELS[lv], "silence_ratio", float(silence_ratio), evidence)


def _vocal_dynamics(metrics: dict) -> Optional[DimensionResult]:
    """
    Reference: CV of RMS energy measures how much the volume varies.
    < 15%: very flat, monotone delivery.
    15–30%: moderate variation, adequate.
    30–50%: dynamic, engaging delivery.
    > 60%: potentially erratic or inconsistent.

    Note: CV is relative to the speaker's own volume, not an absolute level.
    """
    cv = metrics.get("energy_cv")
    if cv is None:
        return None

    cv_pct = cv * 100

    if cv_pct <= 40:
        base = _piecewise(cv_pct, [
            (0, 20), (8, 35), (15, 58), (22, 75), (30, 90), (36, 97), (40, 100),
        ])
    else:
        base = _piecewise(cv_pct, [
            (40, 100), (50, 88), (62, 70), (75, 52), (90, 35), (110, 20),
        ])

    score = _clamp(base)
    lv = _level(score)
    evidence = f"CV de energía: {cv_pct:.1f}% (referencia: 20–50% = dinámica adecuada)"

    return DimensionResult("vocal_dynamics", score, lv, LEVEL_LABELS[lv], "energy_cv", float(cv), evidence)


def _visual_presence(metrics: dict, events: list[dict]) -> Optional[DimensionResult]:
    """
    Reference: head_forward_ratio = fraction of detected-face frames where
    |yaw| < 20° AND |pitch| < 20°. Higher = more time facing the camera.

    Note: this measures head orientation, not gaze or attention.
    Confidence: 0.75 (PnP estimation from 2D landmarks).
    """
    forward = metrics.get("head_forward_ratio")
    face_ratio = metrics.get("face_visible_ratio")

    if forward is None or face_ratio is None:
        return None  # Vision data not available for this job
    if face_ratio < 0.3:
        return None  # Face rarely detected — not enough data to score reliably

    fwd_pct = forward * 100

    base = _piecewise(fwd_pct, [
        (0, 15), (30, 30), (50, 50), (65, 68), (75, 82), (85, 93), (95, 100),
    ])

    head_away_count = sum(1 for e in events if e.get("event_type") == "head_away")
    away_adj = _clamp(-head_away_count * 4, -16, 0)

    score = _clamp(base + away_adj)
    lv = _level(score)

    evidence = (
        f"{fwd_pct:.0f}% del tiempo con cabeza orientada hacia la cámara"
        + f" · cara visible en {face_ratio * 100:.0f}% de frames"
        + (f" · {head_away_count} evento{'s' if head_away_count != 1 else ''} de cabeza girada" if head_away_count else "")
        + " [confianza: 0.75]"
    )

    return DimensionResult("visual_presence", score, lv, LEVEL_LABELS[lv], "head_forward_ratio", float(forward), evidence)


# ── Public API ────────────────────────────────────────────────────────────────

def run(metrics: dict, events: list[dict]) -> list[dict]:
    """
    Score all applicable dimensions for a presentation.
    Returns list of dicts ready for bulk insert into rubric_scores.
    Dimensions with insufficient data are silently skipped.
    """
    scorers = [
        _verbal_rhythm(metrics, events),
        _filler_density(metrics, events),
        _silence_management(metrics, events),
        _vocal_dynamics(metrics),
        _visual_presence(metrics, events),
    ]

    results = []
    for r in scorers:
        if r is None:
            continue
        results.append({
            "dimension": r.dimension,
            "score": round(r.score, 1),
            "level": r.level,
            "level_label": r.level_label,
            "primary_metric": r.primary_metric,
            "primary_value": round(r.primary_value, 4),
            "evidence": r.evidence,
            "rubric_version": r.rubric_version,
        })

    return results
