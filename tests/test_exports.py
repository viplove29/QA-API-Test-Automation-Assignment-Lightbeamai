from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin

import pytest
import requests

from framework.polling import wait_for_status


def create_export(
    api_client: requests.Session, base_url: str, auth_headers: dict[str, str]
) -> dict[str, Any]:
    response = api_client.post(f"{base_url}/exports", headers=auth_headers, timeout=5)
    assert response.status_code == 202, response.text
    return response.json()


def get_export_status(
    api_client: requests.Session,
    base_url: str,
    auth_headers: dict[str, str],
    job_id: str,
) -> Callable[[], requests.Response]:
    return lambda: api_client.get(
        f"{base_url}/exports/{job_id}", headers=auth_headers, timeout=5
    )


def test_create_export_returns_processing_job(
    api_client: requests.Session, base_url: str, auth_headers: dict[str, str]
) -> None:
    export_job = create_export(api_client, base_url, auth_headers)

    assert export_job["jobId"].startswith("JOB-")
    assert export_job["status"] == "PROCESSING"
    assert export_job["pollIntervalSeconds"] == 5

    status_response = get_export_status(
        api_client, base_url, auth_headers, export_job["jobId"]
    )()
    assert status_response.status_code == 200
    assert status_response.json() == {
        "jobId": export_job["jobId"],
        "status": "PROCESSING",
        "downloadUrl": None,
    }


def test_incomplete_export_cannot_be_downloaded(
    api_client: requests.Session, base_url: str, auth_headers: dict[str, str]
) -> None:
    export_job = create_export(api_client, base_url, auth_headers)

    response = api_client.get(
        f"{base_url}/exports/{export_job['jobId']}/download",
        headers=auth_headers,
        timeout=5,
    )
    assert response.status_code == 400
    assert response.json() == {"error": "Export file is not ready yet"}


@pytest.mark.slow
def test_completed_export_exposes_csv_download(
    api_client: requests.Session, base_url: str, auth_headers: dict[str, str]
) -> None:
    export_job = create_export(api_client, base_url, auth_headers)
    export_status = get_export_status(
        api_client, base_url, auth_headers, export_job["jobId"]
    )

    completed_job = wait_for_status(
        export_status,
        "COMPLETED",
        timeout_seconds=70,
        poll_interval_seconds=export_job["pollIntervalSeconds"],
    )
    assert completed_job["downloadUrl"] == f"/v1/exports/{export_job['jobId']}/download"

    download = api_client.get(
        urljoin(f"{base_url}/", completed_job["downloadUrl"]),
        headers=auth_headers,
        timeout=5,
    )
    assert download.status_code == 200
    assert download.headers["Content-Type"].startswith("text/csv")
    assert download.headers["Content-Disposition"] == 'attachment; filename="orders_report.csv"'
    assert download.text == (
        "orderId,status,totalAmount\n"
        "ORD-10001,COMPLETED,150.00\n"
        "ORD-10002,CANCELLED,45.50"
    )


def test_export_requires_authentication(
    api_client: requests.Session, base_url: str
) -> None:
    response = api_client.post(f"{base_url}/exports", timeout=5)

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized: Missing or invalid token"}


def test_unknown_export_returns_not_found(
    api_client: requests.Session, base_url: str, auth_headers: dict[str, str]
) -> None:
    for path in ("exports/JOB-00000", "exports/JOB-00000/download"):
        response = api_client.get(f"{base_url}/{path}", headers=auth_headers, timeout=5)
        assert response.status_code == 404
        assert response.json() == {"error": "Export job not found"}