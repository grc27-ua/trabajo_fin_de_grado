import json
from pathlib import Path
import folium
import openrouteservice

# ======================
# CONFIGURACIÓN
# ======================

ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImQzMjVhNDcxMzgxNjRmOGY5NWI0NjIzMTU3NjA0MTRmIiwiaCI6Im11cm11cjY0In0="

INPUT_PATH = Path("data/processed/ruta_generada.json")
OUTPUT_PATH = Path("output/mapa_ruta_calles.html")

ORS_PROFILES = {
    "andando": "foot-walking",
    "bicicleta": "cycling-regular",
    "coche": "driving-car"
}

# ======================
# FUNCIONES
# ======================

def obtener_geometria_ruta(cliente, coords, perfil):
    """
    coords: [(lon, lat), (lon, lat), ...]
    """
    ruta = cliente.directions(
        coordinates=coords,
        profile=perfil,
        format="geojson"
    )
    return ruta


def crear_mapa(ruta_pois, transporte):
    cliente = openrouteservice.Client(key=ORS_API_KEY)

    perfil = ORS_PROFILES[transporte]

    # Coordenadas ORS (lon, lat)
    coords = [(poi["lon"], poi["lat"]) for poi in ruta_pois]

    ruta_geojson = obtener_geometria_ruta(cliente, coords, perfil)

    # Centro del mapa
    centro = (ruta_pois[0]["lat"], ruta_pois[0]["lon"])
    mapa = folium.Map(location=centro, zoom_start=13)

    # Dibujar ruta por calles
    folium.GeoJson(
        ruta_geojson,
        name="Ruta por calles"
    ).add_to(mapa)

    # Marcadores
    for i, poi in enumerate(ruta_pois, start=1):
        popup = folium.Popup(f"""
        <div style="width: 250px;">
            <h4>{i}. {poi['nombre']}</h4>
            <b>Categoría:</b> {poi.get('categoria_principal', 'N/D')}<br><br>
            <i>{poi.get('descripcion_llm', 'N/D')}</i>
        </div>
        """, max_width=300)
        folium.Marker(
            location=(poi["lat"], poi["lon"]),
            popup=popup,
            tooltip=f"{i}. {poi['nombre']}",
            icon=folium.Icon(icon="info-sign")
        ).add_to(mapa)

    folium.LayerControl().add_to(mapa)

    return mapa


# ======================
# MAIN
# ======================

def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    ruta_pois = data["ruta"]
    transporte = data["transporte"]

    mapa = crear_mapa(ruta_pois, transporte)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    mapa.save(OUTPUT_PATH)

    print("Mapa con ruta realista generado:")
    print(OUTPUT_PATH.resolve())


if __name__ == "__main__":
    main()
