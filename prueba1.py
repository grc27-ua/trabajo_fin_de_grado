"""
detectar_duplicados.py
──────────────────────
Muestra los POIs que aparecen más de una vez en el JSON,
agrupados por wikidata_id y por nombre.
"""

import json
from collections import Counter
from pathlib import Path

INPUT_PATH = Path("data/processed/alicante_pois_culturales_descripcion.json")

with open(INPUT_PATH, "r", encoding="utf-8") as f:
    pois = json.load(f)

print(f"Total POIs en el JSON: {len(pois)}\n")

# ── Duplicados por wikidata_id ─────────────────────────────────────────────
wids = [p.get("wikidata_id") for p in pois if p.get("wikidata_id")]
contador_wid = Counter(wids)
duplicados_wid = {wid: n for wid, n in contador_wid.items() if n > 1}

print(f"{'='*60}")
print(f"DUPLICADOS POR WIKIDATA_ID ({len(duplicados_wid)} IDs repetidos)")
print(f"{'='*60}")

if duplicados_wid:
    for wid, n in sorted(duplicados_wid.items(), key=lambda x: -x[1]):
        matches = [p for p in pois if p.get("wikidata_id") == wid]
        print(f"\n  [{wid}] — aparece {n} veces")
        for m in matches:
            print(f"    - {m.get('nombre', 'Sin nombre'):50s} "
                  f"| cat: {m.get('categoria_principal', '')}")
else:
    print("  No hay duplicados por wikidata_id.")

# ── Duplicados por nombre ──────────────────────────────────────────────────
nombres = [p.get("nombre", "").strip() for p in pois]
contador_nombre = Counter(nombres)
duplicados_nombre = {n: c for n, c in contador_nombre.items() if c > 1 and n}

print(f"\n{'='*60}")
print(f"DUPLICADOS POR NOMBRE ({len(duplicados_nombre)} nombres repetidos)")
print(f"{'='*60}")

if duplicados_nombre:
    for nombre, n in sorted(duplicados_nombre.items(), key=lambda x: -x[1]):
        matches = [p for p in pois if p.get("nombre", "").strip() == nombre]
        print(f"\n  '{nombre}' — aparece {n} veces")
        for m in matches:
            print(f"    - wikidata_id: {m.get('wikidata_id', 'None'):15s} "
                  f"| cat: {m.get('categoria_principal', '')}")
else:
    print("  No hay duplicados por nombre.")

# ── Resumen ────────────────────────────────────────────────────────────────
total_duplicados = sum(n - 1 for n in duplicados_wid.values())
print(f"\n{'='*60}")
print(f"RESUMEN")
print(f"{'='*60}")
print(f"  POIs únicos por wikidata_id: {len(pois) - total_duplicados}")
print(f"  Entradas redundantes:        {total_duplicados}")
print(f"  (se eliminarían con la deduplicación global)")