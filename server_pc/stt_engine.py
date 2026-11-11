"""Voz a texto con cadena de motores: el más preciso disponible primero, Vosk offline al final.

Motores (orden configurable con STT_ENGINES, por defecto "google,vosk"):
  - whisper: Whisper local con faster-whisper (opcional; requiere instalarlo y, para GPU, CUDA).
  - groq:   Whisper large-v3-turbo en Groq (opcional). Requiere GROQ_API_KEY.
  - google: API web de Google Speech (gratuita, sin clave). Buena precisión en español.
  - vosk:   Modelo local offline. Respaldo cuando no hay internet.
"""
import io
import os
import wave

import requests

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MAX_AUDIO_BYTES = 2_000_000
ONLINE_TIMEOUT = float(os.getenv("STT_TIMEOUT", "6"))


class EngineUnavailable(Exception):
    """El motor no está disponible (sin red, sin clave, error del servicio); se prueba el siguiente."""


def _internet_allowed() -> bool:
    return (os.getenv("ANIMATRONICO_LOCAL_NETWORK") != "1" or
            os.getenv("ANIMATRONICO_INTERNET_SHARED") == "1")


def _read_wav(audio_bytes: bytes):
    if not audio_bytes or len(audio_bytes) < 100:
        raise ValueError("El archivo de audio está vacío o es demasiado corto.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError("Audio demasiado largo; máximo 60 segundos a 16 kHz.")
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2:
                raise ValueError("Se requiere WAV PCM mono de 16 bits.")
            return audio.readframes(audio.getnframes()), audio.getframerate()
    except (wave.Error, EOFError) as exc:
        raise ValueError("El audio no es un WAV válido.") from exc


def _groq(audio_bytes, pcm, rate, language):
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise EngineUnavailable("sin GROQ_API_KEY")
    try:
        response = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
            files={"file": ("frase.wav", audio_bytes, "audio/wav")},
            data={"model": os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo"),
                  "language": language.split("-")[0], "temperature": "0",
                  "response_format": "json"},
            timeout=ONLINE_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise EngineUnavailable(str(exc)) from exc
    return response.json().get("text", "").strip()


def _google(audio_bytes, pcm, rate, language):
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    recognizer.operation_timeout = ONLINE_TIMEOUT
    try:
        return recognizer.recognize_google(sr.AudioData(pcm, rate, 2), language=language).strip()
    except sr.UnknownValueError:
        return ""  # Google respondió, pero no oyó voz: no tiene sentido probar otro motor.
    except (sr.RequestError, OSError) as exc:
        raise EngineUnavailable(str(exc)) from exc


def _whisper(audio_bytes, pcm, rate, language):
    import whisper_local
    if not whisper_local.available():
        raise EngineUnavailable("faster-whisper no instalado")
    try:
        return whisper_local.transcribe(pcm, rate, language)
    except Exception as exc:
        raise EngineUnavailable(str(exc)) from exc


def _vosk(audio_bytes, pcm, rate, language):
    from local_speech import transcribe
    try:
        return transcribe(audio_bytes, language)
    except RuntimeError as exc:
        raise EngineUnavailable(str(exc)) from exc


ENGINES = {"whisper": _whisper, "groq": _groq, "google": _google, "vosk": _vosk}
ONLINE = {"groq", "google"}


def engine_order():
    raw = os.getenv("STT_ENGINES", "whisper,google,vosk")
    names = [n.strip().lower() for n in raw.split(",")]
    return [n for n in names if n in ENGINES]


def transcribe(audio_bytes: bytes, language: str = None):
    """Devuelve (texto, motor). Texto vacío = silencio. RuntimeError si ningún motor está disponible."""
    language = language or os.getenv("STT_LANGUAGE", "es-MX")
    pcm, rate = _read_wav(audio_bytes)
    errors = []
    for name in engine_order():
        if name in ONLINE and not _internet_allowed():
            continue
        try:
            return ENGINES[name](audio_bytes, pcm, rate, language), name
        except EngineUnavailable as exc:
            errors.append(f"{name}: {exc}")
            print(f"[STT] {name} no disponible ({exc}); probando el siguiente.", flush=True)
    raise RuntimeError("Ningún motor de voz disponible. " + "; ".join(errors))


def speech_status():
    from local_speech import speech_status as vosk_status
    available = []
    for name in engine_order():
        if name == "whisper":
            import whisper_local
            if not whisper_local.available():
                continue
        if name == "groq" and (not os.getenv("GROQ_API_KEY") or not _internet_allowed()):
            continue
        if name == "google" and not _internet_allowed():
            continue
        if name == "vosk" and not vosk_status()["ready"]:
            continue
        available.append(name)
    primary = available[0] if available else None
    return {"engine": primary, "engines": available, "ready": bool(available), "local": primary == "vosk"}


def transcribe_audio_bytes(audio_bytes: bytes, language: str = None) -> str:
    text, _ = transcribe(audio_bytes, language)
    if not text:
        raise ValueError("No se entendió el audio. Acerca el micrófono e intenta de nuevo.")
    return text
