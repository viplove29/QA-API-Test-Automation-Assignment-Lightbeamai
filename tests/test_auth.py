from framework.api_client import ApiClient

import pytest


pytestmark = pytest.mark.auth


@pytest.mark.smoke
def test_login_returns_bearer_token(api_client: ApiClient) -> None:
    response = api_client.auth.login({"username": "api-tester", "apiKey": "valid-key"})

    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["expiresIn"] == 3600


@pytest.mark.negative
def test_login_rejects_missing_credentials(api_client: ApiClient) -> None:
    for payload in ({"apiKey": "valid-key"}, {"username": "api-tester"}, {}):
        response = api_client.auth.login(payload)

        assert response.status_code == 400
        assert response.json() == {"error": "Missing credentials"}


@pytest.mark.negative
def test_protected_route_rejects_missing_bearer_token(api_client: ApiClient) -> None:
    response = api_client.orders.get("not-a-real-order", auth_headers={})

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized: Missing or invalid token"}


@pytest.mark.negative
@pytest.mark.parametrize(
    "api_request",
    [
        lambda api_client: api_client.orders.create(
            payload={"customerId": "customer-unauthorized"},
            auth_headers={},
            correlation_id="correlation-unauthorized",
        ),
        lambda api_client: api_client.orders.delete("ORD-00000", auth_headers={}),
        lambda api_client: api_client.exports.create(auth_headers={}),
        lambda api_client: api_client.exports.get("JOB-00000", auth_headers={}),
        lambda api_client: api_client.exports.download("JOB-00000", auth_headers={}),
    ],
    ids=[
        "create-order",
        "cancel-order",
        "create-export",
        "get-export-status",
        "download-export",
    ],
)
def test_protected_endpoints_require_bearer_token(api_client: ApiClient, api_request) -> None:
    response = api_request(api_client)

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized: Missing or invalid token"}