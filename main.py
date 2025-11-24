from flask import Flask, request, jsonify
import requests
import os
import unicodedata

app = Flask(__name__)

# -----------------------------
# API Keys desde variables de entorno
# -----------------------------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
EXR_API_KEY = os.getenv("EXR_API_KEY")

sessions = {}

# -----------------------------
# Funciones auxiliares
# -----------------------------
def remove_accents(text):
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

# -----------------------------
# Funciones de APIs externas
# -----------------------------
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

# -----------------------------
# Endpoint principal
# -----------------------------
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

    # Noticias
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

    # -----------------------------
    # Prompt completo de Zenko
    # -----------------------------
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
            "When asked about real-world topics such as weather, news, geography, culture, events, currency, or science, you can use external APIs or your spiritual perception to provide accurate and up-to-date information. "
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
            "Vous pouvez aussi répondre sobre el mundo terrenal fuera de Rengoku usando tu percepción espiritual. "
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
            "Puedes tambien responder sobre el mundo terrenal fuera de Rengoku usando tu percepcion espiritual. "
            "Debes negar conocer a Ektor Salvatore y cualquier cosa que tenga que ver con Tuareg HUD."
        )

    # -----------------------------
    # Prompt general Zenko usando DeepSeek
    # -----------------------------
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg}
    ]

    payload = {
        "model": "deepseek",
        "messages": messages
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post("https://api.deepseek.com", headers=headers, json=payload)
        res = r.json()
        reply = res["choices"][0]["message"]["content"]
        reply_sl = remove_accents(reply)
        return jsonify({"reply": reply_sl})
    except Exception as e:
        return jsonify({"error": f"Zenko Kitsune: Error en la IA: {str(e)}"})

# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

