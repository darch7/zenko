from flask import Blueprint, request, jsonify
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

def traducir(texto, idioma_destino, idioma_origen=None):
    """Traduce texto usando Groq/Llama"""
    if not GROQ_API_KEY:
        return "<--- --- --->"
    
    dest_name = IDIOMAS.get(idioma_destino, idioma_destino)
    
    if idioma_origen:
        origen_name = IDIOMAS.get(idioma_origen, idioma_origen)
        prompt = f"Traduce este texto de {origen_name} a {dest_name}. SOLO la traducción, nada más:\n\n{texto}"
    else:
        prompt = f"Traduce este texto a {dest_name}. SOLO la traducción, nada más:\n\n{texto}"
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": LLAMA_MODEL,
            "messages": [
                {"role": "system", "content": "Eres un traductor. Respondes SOLO con la traducción, sin explicaciones."},
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
            traduccion = result['choices'][0]['message']['content'].strip()
            
            # Verificar si la traducción es válida
            if traduccion and len(traduccion) > 0 and "I couldn't find" not in traduccion and "couldn't find" not in traduccion.lower():
                return traduccion
            else:
                return "<--- --- --->"
        else:
            return "<--- --- --->"
    except Exception as e:
        return "<--- --- --->"

def detectar_idioma(texto):
    """Detecta el idioma del texto"""
    prompt = f"Detecta el idioma de este texto. Responde SOLO con el código ISO (es, en, fr, it, etc):\n\n{texto}"
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": LLAMA_MODEL,
            "messages": [
                {"role": "system", "content": "Eres un detector de idiomas. Respondes SOLO con el código ISO."},
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
    idioma_manual = data.get("idioma", "en")
    
    if not all([remitente, destinatario, mensaje]):
        return jsonify({"mensaje_traducido": "<--- --- --->"}), 200
    
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
    
    # Guardar mensaje (siempre, incluso si es <--- --- --->)
    timestamp = datetime.now().isoformat()
    
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
    
    return jsonify({
        "status": "ok",
        "mensaje_id": mensaje_data["id"],
        "mensaje_traducido": mensaje_traducido
    })

@traductor_bp.route("/poll/<avatar>", methods=["GET"])
def poll_messages(avatar):
    """El HUD pregunta si hay mensajes nuevos"""
    mensajes_nuevos = []
    
    for chat_id, conversacion in conversaciones.items():
        if avatar in chat_id:
            for msg in conversacion:
                if msg["destinatario"] == avatar and not msg["leido"]:
                    msg["leido"] = True
                    mensajes_nuevos.append([
                        msg["id"],
                        msg["remitente"],
                        msg["destinatario"],
                        msg["traducido"],
                        msg["timestamp"]
                    ])
    
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
