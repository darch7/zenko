from flask import Blueprint, request, jsonify, Response
import requests
import os
import re
from datetime import datetime

traductor_bp = Blueprint('traductor', __name__, url_prefix='/translator')

# CONFIG
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLAMA_MODEL = "llama-3.1-8b-instant"

conversaciones = {}

IDIOMAS = {
    "es": "español", "en": "inglés", "fr": "francés", "it": "italiano",
    "de": "alemán", "pt": "portugués", "ja": "japonés", "zh": "chino",
    "ru": "ruso", "nl": "holandés", "pl": "polaco", "ar": "árabe"
}

# ------------------------
# LIMPIEZA DE TEXTO
# ------------------------
def limpiar_texto(texto):
    limpio = ""
    for c in texto:
        if c.isalnum() or c in " :,.!?@-áéíóúÁÉÍÓÚñÑ[](){}<>":
            limpio += c
        else:
            limpio += " "
    
    limpio = re.sub(r'(.)\1{3,}', r'\1', limpio)
    return limpio.strip()

# ------------------------
# SEPARAR NOMBRE
# ------------------------
def separar_nombre(texto):
    if ":" in texto:
        partes = texto.split(":", 1)
        nombre = partes[0].strip()
        mensaje = partes[1].strip()
        return nombre, mensaje
    return None, texto

# ------------------------
# ANTI SPAM
# ------------------------
def es_spam(texto):
    if len(texto) < 3:
        return True
    
    if len(set(texto)) <= 2:
        return True
    
    if texto.count(" ") < 1 and len(texto) > 12:
        return True
    
    return False

# ------------------------
# VALIDACIÓN
# ------------------------
def tiene_sentido(texto):
    if es_spam(texto):
        return False
    
    letras = sum(c.isalpha() for c in texto)
    if letras == 0:
        return False
    
    if letras / len(texto) < 0.4:
        return False
    
    return True

# ------------------------
# TRADUCCIÓN IA (MEJORADA)
# ------------------------
def traducir(texto, idioma_destino, idioma_origen=None):
    if not GROQ_API_KEY:
        return ""
    
    if not tiene_sentido(texto):
        return ""
    
    dest_name = IDIOMAS.get(idioma_destino, idioma_destino)
    origen_name = IDIOMAS.get(idioma_origen, "desconocido") if idioma_origen else "desconocido"

    prompt_sistema = """Eres un traductor profesional avanzado especializado en lenguaje informal y de chat.

Tu tarea es traducir el mensaje con precisión, pero entendiendo el significado real, no solo las palabras.

REGLAS IMPORTANTES:

- Interpreta el contexto antes de traducir.
- Corrige mentalmente errores comunes del usuario (faltas de tildes, escritura rápida, etc).
  Ejemplos:
  - "papa" puede ser "papá" o "papa (comida)" según contexto
  - "bebe" puede ser "bebé" o "bebe (verbo)"
  - "mama" puede ser "mamá" o "mama (anatómico)"
- Asume lenguaje informal tipo chat (Second Life, juegos, etc).
- NO traduzcas palabra por palabra si eso rompe el sentido.
- Mantén el significado original aunque tengas que reformular.
- Mantén nombres propios intactos.
- NO traduzcas símbolos ni emojis.
- NO agregues explicaciones.
- Si el texto no tiene sentido, responde vacío.

Devuelve SOLO la traducción final limpia y natural."""

    prompt_usuario = f"""Texto original:
{texto}

Idioma origen: {origen_name}
Traducir a: {dest_name}

Traducción:"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": LLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_usuario}
                ],
                "temperature": 0.3,
                "max_tokens": 300
            },
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            traduccion = result['choices'][0]['message']['content'].strip()

            if traduccion.lower() == texto.lower():
                return ""

            return traduccion

    except Exception as e:
        print("Error:", e)

    return ""

# ------------------------
# DETECTAR IDIOMA
# ------------------------
def detectar_idioma(texto):
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": LLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": "Responde SOLO con código ISO (es,en,fr,it,etc)."},
                    {"role": "user", "content": texto}
                ],
                "temperature": 0.0,
                "max_tokens": 5
            },
            timeout=5
        )

        if response.status_code == 200:
            lang = response.json()['choices'][0]['message']['content'].strip().lower()
            if lang in IDIOMAS:
                return lang

    except:
        pass

    return "es"

# ------------------------
# ENDPOINT SEND
# ------------------------
@traductor_bp.route("/send", methods=["POST"])
def send_message():
    data = request.json

    remitente = data.get("remitente")
    destinatario = data.get("destinatario")
    mensaje_original = data.get("mensaje")

    if not all([remitente, destinatario, mensaje_original]):
        return "", 200

    nombre, mensaje = separar_nombre(mensaje_original)

    mensaje_limpio = limpiar_texto(mensaje)

    if not mensaje_limpio:
        return "", 200

    idioma_origen = detectar_idioma(mensaje_limpio)
    idioma_destino = data.get("idioma_receptor", "en")

    if idioma_origen == idioma_destino:
        return "", 200

    traduccion = traducir(mensaje_limpio, idioma_destino, idioma_origen)

    if not traduccion:
        return "", 200

    if nombre:
        resultado = f"{nombre}: {traduccion}"
    else:
        resultado = traduccion

    # Guardado
    chat_id = "_".join(sorted([remitente, destinatario]))

    if chat_id not in conversaciones:
        conversaciones[chat_id] = []

    conversaciones[chat_id].append({
        "remitente": remitente,
        "destinatario": destinatario,
        "traducido": resultado,
        "leido": False
    })

    return Response(resultado, mimetype='text/plain')

# ------------------------
# POLL
# ------------------------
@traductor_bp.route("/poll/<avatar>", methods=["GET"])
def poll_messages(avatar):
    mensajes = []

    for chat_id in conversaciones:
        if avatar in chat_id:
            for msg in conversaciones[chat_id]:
                if msg["destinatario"] == avatar and not msg["leido"]:
                    msg["leido"] = True
                    mensajes.append(msg["traducido"])

    return jsonify(mensajes)

# ------------------------
# HEALTH
# ------------------------
@traductor_bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "groq": bool(GROQ_API_KEY),
        "chats": len(conversaciones)
    })
