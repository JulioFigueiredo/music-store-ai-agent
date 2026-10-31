"""Text helpers for case-, accent- and punctuation-insensitive matching.

Customers type "violao", "Takamine GD 20" or "gianini", while the data says
"Violões", "Takamine GD20" and "Giannini". These helpers make both sides
comparable.
"""

import re
import unicodedata
from difflib import SequenceMatcher

# Hyphens and apostrophes join the parts of a model code ("GD-20", "'50s"),
# so they are removed. Any other punctuation separates words.
_JOINING_PUNCTUATION = re.compile(r"[-'’]")
_OTHER_PUNCTUATION = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    """Remove accents: "Violão Três" -> "Violao Tres"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def normalize(text: str) -> str:
    """Lowercase, remove accents and punctuation, and collapse spaces.

    Example: "  Violão Takamine GD-20! " -> "violao takamine gd20".
    """
    text = strip_accents(text).lower()
    text = _JOINING_PUNCTUATION.sub("", text)
    text = _OTHER_PUNCTUATION.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def compact(text: str) -> str:
    """Return normalize() without spaces, so "GD 20", "GD-20" and "GD20" match."""
    return normalize(text).replace(" ", "")


def digits_only(text: str) -> str:
    """Keep only digits: "(67) 99812-3456" -> "67998123456"."""
    return re.sub(r"\D", "", text)


def normalize_email(text: str) -> str:
    """Trim and lowercase an email address so comparisons ignore casing."""
    return text.strip().lower()


def contains_phrase(text: str, phrase: str) -> bool:
    """Check for a whole-word phrase, ignoring case, accents and punctuation.

    "kala" is found in "Kala KA-T Tenor", but not in "Kalani KAL-700T".
    """
    return f" {normalize(phrase)} " in f" {normalize(text)} "


def word_similarity(query: str, text: str) -> float:
    """Score from 0 to 1: how well the query's words match the text's words.

    For each query word, take the most similar word in the text (difflib
    ratio), then average. Comparing whole strings would punish short queries
    against long product names; comparing word by word tolerates typos and
    missing words ("gianini gn15" vs. "Giannini GN-15 Nylon Cedr Natural").
    """
    query_words = normalize(query).split()
    text_words = normalize(text).split()
    if not query_words or not text_words:
        return 0.0
    best_scores = [
        max(
            SequenceMatcher(None, query_word, text_word).ratio()
            for text_word in text_words
        )
        for query_word in query_words
    ]
    return sum(best_scores) / len(best_scores)


def rank_by_similarity(
    query: str, candidates: list[str], limit: int, min_score: float
) -> list[str]:
    """Return up to `limit` candidates scoring at least `min_score`, best first."""
    scored = [
        (word_similarity(query, candidate), candidate) for candidate in candidates
    ]
    good_enough = [item for item in scored if item[0] >= min_score]
    good_enough.sort(key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in good_enough[:limit]]
