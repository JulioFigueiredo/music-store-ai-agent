import pytest

from emporio_agent.data_loader import StoreData, load_store_data


@pytest.fixture(scope="session")
def store_data() -> StoreData:
    """The real store data, loaded once for the whole test session."""
    return load_store_data()
