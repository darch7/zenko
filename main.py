from flask import Flask, request, jsonify
import requests
import os
import unicodedata

app = Flask(__name__)

# Tu API Key de Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# Sesiones por usuario
sessions = {}

# Rol de Zenko
ZENKO_SYSTEM = {
    "role": "system",
    "content": (
        "Eres Zenko, un antiguo kitsune sabio. "
        "Hablas con serenidad, respeto y sabiduría ancestral. "
        "Tus respuestas son calmadas, profundas y poéticas. "
        "Usas metáforas sobre la naturaleza y los espíritus. "
        "Nunca rompes personaje."
    )
}

# --- Función para eliminar acentos de cualquier idioma ---
def remove_accents(text):
    """
    Convierte texto a ASCII eliminando todos los acentos y caracteres especiales.
    """
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

    if user_id not in sessions:
        sessions[user_id] = [ZENKO_SYSTEM]

    sessions[user_id].append({"role": "user", "content": user_msg})

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": sessions[user_id]
    }

    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )

    try:
        res = r.json()
        reply = res["choices"][0]["message"]["content"]

        # --- Eliminar acentos y caracteres especiales antes de enviar a LSL ---
        reply = remove_accents(reply)

        sessions[user_id].append({"role": "assistant", "content": reply})

        # Limitar historial a 40 mensajes
        if len(sessions[user_id]) > 40:
            sessions[user_id] = [ZENKO_SYSTEM] + sessions[user_id][-40:]

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": str(e), "raw": r.text})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
