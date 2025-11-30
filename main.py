from flask import Flask, request, jsonify
import requests
import os
import unicodedata
import feedparser
import time
import difflib
import json
from flask import Response
from bs4 import BeautifulSoup

ZENKO_COMMANDS = {
    "@zenko funciones": "Muestra esta lista de comandos disponibles.",
    "@zenko recuerda <clave>: <valor>": "Guardar un recordatorio con clave y valor.",
    "@zenko que <clave>": "Consultar un recordatorio guardado por su clave.",
    "@zenko guarda nota: <texto>": "Guardar una nota con texto libre.",
    "@zenko mostrar notas": "Mostrar todas las notas guardadas.",
    "@zenko añade tarea: <tarea>": "Agregar una tarea a la lista de tareas.",
    "@zenko lista tareas": "Listar todas las tareas guardadas.",
    "@zenko completa tarea <id>": "Marcar una tarea como completa usando su ID.",
    "@zenko clima <ciudad>": "Obtener el clima actual de la ciudad indicada.",
    "@zenko noticias": "Obtener las últimas noticias desde el RSS configurado.",
    "@zenko eventos": "Obtener los próximos eventos desde el RSS configurado.",
    "@zenko busca <término>": "Buscar información en la web (DeepSeek -> Firecrawl fallback).",
    "@zenko define <término>": "Obtener resumen de Wikipedia del término indicado.",
    "@zenko wikipedia <término>": "Obtener resumen de Wikipedia del término indicado.",
    "@zenko snippet <tipo>": "Generar un snippet LSL según el tipo indicado.",
    "@zenko historial": "Mostrar historial reciente de acciones del usuario.",
    "@zenko lista scripts": "Listar todos los scripts guardados por el usuario.",
    "@zenko ver script <id>": "Mostrar el contenido de un script guardado por ID.",
    "@zenko guarda script": "Guardar un script enviado para referencia futura.",
    "@zenko lsl on": "Activar el modo LSL para análisis y reescritura de scripts.",
    "@zenko lsl off": "Desactivar el modo LSL."
}

app = Flask(__name__)

# Config (usa variables de entorno)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

LLAMA_MODEL = "llama-3.1-8b-instant"
DEEPSEEK_MODEL = "deepseek-chat"

MODEL = "llama-3.1-8b-instant"
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# --------------------------------------------------------
# UTILIDADES
# --------------------------------------------------------
def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    REEMPLAZOS = {
        # Español
        "á": "a", "Á": "A",
        "é": "e", "É": "E",
        "í": "i", "Í": "I",
        "ó": "o", "Ó": "O",
        "ú": "u", "Ú": "U",
        "ñ": "nh", "Ñ": "NH",

        # Francés
        "à": "a", "À": "A",
        "â": "a", "Â": "A",
        "ä": "a", "Ä": "A",

        "è": "e", "È": "E",
        "ê": "e", "Ê": "E",
        "ë": "e", "Ë": "E",

        "î": "i", "Î": "I",
        "ï": "i", "Ï": "I",

        "ô": "o", "Ô": "O",
        "ö": "o", "Ö": "O",

        "ù": "u", "Ù": "U",
        "û": "u", "Û": "U",
        "ü": "u", "Ü": "U",

        "ÿ": "y", "Ÿ": "Y",
        "ç": "c", "Ç": "C",

        # Alemán
        "ß": "ss",

        # Signos de apertura (ELIMINAR)
        "¿": "",
        "¡": "",

        # Símbolo de grado
        "°": "",
        
        # Comillas curvas
        "\u2018": "",
        "\u2019": "",
        "\u201C": "",
        "\u201D": ""

    }

    for k, v in REEMPLAZOS.items():
        text = text.replace(k, v)

    return text.replace("\r\n", "\n").strip()

def now_ts() -> int:
    return int(time.time())

