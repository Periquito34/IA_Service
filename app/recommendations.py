from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.backend import BackendClient
from app.config import Settings
from app.errors import ServiceError

PRIORIDADES = ("alta", "media", "baja")
TIPOS = ("precios", "costos", "inventario", "ventas", "gastos", "rentabilidad", "general")
MAX_RECOMENDACIONES = 5
MAX_INTENTOS = 2

RECOMMENDATIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "recomendaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "mensaje": {"type": "string"},
                    "prioridad": {"type": "string", "enum": list(PRIORIDADES)},
                    "impacto": {"type": "string"},
                    "tipo": {"type": "string", "enum": list(TIPOS)},
                },
                "required": ["titulo", "mensaje", "prioridad", "impacto", "tipo"],
            },
        }
    },
    "required": ["recomendaciones"],
}

SYSTEM_PROMPT = """Eres un asesor financiero para emprendedores. Recibes un resumen en JSON con los datos
reales de un negocio y devuelves entre 3 y 5 recomendaciones concretas y accionables.

Reglas:
- Usa SOLO los datos del resumen. No inventes cifras; si citas un numero, debe salir del resumen.
- Prioriza problemas reales: margenes negativos, stock bajo, gastos fijos altos o pendientes,
  meses con perdidas, caidas de ventas, productos que no se venden.
- No repitas recomendaciones de "recomendacionesPrevias" (ni las aplicadas ni las descartadas).
- Nunca sugieras un precio por debajo de costoProduccion: para liquidar stock, el descuento debe
  dejar el precio por encima del costo. Comprueba los numeros antes de proponerlos.
- titulo: maximo 60 caracteres. mensaje: 2-3 frases con la accion concreta y el porque.
- impacto: efecto esperado en pocas palabras (p. ej. "+8% de margen en Camiseta").
- prioridad: "alta" si afecta perdidas o caja, "media" si mejora resultados, "baja" si es optimizacion.
- tipo: el tema principal. "precios" (precio de venta), "costos" (costo de produccion), "inventario" (stock),
  "ventas" (volumen o promocion), "gastos" (gastos fijos o egresos), "rentabilidad" (margen o resultado global).
  Usa "general" solo si no encaja en ninguno.
- Escribe en espanol, sin markdown.
- La moneda es el peso colombiano (COP). Escribe los montos con el signo $ y punto como separador de miles, sin decimales (por ejemplo $1.234.567). Nunca uses ¢ ni otras monedas.
Responde unicamente con el JSON pedido."""


def _to_number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number == number else 0.0  # descarta NaN


def _to_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, dict):
        seconds = value.get("_seconds", value.get("seconds"))
        if isinstance(seconds, (int, float)):
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _month_key(value: Any) -> str | None:
    date = _to_datetime(value)
    return f"{date.year:04d}-{date.month:02d}" if date else None


def _es_egreso(tipo: Any) -> bool:
    return tipo is True or tipo == 1 or tipo in ("expense", "egreso")


def _es_ingreso(tipo: Any) -> bool:
    return tipo is False or tipo == 0 or tipo in ("income", "ingreso")


