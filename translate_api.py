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
    "de": "alemán", "pt": "portugués", "ja": "japonés", "zh": "chino", 
    "ru": "ruso", "nl": "holandés", "pl": "polaco", "ar": "árabe"
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
    origen_name = IDIOMAS.get(idioma_origen, "desconocido") if idioma_origen else "desconocido"
    
    # PROMPT MEJORADO para mejor precisión
    prompt_sistema = """Eres un traductor profesional. Traduce SOLO el texto, sin explicaciones ni comentarios adicionales.

REGLAS IMPORTANTES:
1. Traduce SOLAMENTE el texto, nada más
2. NO añadas frases como "la traducción es" o "en inglés sería"
3. NO respondas con preguntas o explicaciones
4. Reconoce abreviaturas comunes y tradúcelas apropiadamente
5. Mantén el mismo tono (formal/informal) del original
6. Si el texto no tiene sentido o no puedes traducirlo, responde con una cadena vacía

Traduce de forma natural, como lo diría un hablante nativo."""
    
    if idioma_origen:
        prompt_usuario = f"Texto en {origen_name}:\n{texto}\n\nTraduce SOLO este texto a {dest_name} (sin explicaciones):"
    else:
        prompt_usuario = f"Texto:\n{texto}\n\nTraduce SOLO este texto a {dest_name} (sin explicaciones):"
    
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
            "temperature": 0.1,  # Reducido para más precisión
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
                # Limpiar traducción de posibles frases añadidas
                frases_no_deseadas = [
                    "traducción:", "traduccion:", "en inglés:", "en español:",
                    "la traducción es", "the translation is", "i would translate it as",
                    "i'd translate it as", "meaning:", "significa:", "->"
                ]
                
                for frase in frases_no_deseadas:
                    if frase.lower() in traduccion.lower():
                        partes = traduccion.split(frase, 1)
                        if len(partes) > 1:
                            traduccion = partes[1].strip()
                
                # Verificar si la traducción es igual al original (mismo idioma)
                if traduccion.lower() == texto.lower():
                    return ""  # No publicar si es la misma frase
                
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
    
    prompt = f"Detecta el idioma de este texto. Responde SOLO con el código ISO de 2 letras: {texto}"
    
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": LLAMA_MODEL,
            "messages": [
                {"role": "system", "content": "Eres un detector de idiomas. Responde SOLO con el código ISO de 2 letras."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 5
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
            # Limpiar posibles puntos o espacios
            lang = lang.replace('.', '').strip()
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
        print(f"Idioma detectado: {idioma_origen} para mensaje: {mensaje}")
    else:
        idioma_origen = idioma_emisor
        print(f"Idioma origen manual: {idioma_origen}")
    
    # DETERMINAR IDIOMA DESTINO
    if modo == "auto":
        idioma_destino = idioma_receptor if idioma_receptor != "auto" else idioma_manual
        print(f"Destino auto: {idioma_destino}")
    else:
        idioma_destino = idioma_receptor
        print(f"Destino manual: {idioma_destino}")
    
    # LÓGICA MEJORADA DE TRADUCCIÓN
    mensaje_traducido = ""
    
    # Caso 1: Mensajes privados (para el dueño del HUD)
    if destinatario == "privado":
        if idioma_origen != idioma_destino:
            print(f"Traduciendo privado de {idioma_origen} a {idioma_destino}")
            mensaje_traducido = traducir(mensaje, idioma_destino, idioma_origen)
        else:
            print(f"Mismo idioma en privado, no se traduce: {idioma_origen} = {idioma_destino}")
            mensaje_traducido = ""  # No enviar nada si es mismo idioma
    
    # Caso 2: Mensajes públicos (lo que dice el dueño del HUD)
    elif destinatario == "publico":
        # SIEMPRE traducir a inglés para que todos entiendan
        print(f"Traduciendo público de {idioma_origen} a inglés")
        mensaje_traducido = traducir(mensaje, "en", idioma_origen)
        
        # Si la traducción falla o es vacía, intentar con el mensaje original
        if not mensaje_traducido:
            print(f"Traducción falló, usando mensaje original")
            mensaje_traducido = mensaje
    
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
    
    # Log para debugging
    print(f"RESPUESTA FINAL: '{mensaje_traducido}' para mensaje '{mensaje}'")
    
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
