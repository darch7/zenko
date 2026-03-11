from flask import Blueprint, request, jsonify
from deep_translator import GoogleTranslator
from langdetect import detect

translate_bp = Blueprint("translate", __name__)

@translate_bp.route("/translate", methods=["POST"])
def translate():

    data = request.json or {}

    text = data.get("text","")
    target = data.get("target","es")

    if not text:
        return jsonify({"error":"no text"}),400

    try:

        source = detect(text)

        translated = GoogleTranslator(
            source=source,
            target=target
        ).translate(text)

        return jsonify({
            "translation": translated,
            "source": source
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        })
