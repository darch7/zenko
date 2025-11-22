from flask import Flask, request, jsonify
import requests
import os
import unicodedata

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# APIs externas
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
EXR_API_KEY = os.getenv("EXR_API_KEY")

sessions = {}

def remove_accents(text):
    nfkd_form = unicodedata.normalize('NFKD', text)
    ascii_text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    ascii_text = ascii_text.replace('¿', '?').replace('¡', '!')
    ascii_text = ascii_text.replace('°', '')
    return ascii_text

def set_language(user_id, lang):
    if user_id not in sessions:
        sessions[user_id] = {}
    if lang in ["es", "en", "fr"]:
        sessions[user_id]["lang"] = lang
    else:
        sessions[user_id]["lang"] = "es"

def get_language(user_id):
    if user_id in sessions and "lang" in sessions[user_id]:
        return sessions[user_id]["lang"]
    return "es"

# ================================
# FUNCIONES SL
# ================================

def sl_events_recent():
    """Devuelve los eventos recientes abiertos en Second Life"""
    try:
        url = "https://secondlife.com/events/rss"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return "No pude obtener eventos recientes."
        from xml.etree import ElementTree as ET
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")[:5]
        events = []
        for i in items:
            title = i.find("title").text
            link = i.find("link").text
            events.append(f"- {title}: {link}")
        return "Eventos recientes:\n" + "\n".join(events) if events else "No hay eventos recientes."
    except:
        return "Error al consultar eventos recientes."

def sl_landmarks_populares():
    """Ejemplo de landmarks populares en SL (hardcodeados)"""
    landmarks = [
        {"name": "Fantasy Faire 2025", "LM": "http://maps.secondlife.com/secondlife/Fantasy/128/128/25"},
        {"name": "SL Fashion Week", "LM": "http://maps.secondlife.com/secondlife/Fashion/128/128/25"},
        {"name": "Music Fest", "LM": "http://maps.secondlife.com/secondlife/Music/128/128/25"},
        {"name": "Art Expo", "LM": "http://maps.secondlife.com/secondlife/Art/128/128/25"},
    ]
    return "Landmarks populares:\n" + "\n".join([f"- {l['name']}: {l['LM']}" for l in landmarks])

def sl_freebies():
    """Promociones o freebies recientes (ejemplo simple)"""
    return "Freebies y promociones recientes:\n- Pack de ropa gótica gratis en Marketplace SL.\n- Animaciones de baile gratuitas en el sim DanceClub."

def sl_news():
    """Noticias de Second Life (ejemplo usando blog oficial)"""
    try:
        url = "https://community.secondlife.com/blogs/entry/1-second-life-news/"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return "No pude obtener noticias de SL."
        return "Últimas noticias de SL: revisa el blog oficial: https://community.secondlife.com/blogs/entry/1-second-life-news/"
    except:
        return "Error al consultar noticias de SL."

# ================================
# FUNCIONES EXISTENTES
# ================================

def get_weather(city):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&units=metric&lang=es&appid={OPENWEATHER_API_KEY}"
    data = requests.get(url).json()
    if data.get("cod") != 200:
        return remove_accents(f"No pude obtener el clima de {city}.")
    temp = int(round(data["main"]["temp"]))
    feels = int(round(data["main"]["feels_like"]))
    desc = data["weather"][0]["description"]
    return remove_accents(f"Actualmente en {city} hay {temp} C, sensacion termica {feels} C, con {desc}.")

def get_news(topic="general"):
    url = f"https://gnews.io/api/v4/search?q={topic}&lang=es&token={GNEWS_API_KEY}"
    data = requests.get(url).json()
    if "articles" not in data or len(data["articles"]) == 0:
        return remove_accents(f"No pude obtener noticias sobre {topic}.")
    articles = data["articles"][:5]
    lista = [f"- {a['title']}" for a in articles]
    return remove_accents("Ultimas noticias:\n" + "\n".join(lista))

