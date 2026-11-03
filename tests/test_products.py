import pytest

from emporio_agent.tools.products import ProductTools


def names(result: dict) -> list[str]:
    return [product["name"] for product in result["products"]]


# --- search_products -------------------------------------------------------


def test_violoes_up_to_1000_are_sorted_and_truncated(
    product_tools: ProductTools,
) -> None:
    result = product_tools.search_products(category="violões", max_price=1000)
    assert result["total_matches"] == 12
    assert result["truncated"] is True
    assert len(result["products"]) == 10
    prices = [product["price_brl"] for product in result["products"]]
    assert prices == sorted(prices)
    assert prices[0] == 429.9
    # Out of stock (96) and discontinued (113) are hidden, and counted.
    assert result["unavailable_matches_hidden"] == 2
    assert "Giannini GF-3D Dreadnought Sunburst" not in names(result)


def test_category_matching_is_fuzzy(product_tools: ProductTools) -> None:
    result = product_tools.search_products(category="violao")
    assert {p["category"] for p in result["products"]} == {"Violões"}


def test_query_must_match_every_word(product_tools: ProductTools) -> None:
    result = product_tools.search_products(query="yamaha nylon")
    assert names(result) == [
        "Yamaha C40 Nylon Natural",
        "Yamaha C70 Nylon Natural",
        "Yamaha CG162S Nylon Natural",
        "Yamaha NTX1 Elétrico Nylon Natural",
    ]


def test_price_range_filter(product_tools: ProductTools) -> None:
    result = product_tools.search_products(min_price=10000, max_price=13000)
    prices = [product["price_brl"] for product in result["products"]]
    assert prices and all(10000 <= price <= 13000 for price in prices)


def test_unavailable_products_can_be_included(product_tools: ProductTools) -> None:
    result = product_tools.search_products(query="giannini gf3d", only_available=False)
    assert result["products"][0]["availability"].startswith(
        "temporariamente indisponível"
    )


@pytest.mark.parametrize("category", ["saxofone", "violino", "sopro"])
def test_empty_category_is_not_reported_as_out_of_stock(
    product_tools: ProductTools, category: str
) -> None:
    result = product_tools.search_products(category=category)
    assert result["found"] is False
    assert "does not carry" in result["message"]


def test_unknown_category_lists_the_real_ones(product_tools: ProductTools) -> None:
    result = product_tools.search_products(category="xyzw")
    assert result["found"] is False
    assert "Violões" in result["available_categories"]


def test_active_promotion_appears_in_search_results(
    product_tools: ProductTools,
) -> None:
    result = product_tools.search_products(query="crafter ht100")
    assert result["products"][0]["active_promotion"]["discount_percent"] == 18


# --- get_product_details ---------------------------------------------------


def test_details_ignore_punctuation_in_names(product_tools: ProductTools) -> None:
    result = product_tools.get_product_details("Takamine GD-20")
    assert result["found"] is True
    assert result["name"] == "Takamine GD20 Dreadnought Natural"
    assert result["price_brl"] == 2199.0


def test_out_of_stock_product_offers_alternatives(
    product_tools: ProductTools,
) -> None:
    result = product_tools.get_product_details("Giannini GF-3D")
    assert result["availability"] == "temporariamente indisponível (sem estoque)"
    assert "stock_quantity" not in result
    alternatives = result["available_alternatives"]
    assert len(alternatives) == 3
    assert all(item["availability"] == "disponível" for item in alternatives)
    assert all(item["category"] == "Violões" for item in alternatives)


def test_discontinued_product_with_stock_is_not_sold(
    product_tools: ProductTools,
) -> None:
    result = product_tools.get_product_details("Ibanez Bass 2X")
    assert result["availability"].startswith("descontinuado")
    assert "stock_quantity" not in result
    assert result["available_alternatives"]


def test_coming_soon_product(product_tools: ProductTools) -> None:
    result = product_tools.get_product_details("Kala KA-ABP-CTG")
    assert result["availability"] == "em breve"


def test_unreliable_description_is_omitted(product_tools: ProductTools) -> None:
    result = product_tools.get_product_details("Music Man Bass 1X")
    assert result["found"] is True
    assert "description" not in result


def test_ambiguous_name_lists_the_options(product_tools: ProductTools) -> None:
    result = product_tools.get_product_details("Martin D-28")
    assert result["found"] is False
    assert len(result["matching_products"]) == 2


def test_typo_returns_suggestions(product_tools: ProductTools) -> None:
    result = product_tools.get_product_details("gianini cedro")
    assert result["found"] is False
    assert result["suggestions"][0] == "Giannini GN-15 Nylon Cedr Natural"
