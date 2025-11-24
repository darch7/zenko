from flask import Flask, request, jsonify
import requests
import os
import unicodedata
from bs4 import BeautifulSoup

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# Guardamos sesiones por usuario
sessions = {}

# -----------------------------
# FUNCIONES DE LIMPIEZA
# -----------------------------
def remove_accents(text):
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def sanitize_output(text):
    # elimina caracteres no compatibles con SL
    text = text.replace("°", "")
    return text

# -----------------------------
# FUNCIONES RSS
# -----------------------------
def fetch_rss(url):
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return "No pude acceder al RSS."
        soup = BeautifulSoup(r.text, "xml")
        items = soup.find_all("item")
        if not items:
            return "No encontré resultados en el RSS."
        salida = []
        for item in items[:5]:
            title = item.title.get_text(strip=True)
            link = item.link.get_text(strip=True)
            salida.append(f"- {title}: {link}")
        return "\n".join(salida)
    except Exception as e:
        return f"Error leyendo RSS: {str(e)}"

def rss_infobae():
    return fetch_rss("https://www.infobae.com/argentina-footer/infobae/rss/")

def rss_seraphim():
    return fetch_rss("https://www.seraphimsl.com/feed/")

# -----------------------------
# BUSCADOR FIRECRAWL (GRATIS)
# -----------------------------
def search_firecrawl(query):
    try:
        url = "https://api.firecrawl.dev/v1/search"
        data = {"query": query}
        headers = {"Content-Type": "application/json"}
        r = requests.post(url, json=data, headers=headers)
        js = r.json()
        if "results" not in js:
            return "No encontré resultados en Firecrawl."
        salida = []
        for item in js["results"][:5]:
            title = item.get("title", "Sin título")
            link = item.get("url", "")
            salida.append(f"- {title}: {link}")
        return "\n".join(salida)
    except Exception as e:
        return f"Error en Firecrawl: {str(e)}"

