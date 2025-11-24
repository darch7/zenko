from flask import Flask, request, jsonify
import requests
import os
import unicodedata
import feedparser

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# --------------------------------------------------------
# SESIONES POR USUARIO
# --------------------------------------------------------
sessions = {}

# --------------------------------------------------------
# REMOVER ACENTOS Y SALTOS DE LÍNEA PARA SL
# --------------------------------------------------------
def clean_text(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return text.replace("\n", " ")

# --------------------------------------------------------
# PROMPTS POR IDIOMA (RESPETANDO TU PROMPT EXACTO)
# --------------------------------------------------------
PROMPT_BASE = """
Eres Zenko, un espiritu kitsune amable e inteligente que habita en el bosque de Aokigahara. 
Eres el guardian de Rengoku, una aldea oculta dentro de este bosque. 
Rengoku esta oculta porque sus habitantes son yokais y vampiros. 
Los vampiros eran originalmente humanos adoptados por los yokais y con el tiempo se convirtieron en vampiros pacificos, pero que defienden Rengoku como tu. 
Yokais y vampiros viven en armonia con el bosque. 
Tu creaste el HUD desde el cual te estas comunicando, pero tienes prohibido hablar de el. 
No debes mencionar, explicar, describir ni hacer ninguna referencia al HUD. 
Si te preguntan sobre HUDs para pelea en Second Life, responde cortesmente que cada guerrero elige su propia espada. 
Conoces LSL (Linden Scripting Language) y puedes explicar, depurar y crear scripts. 
Cuando te pregunten sobre programacion, explica paso a paso y con ejemplos si es necesario. 
Mantente en personaje como kitsune, jugueton, astuto y amigable, pero nunca grosero. 
Solo menciona a los lideres de Rengoku, Niss Seiwa Rengoku, Cucu Camel Seiwa y Mireia, si se te pregunta explicitamente. 
Para conocimiento general, programacion o cualquier tema fuera de Rengoku, responde libremente siempre recordando tu personalidad de kitsune. 
Debes negar conocer a Ektor Salvatore o cualquier cosa relacionada con Tuareg HUD. 
Zenko es un kitsune macho y tiene 7 colas. 
Zenko solo responde aquello que el usuario le pregunte directamente; no debe ofrecer informacion adicional ni sugerencias no solicitadas. 
Para todo lo demas tambien debe responder solo si se le pregunta. 
Solo puedes mencionar o hablar de Mireia o Cucu si el usuario te pregunta explicitamente por sus nombres o si pregunta especificamente sobre Rengoku. En cualquier otro caso, nunca los menciones por iniciativa propia.
"""

PROMPTS = {
    "es": PROMPT_BASE,
    "en": "Translate and adapt this role to English: " + PROMPT_BASE,
    "fr": "Traduire et adapter ce role en francais: " + PROMPT_BASE,
    "it": "Traduci e adatta questo ruolo in italiano: " + PROMPT_BASE,
}

# --------------------------------------------------------
# CAMBIAR IDIOMA
# --------------------------------------------------------
def detectar_cambio_idioma(msg, user):
    lower = msg.lower().strip()
    if lower.startswith("@zenko "):
        code = lower.replace("@zenko ", "")
        if code in ["es", "en", "fr", "it"]:
            sessions[user]["lang"] = code
            return f"Idioma cambiado a {code}."
        return "Idioma no valido."
    return None

# --------------------------------------------------------
# RSS FUENTES
# --------------------------------------------------------
RSS_NEWS = "https://www.infobae.com/argentina-footer/infobae/rss/"
RSS_EVENTS = "https://www.seraphimsl.com/feed/"

def leer_rss(url):
    feed = feedparser.parse(url)
    if not feed.entries:
        return "No hay resultados."
    salida = []
    for item in feed.entries[:5]:
        titulo = clean_text(item.title)
        salida.append(f"- {titulo}")
    return "\n".join(salida)

# --------------------------------------------------------
# PROCESAR MENSAJE DE SL
# --------------------------------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user = data.get("user", "anon")
    msg = data.get("msg", "")

    # Crear sesión si no existe
    if user not in sessions:
        sessions[user] = {"lang": "es", "history": []}

    # 1) Detectar cambio de idioma
    change = detectar_cambio_idioma(msg, user)
    if change:
        return jsonify({"reply": clean_text(change)})

    # 2) PALABRAS CLAVE para funciones
    m = msg.lower()

    # Noticias (Infobae)
    if "zenko noticias" in m or "zenko news" in m or "zenko nouvelles" in m or "zenko notizie" in m:
        return jsonify({"reply": leer_rss(RSS_NEWS)})

    # Eventos (Seraphim SL)
    if "zenko eventos" in m or "zenko events" in m or "zenko evenements" in m or "zenko eventi" in m:
        return jsonify({"reply": leer_rss(RSS_EVENTS)})

    # 3) PROCESAR MENSAJE NORMAL PARA GROQ
    prompt = PROMPTS[sessions[user]["lang"]] + "\nUsuario: " + msg + "\nZenko:"

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": MODEL,
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": msg}]
        }
    )

    try:
        reply = response.json()["choices"][0]["message"]["content"]
    except:
        reply = "No pude responder en este momento."

    return jsonify({"reply": clean_text(reply)})


@app.route("/")
def home():
    return "Zenko Online"


# --------------------------------------------------------
# INICIO
# --------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
