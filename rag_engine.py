import json
import pickle
import numpy as np
from pathlib import Path

try:
    import faiss
except ImportError:
    raise ImportError("Instala faiss-cpu: pip install faiss-cpu")

import ollama

# ── Configuración ──────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "mxbai-embed-large"
LLM_MODEL       = "mistral"          # Modelo local para expandir la query
INDEX_PATH      = Path("data/rag_index.faiss")
META_PATH       = Path("data/rag_meta.pkl")
# ──────────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────────
# EMBEDDINGS
# ──────────────────────────────────────────────────────────────────────────────

def _get_embedding(text: str, host: str) -> np.ndarray:
    client = ollama.Client(host=host)
    response = client.embeddings(model=EMBEDDING_MODEL, prompt=text)
    return np.array(response["embedding"], dtype=np.float32)


def _texto_poi(poi: dict) -> str:
    """
    Texto de indexación por POI.
    
    MEJORA CLAVE: se elimina el sufijo genérico que antes compartían todos los
    POIs ("lugar cultural en Alicante relacionado con historia, arquitectura y
    turismo"). Ese sufijo hacía que todos los vectores convergieran hacia el
    mismo espacio semántico, impidiendo distinguir temáticas concretas.

    Ahora se usa 'instance_of' (tipo real del POI) y se prioriza
    'descripcion_enriquecida' sobre 'descripcion_llm', que suele ser más genérica.
    También se añade el campo 'keywords' si existe, para enriquecer
    semánticamente los POIs que tengan términos históricos específicos.
    """
    nombre      = poi.get("nombre", "")
    tipo        = poi.get("instance_of", "")           # tipo real, no genérico
    categoria   = poi.get("categoria_principal", "")
    descripcion = (
        poi.get("descripcion_enriquecida")
        #or poi.get("descripcion_llm", "")
    )
    keywords = poi.get("keywords", "")                 # campo opcional de términos clave

    partes = [
        f"Nombre: {nombre}",
        f"Tipo: {tipo}",
        f"Categoria: {categoria}",
        f"Descripcion: {descripcion}",
    ]
    if keywords:
        partes.append(f"Keywords: {keywords}")

    return "\n".join(partes)


# ──────────────────────────────────────────────────────────────────────────────
# EXPANSIÓN SEMÁNTICA DE LA QUERY
# ──────────────────────────────────────────────────────────────────────────────

def _expandir_tematica(tematica: str, ollama_host: str) -> str:
    """
    Expande la query del usuario con términos relacionados antes de embeber.

    PROBLEMA ORIGINAL: queries cortas como "guerra civil" producen vectores muy
    compactos que no coinciden bien con descripciones que usan vocabulario
    indirecto ("bombardeos", "1936", "refugio", "Segunda República").

    SOLUCIÓN: se le pide al LLM local que genere entre 3 y 5 términos o frases
    clave relacionados con la temática en el contexto histórico y cultural de
    Alicante. El embedding resultante tiene mucho mayor radio semántico.

    Si el LLM falla (timeout, modelo no disponible, etc.), se devuelve la
    temática original para no interrumpir el flujo.
    """
    try:
        client = ollama.Client(host=ollama_host)
        prompt = (
            f"Escribe entre 3 y 5 términos o frases clave relacionados con "
            f"'{tematica}' en el contexto histórico y cultural de Alicante, España. "
            f"Solo las palabras clave separadas por comas, sin explicación adicional."
        )
        resp = client.generate(model=LLM_MODEL, prompt=prompt)
        keywords = resp["response"].strip()
        expandida = f"{tematica}, {keywords}"
        print(f"[RAG] Query expandida: {expandida}")
        return expandida
    except Exception as e:
        print(f"[RAG] Expansión fallida ({e}), usando query original.")
        return tematica


# ──────────────────────────────────────────────────────────────────────────────
# BUILD INDEX
# ──────────────────────────────────────────────────────────────────────────────

def build_index(pois: list, ollama_host: str, force_rebuild: bool = False):
    """
    Construye el índice FAISS con los embeddings de todos los POIs.

    Se reconstruye si force_rebuild=True o si el índice no existe en disco.
    El índice usa producto interno (IndexFlatIP) con normalización L2, lo que
    equivale a similitud coseno, más robusta que la distancia euclidiana para
    textos de longitud variable.
    """
    if not force_rebuild and INDEX_PATH.exists() and META_PATH.exists():
        print("[RAG] Índice ya existe, no se reconstruye.")
        return

    print(f"[RAG] Construyendo índice con {len(pois)} POIs...")

    vectors = []
    meta    = []

    for i, poi in enumerate(pois):
        texto = _texto_poi(poi)
        try:
            vec = _get_embedding(texto, ollama_host)
            vectors.append(vec)
            meta.append(poi)
            if (i + 1) % 20 == 0:
                print(f"[RAG] {i+1}/{len(pois)} embeddings generados")
        except Exception as e:
            print(f"[RAG] Error en {poi.get('nombre')}: {e}")

    if not vectors:
        print("[RAG] ERROR: No se generaron embeddings")
        return

    dim    = len(vectors[0])
    index  = faiss.IndexFlatIP(dim)
    matrix = np.vstack(vectors)
    faiss.normalize_L2(matrix)
    index.add(matrix)

    faiss.write_index(index, str(INDEX_PATH))
    with open(META_PATH, "wb") as f:
        pickle.dump(meta, f)

    print(f"[RAG] Índice creado con {index.ntotal} vectores")


