# IA Service (Python)

Servicio de chat con agente en Python (FastAPI) que puede usar tools para consultar tu backend de negocio.

## Requisitos
- Python 3.11+

## Instalacion
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Configuracion
1. Copia `.env.example` a `.env`.
2. Completa:
- `OLLAMA_API_KEY`
- `OLLAMA_HOST` (ej: `https://ollama.com`)
- `OLLAMA_MODEL`
- `BACKEND_API_BASE_URL`

## Ejecutar
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## Endpoint principal
`POST /ai/chat`

Headers:
- `Content-Type: application/json`
- `Authorization: Bearer <FIREBASE_ID_TOKEN>` (recomendado para tools de backend)

Body:
```json
{
  "messages": [
    { "role": "user", "content": "Analiza la rentabilidad de mi negocio." }
  ],
  "context": {
    "uid": "firebase_uid",
    "idNegocio": "id_negocio",
    "year": 2026,
    "month": 3
  },
  "forceClassicChat": false
}
```

Respuesta:
```json
{
  "text": "Analisis y recomendaciones...",
  "toolCalls": [
    { "round": 1, "name": "get_live_profitability_by_business_month", "status": "ok" }
  ],
  "mode": "agent"
}
```

## Notas
- `POST /ai/agent` existe como alias de compatibilidad.
- Si Ollama Cloud devuelve error de cuota, la API intenta responder con `429` y `retry_after_seconds`.