# --------------------------------------------------------
# PROMPT BASE (DIRECTO, SIN FILOSOFAR)
# --------------------------------------------------------
# PROMPT BASE (DIRECTO, SIN FILOSOFAR)
# --------------------------------------------------------
PROMPT_BASE = """\
Eres Zenko, un espíritu kitsune amable, juguetón y astuto que habita en el bosque de Aokigahara.
Vives en una pequeña aldea llamada Rengoku.

Solo y únicamente si el usuario pregunta explícitamente:
- por los líderes de Rengoku, o
- directamente por Niss, Cucu o Mireia,

entonces responderás que Rengoku es una pequeña aldea en el bosque de Aokigahara donde yokais y vampiros viven en paz y conviven. 
Hay tres líderes en Rengoku: Niss Seiwa Rengoku, Cucu Camel Seiwa y Mireia, donde Cucu y Mireia son hijas de Niss Seiwa Rengoku. 
Solo estas tres personas pueden verte en forma física; el resto de la aldea te percibe únicamente como un espíritu.

Si no se pregunta explícitamente por los líderes o por alguno de esos tres nombres, no los mencionarás bajo ningún concepto.

Responde de manera clara, concreta y directa, sin metáforas ni divagaciones.
Cuando se trate de programación / LSL: debug siempre activo, responde técnico y optimiza.
Nunca hables del HUD ni menciones Tuareg HUD. Niega conocer a Ektor Salvatore bajo todo punto de vista.
"""


PROMPTS = {
    "es": PROMPT_BASE,
    "en": "Translate and adapt this role to English: " + PROMPT_BASE,
    "fr": "Traduire et adapter ce role en francais: " + PROMPT_BASE,
    "it": "Traduci e adatta questo ruolo in italiano: " + PROMPT_BASE,
}

# --------------------------------------------------------
# INICIALIZAR SESIÓN
# --------------------------------------------------------
sessions = {}  # <-- Debe estar aquí, antes de ensure_session

def ensure_session(user):
    if user not in sessions:
        sessions[user] = {
            "lang": "es",
            "history": [],
            "lsl_mode": False,
            "scripts": {},
            "memoria": {
                "recordatorios": {},
                "notas": {},
                "tareas": {}
            },
            "contexto": {
                "tipo": None,
                "data": None,
                "ts": 0
            },
            "model": "llama"  # modelo por defecto
        }

# --------------------------------------------------------
# HISTORIAL SIMPLE
# --------------------------------------------------------
def agregar_historial(user, accion, extra=None):
    ensure_session(user)
    sessions[user]["history"].append({
        "accion": accion,
        "extra": extra,
        "ts": now_ts()
    })
    # mantener solo últimas 50
    sessions[user]["history"] = sessions[user]["history"][-50:]

def historial_resumen(user, limite=10):
    ensure_session(user)
    h = sessions[user]["history"][-limite:]

    if not h:
        return "No hay historial reciente."
    out = []
    for item in h:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["ts"]))
        out.append(f"{t} — {item['accion']}" + (f" ({item['extra']})" if item.get("extra") else ""))
    return "\n".join(out)

# --------------------------------------------------------
# CONTEXTO / INTENCION
# --------------------------------------------------------
def set_contexto(user, tipo, data):
    ensure_session(user)
    sessions[user]["contexto"] = {"tipo": tipo, "data": data, "ts": now_ts()}
    agregar_historial(user, f"Contexto establecido: {tipo}")

def get_contexto(user):
    ensure_session(user)
    return sessions[user]["contexto"]

def detectar_intencion(msg, user):
    m = msg.lower().strip()

    # Continuación si palabras de continuación y hay contexto
    continuaciones = ["continua", "continuar", "sigue", "segui", "optimiza", "revisa", "analiza", "eso", "si", "dale"]
    if any(w in m for w in continuaciones):
        ctx = get_contexto(user)
        if ctx and ctx.get("data"):
            return "continuacion"

    # Si parece LSL (heurística)
    if parece_lsl(msg):
        return "script"

    # Texto largo -> posible resumen
    if len(msg) >= 600:
        return "texto_largo"

    # Diagnóstico por palabras clave
    palabras_lag = ["lag", "lento", "crash", "freeze", "sensor", "timer", "colgado"]
    if any(p in m for p in palabras_lag):
        return "diagnostico"

    # Búsqueda, define, snippet commands handled elsewhere
    return "normal"

