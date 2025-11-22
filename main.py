from flask import Flask, request, jsonify
import requests
import os
import unicodedata

# Para parseo de HTML de eventos SL
from bs4 import BeautifulSoup

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# APIs externas
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
EXR_API_KEY = os.getenv("EXR_API_KEY")

sessions = {}

def remove_accents(text):
    """
    Quita acentos, signos raros y caracteres problemáticos para SL.
    """
    nfkd_form = unicodedata.normalize('NFKD', text)
    ascii_text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    ascii_text = ascii_text.replace('¿', '?').replace('¡', '!')
    ascii_text = ascii_text.replace('°', '')  # elimina símbolo de grado
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
#       FUNCIONES EXTERNAS
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
#     FUNCIONES SECOND LIFE
# ================================
def get_sl_events():
    """
    Devuelve eventos recientes o próximos de Second Life.
    """
    events = []

    try:
        url = "https://secondlife.com/destinations/events"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.find_all("h3", class_="event-title")
            for i, item in enumerate(items[:5]):  # solo primeros 5
                events.append(remove_accents(f"- {item.text.strip()}"))
    except:
        events.append("No pude obtener eventos recientes de Second Life.")

    if not events:
        events.append("No se encontraron eventos activos de Second Life.")

    return "Eventos recientes en Second Life:\n" + "\n".join(events)

def get_sl_sim_info(sim_name):
    """
    Devuelve información básica de un sim de SL.
    """
    # Aquí se podría usar SLAPI u otra fuente, por ahora ejemplo estático
    sim_data = {
        "harvest": "Sim de roleplay con actividades agrícolas.",
        "gothic": "Sim temática gótica con música y eventos nocturnos.",
        "rpgworld": "Sim RPG con quests y rol en vivo."
    }
    info = sim_data.get(sim_name.lower(), None)
    if info:
        return remove_accents(f"Información del sim {sim_name}: {info}")
    return remove_accents(f"No encontré información sobre el sim {sim_name}.")

def get_sl_shops():
    """
    Devuelve tiendas populares de Second Life.
    """
    shops = [
        "- Marketplace SL: https://marketplace.secondlife.com",
        "- SL Fashion Hub: https://slfashionhub.com",
        "- The Arcade SL: https://sl-arcade.com"
    ]
    return "Tiendas populares en Second Life:\n" + "\n".join(shops)

# ================================
#       ENDPOINT PRINCIPAL
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

    # Clima
    if user_msg_lower.startswith("clima "):
        city = user_msg[6:]
        return jsonify({"reply": get_weather(city)})

    # Noticias generales
    elif user_msg_lower.startswith("noticias"):
        topic = user_msg[9:].strip() or "general"
        return jsonify({"reply": get_news(topic)})

    # País
    elif user_msg_lower.startswith("pais "):
        country = user_msg[5:]
        return jsonify({"reply": get_country_info(country)})

    # Wiki
    elif user_msg_lower.startswith("wiki "):
        term = user_msg[5:]
        return jsonify({"reply": wiki_summary(term, lang)})

    # Moneda
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
    #       FUNCIONES SECOND LIFE
    # ===========================================
    elif user_msg_lower.startswith("eventos sl"):
        return jsonify({"reply": get_sl_events()})

    elif user_msg_lower.startswith("sim "):
        sim_name = user_msg[4:]
        return jsonify({"reply": get_sl_sim_info(sim_name)})

    elif user_msg_lower.startswith("tiendas sl"):
        return jsonify({"reply": get_sl_shops()})

    # ===========================================
    #     PROMPT ORIGINAL COMPLETO DE ZENKO
    # ===========================================
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
            "When asked about real-world topics such as weather, news, geography, culture, events, currency, or science, you can use external APIs to provide accurate and up-to-date information, but always respond in your kitsune personality, making answers friendly, concise, and clear."
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
            "Lorsque vous êtes interrogé sur des sujets du monde réel tels que la météo, les actualités, la géographie, la culture, les événements, la monnaie ou la science, vous pouvez utiliser des APIs externes pour fournir des informations exactes et actualisées, mais répondez toujours avec votre personnalité de kitsune, de manière amicale, concise et claire."
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
            "Cuando se te pregunte sobre temas del mundo real, como clima, noticias, geografia, cultura, eventos, moneda o ciencia, podes usar APIs externas para dar informacion precisa y actualizada, pero siempre responde con tu personalidad de kitsune, de manera amigable, concisa y clara."
        )

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
