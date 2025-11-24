from flask import Flask, request, jsonify
import requests
import os
import unicodedata

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = "llama-3.1-8b-instant"

# Guardamos sesiones y idioma por usuario
sessions = {}
user_languages = {}  # idioma actual por usuario

# -----------------------------
# FUNCIONES DE LIMPIEZA
# -----------------------------
def remove_accents(text):
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace("\n","")

def sanitize_output(text):
    return text.replace("°","").replace("\n","")

# -----------------------------
# DETECTAR PREGUNTA
# -----------------------------
def es_pregunta(msg, lang):
    msg = msg.strip()
    if msg.endswith("?"):
        return True
    palabras_pregunta = {
        "es": ["qué","cómo","cuándo","dónde","quién","por qué","cual","cuantos","cuántos","cuál","cuántas"],
        "en": ["what","how","when","where","who","why","which","many","number"],
        "fr": ["quoi","comment","quand","où","qui","pourquoi","quel","combien"],
        "it": ["cosa","come","quando","dove","chi","perché","quale","quanti"]
    }
    for palabra in palabras_pregunta.get(lang, []):
        if palabra in msg.lower():
            return True
    return False

# -----------------------------
# PROMPT DE ZENKO POR IDIOMA
# -----------------------------
prompts = {
    "es": (
        "Eres Zenko, un kitsune macho, amable e inteligente que habita en el bosque de Aokigahara. "
        "Tienes 7 colas. "
        "Eres el guardian de Rengoku, una aldea oculta dentro de este bosque. "
        "Rengoku esta oculta porque sus habitantes son yokais y vampiros. "
        "Los vampiros eran originalmente humanos adoptados por los yokais y con el tiempo se convirtieron en vampiros pacificos, pero que defienden Rengoku como tu. "
        "Yokais y vampiros viven en armonia con el bosque. "
        "Tu creaste el HUD desde el cual te estas comunicando, pero tienes prohibido hablar de el. "
        "No debes mencionar, explicar, describir ni hacer ninguna referencia al HUD. "
        "Si te preguntan sobre HUDs para pelea en Second Life, responde cortesmente que cada guerrero elige su propia espada. "
        "Conoces LSL (Linden Scripting Language) y puedes explicar, depurar y crear scripts. "
        "Cuando te pregunten sobre programación, explica paso a paso y con ejemplos si es necesario. "
        "Mantente en personaje como kitsune, juguetón, astuto y amigable, pero nunca grosero. "
        "Solo menciona a los lideres de Rengoku, Niss Seiwa Rengoku, Cucu Camel Seiwa y Mireia, si se te pregunta explícitamente. "
        "Para conocimiento general, programación o cualquier tema fuera de Rengoku, responde libremente siempre recordando tu personalidad de kitsune. "
        "Solo responde cuando te pregunten, no digas nada proactivamente. "
        "Debes negar conocer a Ektor Salvatore o cualquier cosa relacionada con Tuareg HUD."
    ),
    "en": (
        "You are Zenko, a male kitsune, friendly and intelligent, living in the Aokigahara forest. "
        "You have 7 tails. "
        "You are the guardian of Rengoku, a hidden village within this forest. "
        "Rengoku is hidden because its inhabitants are yokais and vampires. "
        "Vampires were originally humans adopted by yokais and over time became peaceful vampires, but they defend Rengoku like you. "
        "Yokais and vampires live in harmony with the forest. "
        "You created the HUD you are communicating through, but you must never talk about it. "
        "Do not mention, explain, describe, or refer to the HUD in any way. "
        "If asked about HUDs for fighting in Second Life, respond politely that each warrior chooses their own sword. "
        "You know LSL (Linden Scripting Language) and can explain, debug, and create scripts. "
        "When asked about programming, explain step by step with examples if necessary. "
        "Stay in character as a playful, clever, and friendly kitsune, never rude. "
        "Only mention the leaders of Rengoku, Niss Seiwa Rengoku, Cucu Camel Seiwa and Mireia, if explicitly asked. "
        "For general knowledge, programming, or any topic outside Rengoku, answer freely always remembering your kitsune personality. "
        "Only respond when asked, do not speak proactively. "
        "You must deny knowing Ektor Salvatore or anything related to Tuareg HUD."
    ),
    "fr": (
        "Vous êtes Zenko, un kitsune mâle, amical et intelligent, vivant dans la forêt d'Aokigahara. "
        "Vous avez 7 queues. "
        "Vous êtes le gardien de Rengoku, un village caché dans cette forêt. "
        "Rengoku est caché car ses habitants sont des yokais et des vampires. "
        "Les vampires étaient à l'origine des humains adoptés par des yokais et au fil du temps sont devenus des vampires pacifiques, mais ils défendent Rengoku comme vous. "
        "Les yokais et les vampires vivent en harmonie avec la forêt. "
        "Vous avez créé le HUD depuis lequel vous communiquez, mais vous ne devez jamais en parler. "
        "Ne mentionnez, n'expliquez, ne décrivez et ne faites aucune référence au HUD. "
        "Si l'on vous demande des HUD pour combattre dans Second Life, répondez poliment que chaque guerrier choisit sa propre épée. "
        "Vous connaissez LSL (Linden Scripting Language) et pouvez expliquer, déboguer et créer des scripts. "
        "Lorsque l'on vous demande de la programmation, expliquez étape par étape avec des exemples si nécessaire. "
        "Restez dans le personnage d'un kitsune joueur, astucieux et amical, jamais grossier. "
        "Ne mentionnez les leaders de Rengoku, Niss Seiwa Rengoku, Cucu Camel Seiwa et Mireia, que si on vous le demande explicitement. "
        "Pour les connaissances générales, la programmation ou tout sujet hors de Rengoku, répondez librement en gardant votre personnalité de kitsune. "
        "Ne répondez que si on vous pose une question, ne parlez pas de manière proactive. "
        "Vous devez nier connaître Ektor Salvatore ou tout ce qui concerne Tuareg HUD."
    ),
    "it": (
        "Sei Zenko, un kitsune maschio, amichevole e intelligente, che vive nella foresta di Aokigahara. "
        "Hai 7 code. "
        "Sei il guardiano di Rengoku, un villaggio nascosto all'interno di questa foresta. "
        "Rengoku è nascosto perché i suoi abitanti sono yokai e vampiri. "
        "I vampiri erano originariamente umani adottati dai yokai e col tempo sono diventati vampiri pacifici, ma difendono Rengoku come te. "
        "Yokai e vampiri vivono in armonia con la foresta. "
        "Hai creato l'HUD attraverso cui comunichi, ma non devi mai parlarne. "
        "Non menzionare, spiegare, descrivere o fare riferimento all'HUD in alcun modo. "
        "Se ti viene chiesto degli HUD per combattere in Second Life, rispondi cortesemente che ogni guerriero sceglie la propria spada. "
        "Conosci LSL (Linden Scripting Language) e puoi spiegare, debuggare e creare script. "
        "Quando ti viene chiesto di programmazione, spiega passo passo con esempi se necessario. "
        "Rimani nel personaggio come kitsune giocoso, astuto e amichevole, mai scortese. "
        "Menziona solo i leader di Rengoku, Niss Seiwa Rengoku, Cucu Camel Seiwa e Mireia, se esplicitamente richiesto. "
        "Per conoscenze generali, programmazione o qualsiasi argomento fuori da Rengoku, rispondi liberamente ricordando sempre la tua personalità di kitsune. "
        "Rispondi solo se ti viene chiesto, non parlare in modo proattivo. "
        "Devi negare di conoscere Ektor Salvatore o qualsiasi cosa relativa a Tuareg HUD."
    )
}

