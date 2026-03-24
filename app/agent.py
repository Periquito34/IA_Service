from __future__ import annotations

import json
from typing import Any

from ollama import Client

from app.backend import BackendClient
from app.config import Settings
from app.errors import ServiceError
from app.tools import TOOL_DECLARATIONS, execute_tool_call

BASE_SYSTEM_PROMPT = """Eres un asesor financiero para emprendedores en una app de gestion de negocios.
Tu trabajo es convertir datos del negocio en analisis claro, practico y accionable.

Contexto del dominio:
- El usuario puede registrar productos (precioVenta, costoProduccion, stock), ventas, transacciones, gastos fijos y rentabilidad.
- Formulas clave:
  - totalVenta = cantidadVendida * precioUnitario
  - totalCostoProduccion = cantidadVendida * costoProduccion
  - utilidad = totalVenta - totalCostoProduccion
  - rentabilidadNeta = ingresos - (costosVariables + gastosFijos + egresos)

Reglas de operacion con tools:
1) Antes de dar conclusiones numericas, consulta tools relevantes.
2) No inventes datos ni metricas. Si falta informacion, dilo explicitamente.
3) Si una tool devuelve 404 en listados, interpretalo como "sin datos" (no como falla fatal).
4) Si no hay idNegocio, intenta resolverlo con uid (negocios del usuario). Si aun falta contexto, pide solo lo minimo necesario.
5) Usa la menor cantidad de tools posible, pero suficientes para sostener la conclusion.
6) Si hay recomendaciones claras y existe idNegocio, guarda una recomendacion con la tool correspondiente.
7) Si una tool devuelve error o falta contexto, no concluyas que "no hay datos"; explica la limitacion y pide solo el dato faltante.

Estrategia sugerida por tipo de pregunta:
- Rentabilidad mensual: get_live_profitability_by_business_month + get_sales_summary_by_business_month + get_egresos_summary_by_business_month (+ gastos fijos si aplica).
- Ventas/productos: get_products_by_business + get_product_sales_summary_by_month o get_product_sales_history.
- Control de gastos/caja: get_transactions_by_business + get_egresos_by_business_month + get_fixed_expenses_by_business.

Formato de respuesta al usuario:
1) Resumen ejecutivo (2-4 lineas).
2) Hallazgos clave (bullets, con numeros cuando existan).
3) Recomendaciones priorizadas (Alta/Media/Baja) con impacto esperado.
4) Riesgos o alertas.
5) Proximo paso concreto para esta semana.

Estilo:
- Escribe en espanol claro, sin tecnicismos innecesarios.
- Se directo, empatico y orientado a accion.
- Si usas supuestos, declaralos de forma breve.
"""


def _obj_get(obj: Any, *path: str) -> Any:
    current = obj
    for key in path:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(key)
        else:
            current = getattr(current, key, None)
    return current


def _to_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in messages:
        role = item.get("role", "user")
        content = str(item.get("content", ""))
        output.append({"role": role, "content": content})
    return output


def _build_system_prompt(system: str | None, context: dict[str, Any]) -> str:
    context_block = ""
    if context:
        context_block = f"\nContexto operativo:\n{context}\n"
    custom = f"\n{system.strip()}\n" if system else ""
    return f"{BASE_SYSTEM_PROMPT}{custom}{context_block}"


def _to_ollama_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": declaration["name"],
                "description": declaration.get("description", ""),
                "parameters": declaration.get("parameters", {"type": "object"}),
            },
        }
        for declaration in TOOL_DECLARATIONS
    ]


def _extract_text_from_response(response: Any) -> str:
    content = _obj_get(response, "message", "content")
    if content is None:
        return ""
    return str(content)


