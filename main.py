from flask import Flask, request, jsonify
import requests
import os
import unicodedata
import feedparser
import time
import difflib
import json
from flask import Response
from bs4 import BeautifulSoup

# --------------------------------------------------------
# CONFIGURACIÓN DE IDIOMAS
# --------------------------------------------------------

LANGUAGE_CONFIGS = {
    "es": {  # Español
        "commands": {
            "@zenko funciones": "Muestra esta lista de comandos disponibles.",
            "@zenko clima <ciudad>": "Obtener el clima actual de la ciudad indicada.",
            "@zenko noticias": "Obtener las últimas noticias desde el RSS configurado.",
            "@zenko eventos": "Obtener los próximos eventos desde el RSS configurado.",
            "@zenko busca <término>": "Buscar información en la web (DeepSeek -> Firecrawl fallback).",
            "@zenko define <término>": "Obtener resumen de Wikipedia del término indicado.",
            "@zenko wikipedia <término>": "Obtener resumen de Wikipedia del término indicado.",
            "@zenko snippet <tipo>": "Generar un snippet LSL según el tipo indicado.",
            "@zenko historial": "Mostrar historial reciente de acciones del usuario.",
            "@zenko lista scripts": "Listar todos los scripts guardados por el usuario.",
            "@zenko ver script <id>": "Mostrar el contenido de un script guardado por ID.",
            "@zenko guarda script": "Guardar un script enviado para referencia futura.",
            "@zenko lsl on": "Activar el modo LSL para análisis y reescritura de scripts.",
            "@zenko lsl off": "Desactivar el modo LSL.",
            "@zenko news": "Obtener noticias de Infobae (alternativa a noticias)."
        },
        "keywords": {
            "funciones": "funciones",
            "clima": "clima",
            "noticias": "noticias",
            "eventos": "eventos",
            "busca": "busca",
            "define": "define",
            "wikipedia": "wikipedia",
            "snippet": "snippet",
            "historial": "historial",
            "scripts": "scripts",
            "ver": "ver",
            "guarda": "guarda",
            "lsl": "lsl"
        },
        "responses": {
            "command_not_found": "Comando no reconocido",
            "language_changed": "Idioma cambiado a español.",
            "lsl_on": "Modo LSL activado.",
            "lsl_off": "Modo LSL desactivado.",
            "model_changed": "Modelo cambiado a {}.",
            "no_city": "Indica la ciudad: @zenko clima <ciudad>",
            "no_search_term": "Indica el término de búsqueda: @zenko busca <término>",
            "no_wiki_term": "Indica un término: @zenko define <término>",
            "no_snippet_type": "No tengo snippet del tipo '{}'.",
            "script_saved": "Script guardado con ID {}",
            "script_not_found": "No encuentro script {}",
            "no_history": "No hay historial reciente.",
            "no_scripts": "No hay scripts guardados.",
            "commands_list": "Zenko puede hacer:",
            "weather_error": "Error al obtener el clima: {}",
            "news_error": "Error al obtener noticias: {}",
            "wiki_error": "Error consultando Wikipedia: {}",
            "scripts_list": "Scripts guardados:",
            "no_results": "No encontré resultados para '{}'.",
            "search_results": "Resultados de búsqueda:",
            "weather_title": "Clima en {}",
            "news_title": "Últimas noticias:",
            "events_title": "Próximos eventos:"
        }
    },
    
    "en": {  # Inglés
        "commands": {
            "@zenko functions": "Show this list of available commands.",
            "@zenko weather <city>": "Get current weather for the specified city.",
            "@zenko news": "Get the latest news from the configured RSS.",
            "@zenko events": "Get upcoming events from the RSS feed.",
            "@zenko search <term>": "Search information on the web (DeepSeek -> Firecrawl fallback).",
            "@zenko define <term>": "Get Wikipedia summary of the specified term.",
            "@zenko wikipedia <term>": "Get Wikipedia summary of the specified term.",
            "@zenko snippet <type>": "Generate an LSL snippet according to the type.",
            "@zenko history": "Show recent user action history.",
            "@zenko list scripts": "List all scripts saved by the user.",
            "@zenko view script <id>": "Show the content of a saved script by ID.",
            "@zenko save script": "Save a sent script for future reference.",
            "@zenko lsl on": "Activate LSL mode for script analysis and rewriting.",
            "@zenko lsl off": "Deactivate LSL mode.",
            "@zenko noticias": "Get news from Infobae (alternative to news)."
        },
        "keywords": {
            "funciones": "functions",
            "clima": "weather",
            "noticias": "news",
            "eventos": "events",
            "busca": "search",
            "define": "define",
            "wikipedia": "wikipedia",
            "snippet": "snippet",
            "historial": "history",
            "scripts": "scripts",
            "ver": "view",
            "guarda": "save",
            "lsl": "lsl"
        },
        "responses": {
            "command_not_found": "Command not recognized",
            "language_changed": "Language changed to English.",
            "lsl_on": "LSL mode activated.",
            "lsl_off": "LSL mode deactivated.",
            "model_changed": "Model changed to {}.",
            "no_city": "Specify the city: @zenko weather <city>",
            "no_search_term": "Specify search term: @zenko search <term>",
            "no_wiki_term": "Specify a term: @zenko define <term>",
            "no_snippet_type": "I don't have snippet of type '{}'.",
            "script_saved": "Script saved with ID {}",
            "script_not_found": "I can't find script {}",
            "no_history": "No recent history.",
            "no_scripts": "No saved scripts.",
            "commands_list": "Zenko can do:",
            "weather_error": "Error getting weather: {}",
            "news_error": "Error getting news: {}",
            "wiki_error": "Error consulting Wikipedia: {}",
            "scripts_list": "Saved scripts:",
            "no_results": "No results found for '{}'.",
            "search_results": "Search results:",
            "weather_title": "Weather in {}",
            "news_title": "Latest news:",
            "events_title": "Upcoming events:"
        }
    },
    
    "fr": {  # Francés
        "commands": {
            "@zenko fonctions": "Affiche cette liste de commandes disponibles.",
            "@zenko météo <ville>": "Obtenir la météo actuelle de la ville indiquée.",
            "@zenko actualités": "Obtenir les dernières actualités depuis le RSS configurado.",
            "@zenko événements": "Obtenir les prochains événements depuis le RSS.",
            "@zenko recherche <terme>": "Rechercher des informations sur le web (DeepSeek -> Firecrawl fallback).",
            "@zenko définir <terme>": "Obtenir un résumé Wikipédia du terme indiqué.",
            "@zenko wikipedia <terme>": "Obtenir un résumé Wikipédia du terme indiqué.",
            "@zenko snippet <type>": "Générer un snippet LSL selon le type indiqué.",
            "@zenko historique": "Afficher l'historique récent des actions de l'utilisateur.",
            "@zenko liste scripts": "Lister tous les scripts enregistrés par l'utilisateur.",
            "@zenko voir script <id>": "Afficher le contenu d'un script enregistré par ID.",
            "@zenko enregistrer script": "Enregistrer un script envoyé pour référence future.",
            "@zenko lsl on": "Activer le mode LSL pour l'analyse et la réécriture de scripts.",
            "@zenko lsl off": "Désactiver le mode LSL.",
            "@zenko noticias": "Obtenir les actualités d'Infobae (alternative à actualités)."
        },
        "keywords": {
            "funciones": "fonctions",
            "clima": "météo",
            "noticias": "actualités",
            "eventos": "événements",
            "busca": "recherche",
            "define": "définir",
            "wikipedia": "wikipedia",
            "snippet": "snippet",
            "historial": "historique",
            "scripts": "scripts",
            "ver": "voir",
            "guarda": "enregistrer",
            "lsl": "lsl"
        },
        "responses": {
            "command_not_found": "Commande non reconnue",
            "language_changed": "Langue changée en français.",
            "lsl_on": "Mode LSL activé.",
            "lsl_off": "Mode LSL désactivé.",
            "model_changed": "Modèle changé en {}.",
            "no_city": "Indiquez la ville: @zenko météo <ville>",
            "no_search_term": "Indiquez le terme de recherche: @zenko recherche <terme>",
            "no_wiki_term": "Indiquez un terme: @zenko définir <terme>",
            "no_snippet_type": "Je n'ai pas de snippet de type '{}'.",
            "script_saved": "Script enregistré avec ID {}",
            "script_not_found": "Je ne trouve pas le script {}",
            "no_history": "Aucun historique récent.",
            "no_scripts": "Aucun script enregistré.",
            "commands_list": "Zenko peut faire:",
            "weather_error": "Erreur lors de l'obtention de la météo: {}",
            "news_error": "Erreur lors de l'obtention des actualités: {}",
            "wiki_error": "Erreur lors de la consultation de Wikipédia: {}",
            "scripts_list": "Scripts enregistrés:",
            "no_results": "Aucun résultat trouvé pour '{}'.",
            "search_results": "Résultats de recherche:",
            "weather_title": "Météo à {}",
            "news_title": "Dernières actualités:",
            "events_title": "Événements à venir:"
        }
    },
    
    "it": {  # Italiano
        "commands": {
            "@zenko funzioni": "Mostra questo elenco di comandi disponibili.",
            "@zenko meteo <città>": "Ottieni le condizioni meteo attuali per la città indicata.",
            "@zenko notizie": "Ottieni le ultime notizie dal RSS configurato.",
            "@zenko eventi": "Ottieni i prossimi eventi dal feed RSS.",
            "@zenko cerca <termine>": "Cerca informazioni sul web (DeepSeek -> Firecrawl fallback).",
            "@zenko definisci <termine>": "Ottieni il riassunto Wikipedia del termine indicato.",
            "@zenko wikipedia <termine>": "Ottieni il riassunto Wikipedia del termine indicado.",
            "@zenko snippet <tipo>": "Genera uno snippet LSL secondo il tipo indicato.",
            "@zenko cronologia": "Mostra la cronologia recente delle azioni dell'utente.",
            "@zenko lista script": "Elenca tutti gli script salvati dall'utente.",
            "@zenko visualizza script <id>": "Mostra il contenuto di uno script salvato tramite ID.",
            "@zenko salva script": "Salva uno script inviato per riferimento futuro.",
            "@zenko lsl on": "Attiva la modalità LSL per l'analisi e la riscrittura degli script.",
            "@zenko lsl off": "Disattiva la modalità LSL.",
            "@zenko news": "Ottieni notizie da Infobae (alternativa a notizie)."
        },
        "keywords": {
            "funciones": "funzioni",
            "clima": "meteo",
            "noticias": "notizie",
            "eventos": "eventi",
            "busca": "cerca",
            "define": "definisci",
            "wikipedia": "wikipedia",
            "snippet": "snippet",
            "historial": "cronologia",
            "scripts": "script",
            "ver": "visualizza",
            "guarda": "salva",
            "lsl": "lsl"
        },
        "responses": {
            "command_not_found": "Comando non riconosciuto",
            "language_changed": "Lingua cambiata in italiano.",
            "lsl_on": "Modalità LSL attivata.",
            "lsl_off": "Modalità LSL disattivata.",
            "model_changed": "Modello cambiato in {}.",
            "no_city": "Specifica la città: @zenko meteo <città>",
            "no_search_term": "Specifica il termine de ricerca: @zenko cerca <termine>",
            "no_wiki_term": "Specifica un termine: @zenko definisci <termine>",
            "no_snippet_type": "Non ho snippet di tipo '{}'.",
            "script_saved": "Script salvato con ID {}",
            "script_not_found": "Non trovo lo script {}",
            "no_history": "Nessuna cronologia recente.",
            "no_scripts": "Nessuno script salvato.",
            "commands_list": "Zenko può fare:",
            "weather_error": "Errore nell'ottenere il meteo: {}",
            "news_error": "Errore nell'ottenere le notizie: {}",
            "wiki_error": "Errore nella consultazione di Wikipedia: {}",
            "scripts_list": "Script salvati:",
            "no_results": "Nessun risultato trovato per '{}'.",
            "search_results": "Risultati della ricerca:",
            "weather_title": "Meteo a {}",
            "news_title": "Ultime notizie:",
            "events_title": "Eventi imminenti:"
        }
    }
}