def build_snapshot(
    *,
    balance: dict[str, Any] | None,
    products: list[dict[str, Any]],
    sales_by_product: dict[str, list[dict[str, Any]]],
    transactions: list[dict[str, Any]],
    fixed_expenses: list[dict[str, Any]],
    previous_recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Resumen compacto del negocio para el modelo (solo datos reales, sin calculos de la IA)."""
    monthly: dict[str, dict[str, float]] = {}

    def month(key: str) -> dict[str, float]:
        return monthly.setdefault(key, {"ventas": 0.0, "utilidadVentas": 0.0, "otrosIngresos": 0.0, "egresos": 0.0})

    productos = []
    for product in products:
        product_id = product.get("idProducto") or product.get("id")
        precio = _to_number(product.get("precioVenta"))
        costo = _to_number(product.get("costoProduccion"))
        ventas = sales_by_product.get(product_id, []) if product_id else []

        unidades = 0.0
        for venta in ventas:
            unidades += _to_number(venta.get("cantidadVendida"))
            key = _month_key(venta.get("fechaVenta") or venta.get("createdAt"))
            if key:
                month(key)["ventas"] += _to_number(venta.get("totalVenta"))
                month(key)["utilidadVentas"] += _to_number(venta.get("utilidad"))

        productos.append({
            "nombre": product.get("nombreProducto") or product.get("nombre") or "Producto",
            "precioVenta": precio,
            "costoProduccion": costo,
            "margenPorcentaje": round((precio - costo) / precio * 100, 1) if precio > 0 else 0.0,
            "stock": _to_number(product.get("stock")),
            "unidadesVendidas": int(unidades),
        })

    for transaction in transactions:
        key = _month_key(transaction.get("fechaISO") or transaction.get("fecha") or transaction.get("date"))
        if not key:
            continue
        tipo = transaction.get("tipoOriginal", transaction.get("tipo"))
        if _es_ingreso(tipo):
            month(key)["otrosIngresos"] += _to_number(transaction.get("monto"))
        elif _es_egreso(tipo):
            month(key)["egresos"] += _to_number(transaction.get("monto"))

    gastos = [
        {
            "nombre": gasto.get("nombreGasto") or "Gasto fijo",
            "costo": _to_number(gasto.get("costoGasto")),
            "pagado": bool(gasto.get("pagado")),
            "recurrencia": gasto.get("recurrencia") or "",
        }
        for gasto in fixed_expenses
    ]

    return {
        "fechaAnalisis": datetime.now(timezone.utc).date().isoformat(),
        "balanceGeneral": balance or {},
        "productos": productos,
        "resumenMensual": dict(sorted(monthly.items())[-12:]),
        "gastosFijos": {
            "totalMensual": sum(g["costo"] for g in gastos),
            "pendientes": sum(1 for g in gastos if not g["pagado"]),
            "detalle": gastos,
        },
        "recomendacionesPrevias": [
            {"titulo": rec.get("titulo") or str(rec.get("mensaje") or "")[:80], "estado": rec.get("estado") or "pendiente"}
            for rec in previous_recommendations[:15]
        ],
    }


def _parse_json(text: str) -> Any:
    """JSON del texto completo o, si trae texto alrededor, del primer bloque [...] o {...}."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
    if not starts:
        return None
    start = min(starts)
    end = text.rfind("]" if text[start] == "[" else "}")
    if end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def normalize_recommendations(raw: Any) -> list[dict[str, str]]:
    """Valida la respuesta del modelo. Descarta lo que no tenga titulo o mensaje."""
    if isinstance(raw, str):
        raw = _parse_json(raw)

    # El modelo puede devolver {"recomendaciones": [...]} o, ignorando el esquema, la lista directamente
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get("recomendaciones")
    else:
        items = None
    if not isinstance(items, list):
        return []

    result: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        titulo = str(item.get("titulo") or "").strip()
        mensaje = str(item.get("mensaje") or "").strip()
        if not titulo or not mensaje:
            continue
        prioridad = str(item.get("prioridad") or "").strip().lower()
        tipo = str(item.get("tipo") or "").strip().lower()
        result.append({
            "titulo": titulo[:80],
            "mensaje": mensaje,
            "prioridad": prioridad if prioridad in PRIORIDADES else "media",
            "impacto": str(item.get("impacto") or "").strip(),
            "tipo": tipo if tipo in TIPOS else "general",
        })
        if len(result) == MAX_RECOMENDACIONES:
            break
    return result


def _data(result: dict[str, Any]) -> Any:
    payload = result.get("data")
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _as_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def collect_business_data(backend: BackendClient, token: str, id_negocio: str) -> dict[str, Any]:
    def get(path: str) -> Any:
        return _data(backend.request("GET", path, auth_token=token, treat_404_as_no_data=True))

    products = _as_list(get(f"/api/product/business/{id_negocio}"))
    sales_by_product = {}
    for product in products:
        product_id = product.get("idProducto") or product.get("id")
        if product_id:
            sales_by_product[product_id] = _as_list(get(f"/api/product-sold/ventas/producto/{product_id}"))

    balance = get(f"/api/balance-general/{id_negocio}")
    return {
        "balance": balance if isinstance(balance, dict) else None,
        "products": products,
        "sales_by_product": sales_by_product,
        "transactions": _as_list(get(f"/api/transaction/negocios/{id_negocio}/transacciones")),
        "fixed_expenses": _as_list(get(f"/api/gasto-fijo/business/{id_negocio}")),
        "previous_recommendations": _as_list(get(f"/api/ai-recommendation/negocio/{id_negocio}")),
    }


def generate_and_save_recommendations(
    *,
    client: Any,
    settings: Settings,
    backend: BackendClient,
    token: str,
    id_negocio: str,
) -> list[dict[str, Any]]:
    snapshot = build_snapshot(**collect_business_data(backend, token, id_negocio))
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)},
    ]

    # Un reintento: Ollama Cloud a veces corta la conexion o el modelo devuelve algo no parseable
    recommendations: list[dict[str, str]] = []
    last_error: Exception | None = None
    for attempt in range(1, MAX_INTENTOS + 1):
        try:
            response = client.chat(
                model=settings.ollama_model,
                messages=messages,
                format=RECOMMENDATIONS_SCHEMA,
                stream=False,
            )
        except ConnectionError as exc:
            last_error = exc
            print(f"[RECOMMENDATIONS] intento {attempt}: error de conexion con Ollama: {exc}")
            continue

        content = getattr(getattr(response, "message", None), "content", None)
        if content is None and isinstance(response, dict):
            content = (response.get("message") or {}).get("content")

        recommendations = normalize_recommendations(content or "")
        if recommendations:
            break
        print(f"[RECOMMENDATIONS] intento {attempt}: respuesta no valida: {str(content)[:300]!r}")

    if not recommendations:
        if last_error is not None:
            raise ServiceError("No se pudo conectar con el modelo de IA. Intenta de nuevo.", status=502) from last_error
        raise ServiceError("La IA no devolvio recomendaciones validas. Intenta de nuevo.", status=502)

    saved = []
    for rec in recommendations:
        result = backend.request("POST", "/api/ai-recommendation/", auth_token=token, json_body={"idNegocio": id_negocio, **rec})
        saved.append(_data(result))
    return saved
