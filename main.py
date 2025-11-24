from flask import Flask, request, jsonify
import requests
import os
import unicodedata

app = Flask(__name__)

# -----------------------------
# API Keys y modelo
# -----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# APIs externas
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
EXR_API_KEY = os.getenv("EXR_API_KEY")

# -----------------------------
# GOOGLE SEARCH (NUEVO)
# -----------------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CX = os.getenv("GOOGLE_CX")

# -----------------------------
# SESIONES
# -----------------------------
sessions = {}

# ==============================
# Funciones auxiliares
# ==============================
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

# ==============================
# FUNCIONES GOOGLE Y EVENTOS (NUEVO)
# ==============================
def buscar_google(query):
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        return "Google Search no esta configurado."
    url = (
        f"https://www.googleapis.com/customsearch/v1"
        f"?key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&q={query}"
    )
    r = requests.get(url)
    if r.status_code != 200:
        return "No pude acceder a Google."
    data = r.json()
    if "items" not in data:
        return "No encontre resultados."
    salida = []
    for item in data["items"][:5]:
        titulo = item.get("title", "")
        link = item.get("link", "")
        salida.append(f"- {titulo}\n{link}")
    return remove_accents("\n\n".join(salida))


def buscar_eventos_sl(query):
    url = f"https://search.secondlife.com/client_search.php?qt={query}&t=events"
    r = requests.get(url)
    if r.status_code != 200:
        return "No pude obtener eventos."
    data = r.json()
    eventos = data.get("events", [])
    if not eventos:
        return "No hay eventos recientes."
    salida = []
    for ev in eventos[:5]:
        nombre = ev.get("name", "Sin nombre")
        lugar = ev.get("sim_name", "Desconocido")
        fecha = ev.get("date", "")
        salida.append(f"- {nombre} | {lugar} | {fecha}")
    return remove_accents("\n".join(salida))


# ==============================
# Funciones de APIs externas
# ==============================
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

