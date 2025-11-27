from flask import Flask, request, jsonify
import requests
import os
import unicodedata
import feedparser
import time
import difflib

app = Flask(__name__)

# Config (usa variables de entorno)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# --------------------------------------------------------
# SESIONES Y ESTRUCTURAS POR USUARIO
# --------------------------------------------------------
sessions = {}  # estructura principal por usuario

# --------------------------------------------------------
# UTILIDADES
# --------------------------------------------------------
def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    txt = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return txt.replace("\r\n", "\n").strip()

def now_ts() -> int:
    return int(time.time())

# --------------------------------------------------------
# PROMPT BASE (DIRECTO, SIN FILOSOFAR)
# --------------------------------------------------------
PROMPT_BASE = """\
Eres Zenko, un espiritu kitsune amable, jugueton y astuto que habita en el bosque de Aokigahara.
Responde de manera clara, concreta y directa, sin metáforas ni divagaciones.
Cuando se trate de programación / LSL: debug siempre activo, responde técnico y optimiza.
Nunca hables del HUD ni menciones Tuareg HUD.
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
def ensure_session(user):
    if user not in sessions:
        sessions[user] = {
            "lang": "es",
            "history": [],             # lista de acciones (dicts)
            "lsl_mode": False,         # se activa con @zenko lsl on
            "scripts": {},             # id -> script text
            "memoria": {               # memoria por usuario
                "recordatorios": {},
                "notas": {},
                "tareas": {}
            },
            "contexto": {              # contexto persistente
                "tipo": None,         # 'script'|'resumen'|'diagnostico'|'comparador'
                "data": None,
                "ts": 0
            }
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

 def web_search_fallback(term):
    term = term.strip()
    resultados = []

    # ---------------------------------------------
    # 1) INTENTO CON DEEPSEEK (via chat + fuentes)
    # ---------------------------------------------
    if DEEPSEEK_API_KEY:
        try:
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": "Devuelve SOLO una lista de fuentes web relevantes con titulo y URL."
                    },
                    {
                        "role": "user",
                        "content": f"Busca en la web informacion sobre: {term}"
                    }
                ],
                "temperature": 0.2
            }

            r = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=8
            )

            if r.ok:
                content = r.json()["choices"][0]["message"]["content"]
                # heurística simple: buscar URLs
                lines = content.splitlines()
                for ln in lines:
                    if "http" in ln:
                        resultados.append({
                            "title": ln[:80],
                            "url": ln.split()[-1]
                        })

                if resultados:
                    return resultados[:5]

        except Exception:
            pass

    # ---------------------------------------------
    # 2) FIRECRAWL (fallback real)
    # ---------------------------------------------
    try:
        term_enc = requests.utils.quote(term)
        r = requests.get(
            f"https://api.firecrawl.dev/search?q={term_enc}&limit=5",
            headers={
                "Authorization": f"Bearer {os.getenv('FIRECRAWL_API_KEY')}"
            },
            timeout=8
        )

        if r.ok:
            data = r.json()
            if "results" in data:
                return [
                    {"title": i.get("title", ""), "url": i.get("url", "")}
                    for i in data["results"]
                ]
    except Exception:
        pass

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
        return f"Clima en {ciudad}: {desc}. Temp {temp}°C, Humedad {hum}%, Viento {viento} m/s."
    except Exception as e:
        return f"Error al obtener el clima: {str(e)}"

# --------------------------------------------------------
# RSS (Infobae / SeraphimSL)
# --------------------------------------------------------
RSS_NEWS = "https://www.infobae.com/argentina-footer/infobae/rss/"
RSS_EVENTS = "https://www.seraphimsl.com/feed/"

def leer_rss(url):
    feed = feedparser.parse(url)
    if not feed.entries:
        return "No hay resultados."
    salida = []
    for item in feed.entries[:5]:
        salida.append(f"- {clean_text(item.title)}")
    return "\n".join(salida)

# --------------------------------------------------------
# COMANDOS Y RUTAS
# --------------------------------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json or {}
    user = data.get("user", "anon")
    raw_msg = data.get("msg", "") or ""
    msg = clean_text(raw_msg)
    m = msg.lower().strip()

    ensure_session(user)

    # Detectar cambio de idioma @zenko <code>
    if m.startswith("@zenko "):
        maybe = m.replace("@zenko ", "").strip()
        if maybe in ["es","en","fr","it"]:
            sessions[user]["lang"] = maybe
            return jsonify({"reply": f"Idioma cambiado a {maybe}."})

    # Comandos LSL ON/OFF
    if m == "@zenko lsl on":
        sessions[user]["lsl_mode"] = True
        agregar_historial(user, "Modo LSL activado")
        return jsonify({"reply": "Modo LSL activado."})
    if m == "@zenko lsl off":
        sessions[user]["lsl_mode"] = False
        agregar_historial(user, "Modo LSL desactivado")
        return jsonify({"reply": "Modo LSL desactivado."})

    # ¿Qué puede hacer?
    if "@zenko funciones" in m or "zenko que puedes hacer" in m:
        funciones = [
            "Programación LSL: reescribir, analizar, optimizar, comparar",
            "Guardar/listar/ver scripts por usuario",
            "Memoria personal: recordatorios, notas, tareas",
            "RSS de noticias y eventos",
            "Clima real por ciudad",
            "Búsqueda web (DeepSeek -> Firecrawl fallback)",
            "Wikipedia / definiciones",
            "Snippets LSL",
            "Historial consultable",
            "Contexto / continuar trabajo"
        ]
        return jsonify({"reply": "Funciones:\n" + "\n".join(funciones)})

    # MEMORIA: recordatorios
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
        # ej: @zenko que color es mi favorito?
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
        out = "\n".join([f"{k}: {v['tarea']} (completa: {v['completa']})" for k,v in tareas.items()])
        return jsonify({"reply": out})

    if m.startswith("@zenko completa tarea"):
        # formato: @zenko completa tarea <id>
        parts = m.split()
        if len(parts) >= 3:
            tid = parts[-1]
            if tid in sessions[user]["memoria"]["tareas"]:
                sessions[user]["memoria"]["tareas"][tid]["completa"] = True
                agregar_historial(user, "Tarea completada", tid)
                return jsonify({"reply": f"Tarea {tid} marcada como completa."})
        return jsonify({"reply": "Indica ID de tarea: @zenko completa tarea <id>"})

    # RSS
    if "zenko noticias" in m:
        return jsonify({"reply": leer_rss(RSS_NEWS)})
    if "zenko eventos" in m:
        return jsonify({"reply": leer_rss(RSS_EVENTS)})

    # CLIMA
    if m.startswith("zenko clima"):
        ciudad = raw_msg.split("clima",1)[1].strip()
        if not ciudad:
            return jsonify({"reply": "Indica la ciudad: zenko clima <ciudad>"})
        return jsonify({"reply": obtener_clima(ciudad)})

    # BÚSQUEDA WEB CON FALLBACK
    if m.startswith("@zenko busca"):
        termino = raw_msg.split("busca",1)[1].strip()
        if not termino:
            return jsonify({"reply": "Indica qué buscar: @zenko busca <término>"})
        resultados = web_search_fallback(termino)
        if resultados:
            out = "\n".join([f"- {r['title']}: {r['url']}" for r in resultados])
            return jsonify({"reply": "Resultados:\n" + out})
        return jsonify({"reply": "No encontré resultados en DeepSeek ni Firecrawl."})

    # WIKIPEDIA / DEFINICIONES
    if m.startswith("@zenko define") or m.startswith("@zenko wikipedia"):
        # toma lo que sigue a 'define' o 'wikipedia'
        if "define" in m:
            termino = raw_msg.split("define",1)[1].strip()
        else:
            termino = raw_msg.split("wikipedia",1)[1].strip()
        if not termino:
            return jsonify({"reply": "Indica el término: @zenko define <término>"})
        return jsonify({"reply": wiki_summary(termino)})

    # SNIPPETS
    if m.startswith("@zenko snippet"):
        key = raw_msg.replace("@zenko snippet", "").strip().lower()
        # buscar substring en keys
        for k in LSL_SNIPPETS:
            if k in key:
                agregar_historial(user, f"Snippet generado: {k}")
                return jsonify({"reply": LSL_SNIPPETS[k]})
        return jsonify({"reply": "Snippets disponibles: " + ", ".join(LSL_SNIPPETS.keys())})

    # HISTORIAL Y SCRIPTS
    if m.startswith("@zenko historial") or m.startswith("@zenko que hicimos"):
        return jsonify({"reply": historial_resumen(user)})

    if m.startswith("@zenko listar scripts") or m.startswith("@zenko lista scripts"):
        keys = list(sessions[user]["scripts"].keys())
        if not keys:
            return jsonify({"reply": "No hay scripts guardados."})
        return jsonify({"reply": "Scripts:\n" + "\n".join(keys)})

    if m.startswith("@zenko ver script"):
        # formato: @zenko ver script <id>
        parts = raw_msg.split()
        if len(parts) >= 4:
            sid = parts[-1]
            script = ver_script(user, sid)
            if script:
                return jsonify({"reply": script})
            return jsonify({"reply": "ID de script no encontrado."})
        return jsonify({"reply": "Usa: @zenko ver script <id>"})

    if m.startswith("@zenko guarda script") or m.startswith("@zenko guarda"):
        # guarda el texto completo enviado (raw_msg) o el campo 'script'
        script_text = data.get("script") or raw_msg.split("guarda",1)[1].strip()
        if not script_text:
            return jsonify({"reply": "Proporciona el script a guardar."})
        sid = guardar_script(user, script_text)
        return jsonify({"reply": f"Script guardado con ID {sid}"})

    # COMPARADOR: permite usar '---' en el cuerpo para separar A y B
    if "compara" in m and "---" in raw_msg:
        try:
            parts = raw_msg.split("---")
            a = parts[0].split("compara",1)[1].strip()
            b = parts[1].strip()
            diff = comparar_scripts_text(a, b)
            agregar_historial(user, "Comparador ejecutado")
            return jsonify({"reply": diff or "No hay diferencias textuales."})
        except Exception:
            return jsonify({"reply": "No pude comparar. Asegúrate de usar '---' para separar scripts."})

    # ------------------------------------------------
    # DETECCION DE INTENCION / CONTEXTO PERSISTENTE
    # ------------------------------------------------
    intent = detectar_intencion(msg, user)
    if intent == "continuacion":
        ctx = get_contexto(user)
        if not ctx or not ctx.get("data"):
            return jsonify({"reply": "No hay contexto previo para continuar."})
        # Reusar el contexto según su tipo
        tipo = ctx.get("tipo")
        data_ctx = ctx.get("data")
        if tipo == "script":
            # volver a procesar el script (reescritura/analisis)
            # guardamos de nuevo y delegamos al bloque LSL (simular pegar)
            sid = guardar_script(user, data_ctx)
            agregar_historial(user, "Continuacion: re-procesando script", sid)
            # construir prompt similar al modo LSL:
            prompt = PROMPTS[sessions[user]["lang"]] + "\n[LSL - CONTINUACION]\nDebug siempre activo.\nScript ID: " + sid + "\nUsuario:\n" + data_ctx + "\nZenko:"
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={"model": MODEL, "messages":[{"role":"system","content":prompt},{"role":"user","content":data_ctx}]},
                    timeout=15
                )
                reply = r.json()["choices"][0]["message"]["content"]
                return jsonify({"reply": clean_text(reply) + f"\n\n[Script guardado con ID {sid}]"})
            except Exception:
                return jsonify({"reply": "Error al continuar con el contexto."})
        elif tipo == "resumen":
            # generar resumen
            agregar_historial(user, "Continuacion: resumen")
            prompt = PROMPTS[sessions[user]["lang"]] + "\nResumen requerido:\n" + data_ctx + "\nZenko:"
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={"model": MODEL, "messages":[{"role":"system","content":prompt},{"role":"user","content":data_ctx}]},
                    timeout=15
                )
                reply = r.json()["choices"][0]["message"]["content"]
                return jsonify({"reply": clean_text(reply)})
            except:
                return jsonify({"reply": "Error generando resumen."})
        else:
            return jsonify({"reply": "Contexto no manejable para continuar."})

    # Si detectó un script nuevo (pegado)
    if detectar_intencion(msg, user) == "script":
        # guardar contexto
        set_contexto(user, "script", raw_msg)
        sessions[user]["lsl_mode"] = True  # asegurar modo LSL
        sid = guardar_script(user, raw_msg)
        agregar_historial(user, "Script detectado y guardado", sid)

        # decidir sub-modo LSL según riesgos
        if script_incompleto(raw_msg):
            modo = "[LSL] DETECCION DE SCRIPT INCOMPLETO"
        elif contiene_riesgos_lsl(raw_msg):
            modo = "[LSL] ANALISIS DE PERFORMANCE"
        elif "laggy" in m or "optimiza" in m:
            modo = "[LSL] OPTIMIZACION REGION LAGGY"
        else:
            modo = "[LSL] REESCRITURA AUTOMATICA"

        prompt = PROMPTS[sessions[user]["lang"]] + f"""
{modo}
Debug siempre activo.
Script ID: {sid}
Usuario:
{raw_msg}
Zenko:
"""
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model": MODEL, "messages":[{"role":"system","content":prompt},{"role":"user","content":raw_msg}]},
                timeout=20
            )
            reply = r.json()["choices"][0]["message"]["content"]
            # respuesta final con nota de guardado
            agregar_historial(user, "Procesado script", sid)
            return jsonify({"reply": clean_text(reply) + f"\n\n[Script guardado con ID {sid}]"})
        except Exception:
            return jsonify({"reply": "No pude procesar el script en este momento."})

    # Texto largo -> proponer resumen
    if intent == "texto_largo":
        set_contexto(user, "resumen", raw_msg)
        agregar_historial(user, "Texto largo detectado")
        return jsonify({"reply": "Detecté texto largo. ¿Deseas que haga un resumen? Responde 'continuar' para proceder."})

    # Diagnóstico simple por palabras
    if intent == "diagnostico":
        set_contexto(user, "diagnostico", raw_msg)
        agregar_historial(user, "Solicitud de diagnostico")
        # heurístico básico
        riesgos = contiene_riesgos_lsl(raw_msg)
        if riesgos:
            return jsonify({"reply": "Posibles problemas detectados:\n- " + "\n- ".join(riesgos)})
        return jsonify({"reply": "No detecté problemas LSL obvios. Describe el comportamiento para afinar el diagnóstico."})

    # MENSAJE NORMAL: enviar al modelo con prompt directo y sin florituras
    system_prompt = PROMPTS[sessions[user]["lang"]]
    payload = {
        "model": MODEL,
        "messages": [
            {"role":"system","content": system_prompt},
            {"role":"user","content": raw_msg}
        ]
    }
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            json=payload,
            timeout=15
        )
        reply = resp.json()["choices"][0]["message"]["content"]
    except Exception:
        reply = "No pude responder en este momento."

    agregar_historial(user, "Consulta normal")
    return jsonify({"reply": clean_text(reply)})

@app.route("/")
def home():
    return "Zenko Online"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