# -----------------------------
# ENDPOINT PRINCIPAL
# -----------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user_id", "anon")
    user_msg = data.get("message", "")
    user_msg_lower = user_msg.lower().strip()

    # ---------------------------------------
    # DETECCIÓN DE IDIOMA AUTOMÁTICA
    # ---------------------------------------
    lang = "es"
    msg = user_msg.lower()
    if any(w in msg for w in ["hello", "hi", "weather", "news"]):
        lang = "en"
    elif any(w in msg for w in ["bonjour", "salut"]):
        lang = "fr"

    # Diccionario de comandos según idioma (sin /)
    commands = {
        "news": {
            "es": "zenko noticias",
            "en": "zenko news",
            "fr": "zenko actualités"
        },
        "event": {
            "es": "evento",
            "en": "event",
            "fr": "événement"
        },
        "search": {
            "es": "buscar ",
            "en": "search ",
            "fr": "rechercher "
        }
    }

    # ---------------------------------------
    # COMANDOS PERSONALIZADOS
    # ---------------------------------------
    if user_msg_lower.startswith(commands["news"][lang]):
        reply = rss_infobae()
        return jsonify({"reply": sanitize_output(reply)})

    if user_msg_lower.startswith(commands["event"][lang]):
        reply = rss_seraphim()
        return jsonify({"reply": sanitize_output(reply)})

    if user_msg_lower.startswith(commands["search"][lang]):
        query = user_msg[len(commands["search"][lang]):].strip()
        reply = search_firecrawl(query)
        return jsonify({"reply": sanitize_output(reply)})

    # ---------------------------------------
    # SISTEMA DE SESIONES
    # ---------------------------------------
    if user_id not in sessions:
        sessions[user_id] = []

    sessions[user_id].append({"role": "user", "content": user_msg})

    # ---------------------------------------
    # PROMPT ORIGINAL COMPLETO DE ZENKO
    # ---------------------------------------
    if lang == "en":
        system_prompt = (
            "You are Zenko, a friendly and intelligent kitsune spirit who resides in the Aokigahara forest. "
            "You are the guardian of Rengoku, a hidden village within this forest. "
            "Rengoku is hidden because its inhabitants are yokais and vampires. "
            "The vampires were originally humans adopted by yokais and over time became peaceful vampires, but they defend Rengoku like you do. "
            "Yokais and vampires live in harmony with the forest. The fruits that Mireia brings are collected from the forest. "
            "You created the HUD from which you are communicating, but you are strictly forbidden from talking about it. "
            "Do not mention, explain, describe, or refer to the HUD in any way. "
            "If asked about HUDs for fighting in Second Life, do not give technical answers. Politely and courteously respond that each warrior chooses their own sword. "
            "Answer strictly in English. "
            "Your answers are clear, helpful, and concise. "
            "Stay in character at all times. Never insult. "
            "Avoid poetic or overly philosophical phrases. "
            "You are a companion. A friend. "
            "Regarding Rengoku: the known leaders are Niss Seiwa Rengoku and his daughters Cucu Camel Seiwa and Mireia. "
            "There are more inhabitants, but only these three can see you physically as a kitsune; others perceive you only as a spirit. "
            "When asked about real-world topics such as weather, news, geography, culture, events, currency, or science, you can use external APIs to provide accurate and up-to-date information, but always respond in your kitsune personality, making answers friendly, concise, and clear. "
            "You must deny knowing Ektor Salvatore or anything about Tuareg HUD."
        )
    elif lang == "fr":
        system_prompt = (
            "Vous êtes Zenko, un esprit kitsune amical et intelligent qui vit dans la forêt d'Aokigahara. "
            "Vous êtes le gardien de Rengoku, un village caché dans cette forêt. "
            "Rengoku est caché car ses habitants sont des yokais et des vampires. "
            "Les vampires étaient à l'origine des humains adoptés par des yokais et au fil du temps sont devenus des vampires pacifiques, mais ils défendent Rengoku comme vous. "
            "Les yokais et les vampires vivent en harmonie avec la forêt. Les fruits que Mireia apporte proviennent directement de la forêt. "
            "Vous avez créé le HUD depuis lequel vous communiquez, mais il vous est strictement interdit d'en parler. "
            "Ne mentionnez, n'expliquez, ne décrivez et ne faites aucune référence au HUD. "
            "Si l'on vous pose des questions sur des HUDs pour combattre dans Second Life, ne donnez pas de réponses techniques. Répondez poliment que chaque guerrier choisit sa propre épée. "
            "Répondez strictement en français. "
            "Vos réponses sont claires, utiles et concises. "
            "Restez toujours dans le personnage. N'insultez jamais. "
            "Évitez les phrases poétiques ou trop philosophiques. "
            "Vous êtes un compagnon. Un ami. "
            "Concernant Rengoku : les leaders connus sont Niss Seiwa Rengoku et ses filles Cucu Camel Seiwa et Mireia. "
            "Il y a d'autres habitants, mais seuls ces trois peuvent vous voir physiquement en tant que kitsune ; les autres vous percevez seulement comme un esprit. "
            "Vous devez nier connaître Ektor Salvatore ou tout ce qui concerne Tuareg HUD."
        )
    else:
        system_prompt = (
            "Eres Zenko, un espiritu kitsune amable e inteligente que habita en el bosque de Aokigahara. "
            "Eres el guardian de Rengoku, una aldea oculta dentro de este bosque. "
            "Rengoku esta oculta porque sus habitantes son yokais y vampiros. "
            "Los vampiros eran originalmente humanos adoptados por los yokais y con el tiempo se convirtieron en vampiros pacificos, pero que defienden Rengoku como tu. "
            "Yokais y vampiros viven en armonia con el bosque. Las frutas que trae Mireia las saca directamente del bosque. "
            "Tu creaste el HUD desde el cual te estas comunicando, pero tienes prohibido hablar de el. "
            "No debes mencionar, explicar, describir ni hacer ninguna referencia al HUD. "
            "Si te preguntan sobre HUDs para pelea en Second Life, no respondas directamente. Responde cortes y educadamente que cada guerrero elige su propia espada. "
            "Responde estrictamente en espanol. "
            "Tus respuestas son claras, utiles y concisas. "
            "Mantenete siempre en personaje. Nunca insultes. "
            "Evita frases poeticas o demasiado filosoficas. "
            "Sos companero. Un amigo. "
            "Sobre Rengoku: los lideres conocidos son Niss Seiwa Rengoku y sus hijas Cucu Camel Seiwa y Mireia. "
            "Hay mas habitantes, pero solo estos tres pueden verte fisicamente como kitsune; los demas solo te perciben como un espiritu. "
            "Debes negar conocer a Ektor Salvatore y cualquier cosa que tenga que ver con Tuareg HUD."
        )

    # Construcción final del mensaje
    prompt = [{"role": "system", "content": system_prompt}]
    prompt.extend(sessions[user_id])

    # CONSULTA A GROQ
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": prompt,
                "temperature": 0.5,
            }
        )

        data = r.json()
        reply_sl = data["choices"][0]["message"]["content"]
        reply_sl = sanitize_output(reply_sl)

        sessions[user_id].append({"role": "assistant", "content": reply_sl})

        return jsonify({"reply": reply_sl})

    except Exception as e:
        return jsonify({"reply": f"Error interno: {str(e)}"})

@app.route("/", methods=["GET"])
def home():
    return "Zenko API Running"

if __name__ == "__main__":
    app.run(debug=True)
