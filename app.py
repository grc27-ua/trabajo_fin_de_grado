from flask import Flask, render_template, request, make_response
import json
import io
import os
import openrouteservice
from fpdf import FPDF, XPos, YPos
from dotenv import load_dotenv
from route_engine import generar_ruta, eliminar_duplicados_por_categoria, TIEMPO_VISITA
from rag_engine import build_index, buscar_pois_por_tematica
from pathlib import Path

load_dotenv()

app = Flask(__name__)

INPUT_PATH = Path("data/processed/alicante_pois_culturales_descripcion.json")
CATEGORIAS = list(TIEMPO_VISITA.keys())

ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImQzMjVhNDcxMzgxNjRmOGY5NWI0NjIzMTU3NjA0MTRmIiwiaCI6Im11cm11cjY0In0="
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Construir índice FAISS al arrancar (solo si no existe ya en disco)
with open(INPUT_PATH, "r", encoding="utf-8") as _f:
    _todos_pois = json.load(_f)

build_index(_todos_pois, ollama_host=OLLAMA_HOST, force_rebuild=False)
del _todos_pois

ORS_PROFILES = {
    "andando":   "foot-walking",
    "bicicleta": "cycling-regular",
    "coche":     "driving-car",
}

TRANSPORTE_LABEL = {
    "andando":   "a pie",
    "bicicleta": "en bicicleta",
    "coche":     "en coche",
}


@app.route("/")
def index():
    return render_template("index.html", categorias=CATEGORIAS)


@app.route("/generar", methods=["POST"])
def generar():
    transporte = request.form["transporte"]
    tiempo_max = int(request.form["tiempo"])
    categorias = request.form.getlist("categorias")

    lat_inicio = float(request.form["lat"])
    lon_inicio = float(request.form["lon"])
    punto_inicio = (lat_inicio, lon_inicio)

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        todos = json.load(f)

    pois = [
        p for p in todos
        if p.get("lat") and p.get("lon")
        and (p.get("es_cultural") is True or p.get("es_cultural_llm") == "CULTURAL")
        and p.get("categoria_principal") in categorias
    ]

    pois = eliminar_duplicados_por_categoria(pois)

    # Filtrado semántico por temática (RAG) — solo si el usuario escribió algo
    tematica = request.form.get("tematica", "").strip()
    if tematica:
        pois = buscar_pois_por_tematica(
            tematica,
            pois_candidatos=pois,
            top_k=80,
            ollama_host=OLLAMA_HOST,
        )

    if len(pois) < 2:
        return "No hay suficientes POIs para generar una ruta."

    # ── PUNTO DE PARTIDA COMO POI SINTÉTICO ──────────────────────────────────
    poi_inicio = {
        "wikidata_id":          "inicio_usuario",
        "nombre":               "Punto de partida",
        "lat":                  lat_inicio,
        "lon":                  lon_inicio,
        "categoria_principal":  "inicio",
        "descripcion_llm":      "Punto de inicio seleccionado por el usuario en el mapa.",
        "descripcion_enriquecida": "",
        "es_cultural":          False,
    }

    ruta, tiempo_total = generar_ruta(pois, transporte, tiempo_max, punto_inicio)

    # Insertar el punto de partida como primer elemento de la ruta
    ruta = [poi_inicio] + ruta

    # Ruta real por calles con ORS
    ruta_calles_json = None
    instrucciones_json = None
    ors_fallback = False

    if len(ruta) >= 2:
        if not ORS_API_KEY:
            ors_fallback = True
        else:
            try:
                client_ors = openrouteservice.Client(key=ORS_API_KEY)
                coords_ors = [(poi["lon"], poi["lat"]) for poi in ruta]

                # --- GeoJSON para el trazado del mapa ---
                ruta_geojson = client_ors.directions(
                    coordinates=coords_ors,
                    profile=ORS_PROFILES[transporte],
                    format="geojson",
                )
                ruta_calles_json = json.dumps(ruta_geojson, ensure_ascii=False)

                # --- JSON con instrucciones turn-by-turn ---
                ors_json = client_ors.directions(
                    coordinates=coords_ors,
                    profile=ORS_PROFILES[transporte],
                    format="json",
                    instructions=True,
                    language="es",
                )

                segmentos = ors_json["routes"][0]["segments"]
                instrucciones = []
                for seg in segmentos:
                    pasos = []
                    for paso in seg.get("steps", []):
                        instruccion = paso.get("instruction", "")
                        distancia   = paso.get("distance", 0)
                        duracion    = paso.get("duration", 0)
                        if instruccion:
                            pasos.append({
                                "instruccion": instruccion,
                                "distancia":   round(distancia),
                                "duracion":    round(duracion / 60, 1),
                            })
                    instrucciones.append(pasos)
                instrucciones_json = json.dumps(instrucciones, ensure_ascii=False)

            except Exception as e:
                print(f"ORS falló: {e}")
                ors_fallback = True

    resumen_narrativo = None

    # Contexto serializado (excluir poi_inicio del narrativo)
    pois_para_narrativo = [p for p in ruta if p.get("wikidata_id") != "inicio_usuario"]
    contexto_chat = json.dumps([
        {
            "nombre":      p.get("nombre", "Sin nombre"),
            "categoria":   p.get("categoria_principal", ""),
            "descripcion": p.get("descripcion_enriquecida", ""),
        }
        for p in pois_para_narrativo
    ], ensure_ascii=False)

    ruta_json = json.dumps([
        {
            "nombre":              p.get("nombre", "Sin nombre"),
            "lat":                 p["lat"],
            "lon":                 p["lon"],
            "categoria_principal": p.get("categoria_principal", ""),
            "descripcion_llm":     p.get("descripcion_llm", ""),
            "wikidata_id":         p.get("wikidata_id", ""),
        }
        for p in ruta
    ], ensure_ascii=False)

    tiempo_visita_json = json.dumps(TIEMPO_VISITA, ensure_ascii=False)

    return render_template(
        "resultado.html",
        tiempo_total=round(tiempo_total, 1),
        num_pois=len(ruta),
        ruta_json=ruta_json,
        tiempo_visita_json=tiempo_visita_json,
        ruta_calles_json=ruta_calles_json,
        ors_fallback=ors_fallback,
        transporte=transporte,
        instrucciones_json=instrucciones_json,
        resumen_narrativo=resumen_narrativo,
        contexto_chat=contexto_chat,
        tematica=tematica,
    )


