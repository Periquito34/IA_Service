from __future__ import annotations

from dataclasses import dataclass

import cachecontrol
import requests
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.errors import ServiceError

# Las claves publicas de Google se cachean segun sus cabeceras HTTP (no se descargan en cada peticion)
_google_request = google_requests.Request(session=cachecontrol.CacheControl(requests.Session()))


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    bearer: str  # "Bearer <token>" para reenviarlo al backend


def verify_firebase_bearer(authorization: str | None, project_id: str | None) -> AuthenticatedUser:
    """Verifica la firma, la expiracion, el emisor y la audiencia del Firebase ID token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise ServiceError("Authorization: Bearer <token> es requerido.", status=401)
    if not project_id:
        raise ServiceError("FIREBASE_PROJECT_ID no configurado en el servicio de IA.", status=500)

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise ServiceError("Authorization: Bearer <token> es requerido.", status=401)

    try:
        claims = id_token.verify_firebase_token(token, _google_request, audience=project_id)
    except ValueError as exc:
        raise ServiceError("Token invalido o expirado. Inicia sesion de nuevo.", status=401) from exc
    except Exception as exc:  # noqa: BLE001 - p. ej. sin red para descargar las claves publicas
        raise ServiceError("No se pudo verificar la sesion. Intenta de nuevo.", status=503) from exc

    uid = (claims or {}).get("user_id") or (claims or {}).get("sub")
    if not uid:
        raise ServiceError("Token sin usuario.", status=401)

    return AuthenticatedUser(uid=str(uid), bearer=f"Bearer {token}")
