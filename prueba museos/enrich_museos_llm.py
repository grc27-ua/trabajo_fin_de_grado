import json
import requests
from pathlib import Path
import time

# Rutas
INPUT_PATH = Path("data/processed/museos_arte_madrid.json")
OUTPUT_PATH = Path("data/processed/museos_arte_madrid_enriched.json")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"

def enrich_museum(museum):
    prompt = f"""
Usa únicamente la información proporcionada.

Nombre del museo: {museum['nombre']}
Tipo de museo: {museum['tipo']}

Tareas:
1. Clasifica el museo en una categoría artística principal (por ejemplo: pintura clásica, arte moderno, arte contemporáneo, mixto).
2. Escribe una breve descripción cultural (máximo 3 frases), clara y divulgativa.

Devuelve la respuesta en JSON con las claves:
- categoria_artistica
- descripcion_cultural
"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status()

    return response.json()["response"]

def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        museums = json.load(f)

    enriched = []

    for museum in museums:
        print(f"Enriqueciendo: {museum['nombre']}")

        try:
            llm_response = enrich_museum(museum)

            # Convertimos la respuesta del LLM a dict
            llm_data = json.loads(llm_response)

            museum_enriched = {
                **museum,
                **llm_data
            }

            enriched.append(museum_enriched)

            # Pequeña pausa para no saturar
            time.sleep(1)

        except Exception as e:
            print("Error con", museum["nombre"], ":", e)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    print("Enriquecimiento completado.")
    print("Archivo generado:", OUTPUT_PATH)

if __name__ == "__main__":
    main()
