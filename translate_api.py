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
    """Traduce texto usando Groq/Llama"""
    if not GROQ_API_KEY:
        return ""
    
    if not tiene_sentido(texto):
        return ""
    
    dest_name = IDIOMAS.get(idioma_destino, idioma_destino)
    
    # Prompt mejorado
    prompt_sistema = "Eres un traductor profesional. Traduce SOLO el texto, sin explicaciones. Presta atención a los tiempos verbales. Si el texto no tiene sentido, responde con una cadena vacía."
    
    if idioma_origen:
        origen_name = IDIOMAS.get(idioma_origen, idioma_origen)
        prompt_usuario = f"Traduce este texto de {origen_name} a {dest_name}. Respeta los tiempos verbales: {texto}"
    else:
        prompt_usuario = f"Traduce este texto a {dest_name}. Respeta los tiempos verbales: {texto}"
    
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
            "temperature": 0.2,
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
                errores = ["i couldn't find", "sorry", "i don't know", "cannot translate", "can't translate"]
                if any(error in traduccion.lower() for error in errores):
                    return ""
                
                if len(traduccion) > len(texto) * 3:
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
    """Recibe mensaje del HUD y lo traduce - DEVUELVE SOLO TEXTO"""
    data = request.json
    
    remitente = data.get("remitente")
    destinatario = data.get("destinatario")
    mensaje = data.get("mensaje")
    modo = data.get("modo", "auto")
    
    # Nuevos campos para emisor/receptor
    idioma_emisor = data.get("idioma_emisor", "auto")
    idioma_receptor = data.get("idioma_receptor", "es")
    
    # Compatibilidad con formato antiguo
    idioma_manual = data.get("idioma", "en")
    
    if not all([remitente, destinatario, mensaje]):
        return "", 200  # Devolver vacío si faltan datos
    
    # DETERMINAR IDIOMA ORIGEN
    if modo == "auto" or idioma_emisor == "auto":
        # En modo auto, detectar automáticamente
        idioma_origen = detectar_idioma(mensaje)
        print(f"Idioma detectado automáticamente: {idioma_origen}")
    else:
        # En modo manual, usar el especificado
        idioma_origen = idioma_emisor
        print(f"Idioma origen especificado: {idioma_origen}")
    
    # DETERMINAR IDIOMA DESTINO
    if modo == "auto":
        # En modo auto, usar el receptor especificado
        idioma_destino = idioma_receptor if idioma_receptor != "auto" else idioma_manual
        print(f"Modo auto - Destino: {idioma_destino}")
    else:
        # En modo manual, usar el receptor especificado
        idioma_destino = idioma_receptor
        print(f"Modo manual - Destino: {idioma_destino}")
    
    # DECISIÓN DE TRADUCCIÓN - CORREGIDO
    if modo == "auto":
        # En modo auto, SIEMPRE intentamos traducir
        print(f"Modo auto - Intentando traducción de {idioma_origen} a {idioma_destino}")
        mensaje_traducido = traducir(mensaje, idioma_destino, idioma_origen)
        # Si la traducción falla, devolvemos el original
        if not mensaje_traducido:
            mensaje_traducido = mensaje
    else:
        # En modo manual, solo traducir si son diferentes
        if idioma_origen != idioma_destino:
            print(f"Modo manual - Traduciendo de {idioma_origen} a {idioma_destino}")
            mensaje_traducido = traducir(mensaje, idioma_destino, idioma_origen)
        else:
            print(f"Mismo idioma ({idioma_origen} = {idioma_destino}) - No se traduce")
            mensaje_traducido = mensaje
    
    # Guardar en conversaciones (opcional)
    timestamp = datetime.now().isoformat()
    
    # Crear ID único para la conversación
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
    
    # DEVOLVER SOLO EL TEXTO TRADUCIDO
    return Response(mensaje_traducido, mimetype='text/plain; charset=utf-8')

@traductor_bp.route("/poll/<avatar>", methods=["GET"])
def poll_messages(avatar):
    """El HUD pregunta si hay mensajes nuevos"""
    mensajes_nuevos = []
    
    for chat_id, conversacion in conversaciones.items():
        if avatar in chat_id:
            for msg in conversacion:
                if msg["destinatario"] == avatar and not msg["leido"]:
                    msg["leido"] = True
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
