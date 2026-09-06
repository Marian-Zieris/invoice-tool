"""Multi-tenant izolace - audit ji aktivně zkoušel prolomit na všech
endpointech a nenašel díru. Tenhle test zamyká tenhle stav, aby budoucí
změna (např. nový endpoint, co zapomene na customer_id filtr) spadla v CI,
ne až na produkci s cizími fakturami."""

from app.models import Invoice, InvoiceStatus, LineItem


def _register_and_login(client, admin_headers, email):
    client.post("/auth/register", headers=admin_headers, json={"email": email, "password": "testpass123"})
    login = client.post("/auth/login", json={"email": email, "password": "testpass123"})
    return login.json()["data"]["access_token"]


def _create_invoice_for(db_session, customer_email) -> int:
    from app.models import Customer

    customer = db_session.query(Customer).filter(Customer.email == customer_email).one()
    invoice = Invoice(
        customer_id=customer.id,
        original_filename="test.png",
        file_path="/app/uploads/test.png",
        status=InvoiceStatus.NEEDS_REVIEW.value,
        currency="CZK",
        total_amount=100.0,
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(LineItem(invoice_id=invoice.id, description="Item", amount=100.0, confidence_score=0.9))
    db_session.commit()
    db_session.refresh(invoice)
    return invoice.id


def test_customer_cannot_view_another_customers_invoice(client, admin_headers, db_session):
    _register_and_login(client, admin_headers, "owner@example.com")
    other_token = _register_and_login(client, admin_headers, "attacker@example.com")
    invoice_id = _create_invoice_for(db_session, "owner@example.com")

    response = client.get(f"/invoices/{invoice_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert response.status_code == 404
    assert response.json()["error_code"] == "invoice_not_found"


def test_customer_cannot_patch_another_customers_line_item(client, admin_headers, db_session):
    _register_and_login(client, admin_headers, "owner@example.com")
    other_token = _register_and_login(client, admin_headers, "attacker@example.com")
    invoice_id = _create_invoice_for(db_session, "owner@example.com")
    item_id = db_session.query(LineItem).filter(LineItem.invoice_id == invoice_id).one().id

    response = client.patch(
        f"/items/{item_id}",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"amount": 1},
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "line_item_not_found"


def test_customer_cannot_export_another_customers_invoice(client, admin_headers, db_session):
    _register_and_login(client, admin_headers, "owner@example.com")
    other_token = _register_and_login(client, admin_headers, "attacker@example.com")
    invoice_id = _create_invoice_for(db_session, "owner@example.com")

    response = client.post(
        "/invoices/export",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"invoice_ids": [invoice_id]},
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "invoices_not_found"


def test_owner_can_view_their_own_invoice(client, admin_headers, db_session):
    owner_token = _register_and_login(client, admin_headers, "owner@example.com")
    invoice_id = _create_invoice_for(db_session, "owner@example.com")

    response = client.get(f"/invoices/{invoice_id}", headers={"Authorization": f"Bearer {owner_token}"})
    assert response.status_code == 200
    assert response.json()["data"]["id"] == invoice_id


def test_unauthenticated_request_is_rejected(client):
    response = client.get("/invoices")
    assert response.status_code == 401
