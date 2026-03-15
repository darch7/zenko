@traductor_bp.route("/send", methods=["POST"])
def send_message():
    """Recibe mensaje del HUD y lo traduce - DEVUELVE SOLO TEXTO"""
    data = request.json
    
    remitente = data.get("remitente")
    destinatario = data.get("destinatario")
    mensaje = data.get("mensaje")
    modo = data.get("modo", "auto")
    
    # Nuevos campos para emisor/receptor
    idioma_emisor = data.get("idioma_emisor", "auto")
    idioma_receptor = data.get("idioma_receptor", "es")
    
    # Compatibilidad con formato antiguo
    idioma_manual = data.get("idioma", "en")
    
    if not all([remitente, destinatario, mensaje]):
        return "", 200  # Devolver vacío si faltan datos
    
    if remitente < destinatario:
        chat_id = f"{remitente}_{destinatario}"
    else:
        chat_id = f"{destinatario}_{remitente}"
    
    # DETERMINAR IDIOMA ORIGEN
    if modo == "auto" or idioma_emisor == "auto":
        # En modo auto, detectar automáticamente
        idioma_origen = detectar_idioma(mensaje)
        print(f"Idioma detectado automáticamente: {idioma_origen}")
    else:
        # En modo manual, usar el especificado
        idioma_origen = idioma_emisor
        print(f"Idioma origen especificado: {idioma_origen}")
    
    # DETERMINAR IDIOMA DESTINO
    if modo == "auto":
        # En modo auto, usar el receptor especificado
        idioma_destino = idioma_receptor if idioma_receptor != "auto" else idioma_manual
        print(f"Modo auto - Destino: {idioma_destino}")
    else:
        # En modo manual, usar el receptor especificado
        idioma_destino = idioma_receptor
        print(f"Modo manual - Destino: {idioma_destino}")
    
    # DECISIÓN DE TRADUCCIÓN
    if modo == "auto":
        # En modo auto, SIEMPRE intentamos traducir (aunque el idioma parezca el mismo)
        print(f"Modo auto - Intentando traducción de {idioma_origen} a {idioma_destino}")
        mensaje_traducido = traducir(mensaje, idioma_destino, idioma_origen)
        # Si la traducción falla o está vacía, devolvemos el original?
        if not mensaje_traducido:
            mensaje_traducido = mensaje
    else:
        # En modo manual, solo traducir si son diferentes
        if idioma_origen != idioma_destino:
            print(f"Modo manual - Traduciendo de {idioma_origen} a {idioma_destino}")
            mensaje_traducido = traducir(mensaje, idioma_destino, idioma_origen)
        else:
            print(f"Mismo idioma ({idioma_origen} = {idioma_destino}) - No se traduce")
            mensaje_traducido = mensaje
    
    # Guardar en conversaciones (opcional pero útil)
    timestamp = datetime.now().isoformat()
    
    if chat_id not in conversaciones:
        conversaciones[chat_id] = []
    
    mensaje_data = {
        "id": len(conversaciones[chat_id]),
        "remitente": remitente,
        "destinatario": destinatario,
        "original": mensaje,
        "traducido": mensaje_traducido,
        "timestamp": timestamp,
        "leido": False
    }
    
    conversaciones[chat_id].append(mensaje_data)
    
    # DEVOLVER SOLO EL TEXTO TRADUCIDO (SIN JSON)
    return Response(mensaje_traducido, mimetype='text/plain; charset=utf-8')
