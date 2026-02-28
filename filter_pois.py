import json
from pathlib import Path

INPUT_PATH = Path("data/processed/alicante_pois_clasificados_llm.json")
OUTPUT_PATH = Path("data/processed/alicante_pois_culturales.json")


def es_poi_cultural(poi):
    # Caso 1: Clasificación directa
    if poi.get("es_cultural") is True:
        return True

    # Caso 2: Dudoso resuelto por LLM
    if poi.get("es_cultural") is None and poi.get("es_cultural_llm") == "CULTURAL":
        return True

    return False


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        todos = json.load(f)

    culturales = [p for p in todos if es_poi_cultural(p)]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(culturales, f, ensure_ascii=False, indent=2)

    print(f"POIs totales: {len(todos)}")
    print(f"POIs culturales: {len(culturales)}")
    print(f"Archivo generado: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()