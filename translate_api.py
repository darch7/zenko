from flask import Blueprint, request, jsonify, Response
import requests
import os
from datetime import datetime

traductor_bp = Blueprint('traductor', __name__, url_prefix='/translator')

# Configuración
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLAMA_MODEL = "llama-3.1-8b-instant"

# Almacenamiento temporal de conversaciones
conversaciones = {}

IDIOMAS = {
    "es": "español", "en": "inglés", "fr": "francés", "it": "italiano",
    "de": "alemán", "pt": "portugués", "ja": "japonés", "zh": "chino", "ru": "ruso"
}

def tiene_sentido(texto):
    """Verifica si el texto tiene sentido para traducir"""
    if len(texto) < 3:
        return False
    
    if len(set(texto)) < 3 and len(texto) > 4:
        return False
    
    repeticiones = 1
    max_rep = 1
    for i in range(1, len(texto)):
        if texto[i] == texto[i-1]:
            repeticiones += 1
            max_rep = max(max_rep, repeticiones)
        else:
            repeticiones = 1
    if max_rep > 4:
        return False
    
    letras = sum(c.isalpha() for c in texto)
    if letras == 0:
        return False
    
    if letras / len(texto) < 0.4:
        return False
    
    return True

def traducir(texto, idioma_destino, idioma_origen=None):
    """Traduce texto usando Groq/Llama - CON PROMPT HÍBRIDO"""
    if not GROQ_API_KEY:
        return ""
    
    if not tiene_sentido(texto):
        return ""
    
    dest_name = IDIOMAS.get(idioma_destino, idioma_destino)
    origen_name = IDIOMAS.get(idioma_origen, "desconocido") if idioma_origen else "desconocido"
    
    # PROMPT HÍBRIDO - Combina simplicidad con mejoras
    prompt_sistema = """Eres un traductor profesional. Traduce SOLO el texto, sin explicaciones.

REGLAS IMPORTANTES:
1. Reconoce abreviaturas comunes:
   - Inglés: brb (ya vuelvo), afk (ausente), bc/bcos (porque), ofc (claro), idk (no sé), tbh (sinceramente)
   - Español: xq/pq (porque), tkm/tqm (te quiero), tb/tmb (también), d2 (dedos), vdd (verdad)
   - Risas: lol/lmao → jaja/jeje

2. Traduce modismos por su significado real:
   - "it's raining cats and dogs" → "llueve a cántaros"
   - "break a leg" → "mucha suerte"

3. Mantén el mismo tono (formal/informal) del original

4. Si el texto no tiene sentido, responde con cadena vacía

Traduce de forma natural, como lo diría un hablante nativo."""
    
    if idioma_origen:
        prompt_usuario = f"Texto en {origen_name}:\n{texto}\n\nTraducción natural a {dest_name}:"
    else:
        prompt_usuario = f"Texto:\n{texto}\n\nTraducción natural a {dest_name}:"
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": LLAMA_MODEL,
            "messages": [
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            "temperature": 0.2,  # Mantenemos 0.2 que funcionaba
            "max_tokens": 500
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            traduccion = result['choices'][0]['message']['content'].strip()
            
            if traduccion and len(traduccion) > 0:
                # Lista de frases de error a detectar
                errores = [
                    "i couldn't find", "sorry", "i don't know", 
                    "cannot translate", "can't translate", "unable to translate",
                    "no puedo traducir", "no sé", "la traducción es"
                ]
                if any(error in traduccion.lower() for error in errores):
                    return ""
                
                if len(traduccion) > len(texto) * 4:
                    return ""
                
                return traduccion
            else:
                return ""
        else:
            return ""
    except Exception as e:
        print(f"Error en traducción: {str(e)}")
        return ""

def detectar_idioma(texto):
    """Detecta el idioma del texto"""
    if not tiene_sentido(texto):
        return "es"
    
    prompt = f"Detecta el idioma de este texto. Responde SOLO con el código ISO: {texto}"
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": LLAMA_MODEL,
            "messages": [
                {"role": "system", "content": "Eres un detector de idiomas. Responde SOLO con el código ISO."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 10
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=5
        )
        
        if response.status_code == 200:
            result = response.json()
            lang = result['choices'][0]['message']['content'].strip().lower()
            if lang in IDIOMAS:
                return lang
        return "es"
    except:
        return "es"

@traductor_bp.route("/send", methods=["POST"])
def send_message():
    """Recibe mensaje del HUD y lo traduce"""
    data = request.json
    
    remitente = data.get("remitente")
    destinatario = data.get("destinatario")
    mensaje = data.get("mensaje")
    modo = data.get("modo", "auto")
    
    idioma_emisor = data.get("idioma_emisor", "auto")
    idioma_receptor = data.get("idioma_receptor", "es")
    idioma_manual = data.get("idioma", "en")
    
    if not all([remitente, destinatario, mensaje]):
        return "", 200
    
    # DETECTAR IDIOMA ORIGEN
    if modo == "auto" or idioma_emisor == "auto":
        idioma_origen = detectar_idioma(mensaje)
        print(f"Idioma detectado: {idioma_origen}")
    else:
        idioma_origen = idioma_emisor
        print(f"Idioma origen: {idioma_origen}")
    
    # DETERMINAR IDIOMA DESTINO
    if modo == "auto":
        idioma_destino = idioma_receptor if idioma_receptor != "auto" else idioma_manual
        print(f"Destino: {idioma_destino}")
    else:
        idioma_destino = idioma_receptor
        print(f"Destino: {idioma_destino}")
    
    # DECISIÓN DE TRADUCCIÓN - LÓGICA QUE FUNCIONA
    if modo == "auto":
        print(f"Traduciendo de {idioma_origen} a {idioma_destino}")
        mensaje_traducido = traducir(mensaje, idioma_destino, idioma_origen)
        if not mensaje_traducido:
            mensaje_traducido = ""
    else:
        if idioma_origen != idioma_destino:
            print(f"Traduciendo de {idioma_origen} a {idioma_destino}")
            mensaje_traducido = traducir(mensaje, idioma_destino, idioma_origen)
        else:
            print(f"Mismo idioma, no se traduce")
            mensaje_traducido = ""
    
    # Guardar en conversaciones
    timestamp = datetime.now().isoformat()
    
    if remitente < destinatario:
        chat_id = f"{remitente}_{destinatario}"
    else:
        chat_id = f"{destinatario}_{remitente}"
    
    if chat_id not in conversaciones:
        conversaciones[chat_id] = []
    
    mensaje_data = {
        "id": len(conversaciones[chat_id]),
        "remitente": remitente,
        "destinatario": destinatario,
        "original": mensaje,
        "traducido": mensaje_traducido,
        "timestamp": timestamp,
        "leido": False
    }
    
    conversaciones[chat_id].append(mensaje_data)
    
    return Response(mensaje_traducido, mimetype='text/plain; charset=utf-8')

@traductor_bp.route("/poll/<avatar>", methods=["GET"])
def poll_messages(avatar):
    mensajes_nuevos = []
    for chat_id, conversacion in conversaciones.items():
        if avatar in chat_id:
            for msg in conversacion:
                if msg["destinatario"] == avatar and not msg["leido"]:
                    msg["leido"] = True
                    if msg["traducido"]:
                        mensajes_nuevos.append(msg["traducido"])
    return jsonify(mensajes_nuevos)

@traductor_bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "service": "translator",
        "conversaciones": len(conversaciones),
        "groq_configured": bool(GROQ_API_KEY)
    })

@traductor_bp.route("/", methods=["GET"])
def home():
    return "✅ Traductor Service Online - Usa /send, /poll/[avatar], /health"
