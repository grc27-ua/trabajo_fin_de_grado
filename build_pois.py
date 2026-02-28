import json
from pathlib import Path

INPUT_PATH = Path("data/raw/alicante.json")
OUTPUT_PATH = Path("data/processed/alicante_pois_base.json")


def mapear_categoria_principal(instance_label: str):
    label = instance_label.lower()

    if "muse" in label or "galería" in label:
        return "Museos", True
    if "castillo" in label or "fortaleza" in label:
        return "Castillos", True
    if "palacio" in label:
        return "Palacios", True
    if "iglesia" in label or "catedral" in label or "basílica" in label or "ermita" in label or "convento" in label or "monasterio" in label:
        return "Edificios religiosos", True
    if "monumento" in label or "estatua" in label or "escultura" in label:
        return "Monumentos", True
    if "teatro" in label or "plaza de toros" in label or "auditorio" in label or "centro cultural" in label:
        return "Espacios culturales", True
    if "plaza" in label or "barrio" in label or "mirador" in label:
        return "Espacios urbanos de interés", True
    if "calle" in label or "avenida" in label or "esplanada" in label or "paseo" in label:
        return "Calles y avenidas", True
    if "edificio" in label or "casa" in label or "rascacielos" in label or "hotel" in label:
        return "Edificios de interés cultural", True
    if "colegio" in label or "instituto" in label or "educa" in label or "escuela" in label or "conservatorio" in label:
        return "Centros educativos", False
    if "biblioteca" in label or "archivo" in label:
        return "Bibliotecas", True
    if "fuente" in label:
        return "Fuentes", True
    if "playa" in label or "bahía" in label:
        return "Playas", True 
    if "parada" in label or "estación" in label:
        return "Paradas Tram", False
    if "torre" in label:
        return "Torres", True
    if "hospital" in label:
        return "Hospitales", False
    if "estadio" in label:
        return "Estadios", True
    if "cine" in label:
        return "Cines", True
    if "fosa" in label:
        return "Fosas comúnes", True
    if "faro" in label:
        return "Faros", True 
    if "parque" in label or "colina" in label or "montaña" in label or "cerro" in label:
        return "Espacios naturales", True 
    return "Otros POIs culturales", None


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    pois = []

    for row in data:
        wikidata_url = row["item"]
        wikidata_id = wikidata_url.split("/")[-1]

        poi = {
            "wikidata_id": wikidata_id,
            "nombre": row.get("itemLabel", ""),
            "lat": float(row.get("lat")),
            "lon": float(row.get("lon")),
            "instance_of": row.get("instanceOfLabel", ""),
            "descripcion": row.get("description", "")
        }

        poi["categoria_principal"] = mapear_categoria_principal(poi["instance_of"])
        categoria, es_cultural = mapear_categoria_principal(poi["instance_of"])
        poi["categoria_principal"] = categoria
        poi["es_cultural"] = es_cultural

        pois.append(poi)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)

    print(f"POIs procesados: {len(pois)}")
    print("Archivo generado en:")
    print(OUTPUT_PATH.resolve())


if __name__ == "__main__":
    main()
