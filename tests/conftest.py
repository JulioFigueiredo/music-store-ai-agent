from datetime import datetime

import pytest

from emporio_agent import config
from emporio_agent.data.policies import load_policy_sections
from emporio_agent.data.store_data import StoreData, load_store_data
from emporio_agent.tools.catalog import Catalog
from emporio_agent.tools.orders import OrderTools
from emporio_agent.tools.products import ProductTools
from emporio_agent.tools.promotions import Promotions
from emporio_agent.tools.registry import ToolRegistry, build_tool_registry

# Same simulated "now" as .env.example: a Wednesday, during business hours.
STORE_NOW = datetime(2026, 3, 25, 10, 30, tzinfo=config.STORE_TIMEZONE)


@pytest.fixture(scope="session")
def store_data() -> StoreData:
    """The real store data, loaded once for the whole test session."""
    return load_store_data()


@pytest.fixture(scope="session")
def catalog(store_data: StoreData) -> Catalog:
    return Catalog(store_data)


@pytest.fixture(scope="session")
def promotions(store_data: StoreData, catalog: Catalog) -> Promotions:
    return Promotions(store_data, catalog)


@pytest.fixture(scope="session")
def product_tools(catalog: Catalog, promotions: Promotions) -> ProductTools:
    return ProductTools(catalog, promotions)


@pytest.fixture(scope="session")
def order_tools(store_data: StoreData, catalog: Catalog) -> OrderTools:
    return OrderTools(store_data, catalog, clock=lambda: STORE_NOW)


@pytest.fixture(scope="session")
def tool_registry(store_data: StoreData) -> ToolRegistry:
    return build_tool_registry(
        store_data, load_policy_sections(), clock=lambda: STORE_NOW
    )
