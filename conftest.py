import os
from collections.abc import Callable
from uuid import uuid4

import pytest
import requests


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("BASE_URL", "http://localhost:3000/v1").rstrip("/")


@pytest.fixture(scope="session")
def api_client(base_url: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    try:
        response = session.post(
            f"{base_url}/auth/login",
            json={"username": "health-check", "apiKey": "health-check"},
            timeout=5,
        )
    except requests.ConnectionError as error:
        pytest.fail(
            f"Mock API is unavailable at {base_url}. Start it with 'npm install' then 'npm run start'. {error}",
            pytrace=False,
        )

    if response.status_code != 200:
        pytest.fail(
            f"Mock API health check at {base_url}/auth/login returned {response.status_code}: {response.text}",
            pytrace=False,
        )
    return session


@pytest.fixture(scope="session")
def auth_headers(api_client: requests.Session, base_url: str) -> dict[str, str]:
    response = api_client.post(
        f"{base_url}/auth/login",
        json={"username": "qa-automation", "apiKey": "test-api-key"},
        timeout=5,
    )
    assert response.status_code == 200
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def order_payload_factory() -> Callable[[], dict[str, object]]:
    def create_order_payload() -> dict[str, object]:
        return {
            "customerId": f"customer-{uuid4()}",
            "items": [
                {"sku": "widget-1", "quantity": 2, "unitPrice": 12.5},
                {"sku": "widget-2", "quantity": 3, "unitPrice": 5},
            ],
            "shippingAddress": {
                "line1": "100 Test Street",
                "city": "Automation City",
                "postalCode": "10001",
            },
        }

    return create_order_payload


@pytest.fixture
def correlation_id() -> str:
    return str(uuid4())


def pytest_html_report_title(report: object) -> None:
    report.title = "QA API Automation Report"