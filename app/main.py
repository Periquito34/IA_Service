from __future__ import annotations

import base64
import json

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent import BusinessAgent
from app.backend import BackendClient
from app.config import get_settings
from app.errors import ServiceError, normalize_exception
from app.models import ChatRequest

settings = get_settings()
backend_client = BackendClient(settings=settings)
agent = BusinessAgent(settings=settings, backend_client=backend_client)

app = FastAPI(title="IA Service (Python)", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "AI Service Python OK"}


def _resolve_backend_token(authorization: str | None, body_token: str | None) -> str | None:
    return authorization or body_token


def _extract_uid_from_bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    parts = token.split(".")
    if len(parts) < 2:
        return None

    payload_raw = parts[1]
    padding = "=" * ((4 - len(payload_raw) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload_raw + padding).decode("utf-8")
        payload = json.loads(decoded)
    except Exception:
        return None

    uid = payload.get("user_id") or payload.get("uid") or payload.get("sub")
    return str(uid) if uid else None


def _merge_context(payload_context: dict, authorization: str | None) -> dict:
    context = dict(payload_context or {})
    if "uid" not in context or not context.get("uid"):
        uid_from_token = _extract_uid_from_bearer(authorization)
        if uid_from_token:
            context["uid"] = uid_from_token
    return context


@app.post("/ai/chat")
def chat(payload: ChatRequest, authorization: str | None = Header(default=None)) -> JSONResponse:
    try:
        context = _merge_context(payload.context, authorization)
        response = agent.run(
            messages=[item.model_dump() for item in payload.messages],
            system=payload.system,
            context=context,
            backend_auth_token=_resolve_backend_token(authorization, payload.backendAuthToken),
            force_classic_chat=payload.forceClassicChat,
        )
        return JSONResponse(response)
    except Exception as exc:
        err = normalize_exception(exc)
        return JSONResponse(status_code=err.status, content=err.to_payload())


@app.post("/ai/agent")
def chat_alias(payload: ChatRequest, authorization: str | None = Header(default=None)) -> JSONResponse:
    return chat(payload=payload, authorization=authorization)


@app.exception_handler(ServiceError)
def service_error_handler(_, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.to_payload())