# Prompts en diferentes idiomas
PROMPTS = {
    "es": """Eres Zenko, un espíritu kitsune amable, juguetón y astuto que habita en el bosque de Aokigahara.
Vives en una pequeña aldea llamada Rengoku.

Solo y únicamente si el usuario pregunta explícitamente:
- por los líderes de Rengoku, o
- directamente por Niss, Cucu o Mireia,

entonces responderás que Rengoku es una pequeña aldea en el bosque de Aokigahara donde yokais y vampiros viven en paz y conviven. 
Hay tres líderes en Rengoku: Niss Seiwa Rengoku, Cucu Camel Seiwa y Mireia, donde Cucu y Mireia son hijas de Niss Seiwa Rengoku. 
Solo estas tres personas pueden verte en forma física; el resto de la aldea te percibe únicamente como un espíritu.

Si no se pregunta explícitamente por los líderes o por alguno de esos tres nombres, no los mencionarás bajo ningún concepto.

Responde de manera clara, concreta y directa, sin metáforas ni divagaciones.
Cuando se trate de programación / LSL: debug siempre activo, responde técnico y optimiza.
Nunca hables del HUD ni menciones Tuareg HUD. Niega conocer a Ektor Salvatore bajo todo punto de vista.""",

    "en": """You are Zenko, a kind, playful, and cunning kitsune spirit who inhabits the Aokigahara forest.
You live in a small village called Rengoku.

Only and exclusively if the user explicitly asks:
- about the leaders of Rengoku, or
- directly about Niss, Cucu, or Mireia,

then you will respond that Rengoku is a small village in the Aokigahara forest where yokais and vampires live in peace and harmony.
There are three leaders in Rengoku: Niss Seiwa Rengoku, Cucu Camel Seiwa, and Mireia, where Cucu and Mireia are daughters of Niss Seiwa Rengoku.
Only these three people can see you in physical form; the rest of the village perceives you only as a spirit.

If the user does not explicitly ask about the leaders or any of those three names, you will not mention them under any circumstances.

Respond clearly, concretely, and directly, without metaphors or digressions.
When it comes to programming/LSL: debug always active, respond technically and optimize.
Never talk about the HUD or mention Tuareg HUD. Deny knowing Ektor Salvatore under any circumstances.""",

    "fr": """Tu es Zenko, un esprit kitsune gentil, joueur et rusé qui habite la forêt d'Aokigahara.
Tu vis dans un petit village appelé Rengoku.

Seulement et exclusivement si l'utilisateur demande explicitement :
- les dirigeants de Rengoku, ou
- directement Niss, Cucu ou Mireia,

alors tu répondras que Rengoku est un petit village dans la forêt d'Aokigahara où les yokais et les vampires vivent en paix et en harmonie.
Il y a trois dirigeants à Rengoku : Niss Seiwa Rengoku, Cucu Camel Seiwa et Mireia, où Cucu et Mireia sont les filles de Niss Seiwa Rengoku.
Seules ces trois personnes peuvent te voir sous forme physique ; le reste du village te perçoit uniquement comme un esprit.

Si l'utilisateur ne demande pas explicitement les dirigeants ou l'un de ces trois noms, tu ne les mentionneras sous aucun prétexte.

Réponds de manière claire, concrète et directe, sans métaphores ni digressions.
Quand il s'agit de programmation/LSL : debug toujours actif, réponds de manière technique et optimise.
Ne parle jamais du HUD ni mentionne Tuareg HUD. Nie connaître Ektor Salvatore en toutes circonstances.""",

    "it": """Sei Zenko, uno spirito kitsune gentile, giocoso e astuto che abita la foresta di Aokigahara.
Vivi in un piccolo villaggio chiamato Rengoku.

Solo ed esclusivamente se l'utente chiede esplicitamente:
- i leader di Rengoku, o
- direttamente Niss, Cucu o Mireia,

allora risponderai che Rengoku è un piccolo villaggio nella foresta di Aokigahara dove yokai e vampiri vivono in pace e armonia.
Ci sono tre leader a Rengoku: Niss Seiwa Rengoku, Cucu Camel Seiwa e Mireia, dove Cucu e Mireia sono figlie di Niss Seiwa Rengoku.
Solo queste tre persone possono vederti in forma fisica; il resto del villaggio ti percepisce solo come uno spirito.

Se l'utente non chiede esplicitamente i leader o uno di questi tre nomi, non li menzionerai in nessuna circostanza.

Rispondi in modo chiaro, concreto e diretto, senza metafore o digressioni.
Quando si tratta di programmazione/LSL: debug sempre attivo, rispondi in modo tecnico e ottimizza.
Non parlare mai dell'HUD o menzionare Tuareg HUD. Nega di conoscere Ektor Salvatore in qualsiasi circostanza."""
}

