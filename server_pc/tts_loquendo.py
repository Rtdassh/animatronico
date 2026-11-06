import requests
import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urlencode

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

VOICES = {
    "jorge": {
        "name": "Jorge (España)",
        "engine": 2,
        "voice": 6,
        "language": 2
    },
    "carlos": {
        "name": "Carlos (Latinoamérica)",
        "engine": 2,
        "voice": 1,
        "language": 14
    },
    "carmen": {
        "name": "Carmen (España)",
        "engine": 2,
        "voice": 5,
        "language": 2
    }
}

def build_hash(text: str, engine: int, voice: int, language: int) -> str:
    """Genera el hash MD5 requerido por la pasarela de Oddcast."""
    fragments = [
        f"<engineID>{engine}</engineID>",
        f"<voiceID>{voice}</voiceID>",
        f"<langID>{language}</langID>",
        "<ext>mp3</ext>",
        text
    ]
    raw = "".join(fragments)
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

def get_chunk_audio(text: str, engine: int, voice: int, language: int) -> bytes:
    """Descarga un fragmento individual sintetizado por Loquendo."""
    file_hash = build_hash(text, engine, voice, language)
    params = {
        'engine': engine,
        'language': language,
        'voice': voice,
        'text': text,
        'useUTF8': 1
    }
    url = f"https://cache-a.oddcast.com/c_fs/{file_hash}.mp3?{urlencode(params)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.oddcast.com/'
    }
    
    response = requests.get(url, headers=headers, timeout=20)
    if response.status_code == 200 and len(response.content) > 500:
        return response.content
    raise RuntimeError(f"Error al sintetizar fragmento (Status {response.status_code}, tamaño {len(response.content)})")

def split_text_into_chunks(text: str, max_chars: int = 280) -> list[str]:
    """Divide textos largos en oraciones para no exceder los límites de caracteres de Loquendo."""
    text = text.strip()
    if not text:
        return []
    
    # Separar por signos de puntuación o saltos de línea
    sentences = re.split(r'([.!?;:\n]+)', text)
    chunks = []
    current = ""
    
    for i in range(0, len(sentences), 2):
        s = sentences[i].strip()
        punct = sentences[i+1].strip() if i+1 < len(sentences) else ""
        piece = (s + " " + punct).strip()
        if not piece:
            continue
            
        if len(current) + len(piece) + 1 <= max_chars:
            current = (current + " " + piece).strip()
        else:
            if current:
                chunks.append(current)
            if len(piece) > max_chars:
                # Si una sola oración excede el límite, dividir por palabras
                words = piece.split()
                sub = ""
                for w in words:
                    if len(sub) + len(w) + 1 <= max_chars:
                        sub = (sub + " " + w).strip()
                    else:
                        if sub:
                            chunks.append(sub)
                        sub = w
                current = sub
            else:
                current = piece
                
    if current:
        chunks.append(current)
    return chunks

def generate_loquendo_speech(text: str, voice_key: str = "jorge") -> tuple[bytes, str]:
    """
    Sintetiza el texto completo utilizando la voz de Loquendo seleccionada.
    Incluye caché en disco para optimizar latencia en frases idénticas.
    Retorna una tupla: (audio_bytes, cache_filename).
    """
    vk = voice_key.lower().strip()
    voice_config = VOICES.get(vk, VOICES["jorge"])
    engine = voice_config["engine"]
    voice = voice_config["voice"]
    language = voice_config["language"]

    # Verificar caché en disco
    cache_key = hashlib.md5(f"{vk}:{text}".encode('utf-8')).hexdigest()
    filename = f"loquendo_{cache_key}.mp3"
    cache_path = AUDIO_DIR / filename

    if cache_path.exists() and cache_path.stat().st_size > 1000:
        with open(cache_path, "rb") as f:
            return f.read(), filename

    chunks = split_text_into_chunks(text)
    if not chunks:
        return b"", filename

    audio_parts = []
    for chunk in chunks:
        audio = get_chunk_audio(chunk, engine, voice, language)
        audio_parts.append(audio)

    combined_audio = b"".join(audio_parts)

    # Guardar en caché
    try:
        with open(cache_path, "wb") as f:
            f.write(combined_audio)
    except Exception:
        pass

    return combined_audio, filename

