from __future__ import annotations

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent import BusinessAgent
from app.auth import verify_firebase_bearer
from app.backend import BackendClient
from app.config import get_settings
from app.errors import ServiceError, normalize_exception
from app.models import ChatRequest, RecommendationsRequest
from app.recommendations import generate_and_save_recommendations

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


@app.post("/ai/chat")
def chat(payload: ChatRequest, authorization: str | None = Header(default=None)) -> JSONResponse:
    try:
        user = verify_firebase_bearer(authorization, settings.firebase_project_id)
        # El uid sale SOLO del token verificado; el del body se ignora
        context = {**(payload.context or {}), "uid": user.uid}
        response = agent.run(
            messages=[item.model_dump() for item in payload.messages],
            system=payload.system,
            context=context,
            backend_auth_token=user.bearer,
            force_classic_chat=payload.forceClassicChat,
        )
        return JSONResponse(response)
    except Exception as exc:
        err = normalize_exception(exc)
        return JSONResponse(status_code=err.status, content=err.to_payload())


@app.post("/ai/agent")
def chat_alias(payload: ChatRequest, authorization: str | None = Header(default=None)) -> JSONResponse:
    return chat(payload=payload, authorization=authorization)


@app.post("/ai/recommendations")
def recommendations(payload: RecommendationsRequest, authorization: str | None = Header(default=None)) -> JSONResponse:
    """Analiza el negocio y guarda 3-5 recomendaciones estructuradas."""
    try:
        user = verify_firebase_bearer(authorization, settings.firebase_project_id)
        if not settings.ollama_api_key:
            raise ServiceError("OLLAMA_API_KEY no definido.", status=500)

        saved = generate_and_save_recommendations(
            client=agent._get_client(),
            settings=settings,
            backend=backend_client,
            token=user.bearer,
            id_negocio=payload.idNegocio,
        )
        return JSONResponse({"data": saved, "total": len(saved)})
    except Exception as exc:
        err = normalize_exception(exc)
        return JSONResponse(status_code=err.status, content=err.to_payload())


@app.exception_handler(ServiceError)
def service_error_handler(_, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.to_payload())
