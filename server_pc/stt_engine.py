import speech_recognition as sr
import io
import wave
import tempfile
import os

recognizer = sr.Recognizer()

def transcribe_audio_bytes(audio_bytes: bytes, language: str = "es-MX") -> str:
    from local_speech import transcribe
    text = transcribe(audio_bytes, language)
    if not text:
        raise ValueError("No se entendió el audio. Acerca el micrófono e intenta de nuevo.")
    return text

def transcribe_audio_bytes_online(audio_bytes: bytes, language: str = "es-MX") -> str:
    """
    Recibe los bytes de un archivo WAV de audio enviado desde el celular (16kHz PCM)
    y realiza el reconocimiento de voz a texto (STT) en español.
    """
    if not audio_bytes or len(audio_bytes) < 100:
        raise ValueError("El archivo de audio está vacío o es demasiado corto.")

    # Guardar en archivo temporal para que SpeechRecognition lo procese como AudioFile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_path = tmp_file.name

    try:
        with sr.AudioFile(tmp_path) as source:
            # Ajustar para reducir ruido ambiental si es necesario
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            audio_data = recognizer.record(source)

        # Transcribir usando Google Speech Recognition (soporte en español de alta precisión)
        text = recognizer.recognize_google(audio_data, language=language)
        return text.strip()
    except sr.UnknownValueError:
        # Reintentar con español de España si es-MX falla
        try:
            with sr.AudioFile(tmp_path) as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="es-ES")
            return text.strip()
        except Exception:
            raise ValueError("No se pudo entender el audio. Por favor intenta hablar más claro o más cerca del micrófono.")
    except sr.RequestError as e:
        raise RuntimeError(f"Error al conectar con el servicio de reconocimiento de voz: {e}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

