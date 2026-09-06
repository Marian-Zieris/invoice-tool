"""POST /invoices/{id}/confirm - zákazníkem vyžádaná funkce: označit fakturu
jako zkontrolovanou, i když na ní nic neopravoval (dřív šlo přejít na
`reviewed` jen jako vedlejší efekt PATCH úpravy)."""

from app.models import Customer, Invoice, InvoiceStatus


def _register_and_login(client, admin_headers, email="customer@example.com"):
    client.post("/auth/register", headers=admin_headers, json={"email": email, "password": "testpass123"})
    login = client.post("/auth/login", json={"email": email, "password": "testpass123"})
    return login.json()["data"]["access_token"]


def _seed_invoice(db_session, customer_email, status=InvoiceStatus.NEEDS_REVIEW.value) -> int:
    customer = db_session.query(Customer).filter(Customer.email == customer_email).one()
    invoice = Invoice(
        customer_id=customer.id,
        original_filename="ok.pdf",
        file_path="/app/uploads/ok.pdf",
        status=status,
        currency="CZK",
        total_amount=100.0,
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice.id


def test_confirm_marks_needs_review_invoice_as_reviewed(client, admin_headers, db_session):
    token = _register_and_login(client, admin_headers)
    invoice_id = _seed_invoice(db_session, "customer@example.com")

    response = client.post(f"/invoices/{invoice_id}/confirm", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "reviewed"


def test_confirm_rejects_invoice_not_awaiting_review(client, admin_headers, db_session):
    token = _register_and_login(client, admin_headers)
    invoice_id = _seed_invoice(db_session, "customer@example.com", status=InvoiceStatus.PROCESSING.value)

    response = client.post(f"/invoices/{invoice_id}/confirm", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_status"


def test_confirm_is_scoped_to_owning_customer(client, admin_headers, db_session):
    _register_and_login(client, admin_headers, "owner@example.com")
    other_token = _register_and_login(client, admin_headers, "attacker@example.com")
    invoice_id = _seed_invoice(db_session, "owner@example.com")

    response = client.post(f"/invoices/{invoice_id}/confirm", headers={"Authorization": f"Bearer {other_token}"})
    assert response.status_code == 404