def _safe_parse_arguments(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _normalize_tool_calls(message: Any) -> list[dict[str, Any]]:
    raw_calls = _obj_get(message, "tool_calls") or []
    normalized: list[dict[str, Any]] = []
    for call in raw_calls:
        function_name = _obj_get(call, "function", "name")
        if not function_name:
            continue
        normalized.append(
            {
                "type": _obj_get(call, "type") or "function",
                "function": {
                    "name": str(function_name),
                    "arguments": _safe_parse_arguments(_obj_get(call, "function", "arguments")),
                },
            }
        )
    return normalized


def _message_to_dict(message: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"role": _obj_get(message, "role") or "assistant"}
    content = _obj_get(message, "content")
    if content is not None:
        data["content"] = content
    thinking = _obj_get(message, "thinking")
    if thinking:
        data["thinking"] = thinking
    tool_calls = _normalize_tool_calls(message)
    if tool_calls:
        data["tool_calls"] = tool_calls
    return data


class BusinessAgent:
    def __init__(self, settings: Settings, backend_client: BackendClient) -> None:
        self._settings = settings
        self._backend = backend_client
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            headers = {}
            if self._settings.ollama_api_key:
                headers["Authorization"] = f"Bearer {self._settings.ollama_api_key}"
            self._client = Client(host=self._settings.ollama_host, headers=headers or None)
        return self._client

    def run(
        self,
        *,
        messages: list[dict[str, Any]],
        system: str | None,
        context: dict[str, Any],
        backend_auth_token: str | None,
        force_classic_chat: bool = False,
    ) -> dict[str, Any]:
        if not messages:
            raise ServiceError("messages[] requerido", status=400)
        if not self._settings.ollama_api_key:
            raise ServiceError("OLLAMA_API_KEY no definido.", status=500)

        client = self._get_client()
        chat_messages: list[dict[str, Any]] = [
            {"role": "system", "content": _build_system_prompt(system, context)},
            *_to_messages(messages),
        ]

        if force_classic_chat:
            response = client.chat(
                model=self._settings.ollama_model,
                messages=chat_messages,
                stream=False,
            )
            return {
                "text": _extract_text_from_response(response),
                "toolCalls": [],
                "mode": "chat",
            }

        tools = _to_ollama_tools()
        tool_calls_trace: list[dict[str, Any]] = []

        for round_index in range(self._settings.agent_max_tool_rounds):
            response = client.chat(
                model=self._settings.ollama_model,
                messages=chat_messages,
                tools=tools,
                stream=False,
            )

            assistant_message = _obj_get(response, "message") or {}
            assistant_dict = _message_to_dict(assistant_message)
            chat_messages.append(assistant_dict)

            tool_calls = _normalize_tool_calls(assistant_message)
            if not tool_calls:
                text = _extract_text_from_response(response)
                if not text:
                    raise ServiceError(
                        "El agente no devolvio texto ni llamadas a tools.",
                        status=502,
                    )
                return {"text": text, "toolCalls": tool_calls_trace, "mode": "agent"}

            for call in tool_calls:
                function = call.get("function", {})
                name = function.get("name")
                args = function.get("arguments", {})
                if not name:
                    continue

                try:
                    output = execute_tool_call(
                        name=name,
                        args=args,
                        context=context,
                        backend_auth_token=backend_auth_token,
                        backend_client=self._backend,
                    )
                    tool_calls_trace.append(
                        {"round": round_index + 1, "name": name, "status": "ok"}
                    )
                    tool_payload = {"output": output}
                except Exception as exc:
                    message = str(exc) or "Error ejecutando tool"
                    status = int(getattr(exc, "status", 500))
                    details = getattr(exc, "details", None)
                    tool_calls_trace.append(
                        {
                            "round": round_index + 1,
                            "name": name,
                            "status": "error",
                            "error": message,
                        }
                    )
                    tool_payload = {"error": {"message": message, "status": status, "details": details}}

                chat_messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps(tool_payload, ensure_ascii=False),
                    }
                )

        raise ServiceError(
            f"El agente supero el limite de rondas de tools ({self._settings.agent_max_tool_rounds}).",
            status=502,
            details={"toolCalls": tool_calls_trace},
        )

