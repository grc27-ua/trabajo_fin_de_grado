"""
enriquecer_descripciones.py
────────────────────────────
Enriquece las descripciones de los POIs del JSON usando dos fuentes:

  1. Wikipedia en español (via API, gratis, sin clave): para los POIs que
     tienen artículo en la Wikipedia española se obtiene el extracto introductorio.

  2. Mistral via Ollama (fallback): para los POIs sin artículo Wikipedia,
     se genera una descripción con un prompt más específico que el que se usó
     originalmente, incluyendo categoría y coordenadas para dar contexto geográfico.

El resultado se guarda en un nuevo campo "descripcion_enriquecida" para no
perder las descripciones originales. También se guarda un campo "fuente_descripcion"
con el valor "wikipedia" u "ollama" para saber de dónde viene cada descripción.

Uso:
    python enriquecer_descripciones.py

Requisitos:
    pip install requests ollama
    ollama pull mistral
"""

import json
import time
import urllib.parse
from pathlib import Path

import requests
import ollama

# ── Configuración ──────────────────────────────────────────────────────────────
INPUT_PATH  = Path("data/processed/alicante_pois_culturales_descripcion.json")
OUTPUT_PATH = Path("data/processed/alicante_pois_culturales_descripcion.json")
BACKUP_PATH = Path("data/processed/alicante_pois_culturales_descripcion_backup.json")

OLLAMA_HOST  = "http://localhost:11434"
OLLAMA_MODEL = "mistral"

WIKIPEDIA_API = "https://es.wikipedia.org/w/api.php"
WIKIDATA_API  = "https://www.wikidata.org/w/api.php"

HEADERS = {"User-Agent": "TFG-RutasCulturalesAlicante/1.0 (trabajo académico)"}

# Pausa entre llamadas a la API de Wikipedia para no saturarla
DELAY_WIKIPEDIA = 0.5   # segundos
DELAY_OLLAMA    = 0.2   # segundos
# ──────────────────────────────────────────────────────────────────────────────


def get_wikipedia_title(wikidata_id: str) -> str | None:
    """Obtiene el título del artículo en Wikipedia ES a partir del wikidata_id."""
    try:
        params = {
            "action": "wbgetentities",
            "ids": wikidata_id,
            "languages": "es",
            "props": "sitelinks",
            "format": "json"
        }
        r = requests.get(WIKIDATA_API, params=params, headers=HEADERS, timeout=10)
        data = r.json()
        entity    = data.get("entities", {}).get(wikidata_id, {})
        sitelinks = entity.get("sitelinks", {})
        eswiki    = sitelinks.get("eswiki", {})
        return eswiki.get("title")
    except Exception:
        return None


def get_wikipedia_extract(title: str, max_chars: int = 600) -> str | None:
    """Obtiene el extracto introductorio de un artículo de Wikipedia ES."""
    try:
        params = {
            "action":      "query",
            "titles":      title,
            "prop":        "extracts",
            "exintro":     1,
            "explaintext": 1,
            "format":      "json"
        }
        r = requests.get(WIKIPEDIA_API, params=params, headers=HEADERS, timeout=10)
        data  = r.json()
        pages = data.get("query", {}).get("pages", {})
        page  = list(pages.values())[0]

        if "missing" in page:
            return None

        extract = page.get("extract", "").strip()
        if not extract or len(extract) < 50:
            return None

        # Truncar al primer párrafo completo que sea suficientemente largo
        parrafos = [p.strip() for p in extract.split("\n") if len(p.strip()) > 80]
        if parrafos:
            texto = parrafos[0]
            if len(texto) > max_chars:
                # Cortar en el último punto antes del límite
                corte = texto[:max_chars].rfind(".")
                texto = texto[:corte + 1] if corte > 0 else texto[:max_chars]
            return texto

        return None
    except Exception:
        return None


