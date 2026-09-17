from __future__ import annotations

import re


MIN_JOKE_WORDS = 20
MAX_JOKE_WORDS = 45
MAX_JOKE_SENTENCES = 3

_WORD_PATTERN = re.compile(r"\b\w+(?:[’'-]\w+)*\b", re.UNICODE)
_SENTENCE_END_PATTERN = re.compile(r"[.!?]+(?:[\"'’”»)]*)")


def joke_length_instruction() -> str:
    """Return the shared model-facing length constraint for every condition."""
    return (
        f"Write each joke in {MIN_JOKE_WORDS}-{MAX_JOKE_WORDS} words and at most "
        f"{MAX_JOKE_SENTENCES} sentences. Remove every sentence not needed for the setup, "
        "semantic switch, or punchline. Before returning, silently count the words and "
        "sentences and rewrite any joke that falls outside these limits."
    )


def joke_word_count(text: str) -> int:
    """Count Unicode words using the experiment's deterministic policy."""
    return len(_WORD_PATTERN.findall(text))


def joke_sentence_count(text: str) -> int:
    """Count sentence-ending punctuation groups, treating unpunctuated text as one sentence."""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, len(_SENTENCE_END_PATTERN.findall(stripped)))


def validate_joke_length(text: str, *, label: str = "Joke") -> None:
    """Reject text outside the shared word and sentence limits."""
    words = joke_word_count(text)
    sentences = joke_sentence_count(text)
    if not MIN_JOKE_WORDS <= words <= MAX_JOKE_WORDS:
        raise ValueError(
            f"{label} must contain {MIN_JOKE_WORDS}-{MAX_JOKE_WORDS} words; received {words}."
        )
    if sentences > MAX_JOKE_SENTENCES:
        raise ValueError(
            f"{label} must contain at most {MAX_JOKE_SENTENCES} sentences; received {sentences}."
        )
