from flask import Flask, render_template, request
import json
import folium
import openrouteservice
from route_engine import generar_ruta, eliminar_duplicados_por_categoria, VELOCIDADES, TIEMPO_VISITA
from pathlib import Path

app = Flask(__name__)

INPUT_PATH = Path("data/processed/alicante_pois_culturales_descripcion.json")
CATEGORIAS = list(TIEMPO_VISITA.keys())

# Tu API Key de ORS
ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImQzMjVhNDcxMzgxNjRmOGY5NWI0NjIzMTU3NjA0MTRmIiwiaCI6Im11cm11cjY0In0="
ORS_PROFILES = {
    "andando": "foot-walking",
    "bicicleta": "cycling-regular",
    "coche": "driving-car"
}


@app.route("/")
def index():
    return render_template("index.html", categorias=CATEGORIAS)


@app.route("/generar", methods=["POST"])
def generar():
    # Datos del formulario
    transporte = request.form["transporte"]
    tiempo_max = int(request.form["tiempo"])
    categorias = request.form.getlist("categorias")

    lat_inicio = float(request.form["lat"])
    lon_inicio = float(request.form["lon"])
    punto_inicio = (lat_inicio, lon_inicio)

    # Cargar POIs
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        todos = json.load(f)

    pois = [
        p for p in todos
        if p.get("lat") and p.get("lon")
        and (p.get("es_cultural") is True or p.get("es_cultural_llm") == "CULTURAL")
        and p.get("categoria_principal") in categorias
    ]
    pois = eliminar_duplicados_por_categoria(pois)

    if len(pois) < 2:
        return "No hay suficientes POIs para generar una ruta."

    # Generar ruta
    ruta, tiempo_total = generar_ruta(pois, transporte, tiempo_max, punto_inicio)

    # Crear mapa centrado en punto de inicio
    mapa = folium.Map(location=[lat_inicio, lon_inicio], zoom_start=13)

    # Crear cliente ORS
    client = openrouteservice.Client(key=ORS_API_KEY)
    coords = [(poi["lon"], poi["lat"]) for poi in ruta]

    try:
        ruta_geojson = client.directions(
            coordinates=coords,
            profile=ORS_PROFILES[transporte],
            format="geojson"
        )
        folium.GeoJson(ruta_geojson, name="Ruta por calles", style_function=lambda x: {"color": "blue", "weight": 5, "opacity": 0.7}).add_to(mapa)
    except Exception as e:
        print("Error generando ruta por calles ORS:", e)
        # Si ORS falla, dibujar línea simple
        folium.PolyLine([(poi["lat"], poi["lon"]) for poi in ruta], color="blue", weight=5, opacity=0.7).add_to(mapa)

    # Añadir marcadores con número y descripción
    for i, poi in enumerate(ruta, start=1):
        popup_html = f"""
        <b>{i}. {poi['nombre']}</b><br>
        <b>Categoría:</b> {poi.get('categoria_principal', 'N/D')}<br><br>
        <i>{poi.get('descripcion_llm', '')}</i>
        """
        folium.Marker(
            [poi["lat"], poi["lon"]],
            popup=popup_html,
            tooltip=f"{i}. {poi['nombre']}",
            icon=folium.Icon(icon="info-sign")
        ).add_to(mapa)

    mapa_html = mapa._repr_html_()

    return render_template(
        "resultado.html",
        mapa=mapa_html,
        tiempo_total=round(tiempo_total, 1),
        num_pois=len(ruta)
    )


if __name__ == "__main__":
    app.run(debug=True)