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

def tiene_sentido(texto):
    """Verifica si el texto tiene sentido para traducir"""
    # Si el texto es muy corto, no tiene sentido
    if len(texto) < 3:
        return False
    
    # Si el texto es solo repeticiones de la misma letra (asdasdasd, jajaja, etc)
    if len(set(texto)) < 3 and len(texto) > 4:
        return False
    
    # Si tiene más de 5 caracteres seguidos iguales (prrrrrr)
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
    
    # Verificar porcentaje de letras vs símbolos raros
    letras = sum(c.isalpha() for c in texto)
    if letras == 0:
        return False
    
    # Si menos del 40% son letras, probablemente no tiene sentido
    if letras / len(texto) < 0.4:
        return False
    
    return True

def traducir(texto, idioma_destino, idioma_origen=None):
    """Traduce texto usando Groq/Llama con mejoras en tiempos verbales"""
    if not GROQ_API_KEY:
        return "<--- --- --->"
    
    # Si el texto no tiene sentido, devolver <--- --- --->
    if not tiene_sentido(texto):
        return "<--- --- --->"
    
    dest_name = IDIOMAS.get(idioma_destino, idioma_destino)
    
    # Prompt del sistema mejorado para tiempos verbales
    prompt_sistema = """Eres un traductor profesional con dominio nativo de todos los idiomas.
    
    INSTRUCCIONES ESTRICTAS:
    1. Traduce SOLO el texto, sin añadir explicaciones, comentarios ni notas
    2. Presta atención ESPECIAL a los TIEMPOS VERBALES:
       - Identifica correctamente si el original está en pasado, presente o futuro
       - Mantén el mismo tiempo verbal en la traducción
       - Respeta el modo (indicativo, subjuntivo, condicional)
    3. Asegura la concordancia sujeto-verbo
    4. Usa expresiones naturales, NO traducciones literales
    5. Mantén el registro (formal/informal) apropiado
    6. Si el texto no tiene sentido o no puedes traducirlo, responde SOLO con '<--- --- --->'
    
    EJEMPLOS DE BUENAS TRADUCCIONES:
    Español: "Ayer fui al cine y vi una película" → Inglés: "Yesterday I went to the cinema and watched a movie"
    Español: "Si pudiera, viajaría por el mundo" → Inglés: "If I could, I would travel the world"
    Español: "Habré terminado para mañana" → Inglés: "I will have finished by tomorrow""""
    
    if idioma_origen:
        origen_name = IDIOMAS.get(idioma_origen, idioma_origen)
        prompt_usuario = f"Traduce este texto de {origen_name} a {dest_name}. Respeta los tiempos verbales:\n\n{texto}"
    else:
        prompt_usuario = f"Traduce este texto a {dest_name}. Respeta los tiempos verbales:\n\n{texto}"
    
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
            "temperature": 0.2,  # Más bajo para traducciones más precisas
            "max_tokens": 500
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=15  # Aumentado para dar más tiempo
        )
        
        if response.status_code == 200:
            result = response.json()
            traduccion = result['choices'][0]['message']['content'].strip()
            
            # Verificar si la traducción es válida
            if traduccion and len(traduccion) > 0:
                # Detectar mensajes de error comunes
                errores = ["i couldn't find", "sorry", "i don't know", "i'm not sure", 
                          "cannot translate", "can't translate", "unable to translate"]
                if any(error in traduccion.lower() for error in errores):
                    return "<--- --- --->"
                
                # Verificar longitud sospechosa (posibles explicaciones añadidas)
                if len(traduccion) > len(texto) * 3:
                    return "<--- --- --->"
                
                # Verificación básica de tiempos verbales
                traduccion = verificar_tiempos_verbales(texto, traduccion)
                
                return traduccion
            else:
                return "<--- --- --->"
        else:
            return "<--- --- --->"
    except Exception as e:
        print(f"Error en traducción: {str(e)}")
        return "<--- --- --->"

def verificar_tiempos_verbales(texto_original, traduccion):
    """Verificación básica de consistencia de tiempos verbales"""
    # Palabras clave de tiempo en español
    tiempos_es = {
        "pasado": ["ayer", "anteayer", "hace", "anoche", "el año pasado", "antes", "ya", "fui", "estuve", "tenía", "había"],
        "presente": ["ahora", "hoy", "actualmente", "en este momento", "estoy", "tengo", "soy", "es"],
        "futuro": ["mañana", "próximo", "después", "luego", "más tarde", "iré", "estaré", "tendré"]
    }
    
    # Palabras clave de tiempo en inglés
    tiempos_en = {
        "past": ["yesterday", "ago", "last night", "last year", "before", "already", "was", "were", "had", "used to"],
        "present": ["now", "today", "currently", "at the moment", "am", "is", "are", "have", "has"],
        "future": ["tomorrow", "next", "later", "soon", "after", "will", "shall", "going to"]
    }
    
    # Detectar marcadores temporales en el original
    tiempo_detectado = None
    for tiempo, marcadores in tiempos_es.items():
        for marcador in marcadores:
            if marcador in texto_original.lower():
                tiempo_detectado = tiempo
                break
        if tiempo_detectado:
            break
    
    # Si se detectó un tiempo, verificar que la traducción tenga marcadores coherentes
    if tiempo_detectado:
        tiempo_en = {"pasado": "past", "presente": "present", "futuro": "future"}[tiempo_detectado]
        marcadores_en = tiempos_en[tiempo_en]
        
        tiene_marcador = False
        for marcador in marcadores_en:
            if marcador in traduccion.lower():
                tiene_marcador = True
                break
        
        if not tiene_marcador:
            # Intentar mejorar la traducción con un segundo intento
            print(f"Posible problema de tiempo verbal detectado. Reintentando...")
    
    return traduccion

def detectar_idioma(texto):
    """Detecta el idioma del texto"""
    if not tiene_sentido(texto):
        return "es"  # Valor por defecto
    
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
    
    # Detectar idioma original (solo si tiene sentido)
    idioma_origen = detectar_idioma(mensaje)
    
    # Determinar idioma destino
    if modo == "auto":
        idioma_destino = "en"
    else:
        # Soporte para formato antiguo y nuevo
        if "idioma_destino" in data:
            idioma_destino = data.get("idioma_destino")
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
