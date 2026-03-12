from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

# Configuración
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLAMA_MODEL = "llama-3.1-8b-instant"
PORT = int(os.environ.get("PORT", 5001))

# Almacenamiento temporal de conversaciones
conversaciones = {}

# Idiomas soportados
IDIOMAS = {
    "es": "español",
    "en": "inglés", 
    "fr": "francés",
    "it": "italiano",
    "de": "alemán",
    "pt": "portugués",
    "ja": "japonés",
    "zh": "chino",
    "ru": "ruso"
}

def traducir(texto, idioma_destino, idioma_origen=None):
    """Traduce texto usando Groq/Llama"""
    
    if not GROQ_API_KEY:
        return texto
    
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
            if traduccion.startswith('"') and traduccion.endswith('"'):
                traduccion = traduccion[1:-1]
            return traduccion
        return texto
    except Exception as e:
        print(f"Error en traducción: {e}")
        return texto

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

@app.route("/send", methods=["POST"])
def send_message():
    """Recibe mensaje del HUD y lo traduce"""
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
        "original": mensaje,
        "traducido": mensaje_traducido,
        "idioma_origen": idioma_origen,
        "idioma_destino": idioma_destino,
        "timestamp": timestamp,
        "leido": False
    }
    
    conversaciones[chat_id].append(mensaje_data)
    
    return jsonify({
        "status": "ok",
        "mensaje_id": mensaje_data["id"],
        "mensaje_traducido": mensaje_traducido
    })

@app.route("/poll/<avatar>", methods=["GET"])
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

@app.route("/responder", methods=["POST"])
def responder():
    """Endpoint para responder a un mensaje"""
    data = request.json
    
    remitente = data.get("remitente")
    destinatario = data.get("destinatario")
    respuesta = data.get("respuesta")
    chat_id = data.get("chat_id")
    
    if not all([remitente, destinatario, respuesta, chat_id]):
        return jsonify({"error": "Faltan datos"}), 400
    
    idioma_respuesta = detectar_idioma(respuesta)
    
    conversacion = conversaciones.get(chat_id, [])
    ultimo_mensaje = None
    
    for msg in reversed(conversacion):
        if msg["remitente"] == destinatario:
            ultimo_mensaje = msg
            break
    
    if ultimo_mensaje:
        idioma_destino = ultimo_mensaje["idioma_origen"]
    else:
        idioma_destino = "es"
    
    respuesta_traducida = traducir(respuesta, idioma_destino, idioma_respuesta)
    
    timestamp = datetime.now().isoformat()
    
    mensaje_data = {
        "id": len(conversacion),
        "remitente": remitente,
        "destinatario": destinatario,
        "original": respuesta,
        "traducido": respuesta_traducida,
        "idioma_origen": idioma_respuesta,
        "idioma_destino": idioma_destino,
        "timestamp": timestamp,
        "leido": False
    }
    
    conversaciones[chat_id].append(mensaje_data)
    
    return jsonify({
        "status": "ok",
        "mensaje_id": mensaje_data["id"],
        "respuesta_traducida": respuesta_traducida
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "conversaciones": len(conversaciones),
        "idiomas": list(IDIOMAS.keys())
    })

@app.route("/", methods=["GET"])
def home():
    return "✅ Traductor Service Online - Usa /send, /poll/[avatar], /responder"

if __name__ == "__main__":
    print(f"🚀 Traductor service iniciado en puerto {PORT}")
    print(f"📚 Idiomas soportados: {', '.join(IDIOMAS.keys())}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
