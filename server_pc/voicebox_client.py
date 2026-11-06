import requests
import time
import hashlib
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

VOICEBOX_URL = os.environ.get("VOICEBOX_URL", "http://127.0.0.1:17493")

def is_voicebox_running() -> bool:
    """Verifica si el servidor local de Voicebox está disponible en el puerto 17493."""
    try:
        r = requests.get(f"{VOICEBOX_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def get_voicebox_profiles() -> List[Dict[str, Any]]:
    """Obtiene la lista de perfiles registrados dinámicamente en el servidor local de Voicebox."""
    try:
        r = requests.get(f"{VOICEBOX_URL}/profiles", timeout=3)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []

def get_default_profile_id() -> Optional[str]:
    """Obtiene el ID del perfil de voz por defecto o del entorno."""
    env_id = os.environ.get("VOICEBOX_PROFILE_ID")
    if env_id:
        return env_id
    profiles = get_voicebox_profiles()
    if profiles:
        return profiles[0].get("id")
    return None

def generate_voicebox_speech(
    text: str,
    profile_id: Optional[str] = None,
    language: str = "es",
    engine: str = "qwen",
    timeout: int = 150
) -> tuple[bytes, str]:
    """
    Esqueleto de integración con el motor Voicebox para generación de voz neuronal.
    Detecta dinámicamente el perfil local activo sin almacenar datos privados en el repositorio.
    Retorna: (audio_bytes, filename).
    """
    target_profile = profile_id or get_default_profile_id()
    if not target_profile:
        raise RuntimeError("No se detectó ningún perfil de voz configurado en Voicebox.")

    cache_key = hashlib.md5(f"voicebox:{target_profile}:{text}".encode('utf-8')).hexdigest()
    filename = f"voicebox_{cache_key}.wav"
    cache_path = AUDIO_DIR / filename

    # Si ya está en caché local temporal, devolverlo inmediatamente
    if cache_path.exists() and cache_path.stat().st_size > 1000:
        with open(cache_path, "rb") as f:
            return f.read(), filename

    payload = {
        "profile_id": target_profile,
        "text": text,
        "language": language,
        "engine": engine
    }

    try:
        response = requests.post(f"{VOICEBOX_URL}/generate", json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        gen_id = data.get("id")
    except Exception as e:
        raise RuntimeError(f"Error al enviar solicitud a Voicebox: {e}")

    # Polling hasta que la generación esté lista
    start_time = time.time()
    disk_path = os.path.expandvars(rf"%APPDATA%\sh.voicebox.app\generations\{gen_id}.wav")

    while time.time() - start_time < timeout:
        time.sleep(0.8)

        # 1. Verificar directamente en disco para latencia mínima
        if os.path.exists(disk_path) and os.path.getsize(disk_path) > 1000:
            try:
                with open(disk_path, "rb") as f:
                    audio_bytes = f.read()
                with open(cache_path, "wb") as f:
                    f.write(audio_bytes)
                return audio_bytes, filename
            except Exception:
                pass

        # 2. Verificar vía API REST
        try:
            status_res = requests.get(f"{VOICEBOX_URL}/history/{gen_id}", timeout=3)
            if status_res.status_code == 200:
                s_data = status_res.json()
                if s_data.get("status") == "completed":
                    audio_res = requests.get(f"{VOICEBOX_URL}/audio/{gen_id}", timeout=10)
                    if audio_res.status_code == 200 and len(audio_res.content) > 1000:
                        audio_bytes = audio_res.content
                        with open(cache_path, "wb") as f:
                            f.write(audio_bytes)
                        return audio_bytes, filename
                elif s_data.get("status") == "failed":
                    raise RuntimeError(f"Voicebox falló al generar audio: {s_data.get('error')}")
        except Exception:
            pass

    raise TimeoutError(f"La generación de voz en Voicebox tardó más de {timeout} segundos.")
