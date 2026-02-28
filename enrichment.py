import json
import requests
import time
from pathlib import Path

# =========================
# CONFIG
# =========================
INPUT_PATH = Path("data/processed/alicante_pois_culturales.json")
OUTPUT_PATH = Path("data/processed/alicante_pois_culturales_descripcion.json")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "mistral"   # cámbialo si usas otro: mistral, phi3, etc.
DELAY = 0.5  # segundos entre llamadas para no saturar

# =========================
# LLM
# =========================
def generar_descripcion_llm(poi):
    nombre = poi.get("nombre", "")
    categoria = poi.get("categoria_principal", "")
    instance_of = poi.get("instance_of", "")
    descripcion_wiki = poi.get("descripcion", "")

    prompt = f"""
Responde ÚNICAMENTE en español.

Vas a escribir una breve descripción turística (2 o 3 frases, máximo 40 palabras)
del siguiente punto de interés cultural en Alicante.

REGLAS IMPORTANTES:
- Habla SOLO de este lugar concreto: "{nombre}"
- NO menciones otros lugares (por ejemplo: Castillo de Santa Bárbara u otros)
- NO inventes datos históricos específicos
- Si no conoces bien el lugar, describe de forma general y prudente
- No uses comillas en la respuesta
- No menciones que eres una IA

DATOS:
Nombre: {nombre}
Tipo: {instance_of}
Categoría cultural: {categoria}
Descripción enciclopédica (si existe): {descripcion_wiki}

Devuelve solo la descripción final.
"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2
        }
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()

    data = response.json()
    return data["response"].strip()
# =========================
# MAIN
# =========================
def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        pois = json.load(f)

    total = len(pois)
    print(f"Generando descripciones para {total} POIs con Ollama ({MODEL_NAME})...")

    errores = 0

    for i, poi in enumerate(pois, 1):
        if poi.get("descripcion_llm"):
            continue  # no regenerar si ya existe

        try:
            descripcion = generar_descripcion_llm(poi)
            poi["descripcion_llm"] = descripcion
            print(f"[{i}/{total}]  {poi.get('nombre')}")
            print("  ", descripcion)


        except Exception as e:
            errores += 1
            print(f"[{i}/{total}]  Error en {poi.get('nombre')}: {e}")
            poi["descripcion_llm"] = None

        time.sleep(DELAY)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)

    print("\nProceso terminado")
    print("Archivo generado:", OUTPUT_PATH)
    print("Errores:", errores)


if __name__ == "__main__":
    main()