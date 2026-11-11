"""Voz Windows disponible sin internet; los archivos se reproducen en el celular."""
import hashlib
import subprocess
import sys
import threading
from pathlib import Path

_lock = threading.Lock()
SCRIPT = Path(__file__).with_name('speak_local.ps1')

def generate(text):
    if sys.platform != 'win32':
        raise RuntimeError('La voz Windows requiere Windows; selecciona una voz Voicebox local.')
    folder = Path(__file__).with_name('audio')
    key = hashlib.sha256(text.encode()).hexdigest()[:24]
    output = folder / f'windows_{key}.wav'
    with _lock:
        if not output.exists():
            source = folder / f'windows_{key}.txt'
            source.write_text(text, encoding='utf-8-sig')
            try:
                subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                str(SCRIPT), '-TextFile', str(source), '-OutputFile', str(output)],
                               check=True, capture_output=True, timeout=60,
                               creationflags=subprocess.CREATE_NO_WINDOW)
            finally:
                source.unlink(missing_ok=True)
    return output.read_bytes(), output.name, 'audio/wav'
