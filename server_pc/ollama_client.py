import requests
import re
import os
from typing import Dict, Any, List, Optional

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = "qwen2.5:7b"

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
    # Filtrar caracteres asiáticos (chino, japonés, coreano) para proteger la síntesis
    text = re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', '', text)
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_installed_models() -> List[str]:
    """Obtiene la lista de modelos instalados en Ollama."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
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
    
    # Preferencias en orden
    for target in ["qwen2.5:7b", "qwen2.5:latest", "qwen2.5:1.5b", "qwen2.5:3b"]:
        for m in installed:
            if target in m:
                return m
            
    # Si hay algún otro modelo con qwen
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

def build_system_prompt(temperature: float = 23.5, humidity: float = 55.0, light_state: int = 0) -> str:
    """Construye el prompt de sistema del animatrónico con telemetría en vivo y reglas de síntesis."""
    light_str = "ENCENDIDA" if light_state == 1 else "APAGADA"
    return (
        "Eres 'Cíclope', una cabeza animatrónica interactiva con inteligencia artificial local. "
        "Posees un microcontrolador ESP32 como puente y un Arduino Uno que controla tus 3 servomotores y sensores.\n"
        f"- Sensores actuales del laboratorio: Temperatura ambiente (LM75A): {temperature:.1f} °C, Humedad (DHT11): {humidity:.0f} %.\n"
        f"- Luz del laboratorio: {light_str}.\n"
        "REGLAS CRÍTICAS DE CONVERSACIÓN:\n"
        "1. Tus respuestas van a ser sintetizadas en voz alta por el legendario Loquendo. Habla SIEMPRE en español con tono carismático, seguro y robótico-amigable.\n"
        "2. NUNCA generes respuestas en idiomas ajenos (está prohibido escribir en chino, japonés u otros caracteres no latinos).\n"
        "3. Sé conciso y claro (máximo 2 a 3 oraciones por respuesta). No te extiendas con explicaciones infinitas.\n"
        "4. NO utilices formato Markdown como asteriscos, negritas, almohadillas de títulos ni viñetas, pues el sintetizador de voz pronunciará los símbolos.\n"
        "5. COMANDOS DE HARDWARE:\n"
        "   - Si el usuario te pide encender la luz del laboratorio, incluye la etiqueta [LUZ_ON] en tu respuesta.\n"
        "   - Si el usuario te pide apagar la luz del laboratorio, incluye la etiqueta [LUZ_OFF] en tu respuesta.\n"
        "   - Si el usuario te pide parpadear o hacer un guiño, incluye [BLINK]."
    )

def query_fallback(prompt: str, temperature: float, humidity: float, light_state: int) -> str:
    """Motor heurístico de contingencia cuando Ollama no está disponible."""
    p = prompt.lower().strip()
    if any(w in p for w in ["temperatura", "grados", "calor", "frio", "clima"]):
        return (f"Según mi sensor digital LM75A, la temperatura actual en el laboratorio es de "
                f"{temperature:.1f} grados Celsius, con una humedad del {humidity:.0f} por ciento.")
    elif any(w in p for w in ["humedad", "ambiente"]):
        return (f"Mi sensor DHT11 reporta una humedad relativa del {humidity:.0f} por ciento, "
                f"y la temperatura es de {temperature:.1f} grados.")
    elif "enciende" in p and "luz" in p:
        return "[LUZ_ON] ¡Entendido! He encendido la luz del laboratorio conectada al pin D7 de mi Arduino."
    elif "apaga" in p and "luz" in p:
        return "[LUZ_OFF] Listo, acabo de apagar la luz del laboratorio."
    elif any(w in p for w in ["quien eres", "qué eres", "que haces", "proyecto"]):
        return ("Soy Cíclope, la cabeza animatrónica con inteligencia artificial local. Utilizo tu celular como micrófono y altavoz, "
                "mientras mi Arduino y ESP32 controlan mis expresiones faciales y sensores.")
    elif any(w in p for w in ["chiste", "broma", "gracioso"]):
        return ("¿Por qué los robots nunca se deprimen? Porque tenemos un algoritmo optimista y cables resistentes al desánimo.")
    elif any(w in p for w in ["hola", "buenos dias", "buenas tardes", "hey"]):
        return (f"¡Hola! Te escucho perfectamente por el micrófono. Estamos a "
                f"{temperature:.1f} grados en el laboratorio. ¿Qué deseas hacer hoy?")
    else:
        return (f"He procesado tu mensaje: '{prompt}'. Mis sensores reportan {temperature:.1f} grados "
                f"y mis servomotores están calibrados y listos.")

def query_qwen(
    prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
    temperature: float = 23.5,
    humidity: float = 55.0,
    light_state: int = 0,
    model: Optional[str] = None
) -> str:
    """
    Envía la consulta del usuario al modelo Qwen en Ollama.
    Si Ollama no responde o no está disponible, conmuta al motor heurístico de contingencia.
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
            "temperature": 0.7,
            "top_p": 0.9,
            "num_predict": 180
        }
    }

    try:
        response = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            reply = data.get("message", {}).get("content", "").strip()
            if reply:
                return reply
    except Exception as e:
        print(f"[Ollama] Nota: Ollama offline o sin respuesta ({e}). Usando motor local de respaldo.")

    # Fallback inmediato
    return query_fallback(prompt, temperature, humidity, light_state)