def generar_descripcion_ollama(poi: dict, client: ollama.Client) -> str:
    """Genera una descripción con Mistral para POIs sin artículo en Wikipedia."""
    nombre   = poi.get("nombre", "")
    cat      = poi.get("categoria_principal", "")
    lat      = poi.get("lat", "")
    lon      = poi.get("lon", "")
    desc_raw = poi.get("descripcion", "")   # descripción original de Wikidata (en inglés)

    prompt = (
        f"Escribe una descripción cultural breve (3-4 frases) en español sobre '{nombre}', "
        f"un/a {cat.lower()} situado/a en Alicante, España "
        f"(coordenadas: {lat:.4f}N, {abs(lon):.4f}O). "
    )
    if desc_raw:
        prompt += f"Información disponible: {desc_raw}. "
    prompt += (
        "Si no tienes información específica sobre este lugar, describe qué tipo de lugar es "
        "y su posible relevancia cultural para la ciudad de Alicante. "
        "No inventes datos históricos concretos que no conozcas. "
        "Responde únicamente con el texto de la descripción, sin título ni introducción."
    )

    try:
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": "Eres un experto en patrimonio cultural de Alicante. Respondes siempre en español con precisión y brevedad."},
                {"role": "user",   "content": prompt}
            ]
        )
        return response["message"]["content"].strip()
    except Exception as e:
        print(f"    Error Ollama: {e}")
        return poi.get("descripcion_llm", "")   # mantener la descripción anterior


def main():
    # Cargar datos
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        pois = json.load(f)

    print(f"Total POIs a procesar: {len(pois)}")

    # Hacer backup antes de modificar
    with open(BACKUP_PATH, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)
    print(f"Backup guardado en {BACKUP_PATH}")

    client_ollama = ollama.Client(host=OLLAMA_HOST)

    stats = {"wikipedia": 0, "ollama": 0, "sin_cambio": 0, "errores": 0}

    for i, poi in enumerate(pois):
        nombre      = poi.get("nombre", "Sin nombre")
        wikidata_id = poi.get("wikidata_id", "")

        print(f"[{i+1:3}/{len(pois)}] {nombre[:50]}")

        # Si ya tiene descripción enriquecida, saltar
        if poi.get("descripcion_enriquecida"):
            print(f"         Ya procesado, saltando.")
            stats["sin_cambio"] += 1
            continue

        descripcion_nueva = None
        fuente            = None

        # ── Intentar Wikipedia primero
        if wikidata_id:
            time.sleep(DELAY_WIKIPEDIA)
            wiki_title = get_wikipedia_title(wikidata_id)

            if wiki_title:
                time.sleep(DELAY_WIKIPEDIA)
                extract = get_wikipedia_extract(wiki_title)

                if extract:
                    descripcion_nueva = extract
                    fuente            = "wikipedia"
                    print(f"         Wikipedia: {extract[:80]}...")
                    stats["wikipedia"] += 1

        # ── Fallback a Mistral si Wikipedia no tiene nada
        if not descripcion_nueva:
            time.sleep(DELAY_OLLAMA)
            descripcion_nueva = generar_descripcion_ollama(poi, client_ollama)
            fuente            = "ollama"
            print(f"         Ollama: {descripcion_nueva[:80]}...")
            stats["ollama"] += 1

        # Guardar en el POI
        poi["descripcion_enriquecida"] = descripcion_nueva
        poi["fuente_descripcion"]      = fuente

        # Guardar progreso cada 20 POIs para no perder trabajo si falla
        if (i + 1) % 20 == 0:
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(pois, f, ensure_ascii=False, indent=2)
            print(f"    >> Progreso guardado ({i+1}/{len(pois)})")

    # Guardado final
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(pois, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"PROCESO COMPLETADO")
    print(f"  Wikipedia: {stats['wikipedia']} POIs")
    print(f"  Ollama:    {stats['ollama']} POIs")
    print(f"  Sin cambio: {stats['sin_cambio']} POIs")
    print(f"  Guardado en: {OUTPUT_PATH}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()