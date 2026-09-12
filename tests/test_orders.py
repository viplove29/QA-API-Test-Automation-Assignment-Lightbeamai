from collections.abc import Callable
from typing import Any

import requests

from framework.polling import wait_for_status


def create_order(
    api_client: requests.Session,
    base_url: str,
    auth_headers: dict[str, str],
    payload: dict[str, object],
    correlation_id: str,
) -> dict[str, Any]:
    response = api_client.post(
        f"{base_url}/orders",
        headers={**auth_headers, "X-Correlation-ID": correlation_id},
        json=payload,
        timeout=5,
    )
    assert response.status_code == 202, response.text
    return response.json()


def get_order_status(
    api_client: requests.Session,
    base_url: str,
    auth_headers: dict[str, str],
    order_id: str,
) -> Callable[[], requests.Response]:
    return lambda: api_client.get(
        f"{base_url}/orders/{order_id}", headers=auth_headers, timeout=5
    )


def test_create_order_calculates_total_and_persists_details(
    api_client: requests.Session,
    base_url: str,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    payload = order_payload_factory()
    created_order = create_order(
        api_client, base_url, auth_headers, payload, correlation_id
    )

    assert created_order["orderId"].startswith("ORD-")
    assert created_order["status"] == "PENDING"
    assert created_order["totalAmount"] == 40
    assert created_order["createdAt"]

    response = get_order_status(
        api_client, base_url, auth_headers, created_order["orderId"]
    )()
    assert response.status_code == 200
    assert response.json()["customerId"] == payload["customerId"]
    assert response.json()["items"] == payload["items"]
    assert response.json()["shippingAddress"] == payload["shippingAddress"]


def test_create_order_requires_correlation_id_and_valid_payload(
    api_client: requests.Session,
    base_url: str,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    missing_header = api_client.post(
        f"{base_url}/orders",
        headers=auth_headers,
        json=order_payload_factory(),
        timeout=5,
    )
    assert missing_header.status_code == 400
    assert missing_header.json() == {"error": "Missing X-Correlation-ID header"}

    invalid_payload = api_client.post(
        f"{base_url}/orders",
        headers={**auth_headers, "X-Correlation-ID": correlation_id},
        json={"customerId": "customer-only"},
        timeout=5,
    )
    assert invalid_payload.status_code == 400
    assert invalid_payload.json() == {"error": "Invalid payload"}


def test_order_transitions_from_pending_to_processing_to_completed(
    api_client: requests.Session,
    base_url: str,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    created_order = create_order(
        api_client,
        base_url,
        auth_headers,
        order_payload_factory(),
        correlation_id,
    )
    get_status = get_order_status(
        api_client, base_url, auth_headers, created_order["orderId"]
    )

    assert get_status().json()["status"] == "PENDING"
    assert wait_for_status(get_status, "PROCESSING", timeout_seconds=8)["status"] == "PROCESSING"
    assert wait_for_status(get_status, "COMPLETED", timeout_seconds=12)["status"] == "COMPLETED"


def test_cancel_order_while_pending_preserves_cancelled_state(
    api_client: requests.Session,
    base_url: str,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    created_order = create_order(
        api_client,
        base_url,
        auth_headers,
        order_payload_factory(),
        correlation_id,
    )

    response = api_client.delete(
        f"{base_url}/orders/{created_order['orderId']}", headers=auth_headers, timeout=5
    )
    assert response.status_code == 200
    assert response.json() == {"orderId": created_order["orderId"], "status": "CANCELLED"}

    status_response = get_order_status(
        api_client, base_url, auth_headers, created_order["orderId"]
    )()
    assert status_response.json()["status"] == "CANCELLED"


def test_cancel_order_while_processing_succeeds(
    api_client: requests.Session,
    base_url: str,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    created_order = create_order(
        api_client,
        base_url,
        auth_headers,
        order_payload_factory(),
        correlation_id,
    )
    get_status = get_order_status(
        api_client, base_url, auth_headers, created_order["orderId"]
    )
    wait_for_status(get_status, "PROCESSING", timeout_seconds=8)

    response = api_client.delete(
        f"{base_url}/orders/{created_order['orderId']}", headers=auth_headers, timeout=5
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


def test_completed_order_cannot_be_cancelled(
    api_client: requests.Session,
    base_url: str,
    auth_headers: dict[str, str],
    order_payload_factory: Callable[[], dict[str, object]],
    correlation_id: str,
) -> None:
    created_order = create_order(
        api_client,
        base_url,
        auth_headers,
        order_payload_factory(),
        correlation_id,
    )
    get_status = get_order_status(
        api_client, base_url, auth_headers, created_order["orderId"]
    )
    wait_for_status(get_status, "COMPLETED", timeout_seconds=18)

    response = api_client.delete(
        f"{base_url}/orders/{created_order['orderId']}", headers=auth_headers, timeout=5
    )
    assert response.status_code == 409
    assert response.json() == {"error": "Cannot cancel completed order"}


def test_unknown_order_returns_not_found(
    api_client: requests.Session, base_url: str, auth_headers: dict[str, str]
) -> None:
    for method in (api_client.get, api_client.delete):
        response = method(
            f"{base_url}/orders/ORD-00000", headers=auth_headers, timeout=5
        )
        assert response.status_code == 404
        assert response.json() == {"error": "Order not found"}