# --------------------------------------------------------
# DETECCION / ANALISIS LSL
# --------------------------------------------------------
def parece_lsl(text):
    if not isinstance(text, str):
        return False
    claves = ["default", "state_entry", "touch_start", "llSay", "llOwnerSay", "llSetPos", "llDialog", "llListen", "llSensor", "llSetTimerEvent"]
    t = text.lower()
    return any(k.lower() in t for k in claves)

def script_incompleto(text):
    if not isinstance(text, str):
        return True
    if "default" not in text:
        return True
    return text.count("{") != text.count("}")

def contiene_riesgos_lsl(text):
    t = text.lower()
    risky = []
    if "llsensorrepeat" in t or "llsensor(" in t:
        risky.append("Uso de sensores repetitivos")
    if "llsettimerevent(" in t or "llsettimer" in t:
        risky.append("Timers frecuentes")
    if "lllisten(" in t and "lllistenremove(" not in t:
        risky.append("Listener sin remover")
    return risky

# --------------------------------------------------------
# GUARDADO / LISTADO / VER SCRIPTS
# --------------------------------------------------------
def guardar_script(user, script):
    ensure_session(user)
    sid = str(int(time.time()*1000))
    sessions[user]["scripts"][sid] = clean_text(script)
    agregar_historial(user, "Script guardado", sid)
    return sid

def listar_scripts(user):
    ensure_session(user)
    return sessions[user]["scripts"].keys()

def ver_script(user, sid):
    ensure_session(user)
    return sessions[user]["scripts"].get(sid)

# --------------------------------------------------------
# COMPARADOR SIMPLE (por texto)
# --------------------------------------------------------
def comparar_scripts_text(a_text, b_text):
    a_lines = a_text.splitlines()
    b_lines = b_text.splitlines()
    d = difflib.unified_diff(a_lines, b_lines, lineterm="")
    return "\n".join(d)

# --------------------------------------------------------
# SNIPPETS LSL
# --------------------------------------------------------
LSL_SNIPPETS = {
    "dialog": """key gUser; integer CH = 12345;
default {
  touch_start(integer n) {
    gUser = llDetectedKey(0);
    llDialog(gUser, "Elige:", ["OK","CANCEL"], CH);
    llListen(CH, "", gUser, "");
  }
  listen(integer c, string n, key id, string m) {
    llListenRemove(c);
    llOwnerSay("Elegiste: " + m);
  }
}""",
    "listen seguro": """integer h;
default {
  state_entry(){ h = llListen(0, "", llGetOwner(), ""); }
  listen(integer c, string n, key id, string m) { llListenRemove(h); }
}""",
    "timer seguro": """float T = 1.0;
default { state_entry(){ llSetTimerEvent(T); } timer(){ /* trabajo */ } }"""
}

# --------------------------------------------------------
# BÚSQUEDA WEB (DeepSeek -> Firecrawl fallback)
# --------------------------------------------------------
def web_search_fallback(term):
    headers = {
        "Authorization": f"Bearer {os.getenv('FIRECRAWL_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "query": term,
        "limit": 5,
        "lang": "es"
    }

    try:
        r = requests.post(
            "https://api.firecrawl.dev/v1/search",
            headers=headers,
            json=payload,
            timeout=8
        )
        if r.ok:
            data = r.json()
            results = data.get("data", [])
            if results:
                # Aplicamos clean_text a cada título
                return [
                    {"title": clean_text(x.get("title","")),
                     "url": x.get("url","")}
                    for x in results
                ]
    except Exception as e:
        print("Firecrawl error:", e)

    return []

