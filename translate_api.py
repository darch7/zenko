from flask import Blueprint, request, jsonify, Response
import requests
import os
from datetime import datetime
from langdetect import detect
import re
import time

traductor_bp = Blueprint('traductor', __name__, url_prefix='/translator')

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")

LLAMA_MODEL = "llama-3.1-8b-instant"

conversaciones = {}

# -------------------------
# ANTI-SPAM
# -------------------------

ultimo_mensaje = {}
mensajes_recientes = {}

def puede_enviar(remitente):
    ahora = time.time()
    if remitente in ultimo_mensaje:
        if ahora - ultimo_mensaje[remitente] < 2:
            return False
    ultimo_mensaje[remitente] = ahora
    return True

def es_repetido(remitente, mensaje):
    if remitente not in mensajes_recientes:
        mensajes_recientes[remitente] = []

    if mensaje in mensajes_recientes[remitente]:
        return True

    mensajes_recientes[remitente].append(mensaje)

    if len(mensajes_recientes[remitente]) > 5:
        mensajes_recientes[remitente].pop(0)

    return False

# -------------------------
# LIMPIEZA
# -------------------------

def limpiar_texto(texto):
    texto = re.sub(r'[\U00010000-\U0010ffff]', '', texto)

    texto = ''.join(
        c for c in texto
        if c.isalnum() or c.isspace() or c in "*.,!?-_'\":"
    )

    texto = re.sub(r'\s+', ' ', texto)
    return texto.strip()

# -------------------------
# NOMBRE
# -------------------------

def separar_nombre_mensaje(texto):
    match = re.match(r'^([^:]{2,40}):\s*(.+)$', texto)

    if match:
        nombre = match.group(1).strip()
        if len(nombre.split()) <= 4:
            return nombre, match.group(2).strip()

    return None, texto

# -------------------------
# UTILIDADES
# -------------------------

def detectar_idioma(texto):
    try:
        return detect(texto)
    except:
        return "es"

def es_texto_simple(texto):
    palabras = texto.split()
    return len(palabras) <= 4 or len(texto) < 35

# -------------------------
# DEEPL
# -------------------------

def traducir_deepl(texto, destino):
    if not DEEPL_API_KEY:
        return ""

    try:
        response = requests.post(
            "https://api-free.deepl.com/v2/translate",
            data={
                "auth_key": DEEPL_API_KEY,
                "text": texto,
                "target_lang": destino.upper()
            },
            timeout=5
        )

        if response.status_code == 200:
            return response.json()["translations"][0]["text"]

    except Exception as e:
        print("DeepL error:", e)

    return ""

# -------------------------
# IA (ZENKO)
# -------------------------

def traducir_ia(texto, destino, origen):
    if not GROQ_API_KEY:
        return ""

    prompt = f"""Traduce el siguiente texto de {origen} a {destino}.
Devuelve SOLO la traducción.
No agregues nada.

Texto:
{texto}
"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": LLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 300
            },
            timeout=8
        )

        if response.status_code == 200:
            texto = response.json()["choices"][0]["message"]["content"].strip()

            if len(texto.split()) > len(texto.split()) * 1.5:
                return ""

            return texto

    except Exception as e:
        print("IA error:", e)

    return ""

# -------------------------
# ENDPOINT
# -------------------------

@traductor_bp.route("/send", methods=["POST"])
def send_message():
    data = request.json

    remitente = data.get("remitente")
    destinatario = data.get("destinatario")
    mensaje = data.get("mensaje")

    idioma_receptor = data.get("idioma_receptor", "es")

    if not all([remitente, destinatario, mensaje]):
        return "", 200

    # ANTI-SPAM
    if not puede_enviar(remitente):
        return "", 200

    if es_repetido(remitente, mensaje):
        return "", 200

    # separar nombre
    nombre, mensaje = separar_nombre_mensaje(mensaje)

    # limpiar
    mensaje = limpiar_texto(mensaje)

    if not mensaje:
        return "", 200

    # detectar idioma
    idioma_origen = detectar_idioma(mensaje)

    if idioma_origen == idioma_receptor:
        return "", 200

    # -------------------------
    # HÍBRIDO
    # -------------------------

    if es_texto_simple(mensaje):
        traducido = traducir_deepl(mensaje, idioma_receptor)
    else:
        traducido = traducir_ia(mensaje, idioma_receptor, idioma_origen)

    if not traducido:
        traducido = mensaje

    # reconstruir
    if nombre:
        traducido = f"{nombre}: {traducido}"

    # guardar
    chat_id = "_".join(sorted([remitente, destinatario]))

    if chat_id not in conversaciones:
        conversaciones[chat_id] = []

    conversaciones[chat_id].append({
        "traducido": traducido,
        "destinatario": destinatario,
        "leido": False
    })

    print(f"{mensaje} => {traducido}")

    return Response(traducido, mimetype='text/plain')

# -------------------------
# POLL
# -------------------------

@traductor_bp.route("/poll/<avatar>", methods=["GET"])
def poll_messages(avatar):
    nuevos = []

    for chat in conversaciones.values():
        for msg in chat:
            if msg["destinatario"] == avatar and not msg["leido"]:
                msg["leido"] = True
                nuevos.append(msg["traducido"])

    return jsonify(nuevos)

# -------------------------
# HEALTH
# -------------------------

@traductor_bp.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "deepl": bool(DEEPL_API_KEY),
        "groq": bool(GROQ_API_KEY)
    })
