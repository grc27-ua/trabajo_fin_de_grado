"""
Pruebas unitarias — rag_engine.py
Cubre: _texto_poi, _expandir_tematica, build_index, buscar_pois_por_tematica
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# ─── Fixtures ─────────────────────────────────────────────────────────────────

POIS_MUESTRA = [
    {
        "wikidata_id": "Q1",
        "nombre": "Castillo de Santa Bárbara",
        "categoria_principal": "Castillos",
        "instance_of": "castillo",
        "descripcion_enriquecida": "Fortaleza árabe sobre el Benacantil. Testigo de la Reconquista.",
        "keywords": "reconquista, árabe, medieval, fortaleza",
        "lat": 38.345, "lon": -0.481,
        "es_cultural": True,
    },
    {
        "wikidata_id": "Q2",
        "nombre": "MACA",
        "categoria_principal": "Museos",
        "instance_of": "museo de arte",
        "descripcion_enriquecida": "Colección de arte contemporáneo del siglo XX.",
        "lat": 38.344, "lon": -0.483,
        "es_cultural": True,
    },
]


def _fake_embedding(text, host=""):
    """Embedding determinístico sin llamar a Ollama."""
    rng = np.random.default_rng(seed=abs(hash(text)) % (2**32))
    vec = rng.random(1024).astype(np.float32)
    vec /= np.linalg.norm(vec)
    return vec


# ─── _texto_poi ───────────────────────────────────────────────────────────────

class TestTextoPoi:
    def test_contiene_campos_clave(self):
        from rag_engine import _texto_poi
        texto = _texto_poi(POIS_MUESTRA[0])
        assert "Castillo de Santa Bárbara" in texto
        assert "castillo" in texto
        assert "Castillos" in texto
        assert "Reconquista" in texto
        assert "reconquista" in texto  # keywords

    def test_sin_keywords_no_falla(self):
        from rag_engine import _texto_poi
        texto = _texto_poi(POIS_MUESTRA[1])
        assert "MACA" in texto
        assert "Keywords" not in texto

    def test_poi_minimo_no_falla(self):
        """Un POI con campos mínimos no debe lanzar excepciones."""
        from rag_engine import _texto_poi
        texto = _texto_poi({})
        assert isinstance(texto, str)


# ─── _expandir_tematica ───────────────────────────────────────────────────────

class TestExpandirTematica:
    def test_enriquece_query(self):
        from rag_engine import _expandir_tematica
        mock_client = MagicMock()
        mock_client.generate.return_value = {"response": "fortaleza, árabe, Benacantil"}
        with patch("rag_engine.ollama.Client", return_value=mock_client):
            resultado = _expandir_tematica("castillo medieval", "http://localhost:11434")
        assert "castillo medieval" in resultado
        assert "fortaleza" in resultado

    def test_fallback_si_llm_falla(self):
        from rag_engine import _expandir_tematica
        mock_client = MagicMock()
        mock_client.generate.side_effect = ConnectionError("Sin conexión")
        with patch("rag_engine.ollama.Client", return_value=mock_client):
            resultado = _expandir_tematica("guerra civil", "http://localhost:11434")
        assert resultado == "guerra civil"

    def test_fallback_si_timeout(self):
        from rag_engine import _expandir_tematica
        mock_client = MagicMock()
        mock_client.generate.side_effect = TimeoutError("Timeout")
        with patch("rag_engine.ollama.Client", return_value=mock_client):
            resultado = _expandir_tematica("arte moderno", "http://localhost:11434")
        assert resultado == "arte moderno"


# ─── build_index ──────────────────────────────────────────────────────────────

class TestBuildIndex:
    def test_crea_archivos_en_disco(self, tmp_path):
        from rag_engine import build_index
        import rag_engine as re_mod
        orig_i, orig_m = re_mod.INDEX_PATH, re_mod.META_PATH
        re_mod.INDEX_PATH = tmp_path / "test.faiss"
        re_mod.META_PATH  = tmp_path / "test.pkl"
        with patch("rag_engine._get_embedding", side_effect=_fake_embedding):
            build_index(POIS_MUESTRA, ollama_host="http://x", force_rebuild=True)
        assert re_mod.INDEX_PATH.exists()
        assert re_mod.META_PATH.exists()
        re_mod.INDEX_PATH, re_mod.META_PATH = orig_i, orig_m

    def test_no_reconstruye_si_existe(self, tmp_path):
        from rag_engine import build_index
        import rag_engine as re_mod
        orig_i, orig_m = re_mod.INDEX_PATH, re_mod.META_PATH
        re_mod.INDEX_PATH = tmp_path / "test.faiss"
        re_mod.META_PATH  = tmp_path / "test.pkl"
        re_mod.INDEX_PATH.touch()
        re_mod.META_PATH.touch()
        with patch("rag_engine._get_embedding", side_effect=_fake_embedding) as mock_e:
            build_index(POIS_MUESTRA, ollama_host="http://x", force_rebuild=False)
        mock_e.assert_not_called()
        re_mod.INDEX_PATH, re_mod.META_PATH = orig_i, orig_m


# ─── buscar_pois_por_tematica ─────────────────────────────────────────────────

class TestBuscarPoisPorTematica:
    def test_tematica_vacia_devuelve_candidatos(self):
        from rag_engine import buscar_pois_por_tematica
        resultado = buscar_pois_por_tematica("", pois_candidatos=POIS_MUESTRA)
        assert resultado == POIS_MUESTRA

    def test_sin_indice_devuelve_candidatos_fallback(self, tmp_path):
        from rag_engine import buscar_pois_por_tematica
        import rag_engine as re_mod
        orig_i, orig_m = re_mod.INDEX_PATH, re_mod.META_PATH
        re_mod.INDEX_PATH = tmp_path / "noexiste.faiss"
        re_mod.META_PATH  = tmp_path / "noexiste.pkl"
        resultado = buscar_pois_por_tematica("guerra civil", pois_candidatos=POIS_MUESTRA)
        assert resultado == POIS_MUESTRA
        re_mod.INDEX_PATH, re_mod.META_PATH = orig_i, orig_m

    def test_filtra_con_indice_construido(self, tmp_path):
        from rag_engine import build_index, buscar_pois_por_tematica
        import rag_engine as re_mod
        orig_i, orig_m = re_mod.INDEX_PATH, re_mod.META_PATH
        re_mod.INDEX_PATH = tmp_path / "test.faiss"
        re_mod.META_PATH  = tmp_path / "test.pkl"
        with patch("rag_engine._get_embedding", side_effect=_fake_embedding):
            build_index(POIS_MUESTRA, ollama_host="http://x", force_rebuild=True)
        with patch("rag_engine._get_embedding", side_effect=_fake_embedding), \
             patch("rag_engine._expandir_tematica", return_value="castillo medieval"):
            resultado = buscar_pois_por_tematica(
                "castillo medieval",
                pois_candidatos=POIS_MUESTRA,
                top_k=10,
                margen_relativo=0.99,
                ollama_host="http://x",
            )
        assert isinstance(resultado, list)
        re_mod.INDEX_PATH, re_mod.META_PATH = orig_i, orig_m
