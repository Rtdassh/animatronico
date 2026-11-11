"""Reconocimiento Vosk local: WAV PCM mono a 16 kHz, sin servicios externos."""
import io
import json
import os
import threading
import wave
from pathlib import Path

MODEL_PATH = Path(os.getenv("VOSK_MODEL_PATH", str(Path(__file__).parent / "models" / "vosk-model-small-es-0.42")))
_model = None
_lock = threading.Lock()

def speech_status():
    return {"engine": "vosk", "ready": (MODEL_PATH / "am" / "final.mdl").exists(), "local": True}

def transcribe(audio_bytes, language="es"):
    global _model
    if not speech_status()["ready"]:
        raise RuntimeError("Falta el modelo Vosk español. Ejecuta tools/preparar_web_unificada.py --download-model")
    if len(audio_bytes) > 2_000_000:
        raise ValueError("Audio demasiado largo; máximo 60 segundos a 16 kHz.")
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
                raise ValueError("Se requiere WAV PCM mono de 16 bits a 16000 Hz.")
            pcm = audio.readframes(audio.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError("El audio no es un WAV válido.") from exc
    from vosk import Model, KaldiRecognizer, SetLogLevel
    with _lock:
        if _model is None:
            SetLogLevel(-1)
            _model = Model(str(MODEL_PATH))
    recognizer = KaldiRecognizer(_model, 16000)
    parts = []
    for offset in range(0, len(pcm), 8000):
        if recognizer.AcceptWaveform(pcm[offset:offset+8000]):
            parts.append(json.loads(recognizer.Result()).get("text", ""))
    parts.append(json.loads(recognizer.FinalResult()).get("text", ""))
    return " ".join(filter(None, parts)).strip()
