from datetime import date
from pathlib import Path

import pytest

from emporio_agent.data_loader import StoreData, mentions_other_brand, read_csv


def product(data: StoreData, product_id: int) -> dict:
    return data.products.set_index("product_id").loc[product_id].to_dict()


def order(data: StoreData, order_id: int) -> dict:
    return data.orders.set_index("order_id").loc[order_id].to_dict()


def test_all_tables_are_loaded(store_data: StoreData) -> None:
    assert len(store_data.categories) == 9
    assert len(store_data.products) == 65
    assert len(store_data.customers) == 50
    assert len(store_data.orders) == 20
    assert len(store_data.order_items) == 22
    assert len(store_data.promotions) == 25


def test_accents_are_read_correctly(store_data: StoreData) -> None:
    assert "Violões" in store_data.categories["name"].tolist()


def test_specs_are_parsed_into_dicts(store_data: StoreData) -> None:
    assert product(store_data, 81)["specs"]["top"] == "Spruce"
    # Rows with spaces after the colons parse too.
    assert product(store_data, 142)["specs"]["keys"] == "61"


def test_mentions_other_brand() -> None:
    assert mentions_other_brand("Music Man Bass 1X", "Contrabaixo Fender Jazz Bass")
    assert not mentions_other_brand("Fender Telecaster", "Guitarra Fender Telecaster")
    assert not mentions_other_brand("Yamaha C40", "Violão clássico para iniciantes")


def test_descriptions_naming_another_brand_are_dropped(store_data: StoreData) -> None:
    dropped = store_data.products.loc[
        store_data.products["description"].isna(), "product_id"
    ]
    assert sorted(dropped) == [135, 137, 139, 140, 142, 144]
    assert product(store_data, 95)["description"].startswith("Violão")
    assert "StingRay" in product(store_data, 138)["description"]


@pytest.mark.parametrize(
    ("product_id", "expected"),
    [
        (81, True),  # active with stock
        (96, False),  # active, out of stock
        (113, False),  # discontinued, out of stock
        (136, False),  # discontinued but still has stock
        (130, False),  # coming soon
    ],
)
def test_availability_rule(
    store_data: StoreData, product_id: int, expected: bool
) -> None:
    assert product(store_data, product_id)["is_available"] is expected


def test_order_dates_are_dates_and_missing_values_are_none(
    store_data: StoreData,
) -> None:
    delivered = order(store_data, 7)
    assert delivered["order_date"] == date(2026, 2, 3)
    assert delivered["estimated_delivery"] == date(2026, 2, 17)
    assert delivered["notes"] is None

    pending = order(store_data, 13)
    assert pending["tracking_code"] is None
    assert pending["estimated_delivery"] is None


def test_customer_contacts_are_normalized(store_data: StoreData) -> None:
    customer = store_data.customers.set_index("customer_id").loc[1]
    assert customer["email_normalized"] == "lucas.mendes@jmail.com"
    assert customer["phone_digits"] == "67998123456"


def test_promotions_have_boolean_active_flag(store_data: StoreData) -> None:
    active = store_data.promotions[store_data.promotions["is_active"]]
    assert sorted(active["product_id"]) == [90, 94, 121, 127]


def test_read_csv_fails_fast_on_missing_columns(tmp_path: Path) -> None:
    broken = tmp_path / "products.csv"
    broken.write_text("product_id,name\n1,Violão\n", encoding="utf-8")
    with pytest.raises(ValueError, match="price_brl"):
        read_csv(broken, ["product_id", "name", "price_brl"])
