from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _to_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except ValueError:
        return default


DEFAULT_ALLOWED_ORIGINS = (
    "https://app-emprendedores-movil2.vercel.app",
    "http://localhost:8100",
    "http://127.0.0.1:8100",
    "capacitor://localhost",
    "https://localhost",
    "http://localhost",
)


@dataclass(frozen=True)
class Settings:
    ollama_api_key: str | None
    ollama_host: str
    ollama_model: str
    backend_api_base_url: str
    backend_timeout_seconds: int
    agent_max_tool_rounds: int
    host: str
    port: int
    allowed_origins: list[str]
    firebase_project_id: str | None


def get_settings() -> Settings:
    # Backward-compatible fallback:
    # si alguien puso la key de Ollama por error en GOOGLE_API_KEY, igual funciona.
    api_key = os.getenv("OLLAMA_API_KEY") or os.getenv("GOOGLE_API_KEY")
    # Web publicada, desarrollo local y app Android (Capacitor). Se sobrescribe con ALLOWED_ORIGINS.
    origins_csv = os.getenv("ALLOWED_ORIGINS", ",".join(DEFAULT_ALLOWED_ORIGINS))
    origins = [item.strip() for item in origins_csv.split(",") if item.strip()]

    return Settings(
        ollama_api_key=api_key,
        ollama_host=os.getenv("OLLAMA_HOST", "https://ollama.com"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3"),
        backend_api_base_url=os.getenv("BACKEND_API_BASE_URL", "http://localhost:3000"),
        backend_timeout_seconds=_to_int(os.getenv("BACKEND_TIMEOUT_SECONDS"), 12),
        agent_max_tool_rounds=_to_int(os.getenv("AGENT_MAX_TOOL_ROUNDS"), 6),
        host=os.getenv("HOST", "0.0.0.0"),
        port=_to_int(os.getenv("PORT"), 8080),
        allowed_origins=origins or list(DEFAULT_ALLOWED_ORIGINS),
        firebase_project_id=os.getenv("FIREBASE_PROJECT_ID"),
    )
