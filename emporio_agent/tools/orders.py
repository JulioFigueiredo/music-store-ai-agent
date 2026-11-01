"""Order tool: get_order_status, with an identity check before any data.

Privacy (manual section 9, LGPD): an order is shown only when the contact
given matches that order's customer, and only what the customer needs.
"""

from collections.abc import Callable
from datetime import date, datetime

from emporio_agent.data.store_data import StoreData
from emporio_agent.text_utils import digits_only, normalize_email
from emporio_agent.tools.catalog import Catalog
from emporio_agent.tools.common import (
    Record,
    ToolResult,
    format_date,
    group_by,
    to_int,
    to_records,
)

ORDER_STATUS_LABELS = {
    "delivered": "entregue",
    "shipped": "enviado",
    "confirmed": "confirmado",
    "pending": "aguardando pagamento/processamento",
    "cancelled": "cancelado",
}
PAYMENT_METHOD_LABELS = {
    "pix": "PIX",
    "debit": "cartão de débito",
    "boleto": "boleto bancário",
    "credit_3x": "cartão de crédito em 3x",
    "credit_6x": "cartão de crédito em 6x",
    "credit_12x": "cartão de crédito em 12x",
}
# Same message for an unknown order and a contact mismatch, so the tool never
# reveals which order numbers exist.
ORDER_NOT_FOUND_MESSAGE = (
    "No order matches this order number and contact. Ask the customer to "
    "check the order number and the email or phone used in the purchase."
)


class OrderTools:
    """Order lookups, using `clock` as "now" for the day counts."""

    def __init__(
        self, data: StoreData, catalog: Catalog, clock: Callable[[], datetime]
    ) -> None:
        self.orders = {o["order_id"]: o for o in to_records(data.orders)}
        self.customers = {c["customer_id"]: c for c in to_records(data.customers)}
        self.items_by_order = group_by(to_records(data.order_items), "order_id")
        self.catalog = catalog
        self.clock = clock

    def get_order_status(self, order_id: int, contact: str) -> ToolResult:
        """Look up one order, only after confirming the customer's identity.

        Before calling, ask the customer for BOTH the order number and the
        email or phone used in the purchase; a name alone is never enough.
        Returns status, items, order total, payment method, tracking code,
        dates and pre-computed day counts: use these numbers, never compute
        dates yourself. For return or exchange questions, combine these facts
        with search_policies.

        Args:
            order_id: Order number, e.g. 8.
            contact: Email or phone number registered in the purchase.
        """
        order = self.orders.get(to_int(order_id))
        customer = self.customers.get(order["customer_id"]) if order else None
        if order is None or customer is None:
            return {"found": False, "message": ORDER_NOT_FOUND_MESSAGE}
        if not contact_matches(contact, customer):
            return {"found": False, "message": ORDER_NOT_FOUND_MESSAGE}
        return self._order_details(order, customer)

    def _order_details(self, order: Record, customer: Record) -> ToolResult:
        """What the customer needs to know about their order, and no more."""
        today = self.clock().date()
        details: ToolResult = {
            "found": True,
            "order_id": order["order_id"],
            "customer_first_name": customer["name"].split()[0],
            "status": ORDER_STATUS_LABELS.get(order["status"], order["status"]),
            "order_date": format_date(order["order_date"]),
            "days_since_purchase": (today - order["order_date"]).days,
            "items": self._order_items(order["order_id"]),
            # The order's own total, never recomputed from current prices.
            "order_total_brl": order["total_brl"],
            "payment_method": PAYMENT_METHOD_LABELS.get(
                order["payment_method"], order["payment_method"]
            ),
        }
        details.update(delivery_facts(order, today))
        if order["status"] == "cancelled" and order["notes"]:
            details["cancellation_reason"] = order["notes"]
        return details

    def _order_items(self, order_id: int) -> list[Record]:
        """Product names and quantities (no unit prices: they are not stored)."""
        items = []
        for item in self.items_by_order.get(order_id, []):
            product = self.catalog.products_by_id.get(item["product_id"])
            name = product["name"] if product else f"Produto #{item['product_id']}"
            items.append({"product": name, "quantity": item["quantity"]})
        return items


def contact_matches(contact: str, customer: Record) -> bool:
    """Check an email or phone against the customer's registered contact.

    Email: case-insensitive. Phone: digits only, with or without the +55
    country code. Names are never accepted (they are not unique).
    """
    if "@" in contact:
        return normalize_email(contact) == customer["email_normalized"]
    phone = customer["phone_digits"]
    return digits_only(contact) in (phone, "55" + phone)


def delivery_facts(order: Record, today: date) -> Record:
    """Tracking, delivery dates and pre-computed day counts for an order.

    Orders have no real receipt date, so for delivered orders the estimated
    delivery date is used and flagged as an estimate. All orders are treated
    as online purchases (they are shipped with tracking).
    """
    facts: Record = {}
    if order["tracking_code"]:
        facts["tracking_code"] = order["tracking_code"]
    estimated = order["estimated_delivery"]
    if estimated is None:
        return facts
    if order["status"] == "delivered":
        facts["receipt_date"] = format_date(estimated)
        facts["receipt_date_is_estimated"] = True
        facts["days_since_receipt"] = (today - estimated).days
        facts["purchase_channel"] = "online (assumed for all orders)"
        return facts
    facts["estimated_delivery"] = format_date(estimated)
    facts["is_delayed"] = order["status"] == "shipped" and estimated < today
    if facts["is_delayed"]:
        facts["days_late"] = (today - estimated).days
    return facts
