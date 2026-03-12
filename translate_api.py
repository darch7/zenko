# ============================================
# traductor.py - Módulo independiente
# ============================================

from flask import Blueprint, request, jsonify
import requests
import os
from datetime import datetime

# Crear blueprint para el traductor
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

def traducir(texto, idioma_destino, idioma_origen=None):
    """Traduce texto usando Groq/Llama"""
    if not GROQ_API_KEY:
        return texto
    
    dest_name = IDIOMAS.get(idioma_destino, idioma_destino)
    
    if idioma_origen:
        origen_name = IDIOMAS.get(idioma_origen, idioma_origen)
        prompt = f"Traduce de {origen_name} a {dest_name}. SOLO la traducción:\n\n{texto}"
    else:
        prompt = f"Traduce a {dest_name}. SOLO la traducción:\n\n{texto}"
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": LLAMA_MODEL,
            "messages": [
                {"role": "system", "content": "Eres un traductor. Respondes SOLO con la traducción."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        return texto
    except:
        return texto

def detectar_idioma(texto):
    """Detecta el idioma del texto"""
    prompt = f"Detecta idioma. Responde SOLO código ISO:\n\n{texto}"
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": LLAMA_MODEL,
            "messages": [
                {"role": "system", "content": "Responde solo con código ISO."},
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
            return lang if lang in IDIOMAS else "es"
        return "es"
    except:
        return "es"

@traductor_bp.route("/send", methods=["POST"])
def send_message():
    """Endpoint para enviar mensajes traducidos"""
    data = request.json
    
    remitente = data.get("remitente")
    destinatario = data.get("destinatario")
    mensaje = data.get("mensaje")
    modo = data.get("modo", "auto")
    idioma_manual = data.get("idioma", "en")
    
    if not all([remitente, destinatario, mensaje]):
        return jsonify({"error": "Faltan datos"}), 400
    
    # Crear ID único para la conversación
    if remitente < destinatario:
        chat_id = f"{remitente}_{destinatario}"
    else:
        chat_id = f"{destinatario}_{remitente}"
    
    # Detectar idioma original
    idioma_origen = detectar_idioma(mensaje)
    
    # Determinar idioma destino
    if modo == "auto":
        idioma_destino = "en"
    else:
        idioma_destino = idioma_manual
    
    # Traducir mensaje
    mensaje_traducido = traducir(mensaje, idioma_destino, idioma_origen)
    
    # Guardar mensaje
    timestamp = datetime.now().isoformat()
    
    if chat_id not in conversaciones:
        conversaciones[chat_id] = []
    
    mensaje_data = {
        "id": len(conversaciones[chat_id]),
        "remitente": remitente,
        "destinatario": destinatario,
        "traducido": mensaje_traducido,
        "timestamp": timestamp,
        "leido": False
    }
    
    conversaciones[chat_id].append(mensaje_data)
    
    return jsonify({
        "status": "ok",
        "mensaje_traducido": mensaje_traducido
    })

@traductor_bp.route("/poll/<avatar>", methods=["GET"])
def poll_messages(avatar):
    """Endpoint para que el HUD pregunte por mensajes nuevos"""
    mensajes_nuevos = []
    
    for chat_id, conversacion in conversaciones.items():
        if avatar in chat_id:
            for msg in conversacion:
                if msg["destinatario"] == avatar and not msg["leido"]:
                    msg["leido"] = True
                    mensajes_nuevos.append([
                        msg["id"],
                        msg["remitente"],
                        msg["traducido"]
                    ])
    
    return jsonify(mensajes_nuevos)

@traductor_bp.route("/health", methods=["GET"])
def health():
    """Health check del traductor"""
    return jsonify({
        "status": "online",
        "service": "translator",
        "conversaciones": len(conversaciones)
    })

@traductor_bp.route("/", methods=["GET"])
def home():
    return "✅ Traductor Service - Usa /send y /poll/[avatar]"
