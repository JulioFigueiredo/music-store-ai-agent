import pytest

from emporio_agent.tools.common import to_money
from emporio_agent.tools.payments import (
    calculate_payment_options,
    max_interest_free_installments,
)


def test_pix_discount_on_regular_price() -> None:
    result = calculate_payment_options(900)
    assert result["pix"] == {"price_brl": 855.0, "discount_percent": 5}


def test_no_pix_discount_on_promotional_price() -> None:
    result = calculate_payment_options(1967.18, is_promotional_price=True)
    assert result["pix"]["price_brl"] == 1967.18
    assert result["pix"]["discount_percent"] == 0


def test_installment_options_stop_at_the_maximum() -> None:
    credit_card = calculate_payment_options(900)["credit_card"]
    assert credit_card["max_interest_free_installments"] == 9
    assert credit_card["options"][-1] == {
        "installments": 9,
        "installment_value_brl": 100.0,
    }


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (150.00, 3),  # 3x of R$ 50.00 (1x-3x minimum: R$ 50)
        (149.99, 2),  # 3x would be below R$ 50
        (320.00, 4),  # 4x of R$ 80.00 (4x-6x minimum: R$ 80)
        (480.00, 6),
        (479.99, 5),
        (700.00, 7),  # 7x of R$ 100.00 (7x-12x minimum: R$ 100)
        (699.99, 6),
        (899.00, 8),  # 9x would be R$ 99.89
        (5000.00, 12),  # never more than 12x
    ],
)
def test_installment_tier_boundaries(amount: float, expected: int) -> None:
    assert max_interest_free_installments(amount) == expected


def test_combining_methods_only_above_2000() -> None:
    allowed = "combining_payment_methods_allowed"
    assert calculate_payment_options(2000)[allowed] is False
    assert calculate_payment_options(2000.01)[allowed] is True


def test_invalid_amount_returns_error() -> None:
    assert "error" in calculate_payment_options(0)


def test_money_rounds_half_up() -> None:
    assert to_money(569.905) == 569.91
    assert to_money(1967.1799999) == 1967.18
