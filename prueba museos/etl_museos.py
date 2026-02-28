import pandas as pd
from pathlib import Path

# Rutas
RAW_PATH = Path("data/raw/museos_arte_madrid.csv")
OUTPUT_PATH = Path("data/processed/museos_arte_madrid.json")

# Cargar CSV
df = pd.read_csv(RAW_PATH)

# Renombrar columnas para trabajar cómodo
df = df.rename(columns={
    "museoLabel": "nombre",
    "tipoLabel": "tipo"
})

# Extraer ID Wikidata desde la URL
df["wikidata_id"] = df["museo"].apply(lambda x: x.split("/")[-1])

# Seleccionar columnas relevantes
df_clean = df[[
    "wikidata_id",
    "nombre",
    "tipo",
    "lat",
    "lon"
]]

# Eliminar duplicados (por si acaso)
df_clean = df_clean.drop_duplicates()

# Guardar en JSON
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
df_clean.to_json(OUTPUT_PATH, orient="records", force_ascii=False, indent=2)

print("ETL completado. Datos guardados en:", OUTPUT_PATH)
