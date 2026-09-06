"""Pokrývá D4 - obsah souboru se musí shodovat s příponou, a limit počtu
uploadů za den. OCR/LLM zpracování je v testech vypnuté (viz conftest), takže
tyhle testy ověřují jen validaci na vstupu endpointu, ne přesnost extrakce."""

import io

from app.models import Invoice


def _register_and_login(client, admin_headers, email="uploader@example.com"):
    client.post("/auth/register", headers=admin_headers, json={"email": email, "password": "testpass123"})
    login = client.post("/auth/login", json={"email": email, "password": "testpass123"})
    return login.json()["data"]["access_token"]


# Nejmenší platný PNG (1x1 černý pixel) - pro test stačí, že libmagic ho
# rozpozná jako "image/png", pipeline stejně reálně neběží (viz conftest).
_MINIMAL_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de000000017352474200aece1ce90000000467414d410000b18f0bfc6105"
    "0000000a49444154789c6300010000050001a5f645400000000049454e44ae"
    "426082"
)


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_disallowed_extension_is_rejected(client, admin_headers):
    token = _register_and_login(client, admin_headers)
    response = client.post(
        "/invoices/upload",
        headers=_auth_header(token),
        files={"files": ("malware.exe", io.BytesIO(b"not really an exe"), "application/octet-stream")},
    )
    assert response.status_code == 200
    result = response.json()["data"][0]
    assert result["status"] == "rejected"
    assert "Unsupported file type" in result["reason"]


def test_content_not_matching_extension_is_rejected(client, admin_headers):
    """Přesně ten scénář z auditu - textový soubor přejmenovaný na .pdf."""
    token = _register_and_login(client, admin_headers)
    response = client.post(
        "/invoices/upload",
        headers=_auth_header(token),
        files={"files": ("invoice.pdf", io.BytesIO(b"this is plain text, not a pdf"), "application/pdf")},
    )
    result = response.json()["data"][0]
    assert result["status"] == "rejected"
    assert "does not match its extension" in result["reason"]


def test_valid_png_is_accepted(client, admin_headers):
    token = _register_and_login(client, admin_headers)
    response = client.post(
        "/invoices/upload",
        headers=_auth_header(token),
        files={"files": ("receipt.png", io.BytesIO(_MINIMAL_PNG), "image/png")},
    )
    result = response.json()["data"][0]
    assert result["status"] == "uploaded"
    assert "invoice_id" in result


def test_daily_upload_quota_is_enforced(client, admin_headers, monkeypatch, db_session):
    monkeypatch.setattr("app.routers.upload.MAX_UPLOADS_PER_DAY", 1)
    token = _register_and_login(client, admin_headers)

    first = client.post(
        "/invoices/upload",
        headers=_auth_header(token),
        files={"files": ("a.png", io.BytesIO(_MINIMAL_PNG), "image/png")},
    )
    assert first.json()["data"][0]["status"] == "uploaded"

    second = client.post(
        "/invoices/upload",
        headers=_auth_header(token),
        files={"files": ("b.png", io.BytesIO(_MINIMAL_PNG), "image/png")},
    )
    result = second.json()["data"][0]
    assert result["status"] == "rejected"
    assert "Daily upload limit" in result["reason"]

    # jistota, že se skutečně založila jen jedna faktura, ne dvě
    assert db_session.query(Invoice).count() == 1