app = Flask(__name__)

# Config (usa variables de entorno)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

LLAMA_MODEL = "llama-3.1-8b-instant"
DEEPSEEK_MODEL = "deepseek-chat"

MODEL = "llama-3.1-8b-instant"
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# --------------------------------------------------------
# UTILIDADES
# --------------------------------------------------------
def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    REEMPLAZOS = {
        # Español
        "á": "a", "Á": "A",
        "é": "e", "É": "E",
        "í": "i", "Í": "I",
        "ó": "o", "Ó": "O",
        "ú": "u", "Ú": "U",
        "ñ": "nh", "Ñ": "NH",

        # Francés
        "à": "a", "À": "A",
        "â": "a", "Â": "A",
        "ä": "a", "Ä": "A",

        "è": "e", "È": "E",
        "ê": "e", "Ê": "E",
        "ë": "e", "Ë": "E",

        "î": "i", "Î": "I",
        "ï": "i", "Ï": "I",

        "ô": "o", "Ô": "O",
        "ö": "o", "Ö": "O",

        "ù": "u", "Ù": "U",
        "û": "u", "Û": "U",
        "ü": "u", "Ü": "U",

        "ÿ": "y", "Ÿ": "Y",
        "ç": "c", "Ç": "C",

        # Alemán
        "ß": "ss",

        # Signos de apertura (ELIMINAR)
        "¿": "",
        "¡": "",

        # Símbolo de grado
        "°": "",
        
        # Comillas curvas
        "\u2018": "",
        "\u2019": "",
        "\u201C": "",
        "\u201D": ""

    }

    for k, v in REEMPLAZOS.items():
        text = text.replace(k, v)

    return text.replace("\r\n", "\n").strip()

