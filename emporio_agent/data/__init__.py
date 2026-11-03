"""The store's data sources, loaded once at startup and cleaned in memory.

    store_data.py  CSVs (products, orders, customers...) -> StoreData
    policies.py    policies PDF -> corrected sections -> keyword search

The files in the repository's data/ folder are read-only: every fix happens
here, at load time.
"""

from emporio_agent.data.policies import PolicySection, load_policy_sections
from emporio_agent.data.store_data import StoreData, load_store_data

__all__ = ["PolicySection", "StoreData", "load_policy_sections", "load_store_data"]
