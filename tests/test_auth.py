import base64
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser, verify_firebase_bearer
from app.errors import ServiceError
from app.main import app


def _jwt_sin_firma(payload: dict) -> str:
    """Un JWT con forma valida pero sin firma real (lo que fabricaria un atacante)."""
    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")
    return f"{b64({'alg': 'RS256', 'kid': 'x'})}.{b64(payload)}.firma-falsa"


class VerifyFirebaseBearerTest(unittest.TestCase):
    def assert_status(self, status, authorization, project_id="proyecto"):
        with self.assertRaises(ServiceError) as ctx:
            verify_firebase_bearer(authorization, project_id)
        self.assertEqual(ctx.exception.status, status)

    def test_sin_cabecera_es_401(self):
        self.assert_status(401, None)
        self.assert_status(401, "Basic abc")
        self.assert_status(401, "Bearer ")

    def test_token_mal_formado_es_401(self):
        self.assert_status(401, "Bearer no-es-un-jwt")

    def test_token_falsificado_es_401(self):
        # Antes el servicio solo decodificaba el payload sin verificar la firma
        token = _jwt_sin_firma({"user_id": "otro-usuario", "aud": "proyecto", "iss": "https://securetoken.google.com/proyecto"})
        self.assert_status(401, f"Bearer {token}")

    def test_sin_project_id_es_500(self):
        self.assert_status(500, "Bearer abc", project_id=None)


class ChatEndpointAuthTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_chat_sin_token_es_401_y_no_llama_a_la_ia(self):
        with patch("app.main.agent.run") as run:
            r = self.client.post("/ai/chat", json={"messages": [{"role": "user", "content": "hola"}]})
        self.assertEqual(r.status_code, 401)
        run.assert_not_called()

    def test_recommendations_sin_token_es_401(self):
        r = self.client.post("/ai/recommendations", json={"idNegocio": "x"})
        self.assertEqual(r.status_code, 401)

    def test_uid_del_body_se_ignora(self):
        usuario = AuthenticatedUser(uid="uid-del-token", bearer="Bearer token-real")
        with patch("app.main.verify_firebase_bearer", return_value=usuario), \
             patch("app.main.agent.run", return_value={"text": "ok", "toolCalls": [], "mode": "chat"}) as run:
            r = self.client.post("/ai/chat", headers={"Authorization": "Bearer token-real"}, json={
                "messages": [{"role": "user", "content": "hola"}],
                "context": {"uid": "uid-de-otro", "idNegocio": "neg-1"},
                "backendAuthToken": "Bearer token-de-otro",
            })
        self.assertEqual(r.status_code, 200)
        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs["context"]["uid"], "uid-del-token")
        self.assertEqual(kwargs["context"]["idNegocio"], "neg-1")
        self.assertEqual(kwargs["backend_auth_token"], "Bearer token-real")


if __name__ == "__main__":
    unittest.main()
