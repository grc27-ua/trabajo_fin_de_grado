import json

with open("data/processed/alicante_pois_culturales_descripcion.json", "r", encoding="utf-8") as f:
    pois = json.load(f)

terminos = ["roman", "lucentum", "arqueol", "romano", "ibero", "siglo i", "siglo ii"]
encontrados = [
    p for p in pois
    if any(t in (p.get("descripcion_enriquecida") or p.get("descripcion_llm") or "").lower()
           for t in terminos)
]

for p in encontrados:
    print(p["wikidata_id"], "|", p["nombre"], "|", p.get("categoria_principal"))