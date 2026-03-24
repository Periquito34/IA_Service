from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.backend import BackendClient
from app.errors import ServiceError


def _resolve_value(args: dict[str, Any], context: dict[str, Any], key: str) -> Any:
    if key in args and args[key] not in (None, ""):
        return args[key]
    if key in context and context[key] not in (None, ""):
        return context[key]
    return None


def _resolve_id_negocio(args: dict[str, Any], context: dict[str, Any]) -> str:
    value = _resolve_value(args, context, "idNegocio")
    if not value:
        raise ServiceError("idNegocio es requerido (args o context).", status=400)
    return str(value)


def _resolve_uid(args: dict[str, Any], context: dict[str, Any]) -> str:
    value = _resolve_value(args, context, "uid")
    if not value:
        raise ServiceError("uid es requerido (args o context).", status=400)
    return str(value)


def _resolve_id_producto(args: dict[str, Any], context: dict[str, Any]) -> str:
    value = _resolve_value(args, context, "idProducto")
    if not value:
        raise ServiceError("idProducto es requerido (args o context).", status=400)
    return str(value)


def _resolve_year_month(args: dict[str, Any], context: dict[str, Any]) -> tuple[int, int]:
    now = datetime.now(tz=timezone.utc)
    year = int(_resolve_value(args, context, "year") or now.year)
    month = int(_resolve_value(args, context, "month") or now.month)
    if month < 1 or month > 12:
        raise ServiceError("month debe estar entre 1 y 12.", status=400, details={"month": month})
    return year, month


def _extract_business_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data_field = payload.get("data")
        if isinstance(data_field, list):
            return [item for item in data_field if isinstance(item, dict)]
    return []


def _extract_products_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data_field = payload.get("data")
        if isinstance(data_field, list):
            return [item for item in data_field if isinstance(item, dict)]
    return []


