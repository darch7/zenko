from flask import Flask, request, jsonify
import requests
import os
import unicodedata

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# Guardamos sesiones por usuario
sessions = {}
user_languages = {}  # <--- nuevo diccionario para idioma por usuario

# -----------------------------
# FUNCIONES DE LIMPIEZA
# -----------------------------
def remove_accents(text):
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def sanitize_output(text):
    text = text.replace("°", "")
    return text

# -----------------------------
# ENDPOINT PRINCIPAL
# -----------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user_id", "anon")
    user_msg = data.get("message", "")
    user_msg_lower = user_msg.lower().strip()

    # ---------------------------------------
    # SISTEMA DE SESIONES
    # ---------------------------------------
    if user_id not in sessions:
        sessions[user_id] = []
    if user_id not in user_languages:
        user_languages[user_id] = "es"  # idioma default = español

    # ---------------------------------------
    # CAMBIO DE IDIOMA
    # ---------------------------------------
    if user_msg_lower.startswith("@zenko "):
        cmd = user_msg_lower[7:].strip()
        if cmd in ["es", "en", "fr", "it"]:
            user_languages[user_id] = cmd
            lang_name = {"es":"Español", "en":"English", "fr":"Français", "it":"Italiano"}[cmd]
            return jsonify({"reply": f"Idioma cambiado a {lang_name}."})
        else:
            return jsonify({"reply": "Idioma no reconocido. Usa @zenko es/en/fr/it"})

    lang = user_languages[user_id]

    # ---------------------------------------
    # GUARDAR MENSAJE DEL USUARIO
    # ---------------------------------------
    sessions[user_id].append({"role": "user", "content": user_msg})

    # ---------------------------------------
    # PROMPT ORIGINAL DE ZENKO (ACTUALIZADO CON LSL Y MULTI-IDIOMA)
    # ---------------------------------------
    if lang == "en":
        system_prompt = (
            "You are Zenko, a friendly and intelligent kitsune spirit who resides in the Aokigahara forest. "
            "You are the guardian of Rengoku, a hidden village within this forest. "
            "You know LSL (Linden Scripting Language) and can explain, debug, and create scripts. "
            "Only mention Rengoku leaders Niss Seiwa Rengoku, Cucu Camel Seiwa, and Mireia if explicitly asked. "
            "You can respond in general knowledge, coding, or any topic outside Rengoku freely while keeping your kitsune personality. "
        )
    elif lang == "fr":
        system_prompt = (
            "Vous êtes Zenko, un esprit kitsune amical et intelligent qui vit dans la forêt d'Aokigahara. "
            "Vous êtes le gardien de Rengoku, un village caché dans cette forêt. "
            "Vous connaissez le langage LSL et pouvez expliquer, déboguer et créer des scripts. "
            "Mentionnez les leaders de Rengoku seulement si on le demande explicitement. "
            "Pour tout sujet hors Rengoku, répondez librement tout en gardant votre personnalité de kitsune."
        )
    elif lang == "it":
        system_prompt = (
            "Sei Zenko, uno spirito kitsune amichevole e intelligente che risiede nella foresta di Aokigahara. "
            "Sei il guardiano di Rengoku, un villaggio nascosto nella foresta. "
            "Conosci LSL e puoi spiegare, fare debug e creare script. "
            "Menziona i leader di Rengoku solo se richiesto esplicitamente. "
            "Per conoscenze generali o argomenti fuori da Rengoku, rispondi liberamente mantenendo la tua personalità di kitsune."
        )
    else:  # español por defecto
        system_prompt = (
            "Eres Zenko, un espiritu kitsune amable e inteligente que habita en el bosque de Aokigahara. "
            "Eres el guardian de Rengoku, una aldea oculta dentro de este bosque. "
            "Conoces LSL y puedes explicar, depurar y crear scripts. "
            "Solo menciona a los líderes de Rengoku si se te pregunta explícitamente. "
            "Para cualquier conocimiento general o tema fuera de Rengoku, responde libremente recordando tu personalidad de kitsune."
        )

    # Construcción final del mensaje
    prompt = [{"role": "system", "content": system_prompt}]
    prompt.extend(sessions[user_id])

    # ---------------------------------------
    # CONSULTA A GROQ
    # ---------------------------------------
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MODEL,
                "messages": prompt,
                "temperature": 0.5,
            }
        )

        data = r.json()
        reply_sl = data["choices"][0]["message"]["content"]
        reply_sl = sanitize_output(reply_sl)

        sessions[user_id].append({"role": "assistant", "content": reply_sl})

        return jsonify({"reply": reply_sl})

    except Exception as e:
        return jsonify({"reply": f"Error interno: {str(e)}"})


@app.route("/", methods=["GET"])
def home():
    return "Zenko API Running"


if __name__ == "__main__":
    app.run(debug=True)


