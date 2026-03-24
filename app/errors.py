from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ServiceError(Exception):
    message: str
    status: int = 500
    details: Any = None
    retry_after_seconds: int | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error": self.message, "details": self.details}
        if self.retry_after_seconds is not None:
            payload["retry_after_seconds"] = self.retry_after_seconds
        return payload


def _parse_status_from_message(message: str) -> int | None:
    match = re.search(r"got status:\s*(\d{3})", message, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _extract_json_block(message: str) -> Any:
    start = message.find("{")
    if start < 0:
        return None
    candidate = message[start:].strip()
    try:
        return json.loads(candidate)
    except Exception:
        return None


def _extract_retry_after_seconds(message: str, details: Any) -> int | None:
    retry_details = None
    if isinstance(details, dict):
        error_obj = details.get("error")
        if isinstance(error_obj, dict):
            maybe_list = error_obj.get("details")
            if isinstance(maybe_list, list):
                for item in maybe_list:
                    if (
                        isinstance(item, dict)
                        and item.get("@type") == "type.googleapis.com/google.rpc.RetryInfo"
                    ):
                        retry_details = item
                        break

    delay = retry_details.get("retryDelay") if isinstance(retry_details, dict) else None
    if isinstance(delay, str):
        cleaned = re.sub(r"[^0-9]", "", delay)
        if cleaned:
            return int(cleaned)

    retry_match = re.search(r"retry in\s*([\d.]+)s", message, re.IGNORECASE)
    if retry_match:
        return int(float(retry_match.group(1)) + 0.9999)
    return None


def normalize_exception(exc: Exception) -> ServiceError:
    if isinstance(exc, ServiceError):
        return exc

    message = str(exc) if str(exc) else "Internal Server Error"
    json_details = _extract_json_block(message)

    status = (
        getattr(exc, "status", None)
        or getattr(exc, "code", None)
        or _parse_status_from_message(message)
        or (
            json_details.get("error", {}).get("code")
            if isinstance(json_details, dict)
            else None
        )
        or 500
    )
    status = int(status)

    parsed_message = (
        json_details.get("error", {}).get("message")
        if isinstance(json_details, dict)
        else None
    )

    retry_after_seconds = _extract_retry_after_seconds(message, json_details)

    return ServiceError(
        message=parsed_message or message,
        status=status,
        details=json_details,
        retry_after_seconds=retry_after_seconds,
    )

