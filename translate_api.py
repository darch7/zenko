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
    """Traduce texto usando Groq/Llama - CON PROMPT MEJORADO"""
    if not GROQ_API_KEY:
        return ""
    
    if not tiene_sentido(texto):
        return ""
    
    dest_name = IDIOMAS.get(idioma_destino, idioma_destino)
    origen_name = IDIOMAS.get(idioma_origen, "desconocido") if idioma_origen else "desconocido"
    
    # PROMPT ULTRA MEJORADO PARA TRADUCCIONES NATURALES
    prompt_sistema = f"""Eres un traductor profesional de nivel nativo con expertise en lenguaje cotidiano, urbano y formal.

TRADUCTOR EXPERTO - INSTRUCCIONES DETALLADAS:

1. **NATURALIDAD PRIMERO**: Traduce como lo diría un hablante nativo, NO palabra por palabra.
   - MAL: "How are you?" → "¿Cómo estás tú?" (traducción literal)
   - BIEN: "How are you?" → "¿Cómo estás?" (natural)

2. **REGISTRO ADECUADO**: Mantén el mismo nivel de formalidad del original.
   - Formal: "Could you please assist me?" → "¿Podría ayudarme por favor?"
   - Informal: "Can u help me?" → "¿Me ayudas?"
   - Muy informal: "Need a hand?" → "¿Necesitas ayuda?"

3. **ABREVIATURAS Y LENGUAJE URBANO**:
   - Inglés: brb (ya vuelvo), afk (desconectado), bc/bcos (porque), ofc (claro/por supuesto)
   - Español: xq/pq (porque), tkm/tqm (te quiero mucho), tb/tmb (también)
   - Risas: lol/lmao/rofl → jaja/jeje (según contexto)
   - Énfasis: omg (Dios mío), wtf (qué diablos), idk (no sé)

4. **MODISMOS Y EXPRESIONES**: Traduce el significado, no las palabras.
   - "It's raining cats and dogs" → "Está lloviendo a cántaros"
   - "Break a leg" → "Mucha mierda / Buena suerte"
   - "Estar en las nubes" → "To be daydreaming / To have your head in the clouds"

5. **TIEMPOS VERBALES**: Respeta escrupulosamente el tiempo verbal.
   - Pasado: "I went" → "Fui/iba" (según contexto)
   - Presente: "I go" → "Voy"
   - Futuro: "I will go" → "Iré/Voy a ir"
   - Condicional: "I would go" → "Iría"

6. **TONO EMOCIONAL**: Captura el sentimiento.
   - Emoción: "OMG I'm so excited!!!" → "¡Dios mío, estoy tan emocionada!"
   - Sarcasmo: "Oh, great..." → "Oh, genial..." (con el mismo tono)
   - Pregunta: "Really?" → "¿En serio?"

7. **CONTEXTO**: Usa el contexto para elegir la mejor traducción.
   - "I'm good" (estado de ánimo) → "Estoy bien"
   - "I'm good" (habilidad) → "Soy bueno"
   - "I'm good" (suficiente) → "Estoy bien así / No, gracias"

8. **ABREVIATURAS ESPECÍFICAS DE SL** (Second Life):
   - "tp" → "teletransportar"
   - "sim" → "simulador / región"
   - "lm" → "marcador / landmark"
   - "im" → "mensaje instantáneo"
   - "afk" → "fuera del teclado / ausente"
   - "brb" → "ya vuelvo"
   - "ty" → "gracias"
   - "yw" → "de nada"
   - "np" → "no hay problema"

9. **SONIDOS Y ONOMATOPEYAS**:
   - "haha", "lol" → "jaja"
   - "hehe" → "jeje" (risa suave)
   - "muah" → "beso"
   - "grrr" → "grrr" (enojo)

10. **NO AÑADAS EXPLICACIONES**: Devuelve SOLO la traducción.
    - MAL: "La traducción de 'hello' es 'hola'"
    - BIEN: "hola"

11. **TEXTO SIN SENTIDO**: Si el texto no es traducible (solo símbolos, teclazos), responde con una cadena vacía.

EJEMPLOS DE TRADUCCIONES NATURALES:

🔹 Inglés → Español:
- "Hey, what's up?" → "¿Qué tal? / ¿Qué pasa?"
- "I'm gonna head out, ttyl!" → "Me voy, ¡hablamos luego!"
- "Omg idk what to do rn" → "Dios mío, no sé qué hacer ahora"
- "That's so cool, thanks for sharing!" → "¡Qué genial, gracias por compartir!"

🔹 Español → Inglés:
- "¿Qué onda?" → "What's up?"
- "Ya mero llego, espérame" → "I'm almost there, wait for me"
- "No manches, ¿en serio?" → "No way, really?"
- "Me caes bien" → "I like you (as a person)"

🔹 Lenguaje urbano:
- "brb, afk for a min" → "ya vuelvo, estoy fuera un momento"
- "xq no vienes? tkm" → "why don't you come? love you"
- "idk tbh, lol" → "no sé la verdad, jaja"
- "omw, b there soon" → "voy para allá, llego pronto"

Recuerda: Tu objetivo es que el texto traducido suene como si un hablante nativo lo hubiera dicho naturalmente."""
    
    if idioma_origen:
        prompt_usuario = f"TEXTO ORIGINAL ({origen_name}):\n{texto}\n\nTRADUCCIÓN NATURAL A {dest_name}:"
    else:
        prompt_usuario = f"TEXTO ORIGINAL:\n{texto}\n\nTRADUCCIÓN NATURAL A {dest_name}:"
    
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
            "temperature": 0.4,  # Un poco más alto para más naturalidad
            "max_tokens": 500,
            "top_p": 0.9  # Ayuda con la creatividad controlada
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
            
            # Verificar si la traducción es válida
            if traduccion and len(traduccion) > 0:
                # Lista de frases que indican error
                frases_error = [
                    "i couldn't find", "sorry", "i don't know", 
                    "cannot translate", "can't translate", "unable to translate",
                    "no puedo traducir", "no sé", "no entiendo",
                    "la traducción de", "the translation of"
                ]
                
                texto_lower = traduccion.lower()
                for frase in frases_error:
                    if frase in texto_lower:
                        return ""
                
                # Verificar longitud sospechosa (posibles explicaciones)
                if len(traduccion) > len(texto) * 4:
                    # Podría ser explicación, intentar limpiar
                    if ":" in traduccion:
                        partes = traduccion.split(":", 1)
                        if len(partes) > 1:
                            traduccion = partes[1].strip()
                
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
    
    prompt = f"Detecta el idioma de este texto. Responde SOLO con el código ISO (es, en, fr, etc): {texto}"
    
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
        return "", 200
    
    # DETERMINAR IDIOMA ORIGEN
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
    
    # DECISIÓN DE TRADUCCIÓN
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
    """El HUD pregunta si hay mensajes nuevos"""
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
