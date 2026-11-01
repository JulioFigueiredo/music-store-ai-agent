"""Promotion rules and the get_active_promotions tool.

Rules from the manual (section 6.2): promotions are not cumulative (only the
highest active discount applies), they last only while stock lasts, and a
promotional price is always shown with the original price and the discount.
"""

from emporio_agent.data_loader import StoreData
from emporio_agent.tools.catalog import Catalog
from emporio_agent.tools.common import (
    Record,
    ToolResult,
    group_by,
    to_money,
    to_records,
)


class Promotions:
    """Active and expired promotions per product (is_active is the only signal)."""

    def __init__(self, data: StoreData, catalog: Catalog) -> None:
        self.catalog = catalog
        self.rows_by_product = group_by(to_records(data.promotions), "product_id")

    def get_active_promotions(self, category: str = "") -> ToolResult:
        """List the promotions active right now, with the original price, the
        discount percentage and the promotional price.

        Use it when the customer asks what is on sale ("tem promoção?"). To
        check one specific product, use get_product_details instead. Only
        products that can be bought now are listed (no rain check).

        Args:
            category: Category name to filter by, e.g. "violões". Optional.
        """
        products = self.catalog.products
        if category:
            category_ids, problem = self.catalog.resolve_category(category)
            if problem:
                return problem
            products = [p for p in products if p["category_id"] in category_ids]
        promotions = []
        for product in products:
            promotion = self.active_for(product)
            if promotion:
                promotions.append({**self.catalog.label(product), **promotion})
        promotions.sort(key=lambda item: item["discount_percent"], reverse=True)
        if not promotions:
            return {"found": False, "message": "No active promotions for this."}
        return {"found": True, "promotions": promotions}

    def active_for(self, product: Record) -> Record | None:
        """The product's best active promotion, or None.

        A product that cannot be bought has no valid promotion (no rain
        check). The promotional price is computed here, never by the model.
        """
        rows = self.rows_by_product.get(product["product_id"], [])
        active = [row for row in rows if row["is_active"]]
        if not active or not product["is_available"]:
            return None
        best = max(active, key=lambda row: row["discount_percent"])
        price = product["price_brl"]
        discount = best["discount_percent"]
        return {
            "promotion": best["description"],
            "original_price_brl": price,
            "discount_percent": discount,
            "promotional_price_brl": to_money(price * (100 - discount) / 100),
        }

    def expired_names(self, product: Record) -> list[str]:
        """Names of the product's inactive promotions (to report as expired)."""
        rows = self.rows_by_product.get(product["product_id"], [])
        return sorted({row["description"] for row in rows if not row["is_active"]})
