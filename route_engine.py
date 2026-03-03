import json
from geopy.distance import geodesic

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
        actual = min(pois, key=lambda p: geodesic(punto_inicio, (p["lat"], p["lon"])).km)
    else:
        centro = calcular_centro(pois)
        actual = min(pois, key=lambda p: geodesic(centro, (p["lat"], p["lon"])).km)

    ruta.append(actual)
    tiempo_total += TIEMPO_VISITA.get(actual["categoria_principal"], 30)

    restantes = [p for p in pois if p != actual]

    while restantes:
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