def _safe(text):
    """Convierte texto a latin-1 sustituyendo caracteres no soportados."""
    return (text or "").encode("latin-1", "replace").decode("latin-1")


def _dist_km(a, b):
    from math import radians, sin, cos, sqrt, atan2
    R = 6371
    dlat = radians(b["lat"] - a["lat"])
    dlon = radians(b["lon"] - a["lon"])
    s = sin(dlat/2)**2 + cos(radians(a["lat"])) * cos(radians(b["lat"])) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(s), sqrt(1 - s))


@app.route("/exportar_pdf", methods=["POST"])
def exportar_pdf():
    """Genera y devuelve un PDF con el itinerario y las instrucciones turn-by-turn."""
    ruta         = json.loads(request.form.get("ruta_json", "[]"))
    tiempo       = float(request.form.get("tiempo_total", 0))
    transporte   = request.form.get("transporte", "andando")
    instrucciones = json.loads(request.form.get("instrucciones_json", "null") or "null")

    # Excluir el poi de inicio del PDF (no es una parada cultural)
    ruta_pdf = [p for p in ruta if p.get("wikidata_id") != "inicio_usuario"]

    VELOCIDADES_PDF = {"andando": 4.5, "bicicleta": 15, "coche": 30}
    TRANS_LABEL     = {"andando": "a pie", "bicicleta": "en bicicleta", "coche": "en coche"}
    vel = VELOCIDADES_PDF.get(transporte, 4.5)
    dist_total = sum(_dist_km(ruta_pdf[i], ruta_pdf[i+1]) for i in range(len(ruta_pdf) - 1))

    pdf = FPDF()
    pdf.add_font("DejaVu",   fname="DejaVuSans.ttf",        uni=True)
    pdf.add_font("DejaVu", "B", fname="DejaVuSans-Bold.ttf",    uni=True)
    pdf.add_font("DejaVu", "I", fname="DejaVuSans-Oblique.ttf", uni=True)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    NL = {"new_x": XPos.LMARGIN, "new_y": YPos.NEXT}

    # ── Cabecera
    pdf.set_font("DejaVu", "B", 20)
    pdf.set_text_color(26, 22, 18)
    pdf.cell(0, 10, "Ruta Cultural — Alicante", **NL)

    pdf.set_font("DejaVu", "", 10)
    pdf.set_text_color(74, 66, 56)
    pdf.cell(0, 6,
        f"{len(ruta_pdf)} paradas | {round(tiempo)} min | "
        f"{dist_total:.1f} km | {TRANS_LABEL.get(transporte, transporte)}", **NL)
    pdf.ln(2)
    pdf.set_draw_color(193, 68, 14)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # ── Índice de paradas
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(26, 22, 18)
    pdf.cell(0, 5, "Paradas de la ruta:", **NL)
    pdf.set_font("DejaVu", "", 9)
    pdf.set_text_color(74, 66, 56)
    for i, poi in enumerate(ruta_pdf, 1):
        pdf.cell(0, 4,
            f"  {i}. {poi.get('nombre', '')} ({poi.get('categoria_principal', '')})",
            **NL)
    pdf.ln(4)
    pdf.set_draw_color(212, 201, 176)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # ── Itinerario detallado
    pdf.set_font("DejaVu", "B", 14)
    pdf.set_text_color(26, 22, 18)
    pdf.cell(0, 9, "Itinerario detallado", **NL)
    pdf.ln(2)

    # Ajustar índice de instrucciones: el segmento 0 es inicio→primer_poi,
    # que en ruta_pdf no existe, así que las instrucciones empiezan en idx 1
    instr_offset = 1  # ruta[0] es poi_inicio, ruta[1] es ruta_pdf[0]

    for i, poi in enumerate(ruta_pdf):
        num    = i + 1
        nombre = poi.get("nombre", "Sin nombre")
        cat    = poi.get("categoria_principal", "")
        desc   = poi.get("descripcion_llm", "")
        tv     = TIEMPO_VISITA.get(cat, 30)

        pdf.set_fill_color(26, 22, 18)
        pdf.set_text_color(245, 240, 232)
        pdf.set_font("DejaVu", "B", 10)
        pdf.cell(0, 7, f"  {num}. {nombre}", fill=True, **NL)

        pdf.set_font("DejaVu", "I", 9)
        pdf.set_text_color(193, 68, 14)
        pdf.cell(0, 5, f"  {cat} — visita estimada: ~{tv} min", **NL)

        if desc:
            pdf.set_font("DejaVu", "", 9)
            pdf.set_text_color(74, 66, 56)
            pdf.multi_cell(0, 5, f"  {desc}")

        pdf.ln(2)

        if i < len(ruta_pdf) - 1:
            siguiente  = ruta_pdf[i + 1]
            dist_km    = _dist_km(poi, siguiente)
            t_min      = round(dist_km / vel * 60)
            sig_nombre = siguiente.get("nombre", "")

            pdf.set_draw_color(212, 201, 176)
            pdf.set_line_width(0.3)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(2)

            pdf.set_font("DejaVu", "B", 8)
            pdf.set_text_color(184, 149, 74)
            pdf.cell(0, 5,
                f"  Hacia {sig_nombre} ({dist_km:.2f} km — ~{t_min} min)", **NL)

            # Instrucciones turn-by-turn (offset +1 por poi_inicio)
            idx_seg = i + instr_offset
            if instrucciones and idx_seg < len(instrucciones):
                pasos = instrucciones[idx_seg]
                pdf.set_font("DejaVu", "", 8)
                pdf.set_text_color(100, 90, 80)
                for paso in pasos:
                    instruccion = paso.get("instruccion", "")
                    d_paso      = paso.get("distancia", 0)
                    if instruccion:
                        dist_str = f"{d_paso} m" if d_paso < 1000 else f"{d_paso/1000:.1f} km"
                        pdf.multi_cell(0, 4, f"   • {instruccion} ({dist_str})")

        pdf.ln(3)
        pdf.set_draw_color(193, 68, 14)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

    # ── Pie de página
    pdf.set_y(-12)
    pdf.set_font("DejaVu", "I", 7)
    pdf.set_text_color(150, 140, 130)
    pdf.cell(0, 5,
        "Generado por Rutas Culturales Alicante — datos OpenStreetMap / OpenRouteService",
        align="C")

    buf = io.BytesIO(pdf.output())
    response = make_response(buf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=ruta_cultural_alicante.pdf"
    return response


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug)
