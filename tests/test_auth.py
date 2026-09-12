import requests


def test_login_returns_bearer_token(api_client: requests.Session, base_url: str) -> None:
    response = api_client.post(
        f"{base_url}/auth/login",
        json={"username": "api-tester", "apiKey": "valid-key"},
        timeout=5,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["expiresIn"] == 3600


def test_login_rejects_missing_credentials(api_client: requests.Session, base_url: str) -> None:
    for payload in ({"apiKey": "valid-key"}, {"username": "api-tester"}, {}):
        response = api_client.post(f"{base_url}/auth/login", json=payload, timeout=5)

        assert response.status_code == 400
        assert response.json() == {"error": "Missing credentials"}


def test_protected_route_rejects_missing_bearer_token(
    api_client: requests.Session, base_url: str
) -> None:
    response = api_client.get(f"{base_url}/orders/not-a-real-order", timeout=5)

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized: Missing or invalid token"}