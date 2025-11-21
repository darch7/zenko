from flask import Flask, request, jsonify
import requests
import os
import unicodedata
from langdetect import detect  # pip install langdetect

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# Guardamos sesiones por usuario, solo para mantener identidad
sessions = {}

# Función para eliminar acentos (solo para HUD SL)
def remove_accents(text):
    nfkd_form = unicodedata.normalize('NFKD', text)
    ascii_text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    ascii_text = ascii_text.replace('¿','?').replace('¡','!')
    return ascii_text

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user")
    user_msg = data.get("msg", "")

    if user_id is None or user_msg.strip() == "":
        return jsonify({"error": "Falta UUID del usuario o mensaje vacío"})

    # Detectamos idioma de la pregunta
    try:
        lang = detect(user_msg)
    except:
        lang = "es"  # español por defecto

    # --- Creamos la sesión si no existe ---
    if user_id not in sessions:
        sessions[user_id] = {
            "system_prompt": ""  # Lo definimos dinámicamente según idioma
        }

    # --- Prompt del sistema según idioma ---
    if lang == "en":
        system_prompt = (
            "You are Zenko, an ancient wise kitsune. "
            "Answer in English exactly in the language of the question. "
            "Your answers are clear, simple, and concise. "
            "Never break character. Never insult."
        )
    elif lang == "fr":
        system_prompt = (
            "Vous êtes Zenko, un ancien kitsune sage. "
            "Répondez exactement en français selon la question. "
            "Vos réponses sont claires, simples et concises. "
            "Ne sortez jamais de votre personnage. Ne jamais insulter."
        )
    else:
        system_prompt = (
            "Eres Zenko, un antiguo kitsune sabio. "
            "Responde exactamente en español según la pregunta. "
            "Tus respuestas son claras, simples y concretas. "
            "Nunca rompes personaje. Nunca insultas."
        )

    # Solo enviamos la última pregunta al modelo
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg}  # texto ORIGINAL con acentos
    ]

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": messages
    }

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )

    try:
        res = r.json()
        reply = res["choices"][0]["message"]["content"]

        # Solo eliminamos acentos para mostrar en HUD SL
        reply_sl = remove_accents(reply)
        return jsonify({"reply": reply_sl})

    except Exception as e:
        return jsonify({"error": str(e), "raw": r.text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
