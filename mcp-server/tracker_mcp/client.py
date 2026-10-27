"""Thin HTTP client for the Project Tracker REST API."""

from typing import Any

import httpx


class TrackerError(Exception):
    """An API call failed; the message is safe to show to the model."""


class TrackerClient:
    def __init__(self, api_url: str, token: str, http: httpx.Client | None = None) -> None:
        self.http = http or httpx.Client(base_url=api_url.rstrip("/"), timeout=20.0)
        self.http.headers["Authorization"] = f"Bearer {token}"

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | list[tuple[str, Any]] | None = None,
    ) -> Any:
        try:
            response = self.http.request(method, f"/api{path}", json=json, params=params)
        except httpx.HTTPError as exc:
            raise TrackerError(f"Could not reach the tracker API: {exc}") from exc
        if response.status_code == 204:
            return None
        try:
            body = response.json()
        except ValueError:
            body = None
        if response.is_error:
            raise TrackerError(_error_message(response.status_code, body))
        return body

    def get(self, path: str, **params: Any) -> Any:
        clean = {k: v for k, v in params.items() if v is not None}
        return self.request("GET", path, params=clean or None)

    def post(self, path: str, body: Any = None) -> Any:
        return self.request("POST", path, json=body if body is not None else {})

    def patch(self, path: str, body: Any) -> Any:
        return self.request("PATCH", path, json=body)


def _error_message(status: int, body: Any) -> str:
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, list) and detail:
        first = detail[0]
        field = ".".join(str(p) for p in first.get("loc", [])[1:])
        detail = f"{field}: {first.get('msg')}" if field else first.get("msg")
    if status == 401:
        return "The API token was rejected (missing, revoked, or the user is deactivated)."
    return f"{detail or 'Request failed'} (HTTP {status})"
