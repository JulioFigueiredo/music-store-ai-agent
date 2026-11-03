import json

from emporio_agent.tools.registry import ToolRegistry


def test_registry_exposes_the_six_tools(tool_registry: ToolRegistry) -> None:
    assert sorted(tool_registry) == [
        "calculate_payment_options",
        "get_active_promotions",
        "get_order_status",
        "get_product_details",
        "search_policies",
        "search_products",
    ]


def test_search_policies_returns_sections(tool_registry: ToolRegistry) -> None:
    result = tool_registry["search_policies"]("posso devolver?")
    assert result["sections"][0]["section"] == "4. Política de Trocas e Devoluções"


def test_search_policies_without_match_lists_topics(
    tool_registry: ToolRegistry,
) -> None:
    result = tool_registry["search_policies"]("capital da França")
    assert result["found"] is False
    assert len(result["available_topics"]) == 10


def test_tool_results_are_json_serializable(tool_registry: ToolRegistry) -> None:
    results = [
        tool_registry["search_products"](category="violões"),
        tool_registry["get_product_details"]("Giannini GF-3D"),
        tool_registry["get_order_status"](7, "leticia.rocha@jmail.com"),
        tool_registry["get_active_promotions"](),
        tool_registry["calculate_payment_options"](899),
        tool_registry["search_policies"]("garantia"),
    ]
    for result in results:
        json.dumps(result, allow_nan=False)
