
import json
from pathlib import Path

# Rutas
INPUT_PATH = Path("data/processed/museos_arte_madrid_enriched.json")
OUTPUT_PATH = Path("data/processed/museos_categorizados.json")

# Palabras clave para determinar arte/no arte
keywords_arte = ["art museum", "museo de arte", "bellas artes", "painting", "pintura", "sculpture", "escultura"]
keywords_no_arte = ["history museum", "science museum", "natural history", "ciencias", "antropología", "arqueología", "etnografía", "técnica", "arqueológico", "museo histórico"]

# Palabras clave para época
keywords_clasico = ["clásico", "clásica", "classical"]
keywords_contemporaneo = ["contemporáneo", "contemporánea", "modern", "moderno"]

# Tipos de arte
tipos_arte = ["Pintura", "Escultura", "Otro tipo de arte"]
epocas = ["Clásica", "Contemporánea"]

# Cargar JSON original
with open(INPUT_PATH, "r", encoding="utf-8") as f:
    pois = json.load(f)

# 1️⃣ Eliminar duplicados por wikidata_id
seen_ids = set()
pois_unique = []
for poi in pois:
    if poi["wikidata_id"] not in seen_ids:
        pois_unique.append(poi)
        seen_ids.add(poi["wikidata_id"])

print(f"POIs únicos: {len(pois_unique)}")

# 2️⃣ Clasificación jerárquica
pois_categorizados = []

for poi in pois_unique:
    tipo_texto = poi.get("tipo", "").lower()
    instance_label = poi.get("instance_of_label", "").lower()  # Ej: "art museum", "history museum"

    # Determinar si es museo
    es_museo = "museum" in tipo_texto or "museo" in tipo_texto

    if es_museo:
        # Determinar si es arte o no
        arte = False
        if any(k in instance_label for k in keywords_arte):
            arte = True
        elif any(k in instance_label for k in keywords_no_arte):
            arte = False
        else:
            # caso mixto/desconocido: asignar a "Otro tipo de arte"
            arte = True

        if arte:
            # Determinar tipo de arte
            categoria_artistica = poi.get("categoria_artistica", "").lower()
            tipos_asignados = []

            if "pintura" in categoria_artistica:
                tipos_asignados.append("Pintura")
            if "escultura" in categoria_artistica:
                tipos_asignados.append("Escultura")
            if not tipos_asignados or "mixto" in categoria_artistica:
                tipos_asignados = ["Pintura", "Escultura", "Otro tipo de arte"]

            # Determinar época
            epocas_asignadas = []
            for k in keywords_clasico:
                if k in categoria_artistica:
                    epocas_asignadas.append("Clásica")
                    break
            for k in keywords_contemporaneo:
                if k in categoria_artistica:
                    epocas_asignadas.append("Contemporánea")
                    break
            if not epocas_asignadas:
                epocas_asignadas = ["Clásica", "Contemporánea"]

            # Crear POIs duplicados según tipo y época
            for tipo in tipos_asignados:
                for epoca in epocas_asignadas:
                    pois_categorizados.append({
                        **poi,
                        "categoria_principal": "Museos",
                        "subcategoria": "Arte",
                        "tipo_arte": tipo,
                        "epoca": epoca
                    })
        else:
            # Museo no artístico
            pois_categorizados.append({
                **poi,
                "categoria_principal": "Museos",
                "subcategoria": "No arte",
                "tipo_arte": None,
                "epoca": None
            })
    else:
        # Otros POIs: Patrimonio u Otros (para futuro)
        pois_categorizados.append({
            **poi,
            "categoria_principal": "Otros",
            "subcategoria": None,
            "tipo_arte": None,
            "epoca": None
        })

# Guardar JSON final
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(pois_categorizados, f, ensure_ascii=False, indent=2)

print(f"Clasificación completada. POIs finales: {len(pois_categorizados)}")
print("Archivo generado:", OUTPUT_PATH)