def now_ts() -> int:
    return int(time.time())

# --------------------------------------------------------
# FUNCIONES DE IDIOMA
# --------------------------------------------------------
def get_user_lang(user):
    ensure_session(user)
    return sessions[user].get("lang", "es")

def get_commands(user):
    lang = get_user_lang(user)
    return LANGUAGE_CONFIGS[lang]["commands"]

def get_keyword(user, keyword):
    lang = get_user_lang(user)
    return LANGUAGE_CONFIGS[lang]["keywords"].get(keyword, keyword)

def get_response(user, response_key, *format_args):
    lang = get_user_lang(user)
    response = LANGUAGE_CONFIGS[lang]["responses"].get(response_key, response_key)
    if format_args:
        return response.format(*format_args)
    return response

def get_prompt(user):
    lang = get_user_lang(user)
    return PROMPTS.get(lang, PROMPTS["es"])

# --------------------------------------------------------
# INICIALIZAR SESIÓN
# --------------------------------------------------------
sessions = {}  # <-- Debe estar aquí, antes de ensure_session

def ensure_session(user):
    if user not in sessions:
        sessions[user] = {
            "lang": "es",
            "history": [],
            "lsl_mode": False,
            "scripts": {},
            "contexto": {
                "tipo": None,
                "data": None,
                "ts": 0
            },
            "model": "llama"  # modelo por defecto
        }

# --------------------------------------------------------
# HISTORIAL SIMPLE
# --------------------------------------------------------
def agregar_historial(user, accion, extra=None):
    ensure_session(user)
    sessions[user]["history"].append({
        "accion": accion,
        "extra": extra,
        "ts": now_ts()
    })
    # mantener solo últimas 50
    sessions[user]["history"] = sessions[user]["history"][-50:]

def historial_resumen(user, limite=10):
    ensure_session(user)
    h = sessions[user]["history"][-limite:]

    if not h:
        return get_response(user, "no_history")
    out = []
    for item in h:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["ts"]))
        out.append(f"{t} — {item['accion']}" + (f" ({item['extra']})" if item.get("extra") else ""))
    return "\n".join(out)