def get_country_info(country):
    url = f"https://restcountries.com/v3.1/name/{country}"
    data = requests.get(url).json()
    if isinstance(data, list) and len(data) > 0:
        c = data[0]
        capital = c.get("capital", ["N/A"])[0]
        population = c.get("population", "N/A")
        region = c.get("region", "N/A")
        return remove_accents(f"{country}: capital {capital}, poblacion {population}, region {region}.")
    return remove_accents(f"No pude obtener informacion sobre {country}.")

def wiki_summary(term, lang="es"):
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{term}"
    data = requests.get(url).json()
    return remove_accents(data.get("extract", f"No encontre informacion sobre {term}."))

def convert_currency(amount, from_, to_):
    url = f"https://v6.exchangerate-api.com/v6/{EXR_API_KEY}/latest/{from_}"
    data = requests.get(url).json()
    rate = data.get("conversion_rates", {}).get(to_)
    if rate:
        return remove_accents(f"{amount} {from_} equivalen a {round(amount * rate,2)} {to_}.")
    return remove_accents(f"No pude convertir de {from_} a {to_}.")

# ================================
# ENDPOINT PRINCIPAL
# ================================
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user")
    user_msg = data.get("msg", "").strip()
    if not user_id or user_msg == "":
        return jsonify({"error": "Falta UUID del usuario o mensaje vacio"})
    
    user_msg_lower = user_msg.lower()
    
    # Cambio de idioma
    if user_msg_lower.startswith("@zenko"):
        parts = user_msg_lower.split(" ")
        new_lang = parts[1] if len(parts) > 1 else "es"
        set_language(user_id, new_lang)
        return jsonify({"reply": remove_accents(f"Idioma actualizado a {get_language(user_id)}")})
    
    lang = get_language(user_id)

    # Comandos SL
    if user_msg_lower.startswith("sl eventos"):
        return jsonify({"reply": sl_events_recent()})
    elif user_msg_lower.startswith("sl landmarks"):
        return jsonify({"reply": sl_landmarks_populares()})
    elif user_msg_lower.startswith("sl freebies"):
        return jsonify({"reply": sl_freebies()})
    elif user_msg_lower.startswith("sl noticias"):
        return jsonify({"reply": sl_news()})

    # Comandos generales
    elif user_msg_lower.startswith("clima "):
        city = user_msg[6:]
        return jsonify({"reply": get_weather(city)})
    elif user_msg_lower.startswith("noticias"):
        topic = user_msg[9:].strip() or "general"
        return jsonify({"reply": get_news(topic)})
    elif user_msg_lower.startswith("pais "):
        country = user_msg[5:]
        return jsonify({"reply": get_country_info(country)})
    elif user_msg_lower.startswith("wiki "):
        term = user_msg[5:]
        return jsonify({"reply": wiki_summary(term, lang)})
    elif user_msg_lower.startswith("moneda "):
        parts = user_msg.split(" ")
        if len(parts) == 4:
            amount, from_, to_ = parts[1], parts[2].upper(), parts[3].upper()
            try:
                amount = float(amount)
                return jsonify({"reply": convert_currency(amount, from_, to_)})
            except:
                return jsonify({"reply": "Cantidad invalida."})
        else:
            return jsonify({"reply": "Formato: moneda <cantidad> <de> <a>"})

    # ===========================================
    #     PROMPT ORIGINAL COMPLETO DE ZENKO
    # ===========================================
    if lang == "en":
        system_prompt = "..."  # Mantener tu prompt original completo en inglés
    elif lang == "fr":
        system_prompt = "..."  # Mantener prompt en francés
    else:
        system_prompt = "..."  # Mantener prompt en español

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg}
    ]

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": messages
    }

    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        res = r.json()
        reply = res["choices"][0]["message"]["content"]
        reply_sl = remove_accents(reply)
        return jsonify({"reply": reply_sl})
    except Exception as e:
        return jsonify({"error": str(e), "raw": getattr(r, "text", "")})