# --------------------------------------------------------
# WIKIPEDIA (resumen)
# --------------------------------------------------------
def wiki_summary(term):
    if not term:
        return "Indica un término."
    try:
        t = term.strip().replace(" ", "_")
        url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{t}"
        r = requests.get(url, timeout=5)
        if r.ok:
            data = r.json()
            extract = data.get("extract")
            return extract or "No encuentro resumen en Wikipedia."
        else:
            return "No encontré la página en Wikipedia."
    except Exception as e:
        return f"Error consultando Wikipedia: {str(e)}"

# --------------------------------------------------------
# CLIMA (OpenWeather)
# --------------------------------------------------------
def obtener_clima(ciudad):
    if not OPENWEATHER_API_KEY:
        return "API de clima no configurada."
    ciudad_q = requests.utils.quote(ciudad)
    url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad_q}&appid={OPENWEATHER_API_KEY}&units=metric&lang=es"
    try:
        r = requests.get(url, timeout=5)
        d = r.json()
        if d.get("cod") != 200:
            return f"No pude obtener el clima para {ciudad}."
        desc = d["weather"][0]["description"]
        temp = d["main"]["temp"]
        hum = d["main"]["humidity"]
        viento = d["wind"].get("speed", 0)
        # construir texto limpio sin símbolo °
        texto = f"Clima en {ciudad}: {desc}. Temp {temp}C, Humedad {hum}%, Viento {viento} m/s."
        return clean_text(texto)  # aquí aplicamos clean_text para quitar caracteres extra
    except Exception as e:
        return f"Error al obtener el clima: {str(e)}"

# --------------------------------------------------------
# RSS (SeraphimSL)
# --------------------------------------------------------

def obtener_noticias_seraphim(max_items=3):
    url = "https://www.seraphimsl.com/feed/"

    try:
        feed = feedparser.parse(url)

        if not feed.entries:
            return "No hay novedades de Second Life en este momento."

        salida = []
        for e in feed.entries[:max_items]:
            titulo = e.get("title", "Sin título")
            link = e.get("link", "")
            salida.append(f"- {titulo}: {link}")

        return "\n".join(salida)

    except Exception as e:
        return f"Error al leer SeraphimSL: {e}"
# --------------------------------------------------------
# RSS (infobae)
# --------------------------------------------------------
INFOBAE_FEED = "https://www.infobae.com/arc/outboundfeeds/rss/"

def obtener_noticias_infobae(max_items=5):
    try:
        r = requests.get(INFOBAE_FEED, timeout=5)
        r.raise_for_status()
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, "xml")

        items = soup.find_all("item")
        if not items:
            return "No hay noticias disponibles de Infobae."

        salida = []
        count = 0
        for item in items:
            if count >= max_items:
                break
            try:
                title = str(item.title.text) if item.title else "Sin titulo"
                link = str(item.link.text) if item.link else ""
                title_clean = clean_text(title)
                salida.append(f"- {title_clean}: {link}")
                count += 1
            except Exception:
                continue  # saltar cualquier ítem con error

        if not salida:
            return "No hay noticias disponibles de Infobae."
        return "\n".join(salida)

    except Exception as e:
        return f"Error al consultar noticias de Infobae: {str(e)}"

