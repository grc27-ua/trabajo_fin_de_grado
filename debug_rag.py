"""
debug_rag.py
────────────
Script de diagnóstico para verificar que el RAG funciona correctamente.
Ejecutar desde la raíz del proyecto:

    python debug_rag.py

Muestra:
  - Si el índice existe y cuántos vectores tiene
  - Los top-10 POIs más similares a una temática de prueba
  - Los scores de similitud para ver si son razonablemente altos
"""

import pickle
import numpy as np
from pathlib import Path

try:
    import faiss
except ImportError:
    print("ERROR: faiss-cpu no está instalado. Ejecuta: pip install faiss-cpu")
    exit(1)

import ollama

INDEX_PATH      = Path("data/rag_index.faiss")
META_PATH       = Path("data/rag_meta.pkl")
EMBEDDING_MODEL = "nomic-embed-text"
OLLAMA_HOST     = "http://localhost:11434"

# ── 1. Verificar que el índice existe
print("=" * 60)
print("DIAGNOSTICO DEL INDICE RAG")
print("=" * 60)

if not INDEX_PATH.exists():
    print(f"ERROR: No se encontro el indice en {INDEX_PATH}")
    print("Arranca la app primero para que se construya el indice.")
    exit(1)

if not META_PATH.exists():
    print(f"ERROR: No se encontro el archivo de metadatos en {META_PATH}")
    exit(1)

index = faiss.read_index(str(INDEX_PATH))
with open(META_PATH, "rb") as f:
    meta = pickle.load(f)

print(f"\nIndice cargado correctamente")
print(f"  - Vectores indexados: {index.ntotal}")
print(f"  - POIs en metadatos:  {len(meta)}")
print(f"  - Dimension vectores: {index.d}")

# ── 2. Mostrar algunos POIs del indice para verificar el contenido
print(f"\n{'─'*60}")
print("MUESTRA DE POIs INDEXADOS (primeros 5):")
print(f"{'─'*60}")
for poi in meta[:5]:
    nombre = poi.get("nombre", "Sin nombre")
    cat    = poi.get("categoria_principal", "")
    desc   = poi.get("descripcion_llm", "")[:80]
    print(f"  - {nombre} ({cat})")
    print(f"    Desc: {desc}...")
    print()

# ── 3. Probar busqueda con distintas tematicas
tematicas_prueba = [
    "guerra civil espanola",
    "arquitectura arabe",
    "estilo renacentista",
    "patrimonio maritimo",
]

client = ollama.Client(host=OLLAMA_HOST)

for tematica in tematicas_prueba:
    print(f"\n{'─'*60}")
    print(f"BUSQUEDA: '{tematica}'")
    print(f"{'─'*60}")

    try:
        response  = client.embeddings(model=EMBEDDING_MODEL, prompt=tematica)
        query_vec = np.array(response["embedding"], dtype=np.float32).reshape(1, -1)
        faiss.normalize_L2(query_vec)

        k = min(10, index.ntotal)
        scores, indices = index.search(query_vec, k)

        print(f"  Top {k} resultados (score = similitud coseno):\n")
        for rank, (idx, score) in enumerate(zip(indices[0], scores[0]), 1):
            if idx < len(meta):
                poi    = meta[idx]
                nombre = poi.get("nombre", "Sin nombre")
                cat    = poi.get("categoria_principal", "")
                print(f"  {rank:2}. [{score:.4f}] {nombre} ({cat})")

        top_score = scores[0][0]
        if top_score > 0.7:
            calidad = "BUENA  - el modelo encuentra similitud clara"
        elif top_score > 0.4:
            calidad = "MEDIA  - similitud debil, resultados pueden no ser relevantes"
        else:
            calidad = "BAJA   - el modelo no encuentra relacion semantica util"
        print(f"\n  Calidad: {calidad} (score max: {top_score:.4f})")

    except Exception as e:
        print(f"  ERROR al generar embedding: {e}")
        print("  Verifica que Ollama este corriendo y nomic-embed-text descargado.")

print(f"\n{'='*60}")
print("FIN DEL DIAGNOSTICO")
print(f"{'='*60}")
