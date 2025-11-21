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

# Función para eliminar acentos
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

    if user_id is None:
        return jsonify({"error": "Falta UUID del usuario"})

    # Detectamos el idioma de la pregunta
    try:
        lang = detect(user_msg)
    except:
        lang = "es"  # por defecto español si falla

    # Si no existe la sesión, crear una con prompt de Zenko
    if user_id not in sessions:
        sessions[user_id] = {
            "system_prompt": (
                "Eres Zenko, un antiguo kitsune sabio. "
                "Tus respuestas son claras, simples, concretas. "
                "Nunca rompes personaje. Nunca insultas. "
            )
        }

    # Ajustamos el prompt según el idioma
    system_prompt = sessions[user_id]["system_prompt"]
    if lang == "en":
        system_prompt += "Responde en inglés."
    elif lang == "fr":
        system_prompt += "Réponds en français."
    else:
        system_prompt += "Responde en español."

    # Solo enviamos la última pregunta al modelo
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg}
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
        reply = remove_accents(reply)
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": str(e), "raw": r.text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
