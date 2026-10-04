"""
Filler word detection from transcript.

Methodology note:
- We detect fillers from the transcribed text, not from audio directly.
- Accuracy depends on Whisper transcribing them correctly (not always guaranteed).
- Results are labeled with confidence=0.7 to reflect this limitation.
- We report COUNT and TIMESTAMPS, never infer meaning ("nervousness", "lack of knowledge").
- Lists are approximate and should be expanded with domain-specific review.
"""

import re
from typing import NamedTuple

FILLERS_ES = {
    "eh", "ehh", "ehhh", "este", "mm", "mmm", "mmmm",
    "ah", "ahh", "o sea", "o sea que", "bueno", "pues",
    "entonces", "o", "este...", "este,", "verdad", "no?",
    "no es así", "digamos", "básicamente", "literalmente",
    "de hecho", "o algo así", "tipo", "o sea tipo",
}

FILLERS_EN = {
    "um", "umm", "uh", "uhh", "like", "you know",
    "basically", "literally", "actually", "right",
    "so", "kind of", "sort of", "i mean", "well",
}


class FillerOccurrence(NamedTuple):
    word: str
    start_seconds: float
    end_seconds: float


def detect_fillers(segments: list[dict], language: str = "es") -> list[FillerOccurrence]:
    """
    Scan word-level timestamps for filler words.

    Returns a list of FillerOccurrence with position in the audio.
    Limitation: multi-word fillers (e.g. 'o sea') require adjacent word matching,
    which is implemented as a simple bigram scan.
    """
    filler_set = FILLERS_ES if language == "es" else FILLERS_EN

    # Flatten all words from all segments
    all_words = []
    for seg in segments:
        for w in seg.get("words", []):
            all_words.append(w)

    occurrences = []
    i = 0
    while i < len(all_words):
        word = all_words[i]["word"].lower().strip(".,!?¿¡")

        # Check bigram first (e.g. "o sea", "you know")
        if i + 1 < len(all_words):
            next_word = all_words[i + 1]["word"].lower().strip(".,!?¿¡")
            bigram = f"{word} {next_word}"
            if bigram in filler_set:
                occurrences.append(FillerOccurrence(
                    word=bigram,
                    start_seconds=all_words[i]["start"],
                    end_seconds=all_words[i + 1]["end"],
                ))
                i += 2
                continue

        # Single word filler
        if word in filler_set:
            occurrences.append(FillerOccurrence(
                word=word,
                start_seconds=all_words[i]["start"],
                end_seconds=all_words[i]["end"],
            ))
        i += 1

    return occurrences


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
