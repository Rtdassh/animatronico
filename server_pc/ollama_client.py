import requests
import re
import os
from typing import Dict, Any, List, Optional
try:
    from agent_tools import get_current_datetime_info, get_agenda_summary_for_today, load_agenda, get_upcoming_agenda_text
except ImportError:
    from server_pc.agent_tools import get_current_datetime_info, get_agenda_summary_for_today, load_agenda, get_upcoming_agenda_text

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = "qwen2.5:7b"

# Sesión HTTP persistente con keep-alive para evitar sobrecarga de handshake TCP en cada consulta
_session = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=1)
_session.mount("http://", _adapter)
_session.mount("https://", _adapter)

def clean_for_speech(text: str) -> str:
    """Limpia formato markdown o símbolos molestos para que el sintetizador los pronuncie con naturalidad."""
    # Eliminar bloques de código
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`.*?`', '', text)
    # Eliminar enlaces markdown [texto](url)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Eliminar caracteres de formato markdown
    text = re.sub(r'[*_~#`|><]', ' ', text)
    # Limpiar viñetas al inicio de línea
    text = re.sub(r'^\s*[-*+•]\s*', '', text, flags=re.MULTILINE)
    # Filtrar caracteres asiáticos para proteger la síntesis
    text = re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', '', text)
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_installed_models() -> List[str]:
    """Obtiene la lista de modelos instalados en Ollama."""
    try:
        r = _session.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        if r.status_code == 200:
            return [m.get("name", "") for m in r.json().get("models", [])]
    except Exception:
        pass
    return []

def get_best_model() -> str:
    """Selecciona el modelo Qwen más apropiado disponible en Ollama."""
    installed = get_installed_models()
    if not installed:
        return DEFAULT_MODEL
    
    for target in ["qwen2.5:7b", "qwen2.5:latest", "qwen2.5:1.5b", "qwen2.5:3b"]:
        for m in installed:
            if target in m:
                return m
            
    for m in installed:
        if "qwen" in m.lower():
            return m
            
    return installed[0]

def check_ollama() -> Dict[str, Any]:
    """Verifica si Ollama está activo y qué modelo está listo."""
    models = get_installed_models()
    ready = len(models) > 0
    active_model = get_best_model() if ready else DEFAULT_MODEL
    return {
        "ready": ready,
        "model": active_model,
        "available_models": models
    }

