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

# Plural endings that do not simply add "s": "violões" -> "violão",
# "metais" -> "metal". Checked in order, before the plain "s".
PLURAL_ENDINGS = (("oes", "ao"), ("aes", "ao"), ("ais", "al"))
FILLER_WORDS = {"com", "para", "pra", "por", "que", "uma", "dos", "das"}


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


def singular(word: str) -> str:
    """Rough Portuguese singular of a normalized word.

    Without it, "violao" is closer to "violas" (orchestral strings) than to
    "violoes". Short words are kept as they are ("aco", "pix").
    """
    if len(word) <= 3:
        return word
    for plural_ending, singular_ending in PLURAL_ENDINGS:
        if word.endswith(plural_ending):
            return word[: -len(plural_ending)] + singular_ending
    return word[:-1] if word.endswith("s") else word


def comparable_words(text: str) -> list[str]:
    """Normalized, singular words of a text, ready to compare."""
    return [singular(word) for word in normalize(text).split()]


def best_word_ratio(word: str, text_words: list[str]) -> float:
    """Similarity (0 to 1) between a word and the closest word in a list."""
    return max(
        (SequenceMatcher(None, word, text_word).ratio() for text_word in text_words),
        default=0.0,
    )


def word_similarity(query: str, text: str) -> float:
    """Score from 0 to 1: how well the query's words match the text's words.

    For each query word, take the most similar word in the text (difflib
    ratio), then average. Comparing whole strings would punish short queries
    against long product names; comparing word by word tolerates typos and
    missing words ("gianini gn15" vs. "Giannini GN-15 Nylon Cedr Natural").
    """
    query_words = comparable_words(query)
    text_words = comparable_words(text)
    if not query_words or not text_words:
        return 0.0
    scores = [best_word_ratio(word, text_words) for word in query_words]
    return sum(scores) / len(scores)


def matches_all_words(query: str, text: str, min_ratio: float) -> bool:
    """True if every meaningful query word has a similar word in the text.

    Used to filter the catalog: "yamaha nylon" must match both words. Filler
    words ("com", "para") and words under 3 letters are ignored.
    """
    query_words = [
        word
        for word in comparable_words(query)
        if len(word) >= 3 and word not in FILLER_WORDS
    ]
    text_words = comparable_words(text)
    return bool(query_words) and all(
        best_word_ratio(word, text_words) >= min_ratio for word in query_words
    )


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