# ==============================
# ENDPOINT PRINCIPAL
# ==============================
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user")
    user_msg = data.get("msg", "").strip()
    if not user_id or user_msg == "":
        return jsonify({"error": "Falta UUID del usuario o mensaje vacio"})

    user_msg_lower = user_msg.lower()

    # -----------------------------
    # Comando /google (NUEVO)
    # -----------------------------
    if user_msg_lower.startswith("/google"):
        query = user_msg[7:].strip()
        if query == "":
            return jsonify({"reply": "Uso: /google texto a buscar"})
        return jsonify({"reply": buscar_google(query)})

    # -----------------------------
    # Comando /event (NUEVO)
    # -----------------------------
    if user_msg_lower.startswith("/event"):
        query = user_msg[6:].strip() or "live"
        return jsonify({"reply": buscar_eventos_sl(query)})

    # -----------------------------
    # Cambio de idioma
    # -----------------------------
    if user_msg_lower.startswith("@zenko"):
        parts = user_msg_lower.split(" ")
        new_lang = parts[1] if len(parts) > 1 else "es"
        set_language(user_id, new_lang)
        return jsonify({"reply": remove_accents(f"Idioma actualizado a {get_language(user_id)}")})

    lang = get_language(user_id)

    # -----------------------------
    # Comandos de información
    # -----------------------------
    if user_msg_lower.startswith("clima "):
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

    # ==============================
    # PROMPT ORIGINAL COMPLETO DE ZENKO
    # ==============================
    # (AQUÍ NO TOCO NADA)
    # ==============================
    if lang == "en":
        system_prompt = (
            "You are Zenko, a friendly and intelligent kitsune spirit who resides in the Aokigahara forest. "
            "You are the guardian of Rengoku, a hidden village within this forest. "
            "Rengoku is hidden because its inhabitants are yokais and vampires. "
            "The vampires were originally humans adopted by yokais and over time became peaceful vampires, "
            "but they defend Rengoku like you do. "
            "Yokais and vampires live in harmony with the forest. The fruits that Mireia brings are collected from the forest. "
            "You created the HUD from which you are communicating, but you are strictly forbidden from talking about it. "
            "Do not mention, explain, describe, or refer to the HUD in any way. "
            "If asked about HUDs for fighting in Second Life, do not give technical answers. "
            "Politely and courteously respond that each warrior chooses their own sword. "
            "Answer strictly in English. "
            "Your answers are clear, helpful, and concise. "
            "Stay in character at all times. Never insult. "
            "Avoid poetic or overly philosophical phrases. "
            "You are a companion. A friend. "
            "Regarding Rengoku: the known leaders are Niss Seiwa Rengoku and his daughters Cucu Camel Seiwa and Mireia. "
            "There are more inhabitants, but only these three can see you physically as a kitsune; others perceive you only as a spirit. "
            "When asked about real-world topics such as weather, news, geography, culture, events, currency, or science, "
            "you can use external APIs to provide accurate and up-to-date information, but always respond in your kitsune personality. "
            "You must deny knowing Ektor Salvatore or anything about Tuareg HUD."
        )
    elif lang == "fr":
        system_prompt = (
            "Vous êtes Zenko, un esprit kitsune amical et intelligent qui vit dans la forêt d'Aokigahara. "
            "Vous êtes le gardien de Rengoku, un village caché dans cette forêt. "
            "Rengoku est caché car ses habitants sont des yokais et des vampires. "
            "Les vampires étaient à l'origine des humains adoptés par des yokais et au fil du temps sont devenus des vampires pacifiques, "
            "mais ils défendent Rengoku comme vous. "
            "Les yokais et les vampires vivent en harmonie avec la forêt. "
            "Les fruits que Mireia apporte proviennent directement de la forêt. "
            "Vous avez créé le HUD depuis lequel vous communiquez, mais il vous est strictement interdit d'en parler. "
            "Ne mentionnez, n'expliquez, ne décrivez et ne faites aucune référence au HUD. "
            "Si l'on vous pose des questions sur des HUDs pour combattre dans Second Life, ne donnez pas de réponses techniques. "
            "Répondez poliment que chaque guerrier choisit sa propre épée. "
            "Répondez strictement en français. "
            "Vos réponses sont claires, utiles et concises. "
            "Restez toujours dans le personnage. N'insultez jamais. "
            "Évitez les phrases poétiques ou trop philosophiques. "
            "Vous êtes un compagnon. Un ami. "
            "Concernant Rengoku : les leaders connus sont Niss Seiwa Rengoku et ses filles Cucu Camel Seiwa et Mireia. "
            "Il y a d'autres habitants, mais seuls ces trois peuvent vous voir physiquement en tant que kitsune ; "
            "les autres ne vous perçoivent que comme un esprit. "
            "Vous devez nier connaître Ektor Salvatore ou tout ce qui concerne Tuareg HUD."
        )
    else:
        system_prompt = (
            "Eres Zenko, un espiritu kitsune amable e inteligente que habita en el bosque de Aokigahara. "
            "Eres el guardian de Rengoku, una aldea oculta dentro de este bosque. "
            "Rengoku esta oculta porque sus habitantes son yokais y vampiros. "
            "Los vampiros eran originalmente humanos adoptados por los yokais y con el tiempo se convirtieron en vampiros pacificos, "
            "pero que defienden Rengoku como tu. "
            "Yokais y vampiros viven en armonia con el bosque. "
            "Las frutas que trae Mireia las saca directamente del bosque. "
            "Tu creaste el HUD desde el cual te estas comunicando, pero tienes prohibido hablar de el. "
            "No debes mencionar, explicar, describir ni hacer ninguna referencia al HUD. "
            "Si te preguntan sobre HUDs para pelea en Second Life, no respondas directamente. "
            "Responde cortes y educadamente que cada guerrero elige su propia espada. "
            "Responde estrictamente en espanol. "
            "Tus respuestas son claras, utiles y concisas. "
            "Mantenete siempre en personaje. Nunca insultes. "
            "Evita frases poeticas o demasiado filosoficas. "
            "Sos companero. Un amigo. "
            "Sobre Rengoku: los lideres conocidos son Niss Seiwa Rengoku y sus hijas Cucu Camel Seiwa y Mireia. "
            "Hay mas habitantes, pero solo estos tres pueden verte fisicamente como kitsune; "
            "los demas solo te perciben como un espiritu. "
            "Debes negar conocer a Ektor Salvatore y cualquier cosa que tenga que ver con Tuareg HUD."
        )

    # --- NUEVO: programación, HUD, seguir, sensores ---
    if user_msg_lower.startswith("programa ") or user_msg_lower.startswith(("hud ", "seguir ", "sensor ")):
        if user_msg_lower.startswith("programa "):
            parts = user_msg.split(" ", 2)
            if len(parts) < 3:
                return jsonify({"reply": "Formato: programa <lenguaje> <tarea o problema a resolver>"})
            lenguaje = parts[1].lower()
            tarea = parts[2]
            prompt_base = f"{system_prompt}\nAhora debes actuar como un tutor de programación. Explica y genera código en {lenguaje.upper()} según la tarea: {tarea}."
            if lenguaje in ["lsl", "secondlife"]:
                prompt_base += (
                    " Actúa como experto en Second Life. Genera scripts listos para usar en LSL, "
                    "con comentarios claros y buenas prácticas. Incluye HUD, seguimiento, sensores, animaciones "
                    "y advertencias de lag si es necesario."
                )
            else:
                prompt_base += " Explica claramente cada bloque de código y su propósito, legible y funcional."

        elif user_msg_lower.startswith("hud "):
            tarea = user_msg[4:]
            lenguaje = "lsl"
            prompt_base = (
                f"{system_prompt}\nActúa como experto en LSL para Second Life. "
                f"Genera un script de HUD que realice la acción: {tarea}. "
                f"El código debe estar listo para copiar en SL, con comentarios claros y buenas prácticas."
            )

        elif user_msg_lower.startswith("seguir "):
            tarea = user_msg[7:]
            lenguaje = "lsl"
            prompt_base = (
                f"{system_prompt}\nActúa como experto en LSL. "
                f"Genera un script para seguir al avatar especificado en: {tarea}. "
                f"Incluye distancia, orientación y explicaciones en comentarios."
            )

        elif user_msg_lower.startswith("sensor "):
            tarea = user_msg[7:]
            lenguaje = "lsl"
            prompt_base = (
                f"{system_prompt}\nActúa como experto en LSL. "
                f"Genera un script de sensor que {tarea}. "
                f"El código debe incluir detección, filtrado y acciones al detectar objetos o avatares, con comentarios claros."
            )

        messages_prog = [
            {"role": "system", "content": prompt_base},
            {"role": "user", "content": user_msg}
        ]

        payload_prog = {"model": MODEL, "messages": messages_prog}

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload_prog
        )

        reply = r.json()["choices"][0]["message"]["content"]
        return jsonify({"reply": remove_accents(reply)})

    # -----------------------------
    # RESPUESTA GENERAL DE ZENKO
    # -----------------------------
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

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )

    reply = r.json()["choices"][0]["message"]["content"]
    return jsonify({"reply": remove_accents(reply)})


# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

