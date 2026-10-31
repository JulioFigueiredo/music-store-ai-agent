import pytest

from emporio_agent.policies import (
    PolicySection,
    apply_corrections,
    load_policy_sections,
    replace_ignoring_whitespace,
    search_policy_sections,
    split_sections,
    strip_header_and_footer,
    tidy_text,
)


@pytest.fixture(scope="module")
def sections() -> list[PolicySection]:
    return load_policy_sections()


def section_text(sections: list[PolicySection], number: int) -> str:
    return sections[number - 1].text


def found_numbers(sections: list[PolicySection], query: str) -> list[int]:
    return [section.number for section in search_policy_sections(sections, query)]


# --- Loading and cleaning --------------------------------------------------


def test_manual_is_split_into_ten_numbered_sections(
    sections: list[PolicySection],
) -> None:
    assert [section.number for section in sections] == list(range(1, 11))
    assert sections[3].heading == "4. Política de Trocas e Devoluções"


def test_numbered_list_inside_section_7_is_not_a_section(
    sections: list[PolicySection],
) -> None:
    # "3. Consulta:" (section 7.2 list item) starts page 7 but is indented.
    assert "Consulta: buscar no sistema" in section_text(sections, 7)
    assert "Consulta" not in section_text(sections, 3)


def test_header_and_footer_are_removed(sections: list[PolicySection]) -> None:
    all_text = "\n".join(section.text for section in sections)
    assert "Manual de Políticas e Procedimentos" not in all_text
    assert "Página" not in all_text


def test_strip_header_and_footer() -> None:
    page = (
        "Empório da Música Manual de Políticas e Procedimentos\n"
        "2. Horário\n"
        "        Página 2  "
    )
    assert strip_header_and_footer(page) == "2. Horário"


def test_corrections_are_applied(sections: list[PolicySection]) -> None:
    assert "(67) 3341-4444" in section_text(sections, 7)
    assert "3321-4500" not in section_text(sections, 7)
    assert "contato@emporiodamusica.com.br" in section_text(sections, 1)
    payments = section_text(sections, 3)
    assert "Parcela mínima conforme a seção 3.1" in payments
    assert "até 3x: sem juros, parcela mínima de R$ 50,00" in payments


def test_replace_ignoring_whitespace_handles_line_breaks() -> None:
    text = "parcela (exceto abaixo de R$\n         50,00)."
    result, count = replace_ignoring_whitespace(text, "R$ 50,00", "R$ 60,00")
    assert (result, count) == ("parcela (exceto abaixo de R$ 60,00).", 1)


def test_missing_correction_fails_fast() -> None:
    with pytest.raises(ValueError, match="correction not found"):
        apply_corrections("text without any of the expected passages")


def test_unexpected_section_numbers_fail_fast() -> None:
    with pytest.raises(ValueError, match="Unexpected policy section"):
        split_sections("1. Only one section\nbody")


def test_tidy_text_formats_lists_and_tables() -> None:
    raw = "    •    Frete grátis\n\n\n\n Sábado                 09:00 às 13:00"
    assert tidy_text(raw) == "• Frete grátis\n\nSábado | 09:00 às 13:00"


# --- Search ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected_first"),
    [
        ("posso devolver?", 4),
        ("Me arrependi da compra do meu ukulele", 4),
        ("que horas vocês abrem?", 2),
        ("abre domingo?", 2),
        ("qual o endereço da loja?", 1),
        ("vendem cordas?", 1),
        ("posso parcelar em 10x?", 3),
        ("quanto custa o frete para Dourados?", 5),
        ("meu pedido não chegou, tem rastreio?", 5),
        ("promoção é cumulativa?", 6),
        ("meu violão quebrou", 8),
        ("quero fazer uma reclamação", 7),
        ("LGPD", 9),
    ],
)
def test_search_finds_the_right_section(
    sections: list[PolicySection], query: str, expected_first: int
) -> None:
    assert found_numbers(sections, query)[0] == expected_first


def test_search_returns_two_sections_when_both_apply(
    sections: list[PolicySection],
) -> None:
    assert sorted(found_numbers(sections, "produto com defeito")) == [4, 8]
    assert sorted(found_numbers(sections, "tem desconto no pix?")) == [3, 6]


def test_search_ignores_accents_and_case(sections: list[PolicySection]) -> None:
    assert found_numbers(sections, "HORARIO") == found_numbers(sections, "horário")


def test_search_returns_nothing_for_unrelated_questions(
    sections: list[PolicySection],
) -> None:
    assert search_policy_sections(sections, "qual a capital da França?") == []