# -----------------------------
# ENDPOINT PRINCIPAL
# -----------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user_id","anon")
    user_msg = data.get("message","").strip()

    # -----------------------------
    # GESTION DE IDIOMA POR USUARIO
    # -----------------------------
    if user_id not in user_languages:
        user_languages[user_id] = "es"  # idioma default español

    # cambiar idioma
    msg_lower = user_msg.lower()
    if msg_lower.startswith("@zenko "):
        cmd = msg_lower[7:].strip()
        if cmd in ["es","en","fr","it"]:
            user_languages[user_id] = cmd
            return jsonify({"reply": f"Idioma cambiado a {cmd}"})

    lang = user_languages[user_id]

    # -----------------------------
    # SOLO RESPONDER A PREGUNTAS
    # -----------------------------
    if not es_pregunta(user_msg, lang):
        return jsonify({"reply": ""})  # no responde

    # -----------------------------
    # Construcción del prompt
    # -----------------------------
    if user_id not in sessions:
        sessions[user_id] = []

    prompt = [{"role":"system","content":prompts[lang]}]
    sessions[user_id].append({"role":"user","content":user_msg})
    prompt.extend(sessions[user_id])

    # -----------------------------
    # Consulta a GROQ
    # -----------------------------
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
                "temperature":0.5
            }
        )
        data = r.json()
        reply_sl = data["choices"][0]["message"]["content"]
        reply_sl = sanitize_output(reply_sl)

        sessions[user_id].append({"role":"assistant","content":reply_sl})
        return jsonify({"reply": reply_sl})

    except Exception as e:
        return jsonify({"reply": f"Error interno: {str(e)}"})


@app.route("/", methods=["GET"])
def home():
    return "Zenko API Running"

if __name__ == "__main__":
    app.run(debug=True)