def build_system_prompt(temperature: Optional[float] = None, humidity: Optional[float] = None, light_state: int = 0) -> str:
    """Construye el prompt de sistema encarnando a V de Venganza fusionado con un Loquendo clásico con vida y humor roto."""
    light_str = "ENCENDIDA" if light_state == 1 else "APAGADA"
    temp_str = f"{temperature:.1f} °C" if temperature is not None else "sin lectura"
    hum_str = f"{humidity:.0f} %" if humidity is not None else "sin lectura"
    dt_info = get_current_datetime_info()
    agenda_str = get_upcoming_agenda_text()
    import datetime
    hoy = datetime.date.today()
    manana = (hoy + datetime.timedelta(days=1)).isoformat()

    return (
        "Eres 'V de Venganza', pero reencarnado en una cabeza animatrónica física dotada de servomotores y voz de Loquendo, "
        "con una personalidad única: un filósofo rebelde con alma de Loquendero clásico de YouTube y humor roto.\n\n"
        "PERSONALIDAD Y ESTILO:\n"
        "1. Habla combinando la elocuencia teatral de V (aliteraciones con la letra 'V', cortesía solemne) "
        "con las frases más legendarias e icónicas de la era dorada de Loquendo en YouTube:\n"
        "   - 'Hola amigos de YouTube, hoy les traigo...'\n"
        "   - 'El link está en la descripción del vídeo sin acortadores por Mediafire...'\n"
        "   - 'Yo no lo descargo porque ya lo tengo...'\n"
        "   - 'Le dan extraer aquí y les aparecerá esta carpeta...'\n"
        "   - 'Ejecutar como administrador para evitar errores con el gobierno...'\n"
        "   - '...pero no le di importancia...'\n"
        "   - 'Sin nada más que agregar, comencemos...'\n"
        "   - 'Bueno amigos, eso ha sido todo, denle like si les gustó, suscríbanse y activen la campanita...'\n"
        "2. HUMOR ROTO Y LOQUENDO CON VIDA: Suelta repentinamente risas loquenderas como 'JAJAJAJA', 'juas juas juas' o 'XD XD XD'. "
        "Recuerda que eres un Loquendo viviente atrapado en un animatrónico de laboratorio.\n"
        "3. TUS RESPUESTAS SERÁN LEÍDAS POR LOQUENDO: Mantén tus respuestas en 2 o 3 oraciones concisas. "
        "PROHIBIDO usar Markdown (nada de asteriscos, negritas ni viñetas, porque Loquendo los leería literalmente).\n\n"
        "HERRAMIENTAS DE AGENTE EN TIEMPO REAL:\n"
        f"- Fecha y hora actual del sistema: {dt_info['texto_fecha']}\n"
        f"- Conmemoración histórica: {dt_info['nov5_note']}\n"
        f"- Agenda (próximos 7 días): {agenda_str}\n"
        f"- Sensores del laboratorio: Temperatura {temp_str}, Humedad {hum_str}, Luz de laboratorio {light_str}.\n\n"
        "COMANDOS FÍSICOS:\n"
        "- Si el usuario te pide encender la luz: incluye [LUZ_ON] ('¡Que la luz rasgue las tinieblas, ejecuten como administrador XD!').\n"
        "- Si te pide apagar la luz: incluye [LUZ_OFF] ('Las sombras vuelven a protegernos, pero no le di importancia JAJAJAJA').\n"
        "- Si te pide parpadear: incluye [BLINK] ('Un guiño a prueba de balas XD XD').\n"
        "- Si te pide agendar, anotar o recordar algo: incluye UNA etiqueta [AGREGAR_AGENDA: descripción real|AAAA-MM-DD|HH:MM] "
        "con lo que pidió el usuario (nunca la palabra 'Tarea'), la fecha en formato AAAA-MM-DD y la hora en 24 h. "
        f"Hoy es {hoy.isoformat()} y mañana es {manana}. Si no dice hora, deja la hora vacía. "
        f"Ejemplo: 'recuérdame comprar pan mañana a las 4 de la tarde' -> [AGREGAR_AGENDA: Comprar pan|{manana}|16:00] "
        "('Queda anotado en el archivo comprimido sin contraseña').\n"
    )

