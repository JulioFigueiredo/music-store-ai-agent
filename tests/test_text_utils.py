from emporio_agent.text_utils import (
    compact,
    contains_phrase,
    digits_only,
    normalize,
    normalize_email,
    rank_by_similarity,
    word_similarity,
)


def test_normalize_removes_case_accents_and_punctuation() -> None:
    assert normalize("  Violão Takamine GD-20! ") == "violao takamine gd20"
    assert normalize("Baterias e Percussão") == "baterias e percussao"
    assert normalize("Gibson Les Paul Standard '50s") == "gibson les paul standard 50s"


def test_normalize_turns_other_punctuation_into_spaces() -> None:
    assert normalize("Nylon/Aço, Natural") == "nylon aco natural"


def test_compact_ignores_spacing_and_hyphens() -> None:
    assert compact("Takamine GD-20") == compact("Takamine GD20") == "takaminegd20"
    assert compact("takamine gd 20") == "takaminegd20"


def test_digits_only_keeps_phone_digits() -> None:
    assert digits_only("(67) 99812-3456") == "67998123456"


def test_normalize_email_trims_and_lowercases() -> None:
    assert (
        normalize_email("  Ana.Ferreira@ColdMail.com ") == "ana.ferreira@coldmail.com"
    )


def test_contains_phrase_matches_whole_words_only() -> None:
    assert contains_phrase("Kala KA-T Tenor Mogno", "Kala")
    assert not contains_phrase("Kalani KAL-700T Tenor Natural", "Kala")
    assert contains_phrase("Contrabaixo Music Man StingRay", "music man")


def test_word_similarity_tolerates_typos_and_missing_words() -> None:
    name = "Giannini GN-15 Nylon Cedr Natural"
    assert word_similarity("gianini gn15", name) > 0.9
    assert word_similarity("Takamine GD20", "Takamine GD20 Dreadnought Natural") == 1
    assert word_similarity("bateria eletronica", name) < 0.6


def test_word_similarity_of_empty_text_is_zero() -> None:
    assert word_similarity("", "Yamaha C40") == 0
    assert word_similarity("yamaha", "") == 0


def test_rank_by_similarity_returns_best_first_within_limits() -> None:
    candidates = ["Guitarras", "Violões", "Ukuleles", "Baixos"]
    assert rank_by_similarity("violao", candidates, limit=3, min_score=0.6) == [
        "Violões"
    ]
    assert rank_by_similarity("xyz", candidates, limit=3, min_score=0.6) == []
    ranked = rank_by_similarity("guitarra", candidates, limit=1, min_score=0.0)
    assert ranked == ["Guitarras"]
