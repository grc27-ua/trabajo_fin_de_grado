import json
from pathlib import Path

INPUT_PATH = Path("data/processed/alicante_pois_base.json")
OUTPUT_PATH = Path("data/processed/alicante_pois_otros.json")


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        pois = json.load(f)

    otros = [poi for poi in pois if poi.get("categoria_principal") == "Otros POIs culturales"]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(otros, f, ensure_ascii=False, indent=2)

    print(f"Total POIs: {len(pois)}")
    print(f"POIs en 'Otros POIs culturales': {len(otros)}")
    print("Archivo generado en:")
    print(OUTPUT_PATH.resolve())


if __name__ == "__main__":
    main()
