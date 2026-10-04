"""
Filler word and self-correction detection from transcript.

Methodology note:
- We detect fillers from the transcribed text, not from audio directly.
- Accuracy depends on Whisper transcribing them correctly (not always guaranteed).
- Results are labeled with confidence=0.7 to reflect this limitation.
- We report COUNT and TIMESTAMPS, never infer meaning ("nervousness", "lack of knowledge").
- Lists are approximate and should be expanded with domain-specific review.
- Self-corrections ("perdón", "me equivoqué") are a separate category from fillers:
  they indicate the speaker noticed and repaired an error, which is a different
  communicative act.
"""

from typing import NamedTuple

FILLERS_ES = {
    "eh", "ehh", "ehhh", "este", "mm", "mmm", "mmmm",
    "ah", "ahh", "o sea", "o sea que", "bueno", "pues",
    "entonces", "este...", "este,", "verdad", "digamos",
    "básicamente", "literalmente", "de hecho", "o algo así",
    "tipo", "o sea tipo",
}

FILLERS_EN = {
    "um", "umm", "uh", "uhh", "like", "you know",
    "basically", "literally", "actually", "right",
    "so", "kind of", "sort of", "i mean", "well",
}

# Self-corrections: speaker notices an error and repairs it.
# Detected separately from fillers — different communicative function.
SELF_CORRECTIONS_ES = {
    "perdón", "disculpa", "disculpen", "corrijo",
    "me equivoqué", "quiero decir", "o mejor dicho",
    "es decir", "no no", "digo", "mejor dicho",
    "quise decir",
}

SELF_CORRECTIONS_EN = {
    "sorry", "i mean", "let me rephrase", "correction",
    "i meant", "rather", "no no",
}


class FillerOccurrence(NamedTuple):
    word: str
    start_seconds: float
    end_seconds: float


class SelfCorrectionOccurrence(NamedTuple):
    phrase: str
    start_seconds: float
    end_seconds: float


def _scan_words(all_words: list[dict], target_set: set[str]) -> list[tuple]:
    """Scan word list for single-word and bigram matches against target_set."""
    results = []
    i = 0
    while i < len(all_words):
        word = all_words[i]["word"].lower().strip(".,!?¿¡\"'")

        if i + 1 < len(all_words):
            next_word = all_words[i + 1]["word"].lower().strip(".,!?¿¡\"'")
            bigram = f"{word} {next_word}"
            if bigram in target_set:
                results.append((bigram, all_words[i]["start"], all_words[i + 1]["end"]))
                i += 2
                continue

        if word in target_set:
            results.append((word, all_words[i]["start"], all_words[i]["end"]))
        i += 1
    return results


def _flatten_words(segments: list[dict]) -> list[dict]:
    words = []
    for seg in segments:
        for w in seg.get("words", []):
            words.append(w)
    return words


def detect_fillers(segments: list[dict], language: str = "es") -> list[FillerOccurrence]:
    filler_set = FILLERS_ES if language == "es" else FILLERS_EN
    all_words = _flatten_words(segments)
    return [
        FillerOccurrence(word=w, start_seconds=s, end_seconds=e)
        for w, s, e in _scan_words(all_words, filler_set)
    ]


def detect_self_corrections(segments: list[dict], language: str = "es") -> list[SelfCorrectionOccurrence]:
    sc_set = SELF_CORRECTIONS_ES if language == "es" else SELF_CORRECTIONS_EN
    all_words = _flatten_words(segments)
    return [
        SelfCorrectionOccurrence(phrase=w, start_seconds=s, end_seconds=e)
        for w, s, e in _scan_words(all_words, sc_set)
    ]


def compute_filler_metrics(
    occurrences: list[FillerOccurrence],
    total_words: int,
    duration_seconds: float,
) -> dict:
    count = len(occurrences)
    rate_per_minute = round((count / duration_seconds) * 60, 2) if duration_seconds > 0 else 0.0
    ratio = round(count / total_words, 4) if total_words > 0 else 0.0

    by_word: dict[str, int] = {}
    for occ in occurrences:
        by_word[occ.word] = by_word.get(occ.word, 0) + 1

    return {
        "filler_count": count,
        "filler_rate_per_minute": rate_per_minute,
        "filler_ratio": ratio,
        "filler_by_word": by_word,
    }