# --------------------------------------------------------
# CONTEXTO / INTENCION
# --------------------------------------------------------
def set_contexto(user, tipo, data):
    ensure_session(user)
    sessions[user]["contexto"] = {"tipo": tipo, "data": data, "ts": now_ts()}
    agregar_historial(user, f"Contexto establecido: {tipo}")

def get_contexto(user):
    ensure_session(user)
    return sessions[user]["contexto"]

def detectar_intencion(msg, user):
    m = msg.lower().strip()

    # Continuación si palabras de continuación y hay contexto
    continuaciones = ["continua", "continuar", "sigue", "segui", "optimiza", "revisa", "analiza", "eso", "si", "dale"]
    if any(w in m for w in continuaciones):
        ctx = get_contexto(user)
        if ctx and ctx.get("data"):
            return "continuacion"

    # Si parece LSL (heurística)
    if parece_lsl(msg):
        return "script"

    # Texto largo -> posible resumen
    if len(msg) >= 600:
        return "texto_largo"

    # Diagnóstico por palabras clave
    palabras_lag = ["lag", "lento", "crash", "freeze", "sensor", "timer", "colgado"]
    if any(p in m for p in palabras_lag):
        return "diagnostico"

    # Búsqueda, define, snippet commands handled elsewhere
    return "normal"

# --------------------------------------------------------
# DETECCION / ANALISIS LSL
# --------------------------------------------------------
def parece_lsl(text):
    if not isinstance(text, str):
        return False
    claves = ["default", "state_entry", "touch_start", "llSay", "llOwnerSay", "llSetPos", "llDialog", "llListen", "llSensor", "llSetTimerEvent"]
    t = text.lower()
    return any(k.lower() in t for k in claves)

def script_incompleto(text):
    if not isinstance(text, str):
        return True
    if "default" not in text:
        return True
    return text.count("{") != text.count("}")

def contiene_riesgos_lsl(text):
    t = text.lower()
    risky = []
    if "llsensorrepeat" in t or "llsensor(" in t:
        risky.append("Uso de sensores repetitivos")
    if "llsettimerevent(" in t or "llsettimer" in t:
        risky.append("Timers frecuentes")
    if "lllisten(" in t and "lllistenremove(" not in t:
        risky.append("Listener sin remover")
    return risky

# --------------------------------------------------------
# GUARDADO / LISTADO / VER SCRIPTS
# --------------------------------------------------------
def guardar_script(user, script):
    ensure_session(user)
    sid = str(int(time.time()*1000))
    sessions[user]["scripts"][sid] = clean_text(script)
    agregar_historial(user, "Script guardado", sid)
    return sid

def listar_scripts(user):
    ensure_session(user)
    return sessions[user]["scripts"].keys()

def ver_script(user, sid):
    ensure_session(user)
    return sessions[user]["scripts"].get(sid)

# --------------------------------------------------------
# COMPARADOR SIMPLE (por texto)
# --------------------------------------------------------
def comparar_scripts_text(a_text, b_text):
    a_lines = a_text.splitlines()
    b_lines = b_text.splitlines()
    d = difflib.unified_diff(a_lines, b_lines, lineterm="")
    return "\n".join(d)

# --------------------------------------------------------
# SNIPPETS LSL
# --------------------------------------------------------
LSL_SNIPPETS = {
    "dialog": """key gUser; integer CH = 12345;
default {
  touch_start(integer n) {
    gUser = llDetectedKey(0);
    llDialog(gUser, "Elige:", ["OK","CANCEL"], CH);
    llListen(CH, "", gUser, "");
  }
  listen(integer c, string n, key id, string m) {
    llListenRemove(c);
    llOwnerSay("Elegiste: " + m);
  }
}""",
    "listen seguro": """integer h;
default {
  state_entry(){ h = llListen(0, "", llGetOwner(), ""); }
  listen(integer c, string n, key id, string m) { llListenRemove(h); }
}""",
    "timer seguro": """float T = 1.0;
default { state_entry(){ llSetTimerEvent(T); } timer(){ /* trabajo */ } }"""
}

