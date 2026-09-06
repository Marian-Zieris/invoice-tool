"""Pokrývá K2 (rate limiting) a základní auth flow - přesně ty věci, které
audit označil jako kriticky rozbité (login šel neomezeně zkoušet)."""


def _register(client, admin_headers, email="customer@example.com", password="testpass123"):
    return client.post(
        "/auth/register",
        headers=admin_headers,
        json={"email": email, "password": password},
    )


def test_register_requires_admin_key(client):
    response = client.post("/auth/register", json={"email": "x@example.com", "password": "testpass123"})
    assert response.status_code == 401


def test_register_rejects_weak_password(client, admin_headers):
    response = client.post(
        "/auth/register",
        headers=admin_headers,
        json={"email": "x@example.com", "password": "short"},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "weak_password"


def test_register_then_login_succeeds(client, admin_headers):
    register_response = _register(client, admin_headers)
    assert register_response.status_code == 200
    assert register_response.json()["data"]["access_token"]

    login_response = client.post(
        "/auth/login", json={"email": "customer@example.com", "password": "testpass123"}
    )
    assert login_response.status_code == 200
    assert login_response.json()["data"]["access_token"]


def test_login_wrong_password_returns_401(client, admin_headers):
    _register(client, admin_headers)
    response = client.post(
        "/auth/login", json={"email": "customer@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "invalid_credentials"


def test_login_is_rate_limited_after_five_failed_attempts(client, admin_headers):
    _register(client, admin_headers)

    statuses = []
    for _ in range(6):
        response = client.post(
            "/auth/login", json={"email": "customer@example.com", "password": "wrong-password"}
        )
        statuses.append(response.status_code)

    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429


def test_successful_login_resets_rate_limit_counter(client, admin_headers):
    _register(client, admin_headers)

    for _ in range(4):
        client.post("/auth/login", json={"email": "customer@example.com", "password": "wrong-password"})

    ok_response = client.post(
        "/auth/login", json={"email": "customer@example.com", "password": "testpass123"}
    )
    assert ok_response.status_code == 200

    # Po úspěšném loginu má počítadlo pro tuhle kombinaci IP+email začínat od
    # nuly znovu - dalších 5 špatných pokusů musí projít jako 401, ne 429.
    after_reset_statuses = [
        client.post("/auth/login", json={"email": "customer@example.com", "password": "wrong-password"}).status_code
        for _ in range(5)
    ]
    assert after_reset_statuses == [401, 401, 401, 401, 401]
