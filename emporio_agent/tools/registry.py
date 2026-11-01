"""Wire the tool modules together and expose them to the agent by name."""

from collections.abc import Callable
from datetime import datetime

from emporio_agent import config
from emporio_agent.data.policies import PolicySection
from emporio_agent.data.store_data import StoreData
from emporio_agent.tools.catalog import Catalog
from emporio_agent.tools.common import ToolResult
from emporio_agent.tools.orders import OrderTools
from emporio_agent.tools.payments import calculate_payment_options
from emporio_agent.tools.policy_search import PolicyTools
from emporio_agent.tools.products import ProductTools
from emporio_agent.tools.promotions import Promotions

ToolRegistry = dict[str, Callable[..., ToolResult]]


def build_tool_registry(
    data: StoreData,
    policy_sections: list[PolicySection],
    clock: Callable[[], datetime] = config.get_store_now,
) -> ToolRegistry:
    """Build every tool over the loaded data and map tool names to functions.

    The agent dispatches the model's tool calls through this dict. `clock`
    returns "now" for the order day counts; tests pass a fixed date.
    """
    catalog = Catalog(data)
    promotions = Promotions(data, catalog)
    products = ProductTools(catalog, promotions)
    orders = OrderTools(data, catalog, clock)
    policies = PolicyTools(policy_sections)
    return {
        "search_products": products.search_products,
        "get_product_details": products.get_product_details,
        "get_order_status": orders.get_order_status,
        "get_active_promotions": promotions.get_active_promotions,
        "calculate_payment_options": calculate_payment_options,
        "search_policies": policies.search_policies,
    }
