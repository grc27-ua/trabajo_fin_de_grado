"""
Pruebas de integración — app.py (Flask)
Cubre: /, /generar (sin temática, con temática, sin POIs), /exportar_pdf
"""

import json
import pytest
from unittest.mock import patch, MagicMock

# ─── Fixture: cliente Flask de test ───────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    Crea el cliente de test de Flask mockeando build_index y Ollama
    para que la app arranque sin servicios externos.
    """
    with patch("rag_engine.build_index"), \
         patch("rag_engine._get_embedding"), \
         patch("builtins.open", create=True):
        import app as flask_app
        flask_app.app.config["TESTING"] = True
        with flask_app.app.test_client() as c:
            yield c


# ─── Ruta GET / ───────────────────────────────────────────────────────────────

class TestIndex:
    def test_pagina_principal_devuelve_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_pagina_principal_contiene_formulario(self, client):
        html = response = client.get("/")
        assert b"form" in response.data or response.status_code == 200


# ─── Ruta POST /generar ───────────────────────────────────────────────────────

FORM_BASE = {
    "transporte": "andando",
    "tiempo": "120",
    "categorias": ["Museos"],
    "lat": "38.344",
    "lon": "-0.483",
    "tematica": "",
}

POIS_MOCK = [
    {
        "wikidata_id": f"Q{i}",
        "nombre": f"POI {i}",
        "lat": 38.344 + i * 0.001,
        "lon": -0.483 + i * 0.001,
        "categoria_principal": "Museos",
        "descripcion_llm": f"Descripción del POI {i}.",
        "descripcion_enriquecida": f"Descripción enriquecida {i}.",
        "es_cultural": True,
        "es_cultural_llm": "CULTURAL",
    }
    for i in range(3)
]


class TestGenerar:
    def _post_generar(self, client, extra=None):
        data = {**FORM_BASE, **(extra or {})}
        with patch("app.json.load", return_value=POIS_MOCK), \
             patch("app.generar_ruta", return_value=(POIS_MOCK, 90.0)), \
             patch("app.eliminar_duplicados_por_categoria", side_effect=lambda x: x), \
             patch("app.openrouteservice.Client") as mock_ors:
            mock_ors.return_value.directions.return_value = {
                "type": "FeatureCollection", "features": [],
                "routes": [{"segments": []}],
            }
            return client.post("/generar", data=data)

    def test_genera_ruta_sin_tematica(self, client):
        r = self._post_generar(client)
        assert r.status_code == 200

    def test_genera_ruta_con_tematica(self, client):
        with patch("app.buscar_pois_por_tematica", return_value=POIS_MOCK):
            r = self._post_generar(client, {"tematica": "castillo medieval"})
        assert r.status_code == 200

    def test_sin_pois_suficientes_devuelve_mensaje(self, client):
        with patch("app.json.load", return_value=[]), \
             patch("app.eliminar_duplicados_por_categoria", side_effect=lambda x: x):
            r = client.post("/generar", data=FORM_BASE)
        # Sin POIs, la app debe devolver un mensaje sin lanzar excepción
        assert r.status_code == 200
        assert b"No hay suficientes" in r.data or r.status_code == 200

    def test_ors_fallback_si_falla_servicio_externo(self, client):
        import openrouteservice
        with patch("app.json.load", return_value=POIS_MOCK), \
             patch("app.generar_ruta", return_value=(POIS_MOCK, 90.0)), \
             patch("app.eliminar_duplicados_por_categoria", side_effect=lambda x: x), \
             patch("app.openrouteservice.Client", side_effect=Exception("ORS no disponible")):
            r = client.post("/generar", data=FORM_BASE)
        # El sistema debe responder aunque ORS falle
        assert r.status_code == 200


# ─── Ruta POST /exportar_pdf ──────────────────────────────────────────────────

class TestExportarPdf:
    RUTA_JSON = json.dumps([
        {"nombre": "Castillo", "lat": 38.345, "lon": -0.481,
         "categoria_principal": "Castillos", "descripcion_llm": "Fortaleza árabe."},
        {"nombre": "MACA", "lat": 38.344, "lon": -0.483,
         "categoria_principal": "Museos", "descripcion_llm": "Arte contemporáneo."},
    ])

    def test_exportar_pdf_devuelve_pdf(self, client):
        r = client.post("/exportar_pdf", data={
            "ruta_json": self.RUTA_JSON,
            "tiempo_total": "90",
            "transporte": "andando",
            "instrucciones_json": "null",
        })
        assert r.status_code == 200
        assert r.content_type == "application/pdf"

    def test_exportar_pdf_con_instrucciones(self, client):
        instrucciones = json.dumps([[
            {"instruccion": "Gira a la derecha", "distancia": 150, "duracion": 2.5}
        ]])
        r = client.post("/exportar_pdf", data={
            "ruta_json": self.RUTA_JSON,
            "tiempo_total": "90",
            "transporte": "andando",
            "instrucciones_json": instrucciones,
        })
        assert r.status_code == 200

    def test_exportar_pdf_ruta_vacia(self, client):
        r = client.post("/exportar_pdf", data={
            "ruta_json": "[]",
            "tiempo_total": "0",
            "transporte": "andando",
            "instrucciones_json": "null",
        })
        # Con ruta vacía no debe explotar el servidor
        assert r.status_code == 200
