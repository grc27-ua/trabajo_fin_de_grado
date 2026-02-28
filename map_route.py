import json
from pathlib import Path
import folium

# Rutas
INPUT_PATH = Path("data/processed/ruta_generada.json")
OUTPUT_PATH = Path("output/mapa_ruta.html")


def crear_mapa(ruta):
    # Centro del mapa (primer POI)
    centro = (ruta[0]["lat"], ruta[0]["lon"])
    mapa = folium.Map(location=centro, zoom_start=13)

    coordenadas = []

    for i, poi in enumerate(ruta, start=1):
        coord = (poi["lat"], poi["lon"])
        coordenadas.append(coord)

        popup_texto = f"""
        <b>{i}. {poi['nombre']}</b><br>
        Tipo de arte: {poi.get('tipo_arte', 'N/D')}<br>
        {poi.get('descripcion_cultural', '')}
        """

        folium.Marker(
            location=coord,
            popup=popup_texto,
            tooltip=f"{i}. {poi['nombre']}",
            icon=folium.Icon(icon="info-sign")
        ).add_to(mapa)

    # Línea de la ruta
    folium.PolyLine(
        locations=coordenadas,
        weight=4,
        opacity=0.8
    ).add_to(mapa)

    return mapa


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    ruta = data["ruta"]

    mapa = crear_mapa(ruta)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    mapa.save(OUTPUT_PATH)

    print("Mapa generado correctamente:")
    print(OUTPUT_PATH.resolve())


if __name__ == "__main__":
    main()