# ──────────────────────────────────────────────────────────────────────────────
# BÚSQUEDA
# ──────────────────────────────────────────────────────────────────────────────

def buscar_pois_por_tematica(
    tematica: str,
    pois_candidatos: list,
    top_k: int = 80,
    margen_relativo: float = 0.04,
    ollama_host: str = "http://localhost:11434"
) -> list:
    """
    Filtra semánticamente los POIs candidatos según una temática libre.

    CAMBIOS RESPECTO A LA VERSIÓN ANTERIOR:
    ────────────────────────────────────────
    1. UMBRAL RELATIVO en lugar de absoluto: en vez de score_min=0.55 fijo,
       se calcula el umbral como (score_máximo - margen_relativo). Con un
       margen de 0.04, solo se aceptan POIs dentro del top 4% del mejor
       resultado. Esto resuelve el problema de scores comprimidos (0.68-0.74)
       donde un umbral fijo no discrimina nada.

    2. top_k=80: se recuperan más candidatos del índice global para no perder
       POIs relevantes que queden fuera del top 30 por la compresión de scores.
       El índice tiene todos los POIs; la intersección con pois_candidatos
       (filtrados por categoría) reduce la lista después.

    3. DIAGNÓSTICO en terminal: se imprime el score máximo, el umbral calculado
       y cuántos POIs superan el corte, para facilitar el ajuste del margen.
    """
    if not tematica.strip():
        return pois_candidatos

    if not INDEX_PATH.exists() or not META_PATH.exists():
        print("[RAG] Índice no encontrado, usando todos los candidatos.")
        return pois_candidatos

    try:
        index = faiss.read_index(str(INDEX_PATH))
        with open(META_PATH, "rb") as f:
            meta = pickle.load(f)

        # 1. Expandir query semánticamente
        tematica_expandida = _expandir_tematica(tematica, ollama_host)

        # 2. Embedding de la query expandida
        query_vec = _get_embedding(tematica_expandida, ollama_host).reshape(1, -1)
        faiss.normalize_L2(query_vec)

        k = min(top_k, index.ntotal)
        scores, indices_faiss = index.search(query_vec, k)

        scores_arr = scores[0]
        score_max  = float(scores_arr[0])
        umbral     = score_max - margen_relativo

        print(f"[RAG] Temática: '{tematica}'")
        print(f"[RAG] Score máximo: {score_max:.4f}  |  Umbral: {umbral:.4f}  "
              f"(margen={margen_relativo})")
        print(f"[RAG] Resultados FAISS (top {k}):")

        # 3. Recoger todos los resultados por encima del umbral relativo
        resultados = []
        for idx, score in zip(indices_faiss[0], scores_arr):
            if idx < len(meta):
                poi = meta[idx]
                marca = "✓" if score >= umbral else " "
                print(f"   {marca} {poi.get('nombre', '')[:45]:45s} ({score:.4f})")
                if score >= umbral:
                    resultados.append((poi, score))

        print(f"[RAG] POIs sobre umbral en índice global: {len(resultados)}")

        # 4. Intersectar con pois_candidatos (filtrados por categoría)
        ids_validos = {p["wikidata_id"] for p, _ in resultados if p.get("wikidata_id")}

        filtrados_dict = {
            p["wikidata_id"]: p
            for p in pois_candidatos
            if p.get("wikidata_id") in ids_validos
        }

        # Ordenar por score descendente
        ids_ordenados = [
            p["wikidata_id"] for p, _ in resultados
            if p.get("wikidata_id") in filtrados_dict
        ]
        filtrados = [filtrados_dict[wid] for wid in ids_ordenados if wid in filtrados_dict]

        print(f"[RAG] Tras intersección con categorías: {len(filtrados)}/{len(pois_candidatos)}")

        if len(filtrados) < 2:
            print("[RAG] Sin resultados relevantes para la temática. "
                  "Considera ampliar las categorías seleccionadas.")
            return []

        return filtrados

    except Exception as e:
        print(f"[RAG] ERROR en búsqueda: {e}")
        return pois_candidatos