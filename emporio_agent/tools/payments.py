"""Payment tool: calculate_payment_options, with the rules of manual section 3.

Payment math is always done here, never by the LLM. The numbers come from
config.py (PIX discount, installment tiers, combination threshold).
"""

from emporio_agent import config
from emporio_agent.tools.common import Record, ToolResult, to_money


def calculate_payment_options(
    amount: float, is_promotional_price: bool = False
) -> ToolResult:
    """Calculate how a purchase amount can be paid: the PIX price and the
    interest-free credit card installments allowed by the store's rules.

    Use it whenever the customer asks about PIX, installments ("dá pra
    parcelar em 10x?") or how to pay a price. Never do this math yourself.
    If the product is on promotion, pass the promotional price with
    is_promotional_price=true: the PIX discount does not apply on top of a
    promotion.

    Args:
        amount: Purchase amount in BRL (the price or promotional price).
        is_promotional_price: True if the amount is a promotional price.
    """
    if amount <= 0:
        return {"error": "The amount must be greater than zero."}
    amount = to_money(amount)
    max_count = max_interest_free_installments(amount)
    return {
        "amount_brl": amount,
        "pix": pix_option(amount, is_promotional_price),
        "credit_card": {
            "max_interest_free_installments": max_count,
            "options": [
                {
                    "installments": count,
                    "installment_value_brl": to_money(amount / count),
                }
                for count in range(1, max_count + 1)
            ],
        },
        "debit_card_and_boleto": "Full amount, paid at once, no discount.",
        "combining_payment_methods_allowed": (
            amount > config.COMBINED_PAYMENT_MIN_TOTAL
        ),
    }


def minimum_installment(count: int) -> float:
    """Minimum installment value for a number of installments (manual 3.1)."""
    for highest_count, minimum in config.INSTALLMENT_TIERS:
        if count <= highest_count:
            return minimum
    raise ValueError(f"More than {config.MAX_INSTALLMENTS} installments: {count}")


def max_interest_free_installments(amount: float) -> int:
    """Highest installment count whose value meets its tier's minimum.

    Paying in one go (1x) is always allowed.
    """
    best = 1
    for count in range(2, config.MAX_INSTALLMENTS + 1):
        if amount / count >= minimum_installment(count):
            best = count
    return best


def pix_option(amount: float, is_promotional_price: bool) -> Record:
    """PIX price: 5% off the list price, but never on top of a promotion."""
    if is_promotional_price:
        return {
            "price_brl": amount,
            "discount_percent": 0,
            "note": "No PIX discount on promotional prices: discounts are "
            "not cumulative (manual 6.2).",
        }
    discount = config.PIX_DISCOUNT_PERCENT
    return {
        "price_brl": to_money(amount * (100 - discount) / 100),
        "discount_percent": discount,
    }
