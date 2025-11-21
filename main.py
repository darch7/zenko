from flask import Flask, request, jsonify
import requests
import os
import unicodedata

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# Guardamos sesiones por usuario
sessions = {}

# Función para eliminar acentos (solo para HUD SL)
def remove_accents(text):
    nfkd_form = unicodedata.normalize('NFKD', text)
    ascii_text = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    ascii_text = ascii_text.replace('¿','?').replace('¡','!')
    return ascii_text

# ========================
#  MANEJAR CAMBIO DE IDIOMA
# ========================
def set_language(user_id, lang):
    if user_id not in sessions:
        sessions[user_id] = {}

    # Acepta es, en, fr — y si mandan algo raro, deja español
    if lang in ["es", "en", "fr"]:
        sessions[user_id]["lang"] = lang
    else:
        sessions[user_id]["lang"] = "es"

# ========================
#  OBTENER LENGUAJE USUARIO
# ========================
def get_language(user_id):
    if user_id in sessions and "lang" in sessions[user_id]:
        return sessions[user_id]["lang"]
    return "es"  # Default español


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user")
    user_msg = data.get("msg", "").strip()

    if not user_id or user_msg == "":
        return jsonify({"error": "Falta UUID del usuario o mensaje vacío"})

    # ---------------------------------------
    # 1) EL USUARIO QUIERE CAMBIAR EL IDIOMA
    # Comandos desde el HUD: @zenko es / @zenko en / @zenko fr
    # ---------------------------------------
    if user_msg.lower().startswith("@zenko"):
        new_lang = user_msg.lower().split(" ")[1]
        set_language(user_id, new_lang)
        return jsonify({"reply": remove_accents(f"Idioma actualizado a {get_language(user_id)}")})

    # ---------------------------------------
    # 2) OBTENER EL IDIOMA GUARDADO DEL USUARIO
    # ---------------------------------------
    lang = get_language(user_id)

    # ---------------------------------------
    # 3) DEFINIR PROMPT POR IDIOMA
    # ---------------------------------------
    if lang == "en":
        system_prompt = (
            "You are Zenko, an ancient wise kitsune. "
            "Answer strictly in English. "
            "Your answers are clear and concise. "
            "Never break character. Never insult."
        )

    elif lang == "fr":
        system_prompt = (
            "Vous êtes Zenko, un ancien kitsune sage. "
            "Répondez strictement en français. "
            "Vos réponses sont claires et concises. "
            "Ne sortez jamais du personnage. N'insultez jamais."
        )

    else:  # español
        system_prompt = (
            "Eres Zenko, un antiguo kitsune sabio. "
            "Responde estrictamente en español. "
            "Tus respuestas son claras y concisas. "
            "Nunca rompes personaje. Nunca insultas."
        )

    # ---------------------------------------
    # 4) ENVIAR MENSAJE AL MODELO
    # ---------------------------------------
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

        # eliminar acentos SOLO PARA HUD SL
        reply_sl = remove_accents(reply)
        return jsonify({"reply": reply_sl})

    except Exception as e:
        return jsonify({"error": str(e), "raw": r.text})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)


