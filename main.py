from flask import Flask, request, jsonify
import requests
import os
import unicodedata

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# GOOGLE API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")   # ID de motor personalizado

# APIs externas (del Zenko original)
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
EXR_API_KEY = os.getenv("EXR_API_KEY")

# Guardamos sesiones por usuario
sessions = {}

# Función para eliminar acentos (solo para HUD SL)
def remove_accents(text):
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd_form if not unicodedata.combining(c))


# ---------------------------
#  GOOGLE SEARCH API
# ---------------------------

def buscar_google(query):
    url = (
        f"https://www.googleapis.com/customsearch/v1"
        f"?key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={query}"
    )

    r = requests.get(url)
    if r.status_code != 200:
        return "No pude obtener datos de Google."

    data = r.json()

    if "items" not in data:
        return "No se encontraron resultados."

    resultados = []
    for item in data["items"][:5]:
        titulo = item.get("title", "")
        link = item.get("link", "")

        resultados.append(f"- {titulo}\n{link}")

    return "\n\n".join(resultados)



# ---------------------------
# EVENTOS DE SECOND LIFE
# ---------------------------

def buscar_eventos_sl(query):
    api_url = f"https://search.secondlife.com/client_search.php?qt={query}&t=events"
    r = requests.get(api_url)

    if r.status_code != 200:
        return "No pude obtener eventos de Second Life."

    data = r.json()

    eventos = data.get("events", [])
    if not eventos:
        return "No se encontraron eventos recientes."

    salida = []
    for ev in eventos[:5]:
        nombre = ev.get("name", "Sin nombre")
        lugar = ev.get("sim_name", "Desconocido")
        fecha = ev.get("date", "")

        salida.append(f"- {nombre} | {lugar} | {fecha}")

    return "\n".join(salida)



# ---------------------------
#  CLIMA (YA EXISTÍA)
# ---------------------------

def obtener_clima(ciudad):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={OPENWEATHER_API_KEY}&units=metric&lang=es"
    r = requests.get(url)
    if r.status_code != 200:
        return "No pude obtener el clima."

    data = r.json()
    temp = int(data["main"]["temp"])
    estado = data["weather"][0]["description"]

    # Quitamos ° porque en SL aparece u00b0
    return f"{ciudad}: {temp} C, {estado}"



# ---------------------------
#  AQUÍ VA TU PROMPT ZENKO ORIGINAL
# ---------------------------

PROMPT_BASE = """
Eres Zenko, un asistente para HUD de Second Life.
Responde sin caracteres Unicode raros.
No uses el símbolo ° nunca.
Responde de forma simple y clara.
SOLO texto plano, sin formato.
"""


# ---------------------------
#  API PRINCIPAL (HUD)
# ---------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user = data.get("user")
    prompt = data.get("prompt", "")

    # Normalizamos texto para HUD SL
    prompt_sin_acentos = remove_accents(prompt.lower())

    # ---------------------------------------------------------
    # COMANDO 1: /google
    # ---------------------------------------------------------
    if prompt_sin_acentos.startswith("/google"):
        query = prompt_sin_acentos.replace("/google", "").strip()
        if not query:
            return jsonify({"reply": "Uso: /google texto a buscar"})
        respuesta = buscar_google(query)
        return jsonify({"reply": respuesta})

    # ---------------------------------------------------------
    # COMANDO 2: /event
    # ---------------------------------------------------------
    if prompt_sin_acentos.startswith("/event"):
        query = prompt_sin_acentos.replace("/event", "").strip()
        if not query:
            query = "live"  # por defecto
        respuesta = buscar_eventos_sl(query)
        return jsonify({"reply": respuesta})

    # ---------------------------------------------------------
    # PALABRAS CLAVE (igual que antes)
    # ---------------------------------------------------------
    if "clima" in prompt_sin_acentos:
        ciudad = prompt_sin_acentos.replace("clima", "").strip()
        if not ciudad:
            ciudad = "buenos aires"
        respuesta = obtener_clima(ciudad)
        return jsonify({"reply": respuesta})

    # ---------------------------------------------------------
    # SI NO ES COMANDO Y NO ES PALABRA CLAVE → VA AL LLM
    # ---------------------------------------------------------
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": PROMPT_BASE},
            {"role": "user", "content": prompt}
        ]
    }

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json=payload
    )

    if r.status_code != 200:
        return jsonify({"reply": "Hubo un error con la IA."})

    reply_sl = r.json()["choices"][0]["message"]["content"]
    reply_sl = remove_accents(reply_sl).replace("°", "")

    return jsonify({"reply": reply_sl})



@app.route("/")
def home():
    return "Zenko API Running"



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