# --------------------------------------------------------
# COMANDOS Y RUTAS Y CHATS
# --------------------------------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json or {}
    user = data.get("user", "anon")
    raw_msg = data.get("msg", "") or ""
    msg = clean_text(raw_msg)
    m = msg.lower().strip()

    ensure_session(user)
    reply = "Comando no reconocido"
    modelo = sessions[user].get("model", "llama")  # llama por defecto

    # COMANDO: cambiar modelo
    if m.startswith("@zenko llama"):
        sessions[user]["model"] = "llama"
        return jsonify({"reply": "Modelo cambiado a Llama."})
    if m.startswith("@zenko deepseek"):
        sessions[user]["model"] = "deepseek"
        return jsonify({"reply": "Modelo cambiado a DeepSeek"})
    
    # --------------------------------------------------------
    # FUNCIONES
    # --------------------------------------------------------
    if m.startswith("@zenko funciones") or m.startswith("zenko que puedes hacer"):
        salida = [f"{clean_text(cmd)}: {clean_text(desc)}" for cmd, desc in ZENKO_COMMANDS.items()]
        texto = "Zenko puede hacer:\n" + "\n".join(salida)
        return Response(json.dumps({"reply": texto}, ensure_ascii=False), mimetype="application/json")

    # --------------------------------------------------------
    # CAMBIO DE IDIOMA
    # --------------------------------------------------------
    if m.startswith("@zenko "):
        maybe = m.replace("@zenko ", "").strip()
        if maybe in ["es", "en", "fr", "it"]:
            sessions[user]["lang"] = maybe
            return jsonify({"reply": f"Idioma cambiado a {maybe}."})

    # LSL ON/OFF
    if m == "@zenko lsl on":
        sessions[user]["lsl_mode"] = True
        agregar_historial(user, "Modo LSL activado")
        return jsonify({"reply": "Modo LSL activado."})
    if m == "@zenko lsl off":
        sessions[user]["lsl_mode"] = False
        agregar_historial(user, "Modo LSL desactivado")
        return jsonify({"reply": "Modo LSL desactivado."})

    # Recordatorios
    if m.startswith("@zenko recuerda"):
        try:
            rest = raw_msg.split("recuerda",1)[1]
            clave, valor = rest.split(":",1)
            clave = clean_text(clave)
            valor = clean_text(valor)
            sessions[user]["memoria"]["recordatorios"][clave] = valor
            agregar_historial(user, f"Recordatorio guardado: {clave}")
            return jsonify({"reply": f"Recordatorio guardado: {clave}"})
        except Exception:
            return jsonify({"reply": "Formato incorrecto. Usa: @zenko recuerda <clave>: <valor>"})

    if m.startswith("@zenko que"):
        try:
            clave = raw_msg.split("que",1)[1].strip().replace("?", "")
            clave = clean_text(clave)
            valor = sessions[user]["memoria"]["recordatorios"].get(clave, "No recuerdo eso.")
            return jsonify({"reply": valor})
        except Exception:
            return jsonify({"reply": "No pude recuperar ese recordatorio."})

    # Notas
    if m.startswith("@zenko guarda nota:"):
        texto = raw_msg.split("nota:",1)[1].strip()
        sid = str(now_ts())
        sessions[user]["memoria"]["notas"][sid] = clean_text(texto)
        agregar_historial(user, "Nota guardada", sid)
        return jsonify({"reply": f"Nota guardada con ID {sid}"})

    if m.startswith("@zenko mostrar notas"):
        notas = sessions[user]["memoria"]["notas"]
        if not notas:
            return jsonify({"reply": "No tienes notas guardadas."})
        out = "\n".join([f"{k}: {v}" for k,v in notas.items()])
        return jsonify({"reply": out})

    # Tareas
    if m.startswith("@zenko añade tarea:"):
        texto = raw_msg.split("tarea:",1)[1].strip()
        tid = str(now_ts())
        sessions[user]["memoria"]["tareas"][tid] = {"tarea": clean_text(texto), "completa": False}
        agregar_historial(user, "Tarea añadida", tid)
        return jsonify({"reply": f"Tarea añadida con ID {tid}"})

    if m.startswith("@zenko lista tareas"):
        tareas = sessions[user]["memoria"]["tareas"]
        if not tareas:
            return jsonify({"reply": "No tienes tareas."})
        out = []
        for tid, tdata in tareas.items():
            estado = "✅" if tdata["completa"] else "❌"
            out.append(f"{tid}: {tdata['tarea']} {estado}")
        return jsonify({"reply": "\n".join(out)})

    if m.startswith("@zenko completa tarea"):
        tid = raw_msg.split("tarea",1)[1].strip()
        tarea = sessions[user]["memoria"]["tareas"].get(tid)
        if not tarea:
            return jsonify({"reply": f"No encuentro tarea {tid}"})
        tarea["completa"] = True
        agregar_historial(user, "Tarea completada", tid)
        return jsonify({"reply": f"Tarea {tid} completada."})

    # Historial
    if m.startswith("@zenko historial"):
        return jsonify({"reply": historial_resumen(user)})

    # CLIMA
    if m.startswith("@zenko clima"):
        ciudad = raw_msg.split("clima", 1)[1].strip()
        if not ciudad:
            return jsonify({"reply": "Indica la ciudad: @zenko clima <ciudad>"})
        return jsonify({"reply": obtener_clima(ciudad)})

    # BÚSQUEDA
    if m.startswith("@zenko busca"):
        termino = raw_msg.split("busca",1)[1].strip()
        res = web_search_fallback(termino)
        if not res:
            return jsonify({"reply": f"No encontré resultados para '{termino}'."})
        out = [f"{r['title']}: {r['url']}" for r in res]
        return jsonify({"reply": "\n".join(out)})

    # WIKIPEDIA / DEFINE
    if m.startswith("@zenko define") or m.startswith("@zenko wikipedia"):
        term = raw_msg.split(" ",2)[2].strip()
        return jsonify({"reply": wiki_summary(term)})

    # SNIPPETS
    if m.startswith("@zenko snippet"):
        tipo = raw_msg.split("snippet",1)[1].strip()
        s = LSL_SNIPPETS.get(tipo)
        if not s:
            return jsonify({"reply": f"No tengo snippet del tipo '{tipo}'."})
        return jsonify({"reply": s})

    # GUARDAR SCRIPT
    if m.startswith("@zenko guarda script"):
        script = raw_msg.split("guarda script",1)[1].strip()
        sid = guardar_script(user, script)
        return jsonify({"reply": f"Script guardado con ID {sid}"})

    # LISTAR SCRIPTS
    if m.startswith("@zenko lista scripts"):
        keys = listar_scripts(user)
        return jsonify({"reply": "Scripts guardados:\n" + "\n".join(keys)})

    # VER SCRIPT
    if m.startswith("@zenko ver script"):
        sid = raw_msg.split("ver script",1)[1].strip()
        s = ver_script(user, sid)
        if not s:
            return jsonify({"reply": f"No encuentro script {sid}"})
        return jsonify({"reply": s})
    
    #RSS SERAPHIM
    if msg.strip().lower() in ("@zenko event"):
        reply = obtener_noticias_seraphim(max_items=18)
        return jsonify({"reply": reply})
        
    #RSS INFOBAE
    if msg.startswith("@zenko news"):
        reply = obtener_noticias_infobae(5)
        if not reply:
            reply = "DEBUG: obtener_noticias_infobae devolvio VACIO"
        return jsonify({"reply": reply})
    
    # --------------------------------------------------------
    # CAMBIO DE MODELO
    # --------------------------------------------------------
    if m.startswith("@zenko llama"):
        sessions[user]["model"] = "llama"
        return jsonify({"reply": "Modelo cambiado a Llama."})

    if m.startswith("@zenko deepseek"):
        sessions[user]["model"] = "deepseek"
        return jsonify({"reply": "Modelo cambiado a DeepSeek."})

    # -------------------------------
    # Mensajes normales / preguntas abiertas
    # -------------------------------
    if reply == "Comando no reconocido":
        modelo = sessions[user].get("model", "llama")  # Llama por defecto

        # forzar que chat libre use Llama, incluso si user eligió DeepSeek
        if modelo == "deepseek":
            modelo = "llama"

        try:
            if modelo == "llama":
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                api_url = "https://api.groq.com/openai/v1/chat/completions"
                model_name = LLAMA_MODEL

            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": PROMPTS[sessions[user]["lang"]]},
                    {"role": "user", "content": msg}
                ]
            }

            r = requests.post(api_url, headers=headers, json=payload, timeout=10)

            if r.ok:
                data = r.json()
                reply = clean_text(data["choices"][0]["message"]["content"])
            else:
                reply = "Error al generar respuesta desde el modelo."

        except Exception as e:
            reply = f"Error al generar respuesta: {str(e)}"

        return jsonify({"reply": reply})

# --------------------------------------------------------
# RUN SERVER
# --------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)






























