"""The agent's tools, one module per domain.

common.py         shared types and helpers (money, dates, records)
catalog.py        products and categories: indexes and matching
promotions.py     promotion rules + get_active_promotions
products.py       search_products, get_product_details
orders.py         get_order_status (with identity check)
payments.py       calculate_payment_options
policy_search.py  search_policies
registry.py       builds the {tool name: function} map for the agent
"""

from emporio_agent.tools.registry import build_tool_registry

__all__ = ["build_tool_registry"]