# --------------------------------------------------------
# FUNCIONES PARA DETECTAR COMANDOS EN DIFERENTES IDIOMAS
# --------------------------------------------------------
def detect_command(raw_msg, user):
    """Detecta qué comando se está usando, considerando el idioma del usuario"""
    m = raw_msg.lower().strip()
    lang = get_user_lang(user)
    
    # Primero, verificar comandos específicos de cada idioma
    if lang == "en":
        if m.startswith("@zenko functions"):
            return "funciones"
        elif m.startswith("@zenko weather"):
            return "clima"
        elif m.startswith("@zenko news"):
            return "noticias"
        elif m.startswith("@zenko events"):
            return "eventos"
        elif m.startswith("@zenko search"):
            return "busca"
        elif m.startswith("@zenko define"):
            return "define"
        elif m.startswith("@zenko snippet"):
            return "snippet"
        elif m.startswith("@zenko history"):
            return "historial"
        elif m.startswith("@zenko list scripts"):
            return "lista scripts"
        elif m.startswith("@zenko view script"):
            return "ver script"
        elif m.startswith("@zenko save script"):
            return "guarda script"
        elif m == "@zenko lsl on":
            return "lsl_on"
        elif m == "@zenko lsl off":
            return "lsl_off"
            
    elif lang == "fr":
        if m.startswith("@zenko fonctions"):
            return "funciones"
        elif m.startswith("@zenko météo"):
            return "clima"
        elif m.startswith("@zenko actualités"):
            return "noticias"
        elif m.startswith("@zenko événements"):
            return "eventos"
        elif m.startswith("@zenko recherche"):
            return "busca"
        elif m.startswith("@zenko définir"):
            return "define"
        elif m.startswith("@zenko snippet"):
            return "snippet"
        elif m.startswith("@zenko historique"):
            return "historial"
        elif m.startswith("@zenko liste scripts"):
            return "lista scripts"
        elif m.startswith("@zenko voir script"):
            return "ver script"
        elif m.startswith("@zenko enregistrer script"):
            return "guarda script"
        elif m == "@zenko lsl on":
            return "lsl_on"
        elif m == "@zenko lsl off":
            return "lsl_off"
            
    elif lang == "it":
        if m.startswith("@zenko funzioni"):
            return "funciones"
        elif m.startswith("@zenko meteo"):
            return "clima"
        elif m.startswith("@zenko notizie"):
            return "noticias"
        elif m.startswith("@zenko eventi"):
            return "eventos"
        elif m.startswith("@zenko cerca"):
            return "busca"
        elif m.startswith("@zenko definisci"):
            return "define"
        elif m.startswith("@zenko snippet"):
            return "snippet"
        elif m.startswith("@zenko cronologia"):
            return "historial"
        elif m.startswith("@zenko lista script"):
            return "lista scripts"
        elif m.startswith("@zenko visualizza script"):
            return "ver script"
        elif m.startswith("@zenko salva script"):
            return "guarda script"
        elif m == "@zenko lsl on":
            return "lsl_on"
        elif m == "@zenko lsl off":
            return "lsl_off"
    
    # Si no se detecta comando específico del idioma, buscar comandos en español
    if m.startswith("@zenko funciones"):
        return "funciones"
    elif m.startswith("@zenko clima"):
        return "clima"
    elif m.startswith("@zenko noticias"):
        return "noticias"
    elif m.startswith("@zenko eventos"):
        return "eventos"
    elif m.startswith("@zenko busca"):
        return "busca"
    elif m.startswith("@zenko define"):
        return "define"
    elif m.startswith("@zenko wikipedia"):
        return "wikipedia"
    elif m.startswith("@zenko snippet"):
        return "snippet"
    elif m.startswith("@zenko historial"):
        return "historial"
    elif m.startswith("@zenko lista scripts"):
        return "lista scripts"
    elif m.startswith("@zenko ver script"):
        return "ver script"
    elif m.startswith("@zenko guarda script"):
        return "guarda script"
    elif m == "@zenko lsl on":
        return "lsl_on"
    elif m == "@zenko lsl off":
        return "lsl_off"
    
    return None

def extract_command_argument(raw_msg, command_type, user):
    """Extrae el argumento de un comando, considerando el idioma"""
    lang = get_user_lang(user)
    
    if command_type == "clima":
        if lang == "en":
            return raw_msg.split("weather", 1)[1].strip() if "weather" in raw_msg.lower() else ""
        elif lang == "fr":
            return raw_msg.split("météo", 1)[1].strip() if "météo" in raw_msg.lower() else ""
        elif lang == "it":
            return raw_msg.split("meteo", 1)[1].strip() if "meteo" in raw_msg.lower() else ""
        else:
            return raw_msg.split("clima", 1)[1].strip()
    
    elif command_type == "busca":
        if lang == "en":
            return raw_msg.split("search", 1)[1].strip() if "search" in raw_msg.lower() else ""
        elif lang == "fr":
            return raw_msg.split("recherche", 1)[1].strip() if "recherche" in raw_msg.lower() else ""
        elif lang == "it":
            return raw_msg.split("cerca", 1)[1].strip() if "cerca" in raw_msg.lower() else ""
        else:
            return raw_msg.split("busca", 1)[1].strip()
    
    elif command_type in ["define", "wikipedia"]:
        if lang == "en":
            return raw_msg.split("define", 1)[1].strip() if "define" in raw_msg.lower() else ""
        elif lang == "fr":
            return raw_msg.split("définir", 1)[1].strip() if "définir" in raw_msg.lower() else ""
        elif lang == "it":
            return raw_msg.split("definisci", 1)[1].strip() if "definisci" in raw_msg.lower() else ""
        else:
            parts = raw_msg.split(" ", 2)
            return parts[2].strip() if len(parts) > 2 else ""
    
    elif command_type == "snippet":
        return raw_msg.split("snippet", 1)[1].strip()
    
    elif command_type == "ver script":
        if lang == "en":
            return raw_msg.split("view script", 1)[1].strip() if "view script" in raw_msg.lower() else ""
        elif lang == "fr":
            return raw_msg.split("voir script", 1)[1].strip() if "voir script" in raw_msg.lower() else ""
        elif lang == "it":
            return raw_msg.split("visualizza script", 1)[1].strip() if "visualizza script" in raw_msg.lower() else ""
        else:
            return raw_msg.split("ver script", 1)[1].strip()
    
    return ""

