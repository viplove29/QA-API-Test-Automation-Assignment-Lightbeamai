from collections.abc import Callable
from typing import Any

import pytest
import requests

from framework.api_client import ApiClient
from framework.polling import wait_for_status


pytestmark = pytest.mark.exports


def create_export(
    api_client: ApiClient, auth_headers: dict[str, str]
) -> dict[str, Any]:
    response = api_client.exports.create(auth_headers)
    assert response.status_code == 202, response.text
    return response.json()


def get_export_status(
    api_client: ApiClient,
    auth_headers: dict[str, str],
    job_id: str,
) -> Callable[[], requests.Response]:
    return lambda: api_client.exports.get(job_id, auth_headers)


@pytest.mark.smoke
def test_create_export_returns_processing_job(
    api_client: ApiClient, auth_headers: dict[str, str]
) -> None:
    export_job = create_export(api_client, auth_headers)

    assert export_job["jobId"].startswith("JOB-")
    assert export_job["status"] == "PROCESSING"
    assert export_job["pollIntervalSeconds"] == 5

    status_response = get_export_status(api_client, auth_headers, export_job["jobId"])()
    assert status_response.status_code == 200
    assert status_response.json() == {
        "jobId": export_job["jobId"],
        "status": "PROCESSING",
        "downloadUrl": None,
    }


@pytest.mark.negative
def test_incomplete_export_cannot_be_downloaded(
    api_client: ApiClient, auth_headers: dict[str, str]
) -> None:
    export_job = create_export(api_client, auth_headers)

    response = api_client.exports.download(export_job["jobId"], auth_headers)
    assert response.status_code == 400
    assert response.json() == {"error": "Export file is not ready yet"}


@pytest.mark.slow
@pytest.mark.lifecycle
def test_completed_export_exposes_csv_download(
    api_client: ApiClient, auth_headers: dict[str, str]
) -> None:
    export_job = create_export(api_client, auth_headers)
    export_status = get_export_status(api_client, auth_headers, export_job["jobId"])

    completed_job = wait_for_status(
        export_status,
        "COMPLETED",
        timeout_seconds=70,
        poll_interval_seconds=export_job["pollIntervalSeconds"],
    )
    assert completed_job["downloadUrl"] == f"/v1/exports/{export_job['jobId']}/download"

    download = api_client.exports.download(export_job["jobId"], auth_headers)
    assert download.status_code == 200
    assert download.headers["Content-Type"].startswith("text/csv")
    assert download.headers["Content-Disposition"] == 'attachment; filename="orders_report.csv"'
    assert download.text == (
        "orderId,status,totalAmount\n"
        "ORD-10001,COMPLETED,150.00\n"
        "ORD-10002,CANCELLED,45.50"
    )


@pytest.mark.negative
def test_export_requires_authentication(api_client: ApiClient) -> None:
    response = api_client.exports.create({})

    assert response.status_code == 401
    assert response.json() == {"error": "Unauthorized: Missing or invalid token"}


@pytest.mark.negative
def test_unknown_export_returns_not_found(
    api_client: ApiClient, auth_headers: dict[str, str]
) -> None:
    for method in (api_client.exports.get, api_client.exports.download):
        response = method("JOB-00000", auth_headers)
        assert response.status_code == 404
        assert response.json() == {"error": "Export job not found"}