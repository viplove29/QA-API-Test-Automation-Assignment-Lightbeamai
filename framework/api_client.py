from typing import Any

import requests


class AuthApi:
    def __init__(self, client: "ApiClient") -> None:
        self._client = client

    def login(self, credentials: dict[str, str]) -> requests.Response:
        return self._client.post("/auth/login", json=credentials)


class OrdersApi:
    def __init__(self, client: "ApiClient") -> None:
        self._client = client

    def create(
        self,
        payload: dict[str, object],
        auth_headers: dict[str, str],
        correlation_id: str,
    ) -> requests.Response:
        return self._client.post(
            "/orders",
            headers={**auth_headers, "X-Correlation-ID": correlation_id},
            json=payload,
        )

    def get(self, order_id: str, auth_headers: dict[str, str]) -> requests.Response:
        return self._client.get(f"/orders/{order_id}", headers=auth_headers)

    def delete(self, order_id: str, auth_headers: dict[str, str]) -> requests.Response:
        return self._client.delete(f"/orders/{order_id}", headers=auth_headers)


class ExportsApi:
    def __init__(self, client: "ApiClient") -> None:
        self._client = client

    def create(self, auth_headers: dict[str, str]) -> requests.Response:
        return self._client.post("/exports", headers=auth_headers)

    def get(self, job_id: str, auth_headers: dict[str, str]) -> requests.Response:
        return self._client.get(f"/exports/{job_id}", headers=auth_headers)

    def download(self, job_id: str, auth_headers: dict[str, str]) -> requests.Response:
        return self._client.get(f"/exports/{job_id}/download", headers=auth_headers)


class ApiClient:
    def __init__(self, base_url: str, timeout_seconds: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})
        self.auth = AuthApi(self)
        self.orders = OrdersApi(self)
        self.exports = ExportsApi(self)

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self._request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> requests.Response:
        return self._request("DELETE", path, **kwargs)

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        return self._session.request(
            method,
            f"{self.base_url}{path}",
            timeout=self._timeout_seconds,
            **kwargs,
        )