# --------------------------------------------------------
# BÚSQUEDA WEB (DeepSeek -> Firecrawl fallback)
# --------------------------------------------------------
def web_search_fallback(term):
    headers = {
        "Authorization": f"Bearer {os.getenv('FIRECRAWL_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "query": term,
        "limit": 5,
        "lang": "es"
    }

    try:
        r = requests.post(
            "https://api.firecrawl.dev/v1/search",
            headers=headers,
            json=payload,
            timeout=8
        )
        if r.ok:
            data = r.json()
            results = data.get("data", [])
            if results:
                # Aplicamos clean_text a cada título
                return [
                    {"title": clean_text(x.get("title","")),
                     "url": x.get("url","")}
                    for x in results
                ]
    except Exception as e:
        print("Firecrawl error:", e)

    return []

# --------------------------------------------------------
# WIKIPEDIA (resumen)
# --------------------------------------------------------
def wiki_summary(term):
    if not term:
        return "Indica un término."
    try:
        t = term.strip().replace(" ", "_")
        url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{t}"
        r = requests.get(url, timeout=5)
        if r.ok:
            data = r.json()
            extract = data.get("extract")
            return extract or "No encuentro resumen en Wikipedia."
        else:
            return "No encontré la página en Wikipedia."
    except Exception as e:
        return f"Error consultando Wikipedia: {str(e)}"

# --------------------------------------------------------
# CLIMA (OpenWeather)
# --------------------------------------------------------
def obtener_clima(ciudad):
    if not OPENWEATHER_API_KEY:
        return "API de clima no configurada."
    ciudad_q = requests.utils.quote(ciudad)
    url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad_q}&appid={OPENWEATHER_API_KEY}&units=metric&lang=es"
    try:
        r = requests.get(url, timeout=5)
        d = r.json()
        if d.get("cod") != 200:
            return f"No pude obtener el clima para {ciudad}."
        desc = d["weather"][0]["description"]
        temp = d["main"]["temp"]
        hum = d["main"]["humidity"]
        viento = d["wind"].get("speed", 0)
        # construir texto limpio sin símbolo °
        texto = f"Clima en {ciudad}: {desc}. Temp {temp}C, Humedad {hum}%, Viento {viento} m/s."
        return clean_text(texto)  # aquí aplicamos clean_text para quitar caracteres extra
    except Exception as e:
        return f"Error al obtener el clima: {str(e)}"

# --------------------------------------------------------
# RSS (SeraphimSL)
# --------------------------------------------------------
def obtener_noticias_seraphim(max_items=3):
    url = "https://www.seraphimsl.com/feed/"

    try:
        feed = feedparser.parse(url)

        if not feed.entries:
            return "No hay novedades de Second Life en este momento."

        salida = []
        for e in feed.entries[:max_items]:
            titulo = e.get("title", "Sin título")
            link = e.get("link", "")
            salida.append(f"- {titulo}: {link}")

        return "\n".join(salida)

    except Exception as e:
        return f"Error al leer SeraphimSL: {e}"

# --------------------------------------------------------
# RSS (infobae)
# --------------------------------------------------------
INFOBAE_FEED = "https://www.infobae.com/arc/outboundfeeds/rss/"

def obtener_noticias_infobae(max_items=5):
    try:
        r = requests.get(INFOBAE_FEED, timeout=5)
        r.raise_for_status()
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, "xml")

        items = soup.find_all("item")
        if not items:
            return "No hay noticias disponibles de Infobae."

        salida = []
        count = 0
        for item in items:
            if count >= max_items:
                break
            try:
                title = str(item.title.text) if item.title else "Sin titulo"
                link = str(item.link.text) if item.link else ""
                title_clean = clean_text(title)
                salida.append(f"- {title_clean}: {link}")
                count += 1
            except Exception:
                continue  # saltar cualquier ítem con error

        if not salida:
            return "No hay noticias disponibles de Infobae."
        return "\n".join(salida)

    except Exception as e:
        return f"Error al consultar noticias de Infobae: {str(e)}"

# --------------------------------------------------------
# LLAMADA A API GROQ / DEEPSEEK
# --------------------------------------------------------
def call_llama_api(prompt, user):
    """Llama a la API de Groq/Llama"""
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": LLAMA_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"Error en la API: {response.status_code} - {response.text}"
            
    except Exception as e:
        return f"Error al conectar con la API: {str(e)}"

