from __future__ import annotations

import time
from typing import Any

import requests

from app.config import Settings
from app.errors import ServiceError


class BackendClient:
    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.backend_api_base_url.rstrip("/")
        self._timeout = settings.backend_timeout_seconds

    def _build_url(self, path: str) -> str:
        normalized_path = "/" + path.lstrip("/")

        # Evita URLs tipo /api/api/... cuando el base_url ya incluye /api
        # y las tools envian paths absolutos bajo /api.
        if self._base_url.endswith("/api") and normalized_path.startswith("/api/"):
            normalized_path = normalized_path[len("/api") :]

        return f"{self._base_url}{normalized_path}"

    @staticmethod
    def _ensure_bearer_token(auth_token: str | None) -> str:
        if not auth_token:
            raise ServiceError(
                message="Authorization: Bearer <token> es requerido para tools de backend.",
                status=400,
            )
        return auth_token if auth_token.startswith("Bearer ") else f"Bearer {auth_token}"

    def request(
        self,
        method: str,
        path: str,
        auth_token: str | None,
        json_body: dict[str, Any] | None = None,
        treat_404_as_no_data: bool = False,
    ) -> dict[str, Any]:
        bearer = self._ensure_bearer_token(auth_token)
        url = self._build_url(path)
        headers = {
            "Accept": "application/json",
            "Authorization": bearer,
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        started_at = time.perf_counter()
        print(f"[BACKEND_TOOL] -> {method.upper()} {url}")

        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json_body,
                timeout=self._timeout,
            )
        except requests.Timeout as exc:
            raise ServiceError(
                message=f"Timeout llamando backend en {self._timeout}s",
                status=502,
                details={"method": method, "path": path},
            ) from exc
        except requests.RequestException as exc:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            print(f"[BACKEND_TOOL] !! {method.upper()} {url} NETWORK_ERROR after {elapsed_ms}ms :: {exc}")
            raise ServiceError(
                message=f"No se pudo consultar backend: {exc}",
                status=502,
                details={"method": method, "path": path},
            ) from exc

        data: Any = None
        raw_text = response.text or ""
        if raw_text:
            try:
                data = response.json()
            except Exception:
                data = {"raw": raw_text}

        if not response.ok:
            if response.status_code == 404 and treat_404_as_no_data:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                print(f"[BACKEND_TOOL] <- {method.upper()} {url} STATUS=404 noData=true in {elapsed_ms}ms")
                return {
                    "ok": True,
                    "noData": True,
                    "status": response.status_code,
                    "endpoint": path,
                    "data": data,
                }

            message = None
            if isinstance(data, dict):
                message = data.get("message") or data.get("error")
            message = message or f"Backend respondio {response.status_code} en {method} {path}"
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            print(f"[BACKEND_TOOL] <- {method.upper()} {url} STATUS={response.status_code} ERROR in {elapsed_ms}ms")
            raise ServiceError(
                message=message,
                status=response.status_code,
                details={"backendResponse": data, "endpoint": path},
            )

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        print(f"[BACKEND_TOOL] <- {method.upper()} {url} STATUS={response.status_code} noData=false in {elapsed_ms}ms")
        return {
            "ok": True,
            "noData": False,
            "status": response.status_code,
            "endpoint": path,
            "data": data,
        }