def _get_businesses_for_uid(
    *,
    uid: str,
    backend_auth_token: str | None,
    backend_client: BackendClient,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    businesses_result = backend_client.request(
        "GET",
        f"/api/business/user/{uid}",
        auth_token=backend_auth_token,
        treat_404_as_no_data=True,
    )
    businesses = _extract_business_list(businesses_result.get("data"))
    return businesses_result, businesses


def _resolve_id_negocio_with_fallback(
    *,
    args: dict[str, Any],
    context: dict[str, Any],
    backend_auth_token: str | None,
    backend_client: BackendClient,
) -> str:
    direct = _resolve_value(args, context, "idNegocio")
    if direct:
        return str(direct)

    uid = _resolve_value(args, context, "uid")
    if not uid:
        raise ServiceError(
            "idNegocio no disponible. Envia idNegocio o uid para resolver negocio.",
            status=400,
        )

    businesses_result, businesses = _get_businesses_for_uid(
        uid=str(uid),
        backend_auth_token=backend_auth_token,
        backend_client=backend_client,
    )

    if businesses_result.get("noData"):
        raise ServiceError(
            "No se encontraron negocios asociados al usuario.",
            status=404,
            details={"uid": uid},
        )

    if not businesses:
        raise ServiceError(
            "No se pudo resolver idNegocio desde el usuario.",
            status=404,
            details={"uid": uid},
        )

    first = businesses[0]
    id_negocio = first.get("idNegocio") or first.get("id") or first.get("businessId")
    if not id_negocio:
        raise ServiceError(
            "El backend devolvio negocios sin idNegocio.",
            status=502,
            details={"uid": uid, "sample": first},
        )

    # Guardamos en context para llamadas siguientes dentro del mismo turno.
    context["idNegocio"] = str(id_negocio)
    return str(id_negocio)


TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "get_user_profile_by_uid",
        "description": "Obtiene perfil de usuario por uid.",
        "parameters": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "UID de Firebase del usuario."}
            },
            "required": ["uid"],
        },
    },
    {
        "name": "get_user_email_by_uid",
        "description": "Obtiene email del usuario por uid.",
        "parameters": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "UID de Firebase del usuario."}
            },
            "required": ["uid"],
        },
    },
    {
        "name": "get_businesses_by_user",
        "description": "Lista negocios por UID de Firebase.",
        "parameters": {
            "type": "object",
            "properties": {
                "uid": {"type": "string", "description": "UID de Firebase del usuario."}
            },
            "required": ["uid"],
        },
    },
    {
        "name": "get_products_by_business",
        "description": "Obtiene productos del negocio con costos y stock.",
        "parameters": {
            "type": "object",
            "properties": {
                "idNegocio": {"type": "string", "description": "ID del negocio."}
            },
            "required": ["idNegocio"],
        },
    },
    {
        "name": "get_product_sales_history",
        "description": "Obtiene historial completo de ventas por idProducto.",
        "parameters": {
            "type": "object",
            "properties": {
                "idProducto": {"type": "string", "description": "ID del producto."}
            },
            "required": ["idProducto"],
        },
    },
    {
        "name": "get_product_sales_by_month",
        "description": "Obtiene ventas de un producto por mes.",
        "parameters": {
            "type": "object",
            "properties": {
                "idProducto": {"type": "string"},
                "year": {"type": "integer"},
                "month": {"type": "integer"},
            },
            "required": ["idProducto", "year", "month"],
        },
    },
    {
        "name": "get_product_sales_summary_by_month",
        "description": "Resumen de ventas de producto por mes (cantidad y total).",
        "parameters": {
            "type": "object",
            "properties": {
                "idProducto": {"type": "string"},
                "year": {"type": "integer"},
                "month": {"type": "integer"},
            },
            "required": ["idProducto", "year", "month"],
        },
    },
    {
        "name": "get_sales_summary_by_business_month",
        "description": "Resumen mensual de ventas por negocio.",
        "parameters": {
            "type": "object",
            "properties": {
                "idNegocio": {"type": "string"},
                "year": {"type": "integer"},
                "month": {"type": "integer"},
            },
            "required": ["idNegocio", "year", "month"],
        },
    },
    {
        "name": "get_transactions_by_business",
        "description": "Lista transacciones del negocio.",
        "parameters": {
            "type": "object",
            "properties": {
                "idNegocio": {"type": "string"}
            },
            "required": ["idNegocio"],
        },
    },
    {
        "name": "get_egresos_by_business_month",
        "description": "Obtiene detalle de egresos de un negocio por mes.",
        "parameters": {
            "type": "object",
            "properties": {
                "idNegocio": {"type": "string"},
                "year": {"type": "integer"},
                "month": {"type": "integer"},
            },
            "required": ["idNegocio", "year", "month"],
        },
    },
    {
        "name": "get_egresos_summary_by_business_month",
        "description": "Obtiene total de egresos por negocio en un mes.",
        "parameters": {
            "type": "object",
            "properties": {
                "idNegocio": {"type": "string"},
                "year": {"type": "integer"},
                "month": {"type": "integer"},
            },
            "required": ["idNegocio", "year", "month"],
        },
    },
    {
        "name": "get_fixed_expenses_by_business",
        "description": "Devuelve gastos fijos y agregados de pagados/no pagados.",
        "parameters": {
            "type": "object",
            "properties": {
                "idNegocio": {"type": "string"}
            },
            "required": ["idNegocio"],
        },
    },
    {
        "name": "get_fixed_expenses_paid_by_month",
        "description": "Obtiene gastos fijos pagados en un mes.",
        "parameters": {
            "type": "object",
            "properties": {
                "idNegocio": {"type": "string"},
                "year": {"type": "integer"},
                "month": {"type": "integer"},
            },
            "required": ["idNegocio", "year", "month"],
        },
    },
    {
        "name": "get_fixed_expenses_total_by_business",
        "description": "Obtiene total global de gastos fijos del negocio.",
        "parameters": {
            "type": "object",
            "properties": {
                "idNegocio": {"type": "string"}
            },
            "required": ["idNegocio"],
        },
    },
    {
        "name": "get_live_profitability_by_business_month",
        "description": "Obtiene rentabilidad live para un negocio por mes.",
        "parameters": {
            "type": "object",
            "properties": {
                "idNegocio": {"type": "string"},
                "year": {"type": "integer"},
                "month": {"type": "integer"},
            },
            "required": ["idNegocio", "year", "month"],
        },
    },
    {
        "name": "save_ai_recommendation",
        "description": "Guarda recomendacion AI en el backend.",
        "parameters": {
            "type": "object",
            "properties": {
                "idNegocio": {"type": "string"},
                "tipo": {"type": "string"},
                "mensaje": {"type": "string"},
            },
            "required": ["idNegocio", "mensaje"],
        },
    },
]


