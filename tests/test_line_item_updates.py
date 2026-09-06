"""PATCH /items/{id} - oprava reportovaná zákazníkem: ruční oprava částky
položky přepočítala invoice.total_amount správně, ale nechala viset starý
základ daně/sazbu DPH z PŮVODNÍ částky, takže "Základ daně"/"DPH %" v review
UI ukazovaly matematicky nesmyslné číslo (např. "DPH 21 %" u položky, kde
skutečný poměr vycházel na stovky procent)."""

from app.models import Customer, Invoice, InvoiceStatus, LineItem


def _register_and_login(client, admin_headers, email="customer@example.com"):
    client.post("/auth/register", headers=admin_headers, json={"email": email, "password": "testpass123"})
    login = client.post("/auth/login", json={"email": email, "password": "testpass123"})
    return login.json()["data"]["access_token"]


def _seed_invoice_with_vat_item(db_session, customer_email) -> tuple[int, int]:
    customer = db_session.query(Customer).filter(Customer.email == customer_email).one()
    invoice = Invoice(
        customer_id=customer.id,
        original_filename="doprava.pdf",
        file_path="/app/uploads/doprava.pdf",
        status=InvoiceStatus.NEEDS_REVIEW.value,
        currency="CZK",
        total_amount=69.0,
    )
    db_session.add(invoice)
    db_session.flush()
    item = LineItem(
        invoice_id=invoice.id,
        description="Doprava",
        category="doprava",
        amount=69.0,
        amount_without_vat=57.02,
        vat_rate=21.0,
        confidence_score=0.95,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return invoice.id, item.id


def test_editing_amount_alone_clears_stale_vat_breakdown(client, admin_headers, db_session):
    token = _register_and_login(client, admin_headers)
    invoice_id, item_id = _seed_invoice_with_vat_item(db_session, "customer@example.com")

    response = client.patch(
        f"/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 800},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["amount"] == 800.0
    # Starý základ daně (57.02) patřil k částce 69, ne 800 - ponechat ho by
    # dalo matematicky nesmyslný rozpad DPH. Musí zmizet, ne zůstat viset.
    assert data["amount_without_vat"] is None
    assert data["vat_rate"] is None

    invoice_response = client.get(f"/invoices/{invoice_id}", headers={"Authorization": f"Bearer {token}"})
    assert invoice_response.json()["data"]["total_amount"] == 800.0


def test_create_and_delete_line_item_recomputes_total(client, admin_headers, db_session):
    token = _register_and_login(client, admin_headers)
    invoice_id, _item_id = _seed_invoice_with_vat_item(db_session, "customer@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(f"/invoices/{invoice_id}/items", headers=headers)
    assert create_response.status_code == 200
    new_item = create_response.json()["data"]
    assert new_item["description"]  # nese placeholder text, nikdy prázdný string
    assert new_item["amount"] == 0.0

    filled = client.patch(f"/items/{new_item['id']}", headers=headers, json={"amount": 50.0, "description": "Doplněk"})
    assert filled.status_code == 200

    after_create = client.get(f"/invoices/{invoice_id}", headers=headers)
    assert after_create.json()["data"]["total_amount"] == 119.0  # 69 (seed) + 50 (nova)

    delete_response = client.delete(f"/items/{new_item['id']}", headers=headers)
    assert delete_response.status_code == 200

    after_delete = client.get(f"/invoices/{invoice_id}", headers=headers)
    assert after_delete.json()["data"]["total_amount"] == 69.0


def test_line_item_create_delete_scoped_to_owning_customer(client, admin_headers, db_session):
    _register_and_login(client, admin_headers, "owner@example.com")
    other_token = _register_and_login(client, admin_headers, "attacker@example.com")
    invoice_id, item_id = _seed_invoice_with_vat_item(db_session, "owner@example.com")
    other_headers = {"Authorization": f"Bearer {other_token}"}

    assert client.post(f"/invoices/{invoice_id}/items", headers=other_headers).status_code == 404
    assert client.delete(f"/items/{item_id}", headers=other_headers).status_code == 404


def test_editing_amount_with_explicit_vat_keeps_it(client, admin_headers, db_session):
    """Když zákazník opraví částku A ZÁROVEŇ dodá i nový základ daně v tom
    samém requestu, nemá se nic mazat - jde o vědomou, úplnou opravu."""
    token = _register_and_login(client, admin_headers)
    _invoice_id, item_id = _seed_invoice_with_vat_item(db_session, "customer@example.com")

    response = client.patch(
        f"/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"amount": 121.0, "amount_without_vat": 100.0, "vat_rate": 21.0},
    )
    data = response.json()["data"]
    assert data["amount_without_vat"] == 100.0
    assert data["vat_rate"] == 21.0
