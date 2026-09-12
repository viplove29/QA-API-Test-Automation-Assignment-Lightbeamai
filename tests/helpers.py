import time
from collections.abc import Callable
from typing import Any

import requests


def wait_for_status(
    get_response: Callable[[], requests.Response],
    expected_status: str,
    timeout_seconds: float,
    poll_interval_seconds: float = 1,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_response: requests.Response | None = None

    while time.monotonic() < deadline:
        response = get_response()
        last_response = response
        if response.status_code == 200 and response.json().get("status") == expected_status:
            return response.json()
        time.sleep(poll_interval_seconds)

    response_details = (
        f"status={last_response.status_code}, body={last_response.text}"
        if last_response is not None
        else "no response received"
    )
    raise AssertionError(
        f"Timed out after {timeout_seconds}s waiting for status {expected_status!r}; {response_details}"
    )