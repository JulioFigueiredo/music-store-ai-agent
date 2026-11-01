from emporio_agent.tools.products import ProductTools
from emporio_agent.tools.promotions import Promotions


def test_active_promotions_sorted_by_discount(promotions: Promotions) -> None:
    result = promotions.get_active_promotions()
    discounts = [item["discount_percent"] for item in result["promotions"]]
    assert discounts == [20, 18, 10, 8]


def test_active_promotions_by_category(promotions: Promotions) -> None:
    result = promotions.get_active_promotions(category="ukulele")
    assert [item["name"] for item in result["promotions"]] == [
        "Ohana CK-20 Concert Natural",
        "Kalani KAL-700T Tenor Natural",
    ]


def test_active_promotion_shows_original_price_and_percent(
    product_tools: ProductTools,
) -> None:
    result = product_tools.get_product_details("Crafter HT-100")
    assert result["active_promotion"] == {
        "promotion": "Desconto Exclusivo",
        "original_price_brl": 2399.0,
        "discount_percent": 18,
        "promotional_price_brl": 1967.18,
    }


def test_expired_promotion_is_reported(product_tools: ProductTools) -> None:
    result = product_tools.get_product_details("Takamine GD20")
    assert result["expired_promotions"] == ["Oferta Especial"]
    assert "active_promotion" not in result


def test_product_with_several_rows_lists_each_expired_name_once(
    product_tools: ProductTools,
) -> None:
    # Product 93 (Martin D-28) has two inactive "Promoção de Páscoa" rows.
    result = product_tools.get_product_details("Martin D-28 Dreadnought")
    assert result["expired_promotions"] == ["Promoção de Páscoa"]


def test_highest_active_promotion_wins(promotions: Promotions) -> None:
    product = {"product_id": 1, "price_brl": 100.0, "is_available": True}
    promotions.rows_by_product[1] = [
        {"description": "A", "discount_percent": 10, "is_active": True},
        {"description": "B", "discount_percent": 25, "is_active": True},
        {"description": "C", "discount_percent": 40, "is_active": False},
    ]
    try:
        promotion = promotions.active_for(product)
    finally:
        del promotions.rows_by_product[1]
    assert promotion is not None
    assert promotion["promotion"] == "B"
    assert promotion["promotional_price_brl"] == 75.0


def test_no_promotion_for_a_product_that_cannot_be_bought(
    promotions: Promotions,
) -> None:
    product = {"product_id": 90, "price_brl": 2399.0, "is_available": False}
    assert promotions.active_for(product) is None
