import json
from pathlib import Path
from typing import List, Optional

# Rutas
INPUT_PATH = Path("data/processed/museos_categorizados.json")
OUTPUT_PATH = Path("data/processed/pois_filtrados_usuario.json")


def filtrar_pois(
    pois: list,
    categoria_principal: Optional[str] = None,
    subcategoria: Optional[str] = None,
    tipos_arte: Optional[List[str]] = None,
    epocas: Optional[List[str]] = None
) -> list:
    """
    Filtra POIs según las preferencias del usuario.
    """

    resultado = []

    for poi in pois:
        if categoria_principal and poi.get("categoria_principal") != categoria_principal:
            continue

        if subcategoria and poi.get("subcategoria") != subcategoria:
            continue

        if tipos_arte and poi.get("tipo_arte") not in tipos_arte:
            continue

        if epocas and poi.get("epoca") not in epocas:
            continue

        resultado.append(poi)

    return resultado


def main():
    # Cargar POIs
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        pois = json.load(f)

    # 🔧 Preferencias del usuario (simulación)
    preferencias_usuario = {
        "categoria_principal": "Museos",
        "subcategoria": "Arte",
        "tipos_arte": ["Pintura"],
        "epocas": ["Clásica"]
    }

    pois_filtrados = filtrar_pois(
        pois,
        categoria_principal=preferencias_usuario["categoria_principal"],
        subcategoria=preferencias_usuario["subcategoria"],
        tipos_arte=preferencias_usuario["tipos_arte"],
        epocas=preferencias_usuario["epocas"]
    )

    # Guardar resultado
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(pois_filtrados, f, ensure_ascii=False, indent=2)

    print(f"POIs totales: {len(pois)}")
    print(f"POIs filtrados: {len(pois_filtrados)}")
    print("Archivo generado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