def execute_tool_call(
    *,
    name: str,
    args: dict[str, Any],
    context: dict[str, Any],
    backend_auth_token: str | None,
    backend_client: BackendClient,
) -> dict[str, Any]:
    if name == "get_user_profile_by_uid":
        uid = _resolve_uid(args, context)
        result = backend_client.request(
            "GET",
            f"/api/users/{uid}",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_user_email_by_uid":
        uid = _resolve_uid(args, context)
        result = backend_client.request(
            "GET",
            f"/api/users/{uid}/email",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_businesses_by_user":
        uid = _resolve_uid(args, context)
        result = backend_client.request(
            "GET",
            f"/api/business/user/{uid}",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_products_by_business":
        id_negocio_direct = _resolve_value(args, context, "idNegocio")
        uid = _resolve_value(args, context, "uid")
        if id_negocio_direct:
            id_negocio = str(id_negocio_direct)
            result = backend_client.request(
                "GET",
                f"/api/product/business/{id_negocio}",
                auth_token=backend_auth_token,
                treat_404_as_no_data=True,
            )
        elif uid:
            _, businesses = _get_businesses_for_uid(
                uid=str(uid),
                backend_auth_token=backend_auth_token,
                backend_client=backend_client,
            )
            if not businesses:
                raise ServiceError(
                    "No se encontraron negocios asociados al usuario.",
                    status=404,
                    details={"uid": uid},
                )

            aggregated_products: list[dict[str, Any]] = []
            businesses_checked: list[str] = []
            for business in businesses:
                business_id = business.get("idNegocio") or business.get("id") or business.get("businessId")
                if not business_id:
                    continue
                businesses_checked.append(str(business_id))
                products_result = backend_client.request(
                    "GET",
                    f"/api/product/business/{business_id}",
                    auth_token=backend_auth_token,
                    treat_404_as_no_data=True,
                )
                if products_result.get("noData"):
                    continue

                current_products = _extract_products_list(products_result.get("data"))
                for prod in current_products:
                    if "idNegocio" not in prod:
                        prod["idNegocio"] = str(business_id)
                aggregated_products.extend(current_products)

            if aggregated_products:
                result = {
                    "ok": True,
                    "noData": False,
                    "status": 200,
                    "endpoint": "/api/product/business/:idNegocio (aggregated_by_uid)",
                    "data": {
                        "message": "Productos agregados por uid",
                        "count": len(aggregated_products),
                        "businessesChecked": businesses_checked,
                        "data": aggregated_products,
                    },
                }
            else:
                result = {
                    "ok": True,
                    "noData": True,
                    "status": 404,
                    "endpoint": "/api/product/business/:idNegocio (aggregated_by_uid)",
                    "data": {
                        "message": "No se encontraron productos en los negocios del usuario.",
                        "businessesChecked": businesses_checked,
                    },
                }
        else:
            raise ServiceError(
                "Para consultar productos debes enviar idNegocio o uid.",
                status=400,
            )
    elif name == "get_product_sales_history":
        id_producto = _resolve_id_producto(args, context)
        result = backend_client.request(
            "GET",
            f"/api/product-sold/ventas/producto/{id_producto}",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_product_sales_by_month":
        id_producto = _resolve_id_producto(args, context)
        year, month = _resolve_year_month(args, context)
        result = backend_client.request(
            "GET",
            f"/api/product-sold/ventas/producto/{id_producto}/{year}/{month}",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_product_sales_summary_by_month":
        id_producto = _resolve_id_producto(args, context)
        year, month = _resolve_year_month(args, context)
        result = backend_client.request(
            "GET",
            f"/api/product-sold/ventas/producto/resumen/{id_producto}/{year}/{month}",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_sales_summary_by_business_month":
        id_negocio = _resolve_id_negocio_with_fallback(
            args=args,
            context=context,
            backend_auth_token=backend_auth_token,
            backend_client=backend_client,
        )
        year, month = _resolve_year_month(args, context)
        result = backend_client.request(
            "GET",
            f"/api/product-sold/ventas/producto/negocio/{id_negocio}/{year}/{month}",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_transactions_by_business":
        id_negocio = _resolve_id_negocio_with_fallback(
            args=args,
            context=context,
            backend_auth_token=backend_auth_token,
            backend_client=backend_client,
        )
        result = backend_client.request(
            "GET",
            f"/api/transaction/negocios/{id_negocio}/transacciones",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_egresos_by_business_month":
        id_negocio = _resolve_id_negocio_with_fallback(
            args=args,
            context=context,
            backend_auth_token=backend_auth_token,
            backend_client=backend_client,
        )
        year, month = _resolve_year_month(args, context)
        result = backend_client.request(
            "GET",
            f"/api/transaction/negocios/{id_negocio}/egresos/{year}/{month}",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_egresos_summary_by_business_month":
        id_negocio = _resolve_id_negocio_with_fallback(
            args=args,
            context=context,
            backend_auth_token=backend_auth_token,
            backend_client=backend_client,
        )
        year, month = _resolve_year_month(args, context)
        result = backend_client.request(
            "GET",
            f"/api/transaction/negocios/{id_negocio}/egresos/{year}/{month}/short",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_fixed_expenses_paid_by_month":
        id_negocio = _resolve_id_negocio_with_fallback(
            args=args,
            context=context,
            backend_auth_token=backend_auth_token,
            backend_client=backend_client,
        )
        year, month = _resolve_year_month(args, context)
        result = backend_client.request(
            "GET",
            f"/api/gasto-fijo/business/{id_negocio}/pagados/{year}/{month}",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_fixed_expenses_total_by_business":
        id_negocio = _resolve_id_negocio_with_fallback(
            args=args,
            context=context,
            backend_auth_token=backend_auth_token,
            backend_client=backend_client,
        )
        result = backend_client.request(
            "GET",
            f"/api/gasto-fijo/business/{id_negocio}/total",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_fixed_expenses_by_business":
        id_negocio = _resolve_id_negocio_with_fallback(
            args=args,
            context=context,
            backend_auth_token=backend_auth_token,
            backend_client=backend_client,
        )
        result = backend_client.request(
            "GET",
            f"/api/gasto-fijo/business/{id_negocio}",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "get_live_profitability_by_business_month":
        id_negocio = _resolve_id_negocio_with_fallback(
            args=args,
            context=context,
            backend_auth_token=backend_auth_token,
            backend_client=backend_client,
        )
        year, month = _resolve_year_month(args, context)
        result = backend_client.request(
            "GET",
            f"/api/rentabilidad/live/{id_negocio}/{year}/{month}",
            auth_token=backend_auth_token,
            treat_404_as_no_data=True,
        )
    elif name == "save_ai_recommendation":
        id_negocio = _resolve_id_negocio_with_fallback(
            args=args,
            context=context,
            backend_auth_token=backend_auth_token,
            backend_client=backend_client,
        )
        tipo = str(args.get("tipo") or "rentabilidad")
        mensaje = str(args.get("mensaje") or "").strip()
        if not mensaje:
            raise ServiceError("mensaje es requerido para save_ai_recommendation.", status=400)
        result = backend_client.request(
            "POST",
            "/api/ai-recommendation/",
            auth_token=backend_auth_token,
            json_body={"idNegocio": id_negocio, "tipo": tipo, "mensaje": mensaje},
        )
    else:
        raise ServiceError(f"Tool no soportada: {name}", status=400)

    return {
        "tool": name,
        "input": args,
        "contextUsed": context,
        "result": result,
    }
