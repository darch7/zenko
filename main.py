from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

sessions = {}

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

        sessions[user_id].append({"role": "assistant", "content": reply})

        if len(sessions[user_id]) > 40:
            sessions[user_id] = [ZENKO_SYSTEM] + sessions[user_id][-40:]

        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"error": str(e), "raw": r.text})