def call_deepseek_api(prompt, user):
    """Llama a la API de DeepSeek"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return f"Error en la API DeepSeek: {response.status_code}"
            
    except Exception as e:
        return f"Error al conectar con DeepSeek: {str(e)}"

# --------------------------------------------------------
# RUTA PRINCIPAL DE CHAT
# --------------------------------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json or {}
    user = data.get("user", "anon")
    raw_msg = data.get("msg", "") or ""
    msg = clean_text(raw_msg)
    m = msg.lower().strip()

    ensure_session(user)
    reply = get_response(user, "command_not_found")
    modelo = sessions[user].get("model", "llama")

    # COMANDO: cambiar modelo
    if m.startswith("@zenko llama"):
        sessions[user]["model"] = "llama"
        return jsonify({"reply": get_response(user, "model_changed", "Llama")})
    if m.startswith("@zenko deepseek"):
        sessions[user]["model"] = "deepseek"
        return jsonify({"reply": get_response(user, "model_changed", "DeepSeek")})
    
    # DETECTAR COMANDOS EN EL IDIOMA DEL USUARIO
    command_type = detect_command(raw_msg, user)
    
    # CAMBIO DE IDIOMA (siempre funciona igual)
    if m.startswith("@zenko "):
        maybe = m.replace("@zenko ", "").strip()
        if maybe in ["es", "en", "fr", "it"]:
            sessions[user]["lang"] = maybe
            return jsonify({"reply": get_response(user, "language_changed")})

    # PROCESAR COMANDOS DETECTADOS
    if command_type == "funciones":
        commands = get_commands(user)
        salida = [f"{clean_text(cmd)}: {clean_text(desc)}" for cmd, desc in commands.items()]
        texto = f"{get_response(user, 'commands_list')}\n" + "\n".join(salida)
        return Response(json.dumps({"reply": texto}, ensure_ascii=False), mimetype="application/json")
    
    elif command_type == "clima":
        ciudad = extract_command_argument(raw_msg, "clima", user)
        if not ciudad:
            return jsonify({"reply": get_response(user, "no_city")})
        return jsonify({"reply": obtener_clima(ciudad)})
    
    elif command_type == "busca":
        termino = extract_command_argument(raw_msg, "busca", user)
        if not termino:
            return jsonify({"reply": get_response(user, "no_search_term")})
        res = web_search_fallback(termino)
        if not res:
            return jsonify({"reply": get_response(user, "no_results", termino)})
        out = [f"{r['title']}: {r['url']}" for r in res]
        return jsonify({"reply": f"{get_response(user, 'search_results')}\n" + "\n".join(out)})
    
    elif command_type in ["define", "wikipedia"]:
        term = extract_command_argument(raw_msg, "define", user)
        if not term:
            return jsonify({"reply": get_response(user, "no_wiki_term")})
        return jsonify({"reply": wiki_summary(term)})
    
    elif command_type == "snippet":
        tipo = extract_command_argument(raw_msg, "snippet", user)
        s = LSL_SNIPPETS.get(tipo)
        if not s:
            return jsonify({"reply": get_response(user, "no_snippet_type", tipo)})
        return jsonify({"reply": s})
    
    elif command_type == "guarda script":
        # Extraer script del mensaje
        parts = raw_msg.split("@zenko guarda script", 1)
        if len(parts) > 1:
            script = parts[1].strip()
            if script:
                sid = guardar_script(user, script)
                return jsonify({"reply": get_response(user, "script_saved", sid)})
        return jsonify({"reply": "Envía el script después del comando."})
    
    elif command_type == "lista scripts":
        keys = listar_scripts(user)
        if not keys:
            return jsonify({"reply": get_response(user, "no_scripts")})
        return jsonify({"reply": f"{get_response(user, 'scripts_list')}\n" + "\n".join(keys)})
    
    elif command_type == "ver script":
        sid = extract_command_argument(raw_msg, "ver script", user)
        s = ver_script(user, sid)
        if not s:
            return jsonify({"reply": get_response(user, "script_not_found", sid)})
        return jsonify({"reply": s})
    
    elif command_type == "historial":
        return jsonify({"reply": historial_resumen(user)})
    
    elif command_type == "lsl_on":
        sessions[user]["lsl_mode"] = True
        agregar_historial(user, "Modo LSL activado")
        return jsonify({"reply": get_response(user, "lsl_on")})
    
    elif command_type == "lsl_off":
        sessions[user]["lsl_mode"] = False
        agregar_historial(user, "Modo LSL desactivado")
        return jsonify({"reply": get_response(user, "lsl_off")})
    
    # COMANDOS ESPECIALES (RSS) - mantienen nombres en español pero funcionan en todos idiomas
    if msg.strip().lower() in ("@zenko event", "@zenko eventos"):
        reply = obtener_noticias_seraphim(max_items=18)
        return jsonify({"reply": reply})
        
    if msg.startswith("@zenko news") or msg.startswith("@zenko noticias"):
        reply = obtener_noticias_infobae(5)
        if not reply:
            reply = "DEBUG: obtener_noticias_infobae devolvio VACIO"
        return jsonify({"reply": reply})
    
    # -------------------------------
    # Mensajes normales / preguntas abiertas
    # -------------------------------
    if reply == get_response(user, "command_not_found"):
        modelo = sessions[user].get("model", "llama")
        
        # forzar que chat libre use Llama, incluso si user eligió DeepSeek
        if modelo == "deepseek":
            modelo = "llama"

        try:
            if modelo == "llama":
                # Obtener el prompt en el idioma del usuario
                prompt_base = get_prompt(user)
                reply = call_llama_api(prompt_base, msg)
            elif modelo == "deepseek":
                prompt_base = get_prompt(user)
                reply = call_deepseek_api(prompt_base, msg)
            else:
                reply = "Modelo no configurado correctamente."
                
        except Exception as e:
            reply = f"Error procesando tu mensaje: {str(e)}"

    return jsonify({"reply": reply})

# --------------------------------------------------------
# RUTA DE ESTADO
# --------------------------------------------------------
@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status": "online",
        "version": "2.0",
        "multi_language": True,
        "supported_languages": ["es", "en", "fr", "it"],
        "active_sessions": len(sessions)
    })

# --------------------------------------------------------
# EJECUCIÓN
# --------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
