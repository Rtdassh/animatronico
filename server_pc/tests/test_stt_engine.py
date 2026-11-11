import io
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest

import stt_engine


def _wav(seconds=0.5):
    out = io.BytesIO()
    with wave.open(out, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b'\x00\x00' * int(16000 * seconds))
    return out.getvalue()


def _fail(*args):
    raise stt_engine.EngineUnavailable('caido')


def test_falls_back_to_next_engine_when_online_fails(monkeypatch):
    monkeypatch.delenv('ANIMATRONICO_LOCAL_NETWORK', raising=False)
    monkeypatch.setitem(stt_engine.ENGINES, 'whisper', _fail)
    monkeypatch.setitem(stt_engine.ENGINES, 'groq', _fail)
    monkeypatch.setitem(stt_engine.ENGINES, 'google', _fail)
    monkeypatch.setitem(stt_engine.ENGINES, 'vosk', lambda *a: 'hola robot')
    assert stt_engine.transcribe(_wav()) == ('hola robot', 'vosk')


def test_uses_first_available_engine(monkeypatch):
    monkeypatch.delenv('ANIMATRONICO_LOCAL_NETWORK', raising=False)
    monkeypatch.setitem(stt_engine.ENGINES, 'whisper', _fail)
    monkeypatch.setitem(stt_engine.ENGINES, 'groq', _fail)
    monkeypatch.setitem(stt_engine.ENGINES, 'google', lambda *a: 'enciende la luz')
    monkeypatch.setitem(stt_engine.ENGINES, 'vosk', lambda *a: pytest.fail('no debería llegar a vosk'))
    assert stt_engine.transcribe(_wav()) == ('enciende la luz', 'google')


def test_skips_online_engines_without_internet(monkeypatch):
    monkeypatch.setenv('ANIMATRONICO_LOCAL_NETWORK', '1')
    monkeypatch.setenv('ANIMATRONICO_INTERNET_SHARED', '0')
    monkeypatch.setitem(stt_engine.ENGINES, 'whisper', _fail)
    monkeypatch.setitem(stt_engine.ENGINES, 'google', lambda *a: pytest.fail('sin internet no se usa google'))
    monkeypatch.setitem(stt_engine.ENGINES, 'vosk', lambda *a: 'modo local')
    assert stt_engine.transcribe(_wav()) == ('modo local', 'vosk')


def test_groq_unavailable_without_key(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    with pytest.raises(stt_engine.EngineUnavailable):
        stt_engine._groq(b'', b'', 16000, 'es-MX')


def test_all_engines_down_raises(monkeypatch):
    monkeypatch.delenv('ANIMATRONICO_LOCAL_NETWORK', raising=False)
    for name in ('whisper', 'groq', 'google', 'vosk'):
        monkeypatch.setitem(stt_engine.ENGINES, name, _fail)
    with pytest.raises(RuntimeError):
        stt_engine.transcribe(_wav())


def test_rejects_invalid_audio():
    with pytest.raises(ValueError):
        stt_engine.transcribe(b'x' * 200)
