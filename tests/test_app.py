"""
Pruebas de integración — app.py (Flask)
Cubre: /, /generar (sin temática, con temática, sin POIs), /exportar_pdf

NOTA: el fixture importa app DENTRO del bloque de mocks para que el código
de nivel módulo (build_index al arrancar) no llegue a ejecutarse de verdad.
"""

import sys
import json
import pytest
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock

# conftest.py ya añade ROOT a sys.path

# ─── Datos de muestra ─────────────────────────────────────────────────────────

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

FORM_BASE = {
    "transporte": "andando",
    "tiempo": "120",
    "categorias": ["Museos"],
    "lat": "38.344",
    "lon": "-0.483",
    "tematica": "",
}

RUTA_JSON_2_PARADAS = json.dumps([
    {
        "nombre": "Castillo de Santa Bárbara",
        "lat": 38.345, "lon": -0.481,
        "categoria_principal": "Castillos",
        "descripcion_llm": "Fortaleza árabe sobre el Benacantil.",
    },
    {
        "nombre": "MACA",
        "lat": 38.344, "lon": -0.483,
        "categoria_principal": "Museos",
        "descripcion_llm": "Colección de arte contemporáneo.",
    },
])


# ─── Fixture: cliente Flask ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """
    Importa app.py con los mocks ya activos para evitar que el código
    de nivel módulo (build_index, open del JSON) se ejecute de verdad.
    El módulo se elimina de sys.modules antes para forzar una reimportación
    limpia con los parches en vigor.
    """
    # Asegurarse de que no hay versión cacheada del módulo
    for mod in ["app", "rag_engine", "route_engine"]:
        sys.modules.pop(mod, None)

    mock_ors_directions = {
        "type": "FeatureCollection",
        "features": [],
        "routes": [{"segments": []}],
    }

    with patch("rag_engine.build_index"), \
         patch("rag_engine._get_embedding"), \
         patch("route_engine.generar_ruta", return_value=(POIS_MOCK, 90.0)), \
         patch("builtins.open", create=True) as mock_open:

        # open() para leer el JSON de POIs devuelve una lista válida
        mock_file = MagicMock()
        mock_file.__enter__ = lambda s: s
        mock_file.__exit__ = MagicMock(return_value=False)
        mock_file.read.return_value = json.dumps(POIS_MOCK)
        mock_open.return_value = mock_file

        import app as flask_app

        flask_app.app.config["TESTING"] = True
        with flask_app.app.test_client() as c:
            yield c

    # Limpiar módulos al finalizar para no afectar otros tests
    for mod in ["app", "rag_engine", "route_engine"]:
        sys.modules.pop(mod, None)


# ─── GET / ────────────────────────────────────────────────────────────────────

class TestIndex:
    def test_pagina_principal_devuelve_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_pagina_principal_contiene_formulario(self, client):
        r = client.get("/")
        assert b"<form" in r.data or b"form" in r.data


# ─── POST /generar ────────────────────────────────────────────────────────────

class TestGenerar:

    def _post(self, client, extra=None):
        data = {**FORM_BASE, **(extra or {})}
        with patch("app.generar_ruta", return_value=(POIS_MOCK, 90.0)), \
             patch("app.eliminar_duplicados_por_categoria", side_effect=lambda x: x), \
             patch("app.json.load", return_value=POIS_MOCK), \
             patch("app.openrouteservice.Client") as mock_ors_cls:
            mock_ors = MagicMock()
            mock_ors_cls.return_value = mock_ors
            mock_ors.directions.return_value = {
                "type": "FeatureCollection",
                "features": [],
                "routes": [{"segments": []}],
            }
            return client.post("/generar", data=data)

    def test_genera_ruta_sin_tematica(self, client):
        r = self._post(client)
        assert r.status_code == 200

    def test_genera_ruta_con_tematica(self, client):
        with patch("app.buscar_pois_por_tematica", return_value=POIS_MOCK):
            r = self._post(client, {"tematica": "castillo medieval"})
        assert r.status_code == 200

    def test_sin_pois_suficientes_devuelve_mensaje(self, client):
        with patch("app.json.load", return_value=[]), \
             patch("app.eliminar_duplicados_por_categoria", side_effect=lambda x: x):
            r = client.post("/generar", data=FORM_BASE)
        assert r.status_code == 200
        assert b"No hay suficientes" in r.data

    def test_ors_fallback_si_falla_servicio_externo(self, client):
        with patch("app.generar_ruta", return_value=(POIS_MOCK, 90.0)), \
             patch("app.eliminar_duplicados_por_categoria", side_effect=lambda x: x), \
             patch("app.json.load", return_value=POIS_MOCK), \
             patch("app.openrouteservice.Client", side_effect=Exception("ORS caído")):
            r = client.post("/generar", data=FORM_BASE)
        assert r.status_code == 200


# ─── POST /exportar_pdf ───────────────────────────────────────────────────────

class TestExportarPdf:

    def test_exportar_pdf_devuelve_pdf(self, client):
        r = client.post("/exportar_pdf", data={
            "ruta_json": RUTA_JSON_2_PARADAS,
            "tiempo_total": "90",
            "transporte": "andando",
            "instrucciones_json": "null",
        })
        assert r.status_code == 200
        assert r.content_type == "application/pdf"

    def test_exportar_pdf_con_instrucciones(self, client):
        instrucciones = json.dumps([[
            {"instruccion": "Gira a la derecha", "distancia": 150, "duracion": 2.5},
            {"instruccion": "Continúa recto", "distancia": 300, "duracion": 4.0},
        ]])
        r = client.post("/exportar_pdf", data={
            "ruta_json": RUTA_JSON_2_PARADAS,
            "tiempo_total": "90",
            "transporte": "bicicleta",
            "instrucciones_json": instrucciones,
        })
        assert r.status_code == 200
        assert r.content_type == "application/pdf"

    def test_exportar_pdf_ruta_vacia(self, client):
        r = client.post("/exportar_pdf", data={
            "ruta_json": "[]",
            "tiempo_total": "0",
            "transporte": "andando",
            "instrucciones_json": "null",
        })
        # Ruta vacía: sin paradas que iterar, debe generar un PDF igualmente
        assert r.status_code == 200
