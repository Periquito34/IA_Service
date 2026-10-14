import unittest

from app.recommendations import build_snapshot, normalize_recommendations


class BuildSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = build_snapshot(
            balance={"capitalInicial": 1000, "balanceTotal": 1550},
            products=[
                {"idProducto": "p1", "nombreProducto": "Camiseta", "precioVenta": 100, "costoProduccion": 60, "stock": 5},
                {"idProducto": "p2", "nombreProducto": "Gorra", "precioVenta": 50, "costoProduccion": 70, "stock": 40},
            ],
            sales_by_product={
                "p1": [
                    {"totalVenta": 300, "utilidad": 120, "cantidadVendida": 3, "fechaVenta": {"_seconds": 1772366400}},  # 2026-03-01
                    {"totalVenta": 100, "utilidad": 40, "cantidadVendida": 1, "fechaVenta": "2026-02-10T12:00:00Z"},
                ],
                "p2": [],
            },
            transactions=[
                {"tipo": False, "monto": 200, "fechaISO": "2026-03-05T10:00:00Z"},
                {"tipo": "income", "monto": 3, "fechaISO": "2026-03-06T10:00:00Z"},
                {"tipo": True, "monto": 80, "fechaISO": "2026-03-07T10:00:00Z"},
            ],
            fixed_expenses=[
                {"nombreGasto": "Arriendo", "costoGasto": 500, "pagado": False, "recurrencia": "mensual"},
            ],
            previous_recommendations=[
                {"titulo": "Subir precio de la gorra", "mensaje": "...", "estado": "aplicada"},
            ],
        )

    def test_productos_con_margen_y_unidades_vendidas(self):
        gorra = next(p for p in self.snapshot["productos"] if p["nombre"] == "Gorra")
        camiseta = next(p for p in self.snapshot["productos"] if p["nombre"] == "Camiseta")
        self.assertEqual(gorra["margenPorcentaje"], -40.0)
        self.assertEqual(camiseta["unidadesVendidas"], 4)
        self.assertEqual(camiseta["stock"], 5)

    def test_resumen_mensual_combina_ventas_y_transacciones(self):
        marzo = self.snapshot["resumenMensual"]["2026-03"]
        self.assertEqual(marzo["ventas"], 300)
        self.assertEqual(marzo["utilidadVentas"], 120)
        self.assertEqual(marzo["otrosIngresos"], 203)
        self.assertEqual(marzo["egresos"], 80)
        self.assertEqual(self.snapshot["resumenMensual"]["2026-02"]["ventas"], 100)

    def test_gastos_fijos_y_recomendaciones_previas(self):
        self.assertEqual(self.snapshot["gastosFijos"]["totalMensual"], 500)
        self.assertEqual(self.snapshot["gastosFijos"]["pendientes"], 1)
        self.assertEqual(self.snapshot["recomendacionesPrevias"], [{"titulo": "Subir precio de la gorra", "estado": "aplicada"}])


class NormalizeRecommendationsTest(unittest.TestCase):
    def test_valida_y_normaliza(self):
        raw = {
            "recomendaciones": [
                {"titulo": " Subir precio ", "mensaje": "Explicacion", "prioridad": "ALTA", "impacto": "+10%", "tipo": "precios"},
                {"titulo": "Sin mensaje", "mensaje": "", "prioridad": "media"},
                {"titulo": "Prioridad rara", "mensaje": "x", "prioridad": "urgente", "tipo": "otra cosa"},
            ]
        }
        result = normalize_recommendations(raw)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {"titulo": "Subir precio", "mensaje": "Explicacion", "prioridad": "alta", "impacto": "+10%", "tipo": "precios"})
        self.assertEqual(result[1]["prioridad"], "media")
        self.assertEqual(result[1]["tipo"], "general")

    def test_acepta_texto_json_y_limita_a_5(self):
        items = [{"titulo": f"R{i}", "mensaje": "m"} for i in range(8)]
        import json
        self.assertEqual(len(normalize_recommendations(json.dumps({"recomendaciones": items}))), 5)

    def test_acepta_lista_sin_objeto_raiz(self):
        # gpt-oss en Ollama Cloud a veces ignora el esquema y devuelve la lista directamente
        import json
        raw = json.dumps([{"titulo": "Subir precio", "mensaje": "m", "prioridad": "alta", "impacto": "", "tipo": "precios"}])
        self.assertEqual(len(normalize_recommendations(raw)), 1)
        self.assertEqual(normalize_recommendations("Aqui van:\n" + raw)[0]["titulo"], "Subir precio")

    def test_respuesta_invalida_devuelve_lista_vacia(self):
        self.assertEqual(normalize_recommendations("no es json"), [])
        self.assertEqual(normalize_recommendations({"otra": 1}), [])


if __name__ == "__main__":
    unittest.main()
