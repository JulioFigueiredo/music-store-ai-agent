"""Load the provided CSVs once, validate them and clean them for the tools.

The files in data/ are read-only: every fix happens here, in memory. The
reasons behind each fix are in docs/data_notes.md.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from emporio_agent import config
from emporio_agent.text_utils import contains_phrase, digits_only, normalize_email

logger = logging.getLogger(__name__)

# Used to spot descriptions that describe another product (e.g. "Music Man
# Bass 1X" described as a Fender Jazz Bass). Includes every brand in the
# product names, plus common brands that could show up in descriptions.
KNOWN_BRANDS = (
    # Brands in product names
    "Crafter",
    "Fender",
    "Giannini",
    "Gibson",
    "Ibanez",
    "Kala",
    "Kalani",
    "Korg",
    "Martin",
    "Music Man",
    "Nord",
    "Ohana",
    "Pearl",
    "PRS",
    "Roland",
    "Rozini",
    "Shelby",
    "Tagima",
    "Takamine",
    "Taylor",
    "Yamaha",
    # Other common brands
    "Casio",
    "Cort",
    "Epiphone",
    "Gretsch",
    "Jackson",
    "Kawai",
    "Ludwig",
    "Squier",
    "Strinberg",
    "Tama",
)

CATEGORY_COLUMNS = ["category_id", "name", "description"]
PRODUCT_COLUMNS = [
    "product_id",
    "price_brl",
    "name",
    "category_id",
    "description",
    "stock_quantity",
    "status",
    "specs",
    "created_at",
]
CUSTOMER_COLUMNS = ["customer_id", "name", "phone", "email", "city"]
ORDER_COLUMNS = [
    "order_id",
    "customer_id",
    "order_date",
    "status",
    "total_brl",
    "payment_method",
    "tracking_code",
    "estimated_delivery",
    "notes",
]
ORDER_ITEM_COLUMNS = ["order_id", "quantity", "product_id"]
PROMOTION_COLUMNS = [
    "promotion_id",
    "product_id",
    "discount_percent",
    "description",
    "is_active",
]


@dataclass(frozen=True)
class StoreData:
    """All store tables, loaded once at startup and passed to the tools."""

    categories: pd.DataFrame
    products: pd.DataFrame
    customers: pd.DataFrame
    orders: pd.DataFrame
    order_items: pd.DataFrame
    promotions: pd.DataFrame


def load_store_data() -> StoreData:
    """Read, validate and clean every CSV. Fails fast if a file is missing."""
    config.check_data_files()
    data = StoreData(
        categories=read_csv(config.CATEGORIES_CSV, CATEGORY_COLUMNS),
        products=prepare_products(read_csv(config.PRODUCTS_CSV, PRODUCT_COLUMNS)),
        customers=prepare_customers(read_csv(config.CUSTOMERS_CSV, CUSTOMER_COLUMNS)),
        orders=prepare_orders(read_csv(config.ORDERS_CSV, ORDER_COLUMNS)),
        order_items=read_csv(config.ORDER_ITEMS_CSV, ORDER_ITEM_COLUMNS),
        promotions=prepare_promotions(
            read_csv(config.PROMOTIONS_CSV, PROMOTION_COLUMNS)
        ),
    )
    logger.info(
        "Loaded %d products, %d customers, %d orders, %d promotions",
        len(data.products),
        len(data.customers),
        len(data.orders),
        len(data.promotions),
    )
    return data


def read_csv(path: Path, expected_columns: list[str]) -> pd.DataFrame:
    """Read a UTF-8 CSV and check that it has the columns the code relies on."""
    table = pd.read_csv(path, encoding="utf-8")
    missing = sorted(set(expected_columns) - set(table.columns))
    if missing:
        raise ValueError(f"{path.name} is missing columns: {missing}")
    return table


def as_optional(column: pd.Series) -> pd.Series:
    """Return the column with None for missing values (NaN is not valid JSON)."""
    return column.astype(object).where(column.notna(), None)


def parse_specs(raw_specs: str) -> dict:
    """Parse the specs JSON string. A broken row becomes {} instead of crashing."""
    try:
        return json.loads(raw_specs)
    except json.JSONDecodeError:
        logger.warning("Could not parse product specs: %r", raw_specs)
        return {}


def mentions_other_brand(name: str, description: str) -> bool:
    """True if the description names a known brand that is not in the name."""
    return any(
        contains_phrase(description, brand) and not contains_phrase(name, brand)
        for brand in KNOWN_BRANDS
    )


def prepare_products(products: pd.DataFrame) -> pd.DataFrame:
    """Parse specs, drop unreliable descriptions and flag availability.

    name, price, stock, status and specs are authoritative. A description
    that names another brand is describing a different product, so it is
    dropped rather than shown to customers.
    """
    products = products.copy()
    products["specs"] = products["specs"].map(parse_specs)
    products["description"] = as_optional(products["description"])

    conflicting = products.apply(
        lambda row: mentions_other_brand(row["name"], row["description"]), axis=1
    )
    products.loc[conflicting, "description"] = None
    logger.info(
        "Dropped %d product descriptions that name a different brand (ids: %s)",
        conflicting.sum(),
        products.loc[conflicting, "product_id"].tolist(),
    )

    products["is_available"] = (products["status"] == "active") & (
        products["stock_quantity"] > 0
    )
    return products


def prepare_customers(customers: pd.DataFrame) -> pd.DataFrame:
    """Add normalized contact columns used by the order identity check."""
    customers = customers.copy()
    customers["email_normalized"] = customers["email"].map(normalize_email)
    customers["phone_digits"] = customers["phone"].map(digits_only)
    return customers


def prepare_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Turn date strings into dates and missing values into None.

    Only shipped and delivered orders have a tracking code and an estimated
    delivery date; the others keep None in those columns.
    """
    orders = orders.copy()
    for column in ["order_date", "estimated_delivery"]:
        dates = pd.to_datetime(orders[column], format="%Y-%m-%d").dt.date
        orders[column] = as_optional(dates)
    for column in ["tracking_code", "notes"]:
        orders[column] = as_optional(orders[column])
    return orders


def prepare_promotions(promotions: pd.DataFrame) -> pd.DataFrame:
    """Turn the 0/1 is_active flag into a boolean (the only validity signal)."""
    promotions = promotions.copy()
    promotions["is_active"] = promotions["is_active"].astype(bool)
    return promotions
