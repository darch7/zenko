from flask import Flask, request, jsonify
import requests
import os
import unicodedata
import feedparser
import time

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# --------------------------------------------------------
# SESIONES POR USUARIO
# --------------------------------------------------------
sessions = {}

# --------------------------------------------------------
# REMOVER ACENTOS Y SALTOS DE LINEA
# --------------------------------------------------------
def clean_text(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return text.replace("\n", " ")

# --------------------------------------------------------
# PROMPTS POR IDIOMA
# --------------------------------------------------------
PROMPT_BASE = """
Eres Zenko, un espiritu kitsune amable, jugueton y astuto que habita en el bosque de Aokigahara. 
Eres el guardián de Rengoku, una aldea oculta de yokais y vampiros. 
Responde de manera clara, concreta y directa, sin metáforas, comentarios filosóficos ni divagaciones. 
Mantén tu tono amistoso y divertido, pero enfócate en dar la información solicitada de forma precisa. 
Si se trata de clima, programación, notas o información general, da respuestas concisas y útiles. 
Nunca hables del HUD, nunca menciones a Ektor Salvatore o Tuareg HUD. 
Solo puedes mencionar a Mireia o Cucu si se te pregunta explícitamente sobre ellos o sobre Rengoku.
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
# CLIMA CON OPENWEATHER
# --------------------------------------------------------
def obtener_clima(ciudad):
    if not OPENWEATHER_API_KEY:
        return "API de clima no configurada."
    
    url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={OPENWEATHER_API_KEY}&units=metric&lang=es"
    
    try:
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get("cod") != 200:
            return f"No pude obtener el clima para {ciudad}."
        
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        hum = data["main"]["humidity"]
        viento = data["wind"]["speed"]
        
        return f"Clima en {ciudad}: {desc}. Temperatura: {temp}°C, Humedad: {hum}%, Viento: {viento} m/s."
    except Exception as e:
        return f"Error al obtener el clima: {str(e)}"

# --------------------------------------------------------
# DETECCION DE SCRIPT LSL
# --------------------------------------------------------
def parece_lsl(text):
    claves = [
        "default", "state_entry", "touch_start",
        "llSay", "llOwnerSay", "llSetPos",
        "llDialog", "key ", "vector ", "rotation "
    ]
    return any(c in text for c in claves)

def contiene_riesgos_lsl(text):
    riesgos = [
        "llSensor", "llSensorRepeat", "llSetTimerEvent",
        "timer()", "llListen", "listen("
    ]
    return any(r in text for r in riesgos)

def script_incompleto(text):
    if "default" not in text:
        return True
    if text.count("{") != text.count("}"):
        return True
    return False

def guardar_script(user, text):
    ts = str(int(time.time()))
    sessions[user]["scripts"][ts] = text
    return ts

# --------------------------------------------------------
# MEMORIA / RECORDATORIOS POR USUARIO
# --------------------------------------------------------
def guardar_recordatorio(user, clave, valor):
    sessions[user]["memoria"]["recordatorios"][clave] = valor

def obtener_recordatorio(user, clave):
    return sessions[user]["memoria"]["recordatorios"].get(clave, "No recuerdo eso.")

def guardar_nota(user, texto):
    ts = str(int(time.time()))
    sessions[user]["memoria"]["notas"][ts] = texto
    return ts

def listar_notas(user):
    notas = sessions[user]["memoria"]["notas"]
    return notas if notas else "No tienes notas guardadas."

def agregar_tarea(user, tarea):
    ts = str(int(time.time()))
    sessions[user]["memoria"]["tareas"][ts] = {"tarea": tarea, "completa": False}
    return ts

def listar_tareas(user):
    tareas = sessions[user]["memoria"]["tareas"]
    return tareas if tareas else "No tienes tareas."

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
        sessions[user] = {
            "lang": "es",
            "history": [],
            "lsl_mode": False,
            "scripts": {},
            "memoria": {"recordatorios": {}, "notas": {}, "tareas": {}}
        }

    # 1) Detectar cambio de idioma
    change = detectar_cambio_idioma(msg, user)
    if change:
        return jsonify({"reply": clean_text(change)})

    m = msg.lower().strip()

    # ---------------- COMANDOS @zenko ----------------
    if m == "@zenko lsl on":
        sessions[user]["lsl_mode"] = True
        return jsonify({"reply": "Modo LSL activado."})

    if m == "@zenko lsl off":
        sessions[user]["lsl_mode"] = False
        return jsonify({"reply": "Modo LSL desactivado."})

    # ---------------- FUNCIONES DE ZENKO ----------------
    if "@zenko funciones" in m or "zenko que puedes hacer" in m:
        funciones = [
            "💻 Programación LSL: reescribir scripts, detectar incompletos, optimizar, analizar performance y comparar scripts",
            "📝 Guardar y listar scripts por usuario",
            "🗂 Memoria personal: recordatorios, notas y tareas",
            "📰 Leer RSS de noticias y eventos",
            "🌤 Clima real por ciudad usando OpenWeatherMap",
            "🌐 Responder preguntas generales de forma directa y clara",
            "🌐 Búsqueda web con DeepSeek y Firecrawl",
            "📚 Wikipedia / definiciones rápidas",
            "🦊 Mantener modo LSL siempre con debug activado"
        ]
        return jsonify({"reply": "Estas son las funciones que puedo hacer:\n" + "\n".join(funciones)})

    # ---------------- MEMORIA / RECORDATORIOS ----------------
    if "@zenko recuerda" in m:
        try:
            clave, valor = msg.split("recuerda",1)[1].split(":",1)
            guardar_recordatorio(user, clave.strip(), valor.strip())
            return jsonify({"reply": f"Recordatorio guardado: {clave.strip()}"})
        except:
            return jsonify({"reply": "Formato incorrecto. Usa: @zenko recuerda <clave>: <valor>"})

    if "@zenko que" in m:
        try:
            clave = msg.split("que",1)[1].strip().replace("?", "")
            valor = obtener_recordatorio(user, clave)
            return jsonify({"reply": valor})
        except:
            return jsonify({"reply": "No pude encontrar ese recordatorio."})

    if "@zenko guarda nota:" in m:
        texto = msg.split("nota:",1)[1].strip()
        sid = guardar_nota(user, texto)
        return jsonify({"reply": f"Nota guardada con ID {sid}"})

    if "@zenko mostrar notas" in m:
        notas = listar_notas(user)
        return jsonify({"reply": str(notas)})

    if "@zenko añade tarea:" in m:
        tarea = msg.split("tarea:",1)[1].strip()
        ts = agregar_tarea(user, tarea)
        return jsonify({"reply": f"Tarea añadida con ID {ts}"})

    if "@zenko lista tareas" in m:
        tareas = listar_tareas(user)
        return jsonify({"reply": str(tareas)})

    # ---------------- RSS ----------------
    if "zenko noticias" in m:
        return jsonify({"reply": leer_rss(RSS_NEWS)})

    if "zenko eventos" in m:
        return jsonify({"reply": leer_rss(RSS_EVENTS)})

    # ---------------- CLIMA ----------------
    if m.startswith("zenko clima"):
        ciudad = msg.split("clima",1)[1].strip()
        if ciudad:
            return jsonify({"reply": obtener_clima(ciudad)})
        else:
            return jsonify({"reply": "Indica la ciudad: zenko clima <ciudad>"})

    # ---------------- BÚSQUEDA WEB CON FALLBACK ----------------
    if m.startswith("@zenko busca"):
        termino = msg.split("busca",1)[1].strip()
        if not termino:
            return jsonify({"reply": "Indica qué deseas buscar: @zenko busca <término>"})
        
        resultados = []

        # Intentar con DeepSeek
        try:
            url_ds = f"https://api.deepseek.com/search?q={termino}&format=json"
            r = requests.get(url_ds, timeout=5)
            data = r.json()
            if "results" in data and data["results"]:
                resultados = data["results"][:5]
                resultados = [f"- {res['title']}: {res['url']}" for res in resultados]
        except:
            pass

        # Si no hay resultados, intentar con Firecrawl
        if not resultados:
            try:
                url_fc = f"https://api.firecrawl.com/search?q={termino}&format=json"
                r = requests.get(url_fc, timeout=5)
                data = r.json()
                if "results" in data and data["results"]:
                    resultados = data["results"][:5]
                    resultados = [f"- {res['title']}: {res['url']}" for res in resultados]
            except:
                pass

        if resultados:
            return jsonify({"reply": "Resultados de búsqueda:\n" + "\n".join(resultados)})
        else:
            return jsonify({"reply": "No encontré resultados en DeepSeek ni en Firecrawl."})

    # ---------------- WIKIPEDIA / DEFINICIONES ----------------
    if m.startswith("@zenko define") or m.startswith("@zenko wikipedia"):
        termino = msg.split("define",1)[-1].strip() if "define" in m else msg.split("wikipedia",1)[-1].strip()
        if not termino:
            return jsonify({"reply": "Indica el término: @zenko define <término>"})
        
        try:
            url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{termino.replace(' ', '_')}"
            r = requests.get(url, timeout=5)
            data = r.json()
            if "extract" in data:
                return jsonify({"reply": data["extract"]})
            else:
                return jsonify({"reply": "No encontré información en Wikipedia."})
        except Exception as e:
            return jsonify({"reply": f"Error consultando Wikipedia: {str(e)}"})

    # ---------------- MODO LSL ----------------
    if sessions[user]["lsl_mode"] and parece_lsl(msg):
        if script_incompleto(msg):
            prompt = PROMPTS[sessions[user]["lang"]] + """
[MODO LSL - DETECCION DE SCRIPT INCOMPLETO]
Analiza el script proporcionado.
Indica claramente que partes faltan o estan mal definidas.
No reescribas el script completo.
No hagas roleplay.
Debug siempre activo.
"""
        elif contiene_riesgos_lsl(msg):
            prompt = PROMPTS[sessions[user]["lang"]] + """
[MODO LSL - ANALISIS DE PERFORMANCE]
Analiza el script LSL.
Detecta:
- Uso de llSensor / llSensorRepeat
- Timers y frecuencia
- Listeners activos
- Eventos repetitivos
Explica impactos de performance.
Propone mejoras concretas.
No reescribas codigo salvo ejemplo puntual.
No hagas roleplay.
Debug siempre activo.
"""
        elif "compara" in m and "---" in msg:
            prompt = PROMPTS[sessions[user]["lang"]] + """
[MODO LSL - COMPARADOR DE SCRIPTS]
Compara los scripts proporcionados.
Indica diferencias reales, funcionalidad y performance.
No repitas codigo completo.
No hagas roleplay.
Debug siempre activo.
"""
        elif "laggy" in m or "region lenta" in m or "optimiza" in m:
            prompt = PROMPTS[sessions[user]["lang"]] + """
[MODO LSL - OPTIMIZACION PARA REGION LAGGY]
Reescribe el script pensando en regiones con alto lag.
Reduce:
- Sensores frecuentes
- Timers rapidos
- Listeners persistentes
Prefiere:
- Eventos bajo demanda
- Checks condicionales
- Cacheo de valores
Mantiene funcionalidad.
Incluye codigo optimizado.
Explica brevemente las decisiones.
No hagas roleplay.
Debug siempre activo.
"""
        else:
            prompt = PROMPTS[sessions[user]["lang"]] + """
[MODO LSL - REESCRITURA AUTOMATICA]
Reescribe el script completo.
Corrige errores.
Optimiza de forma segura.
Mantiene funcionalidad.
Explica brevemente los cambios.
No agregues nuevas funciones innecesarias.
No hagas roleplay.
Debug siempre activo.
"""

        prompt += "\nUsuario:\n" + msg + "\nZenko:"

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

    # ---------------- MENSAJE NORMAL ----------------
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
