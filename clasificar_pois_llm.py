import json
import requests
import time

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"

def clasificar_poi_llm(poi):
    prompt = f"""
Clasifica este punto de interés para rutas turísticas culturales urbanas.

Nombre: {poi.get("nombre")}
Categoría principal: {poi.get("categoria_principal")}
Descripción: {poi.get("descripcion", "")}
Tipo Wikidata: {poi.get("instance_of", "")}

Responde SOLO una palabra:
- CULTURAL
- NO_CULTURAL
- DUDOSO
"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()

    text = response.json()["response"].strip().upper()

    if "CULTURAL" in text and "NO_CULTURAL" not in text:
        return "CULTURAL"
    if "NO_CULTURAL" in text:
        return "NO_CULTURAL"
    return "DUDOSO"


def main():
    with open("data/processed/alicante_pois_base.json", "r", encoding="utf-8") as f:
        pois = json.load(f)

    total = 0

    for poi in pois:
        if poi.get("es_cultural") is None:
            total += 1
            print(f"Clasificando: {poi['nombre']}")

            try:
                resultado = clasificar_poi_llm(poi)
                poi["es_cultural_llm"] = resultado
                print(" →", resultado)
                time.sleep(0.5)  # para no saturar Ollama

            except Exception as e:
                print("Error:", e)
                poi["es_cultural_llm"] = "ERROR"

    with open("alicante_pois_clasificados_llm.json", "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)

    print(f"\nClasificados {total} POIs dudosos.")


if __name__ == "__main__":
    main()
