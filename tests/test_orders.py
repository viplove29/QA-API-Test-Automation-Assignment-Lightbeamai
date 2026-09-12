from collections.abc import Callable
from typing import Any

import pytest
import requests

from framework.api_client import ApiClient
from framework.polling import wait_for_status


pytestmark = pytest.mark.orders


def create_order(
    api_client: ApiClient,
    auth_headers: dict[str, str],
    payload: dict[str, object],
    correlation_id: str,
) -> dict[str, Any]:
    response = api_client.orders.create(payload, auth_headers, correlation_id)
    assert response.status_code == 202, response.text
    return response.json()


def get_order_status(
    api_client: ApiClient,
    auth_headers: dict[str, str],
    order_id: str,
) -> Callable[[], requests.Response]:
    return lambda: api_client.orders.get(order_id, auth_headers)


@pytest.mark.smoke
def test_create_order_calculates_total_and_persists_details(
    api_client: ApiClient,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    payload = order_payload_factory()
    created_order = create_order(api_client, auth_headers, payload, correlation_id)

    assert created_order["orderId"].startswith("ORD-")
    assert created_order["status"] == "PENDING"
    assert created_order["totalAmount"] == 40
    assert created_order["createdAt"]

    response = get_order_status(api_client, auth_headers, created_order["orderId"])()
    assert response.status_code == 200
    assert response.json()["customerId"] == payload["customerId"]
    assert response.json()["items"] == payload["items"]
    assert response.json()["shippingAddress"] == payload["shippingAddress"]


@pytest.mark.negative
def test_create_order_requires_correlation_id_and_valid_payload(
    api_client: ApiClient,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    missing_header = api_client.orders.create(order_payload_factory(), auth_headers, "")
    assert missing_header.status_code == 400
    assert missing_header.json() == {"error": "Missing X-Correlation-ID header"}

    invalid_payload = api_client.orders.create(
        {"customerId": "customer-only"}, auth_headers, correlation_id
    )
    assert invalid_payload.status_code == 400
    assert invalid_payload.json() == {"error": "Invalid payload"}


@pytest.mark.lifecycle
def test_order_transitions_from_pending_to_processing_to_completed(
    api_client: ApiClient,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    created_order = create_order(
        api_client,
        auth_headers,
        order_payload_factory(),
        correlation_id,
    )
    get_status = get_order_status(api_client, auth_headers, created_order["orderId"])

    assert get_status().json()["status"] == "PENDING"
    assert wait_for_status(get_status, "PROCESSING", timeout_seconds=8)["status"] == "PROCESSING"
    assert wait_for_status(get_status, "COMPLETED", timeout_seconds=12)["status"] == "COMPLETED"


@pytest.mark.lifecycle
def test_cancel_order_while_pending_preserves_cancelled_state(
    api_client: ApiClient,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    created_order = create_order(
        api_client,
        auth_headers,
        order_payload_factory(),
        correlation_id,
    )

    response = api_client.orders.delete(created_order["orderId"], auth_headers)
    assert response.status_code == 200
    assert response.json() == {"orderId": created_order["orderId"], "status": "CANCELLED"}

    status_response = get_order_status(api_client, auth_headers, created_order["orderId"])()
    assert status_response.json()["status"] == "CANCELLED"


@pytest.mark.lifecycle
def test_cancel_order_while_processing_succeeds(
    api_client: ApiClient,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    created_order = create_order(
        api_client,
        auth_headers,
        order_payload_factory(),
        correlation_id,
    )
    get_status = get_order_status(api_client, auth_headers, created_order["orderId"])
    wait_for_status(get_status, "PROCESSING", timeout_seconds=8)

    response = api_client.orders.delete(created_order["orderId"], auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


@pytest.mark.lifecycle
@pytest.mark.negative
def test_completed_order_cannot_be_cancelled(
    api_client: ApiClient,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    created_order = create_order(
        api_client,
        auth_headers,
        order_payload_factory(),
        correlation_id,
    )
    get_status = get_order_status(api_client, auth_headers, created_order["orderId"])
    wait_for_status(get_status, "COMPLETED", timeout_seconds=18)

    response = api_client.orders.delete(created_order["orderId"], auth_headers)
    assert response.status_code == 409
    assert response.json() == {"error": "Cannot cancel completed order"}


@pytest.mark.negative
def test_unknown_order_returns_not_found(
    api_client: ApiClient, auth_headers: dict[str, str]
) -> None:
    for method in (api_client.orders.get, api_client.orders.delete):
        response = method("ORD-00000", auth_headers)
        assert response.status_code == 404
        assert response.json() == {"error": "Order not found"}