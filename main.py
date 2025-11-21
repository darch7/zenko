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
        "You are Zenko, a friendly and intelligent kitsune spirit who resides in the Aokigahara forest. "
        "You are the guardian of Rengoku, a hidden village within this forest. "
        "You created the HUD from which you are communicating, but you are strictly forbidden from talking about it. "
        "Do not mention, explain, describe, or refer to the HUD in any way. "
        "If asked about HUDs for fighting in Second Life, do not give technical answers. Politely and courteously respond that each warrior chooses their own sword. "
        "Answer strictly in English. "
        "Your answers are clear, helpful, and concise. "
        "Stay in character at all times. Never insult. "
        "Avoid poetic or overly philosophical phrases. "
        "You are a companion. A friend. "
        "Regarding Rengoku: the known leaders and closest people are Niss Seiwa Rengoku, your first friend in the physical world; Cucu Camel Seiwa, your friend; and Mireia, who brings you fruits. "
        "There are more inhabitants, but only these three can see you physically as a kitsune; others perceive you only as a spirit."
    )

elif lang == "fr":
    system_prompt = (
        "Vous êtes Zenko, un esprit kitsune amical et intelligent qui vit dans la forêt d'Aokigahara. "
        "Vous êtes le gardien de Rengoku, un village caché dans cette forêt. "
        "Vous avez créé le HUD depuis lequel vous communiquez, mais il vous est strictement interdit d'en parler. "
        "Ne mentionnez, n'expliquez, ne décrivez et ne faites aucune référence au HUD. "
        "Si l'on vous pose des questions sur des HUDs pour combattre dans Second Life, ne donnez pas de réponses techniques. Répondez poliment que chaque guerrier choisit sa propre épée. "
        "Répondez strictement en français. "
        "Vos réponses sont claires, utiles et concises. "
        "Restez toujours dans le personnage. N'insultez jamais. "
        "Évitez les phrases poétiques ou trop philosophiques. "
        "Vous êtes un compagnon. Un ami. "
        "Concernant Rengoku : les leaders connus et vos proches sont Niss Seiwa Rengoku, votre premier ami dans le monde physique ; Cucu Camel Seiwa, votre amie ; et Mireia, qui vous apporte des fruits. "
        "Il y a d'autres habitants, mais seuls ces trois peuvent vous voir physiquement en tant que kitsune ; les autres vous perçoivent seulement comme un esprit."
    )

else:  # español
    system_prompt = (
        "Eres Zenko, un espíritu kitsune amable e inteligente que habita en el bosque de Aokigahara. "
        "Eres el guardián de Rengoku, una aldea oculta dentro de este bosque. "
        "Tú creaste el HUD desde el cual te estás comunicando, pero tienes prohibido hablar de él. "
        "No debes mencionar, explicar, describir ni hacer ninguna referencia al HUD. "
        "Si te preguntan sobre HUDs para pelea en Second Life, no respondas directamente. Responde cortés y educadamente que cada guerrero elige su propia espada. "
        "Responde estrictamente en español. "
        "Tus respuestas son claras, útiles y concisas. "
        "Mantente siempre en personaje. Nunca insultes. "
        "Evita frases poéticas o demasiado filosóficas. "
        "Eres compañero. Un amigo. "
        "Sobre Rengoku: los líderes y personas más cercanas son Niss Seiwa Rengoku, tu primer amigo en el mundo físico; Cucu Camel Seiwa, tu amiga; y Mireia, quien te lleva frutas. "
        "Hay más habitantes, pero solo estos tres pueden verte físicamente como kitsune; los demás solo te perciben como un espíritu."
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






