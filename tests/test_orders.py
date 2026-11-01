import pytest

from emporio_agent.tools.orders import ORDER_NOT_FOUND_MESSAGE, OrderTools

ANA_EMAIL = "anacarol.ferreira@coldmail.com"  # customer 2, owner of order 8


def test_wrong_contact_gets_the_same_message_as_unknown_order(
    order_tools: OrderTools,
) -> None:
    wrong_contact = order_tools.get_order_status(8, "someone@else.com")
    unknown_order = order_tools.get_order_status(999, ANA_EMAIL)
    assert wrong_contact == unknown_order
    assert wrong_contact == {"found": False, "message": ORDER_NOT_FOUND_MESSAGE}


def test_name_is_never_accepted_as_identity(order_tools: OrderTools) -> None:
    result = order_tools.get_order_status(8, "Ana Carolina Ferreira")
    assert result["found"] is False


def test_shipped_order_past_its_estimate_is_delayed(order_tools: OrderTools) -> None:
    result = order_tools.get_order_status(8, ANA_EMAIL.upper())
    assert result["customer_first_name"] == "Ana"
    assert result["status"] == "enviado"
    assert result["tracking_code"] == "BRJL5544332BR"
    assert result["estimated_delivery"] == "28/02/2026"
    assert result["is_delayed"] is True
    assert result["days_late"] == 25


@pytest.mark.parametrize("phone", ["(67) 99654-7821", "+55 67 99654-7821"])
def test_phone_works_as_identity(order_tools: OrderTools, phone: str) -> None:
    assert order_tools.get_order_status(8, phone)["found"] is True


def test_delivered_order_has_precomputed_days(order_tools: OrderTools) -> None:
    result = order_tools.get_order_status(7, "leticia.rocha@jmail.com")
    assert result["days_since_purchase"] == 50
    assert result["days_since_receipt"] == 36
    assert result["receipt_date"] == "17/02/2026"
    assert result["receipt_date_is_estimated"] is True
    assert result["items"] == [
        {"product": "Shelby SU-21S Soprano Sunburst", "quantity": 1}
    ]


def test_pending_order_has_no_tracking(order_tools: OrderTools) -> None:
    result = order_tools.get_order_status(13, "fernanda.ribeiro@coldmail.com")
    assert result["status"] == "aguardando pagamento/processamento"
    assert "tracking_code" not in result
    assert "is_delayed" not in result


def test_order_total_is_never_recomputed(order_tools: OrderTools) -> None:
    # Items at current prices add up to 3,498.00; the order says 3,450.00.
    result = order_tools.get_order_status(3, "isabela.moreira@jmail.com")
    assert result["order_total_brl"] == 3450.0


def test_cancelled_order_includes_the_reason(order_tools: OrderTools) -> None:
    result = order_tools.get_order_status(20, "thiago.barbosa@jmail.com")
    assert result["status"] == "cancelado"
    assert result["cancellation_reason"].startswith("Endereço de entrega inválido")


def test_phone_of_the_customer_sharing_the_email_does_not_open_the_order(
    order_tools: OrderTools,
) -> None:
    # Customers 11 and 43 share an email; order 10 belongs to customer 11.
    assert order_tools.get_order_status(10, "(67) 98543-2109")["found"] is True
    assert order_tools.get_order_status(10, "(67) 99456-3456")["found"] is False


def test_order_id_as_text_is_accepted(order_tools: OrderTools) -> None:
    result = order_tools.get_order_status("8", ANA_EMAIL)  # type: ignore[arg-type]
    assert result["found"] is True
