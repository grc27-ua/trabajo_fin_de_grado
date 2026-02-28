import json
from pathlib import Path
from geopy.distance import geodesic

# Rutas
INPUT_PATH = Path("data/processed/alicante_pois_culturales_descripcion.json")
OUTPUT_PATH = Path("data/processed/ruta_generada.json")

# Velocidades medias (km/h)
VELOCIDADES = {
    "andando": 4.5,
    "bicicleta": 15,
    "coche": 30
}

# Tiempo estimado de visita (min)
TIEMPO_VISITA = {
    "Museos": 45,
    "Castillos": 45,
    "Palacios": 20,
    "Edificios religiosos": 15,
    "Monumentos": 5,
    "Espacios culturales": 15,
    "Espacios urbanos de interés": 30,
    "Calles y avenidas": 15,
    "Edificios de interés cultural": 15,  
    "Bibliotecas": 30,
    "Fuentes": 15,
    "Playas": 30,
    "Torres": 15,
    "Estadios": 20,
    "Cines": 30,
    "Fosas comúnes": 5,
    "Faros": 15,
    "Espacios naturales": 60, 
    "Otros POIs culturales": 30
}


def calcular_distancia_km(poi1, poi2):
    coord1 = (poi1["lat"], poi1["lon"])
    coord2 = (poi2["lat"], poi2["lon"])
    return geodesic(coord1, coord2).km


def calcular_centro(pois):
    return (
        sum(p["lat"] for p in pois) / len(pois),
        sum(p["lon"] for p in pois) / len(pois)
    )

def generar_ruta(pois, transporte, duracion_max_min, punto_inicio=None):
    velocidad = VELOCIDADES[transporte]  # km/h
    tiempo_total = 0
    ruta = []

    # Elegir POI inicial
    if punto_inicio is not None:
        # Se toma el POI más cercano al punto de inicio
        actual = min(pois, key=lambda p: geodesic(punto_inicio, (p["lat"], p["lon"])).km)
    else:
        # Si no hay punto de inicio, usamos el centro de todos los POIs
        centro = calcular_centro(pois)
        actual = min(pois, key=lambda p: geodesic(centro, (p["lat"], p["lon"])).km)

    ruta.append(actual)
    tiempo_total += TIEMPO_VISITA.get(actual["categoria_principal"], 30)

    restantes = [p for p in pois if p != actual]

    while restantes:
        # POI más cercano al actual
        siguiente = min(
            restantes,
            key=lambda p: calcular_distancia_km(actual, p)
        )

        distancia = calcular_distancia_km(actual, siguiente)
        tiempo_desplazamiento = (distancia / velocidad) * 60  # minutos
        tiempo_visita = TIEMPO_VISITA.get(siguiente["categoria_principal"], 30)

        if tiempo_total + tiempo_desplazamiento + tiempo_visita > duracion_max_min:
            break

        tiempo_total += tiempo_desplazamiento + tiempo_visita
        ruta.append(siguiente)
        restantes.remove(siguiente)
        actual = siguiente

    return ruta, tiempo_total


def eliminar_duplicados_por_categoria(pois):
    """
    Elimina POIs duplicados dentro de la misma categoría
    (mismo wikidata_id en la misma categoria_principal)
    """
    filtrados = []
    vistos = {}  # key: categoria_principal, value: set de wikidata_id

    for poi in pois:
        cat = poi.get("categoria_principal")
        wid = poi.get("wikidata_id")

        if cat not in vistos:
            vistos[cat] = set()

        if wid not in vistos[cat]:
            filtrados.append(poi)
            vistos[cat].add(wid)

    return filtrados


def main():
    
    transporte = "andando"      # andando | bicicleta | coche
    duracion_max = 180          # minutos
    categoria_seleccionada = "Edificios religiosos"
    punto_inicio = (38.54616667, -0.47030556)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        todos = json.load(f)

    pois = [
        p for p in todos
        if p.get("lat") and p.get("lon")
        and (p.get("es_cultural") is True or p.get("es_cultural_llm") == "CULTURAL")
        and p.get("categoria_principal") == categoria_seleccionada
    ]
    pois = eliminar_duplicados_por_categoria(pois)


    if len(pois) < 2:
        print("No hay suficientes POIs para generar una ruta.")
        return


    ruta, tiempo_total = generar_ruta(pois, transporte, duracion_max, punto_inicio)

    resultado = {
        "transporte": transporte,
        "duracion_maxima_min": duracion_max,
        "duracion_total_min": round(tiempo_total, 1),
        "numero_pois": len(ruta),
        "ruta": ruta
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"Ruta generada con {len(ruta)} POIs")
    print(f"Duración total estimada: {round(tiempo_total, 1)} minutos")
    print("Archivo generado:", OUTPUT_PATH)


if __name__ == "__main__":
    main()