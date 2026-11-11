import io
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from serial_bridge import SerialHardwareBridge
from unified import create_router
from local_speech import transcribe

def test_full_hardware_frame_and_expiration():
    bridge = SerialHardwareBridge()
    bridge._process_line('TELEMETRIA UNO: S,215,590,11,60,45,1,100,0,3,72,0,64')
    frame = bridge.snapshot()
    assert frame['received'] and frame['serialErrors'] == 3
    assert frame['lm'] and frame['pca'] and not frame['lcd']
    bridge._last_frame = time.monotonic() - 7
    assert bridge.snapshot()['frameAgeMs'] >= 7000

def test_old_combined_orders_fit_uno_and_separate_mouth():
    orders = SerialHardwareBridge.normalize('CMD:M=120,EH=100,EV=80,B=1,L=1')
    assert orders == ['CMD:EH=100,EV=80', 'S6:120', 'BLINK', 'LIGHT:1']
    assert all(len(order) <= 31 for order in orders)

def test_routes_use_same_origin_and_no_false_success():
    app = FastAPI()
    app.include_router(create_router(lambda: None))
    with TestClient(app) as client:
        page = client.get('/hardware')
        assert page.status_code == 200
        assert '/api/hardware/status' in page.text
        assert '/api/hardware/cmd' in page.text
        assert client.get('/api/hardware/cmd?c=PING').json()['ok'] is False
        assert client.get('/api/hardware/status').json()['connected'] is False
        assert client.post('/api/transcribe', files={'audio': ('bad.wav', b'bad')}).status_code == 422

def test_silence_is_empty_and_does_not_query_ai():
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b'\x00\x00' * 16000)
    assert transcribe(output.getvalue()) == ''

def test_two_online_voice_failures_keep_local_audio(monkeypatch):
    import app as backend
    import offline_tts
    calls = []
    def unavailable(*args, **kwargs):
        calls.append(kwargs.get('allow_network'))
        raise RuntimeError('Servicio de voz sin conexión')
    monkeypatch.setenv('ANIMATRONICO_LOCAL_NETWORK', '1')
    monkeypatch.setenv('ANIMATRONICO_INTERNET_SHARED', '0')
    monkeypatch.setattr(backend, 'generate_loquendo_speech', unavailable)
    monkeypatch.setattr(offline_tts, 'generate', lambda text: (b'RIFF-local', 'local.wav', 'audio/wav'))
    for text in ('Primera consulta', 'Segunda consulta'):
        assert backend.synthesize_speech(text, 'jorge') == (b'RIFF-local', 'local.wav', 'audio/wav')
    assert calls == [False, False]

def test_second_audio_query_keeps_model_answer_when_online_voice_fails(monkeypatch):
    import app as backend
    import offline_tts
    monkeypatch.setattr(backend, 'transcribe_audio_bytes', lambda *args: 'Dime la temperatura')
    monkeypatch.setattr(backend, 'query_qwen', lambda **kwargs: 'La temperatura es 21 grados.')
    monkeypatch.setattr(backend, 'generate_loquendo_speech', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('Sin internet')))
    monkeypatch.setattr(offline_tts, 'generate', lambda text: (b'RIFF-local', 'local.wav', 'audio/wav'))
    client = TestClient(backend.app)
    for _ in range(2):
        response = client.post('/api/process-audio', data={'voice': 'jorge', 'history_json': '[]'},
                               files={'audio': ('consulta.wav', b'audio-transcrito-por-el-mock', 'audio/wav')})
        assert response.status_code == 200, response.text
        assert response.json()['speech_text'] == 'La temperatura es 21 grados.'
        assert response.json()['audio_base64'].startswith('data:audio/wav;base64,')

def test_loquendo_bgm_audio_served_and_index_structure():
    import app as backend
    client = TestClient(backend.app)
    # Verificar que tanto la ruta .m4a como .mp4 responden OK
    for ext in ['mp4', 'm4a']:
        res = client.get(f'/audio/musica_loquendo.{ext}')
        assert res.status_code == 200
        assert res.headers.get('content-type') == 'audio/mp4'
        assert len(res.content) > 100000

    # Verificar que el botón de luz fue retirado y el elemento de música de fondo está presente
    index_res = client.get('/')
    assert index_res.status_code == 200
    assert 'btnToggleLight' not in index_res.text
    assert 'id="loquendoBgm"' in index_res.text
    assert 'musica_loquendo' in index_res.text