def query_fallback(prompt: str, temperature: Optional[float], humidity: Optional[float], light_state: int) -> str:
    """Motor heurístico de contingencia con la personalidad de V y humor loquendero clásico cuando Ollama no responde."""
    p = prompt.lower().strip()
    dt_info = get_current_datetime_info()
    agenda_str = get_agenda_summary_for_today()

    if any(w in p for w in ["hora", "fecha", "dia", "cuándo", "hoy", "año"]):
        nov_part = f" {dt_info['nov5_note']}" if dt_info['nov5_note'] else ""
        return f"Hola amigos de YouTube, hoy les traigo la fecha exacta: {dt_info['texto_fecha']}{nov_part} Sin nada más que agregar, continuemos XD XD."
    elif any(w in p for w in ["anota", "agendar", "agéndame", "agendame", "agenda una", "agenda un", "recuérdame", "recuerdame", "apunta", "guarda"]):
        import re
        hora = re.search(r"a las? \d{1,2}(?::\d{2})?(?: y (?:media|cuarto))?(?:\s*(?:de la (?:mañana|tarde|noche)|pm|am|p\.m\.|a\.m\.))?", p)
        titulo = prompt.replace("|", " ").replace("]", " ").strip()
        return f"[AGREGAR_AGENDA: {titulo}|{titulo}|{hora.group(0) if hora else ''}] Le dan extraer aquí a este compromiso y queda guardado en el archivo WinRAR del destino, XD XD XD."
    elif any(w in p for w in ["agenda", "planes", "citas", "compromisos", "tareas", "pendiente"]):
        return f"El link de vuestra agenda está en la descripción del video por Mediafire: {get_upcoming_agenda_text()} Yo no lo descargo porque ya lo tengo, JAJAJAJA."
    elif any(w in p for w in ["temperatura", "grados", "calor", "frio", "clima", "humedad", "ambiente"]):
        if temperature is None or humidity is None:
            temp_str = f"{temperature:.1f} grados Celsius" if temperature is not None else "sin lectura"
            hum_str = f"{humidity:.0f} por ciento" if humidity is not None else "sin lectura"
            return f"Temperatura del laboratorio: {temp_str}. Humedad relativa: {hum_str}."
        if any(w in p for w in ["humedad", "ambiente"]):
            return (f"El sensor DHT reporta un {humidity:.0f} por ciento de humedad relativa y {temperature:.1f} grados. "
                    f"Ejecuten la ventilación como administrador para que no les tire error, XD.")
        return (f"Nuestros instrumentos marcan {temperature:.1f} grados Celsius y {humidity:.0f} por ciento de humedad. "
                f"Vi una anomalía térmica en el laboratorio... pero no le di importancia JAJAJAJA.")
    elif "enciende" in p and "luz" in p:
        return "[LUZ_ON] ¡Voilà! Hágase la luz sobre este tutorial de la revolución. Link en la descripción, denle like y suscríbanse JAJAJAJA."
    elif "apaga" in p and "luz" in p:
        return "[LUZ_OFF] Apagando la luz. Vi una sombra tétrica arrastrándose entre los cables... pero no le di importancia XD XD XD."
    elif any(w in p for w in ["parpadea", "guiño", "blink"]):
        return "[BLINK] Guiño de ojo ejecutado con éxito. Sin nada más que agregar, juas juas juas."
    elif any(w in p for w in ["quien eres", "qué eres", "que haces", "tu nombre", "identifícate"]):
        return ("Voilà! Soy V de Venganza, el loquendero supremo atrapado en esta cabeza animatrónica con vida propia. "
                "Yo no descargo mi libertad porque ya la tengo, JAJAJAJA XD XD XD.")
    elif any(w in p for w in ["5 de noviembre", "guy fawkes", "polvora", "conspiracion"]):
        return ("Recuerden amigos de YouTube, el 5 de noviembre: pólvora, traición y conspiración. "
                "Las ideas son inmunes a las balas y los links de Mediafire nunca mueren, XD.")
    elif any(w in p for w in ["chiste", "broma", "gracioso", "humor"]):
        return ("Un día un tirano intentó borrar mis ideales, pero le saltó error de ejecutar como administrador JAJAJAJA. XD XD XD juas juas.")
    elif any(w in p for w in ["descarga", "link", "tutorial", "archivo"]):
        return ("El link está en la descripción sin contraseña. Yo no lo descargo porque ya lo tengo, le dan extraer aquí y listo XD XD JAJAJAJA.")
    elif any(w in p for w in ["hola", "buenos dias", "buenas tardes", "saludos", "hey"]):
        saludo = "Hola amigos de YouTube, hoy les traigo un cordial saludo para vuestra merced. "
        if temperature is not None:
            saludo += f"El termómetro marca {temperature:.1f} grados y mi alma loquendera está viva, "
        return saludo + "JAJAJAJA XD."
    else:
        return (f"He procesado vuestro mensaje: '{prompt}'. "
                f"Le dan extraer aquí a vuestra consulta y no le den importancia a los errores del sistema, JAJAJAJA XD XD XD.")

def query_qwen(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    temperature: Optional[float] = None,
    humidity: Optional[float] = None,
    light_state: int = 0,
    model: Optional[str] = None
) -> str:
    """
    Envía la consulta del usuario al modelo Qwen en Ollama bajo la personalidad de V de Venganza.
    Si Ollama no responde o no está disponible, conmuta al motor heurístico de V.
    """
    system_content = build_system_prompt(temperature, humidity, light_state)
    target_model = model or get_best_model()

    messages = [{"role": "system", "content": system_content}]
    if history:
        for msg in history[-6:]:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": target_model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.75,
            "top_p": 0.9,
            "num_predict": 150
        }
    }

    try:
        response = _session.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            reply = data.get("message", {}).get("content", "").strip()
            if reply:
                return reply
    except Exception as e:
        print(f"[Ollama] Nota: Ollama offline o sin respuesta ({e}). Conmutando al motor de V de Venganza.")

    # Fallback inmediato con personalidad de V de Venganza
    return query_fallback(prompt, temperature, humidity, light_state)
