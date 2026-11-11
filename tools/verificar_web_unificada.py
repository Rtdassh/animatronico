"""Prueba HTTPS real, hardware, STT y video; no necesita el micrófono del usuario."""
import argparse
import io
import json
import time
import wave
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='https://127.0.0.1:8443')
    parser.add_argument('--vision', action='store_true')
    parser.add_argument('--chat', action='store_true')
    args = parser.parse_args()
    session = requests.Session()
    session.trust_env = False
    session.verify = str(ROOT / 'server_pc/certs/asistente-ca.crt')
    report = {}
    def get(path):
        response = session.get(args.url + path, timeout=15)
        response.raise_for_status()
        return response
    def post(path, **kwargs):
        response = session.post(args.url + path, timeout=180, **kwargs)
        response.raise_for_status()
        return response
    page = get('/').text
    assert 'hardwareWorkspace' in page and 'local-speech.js' in page
    assert '/api/hardware/status' in get('/hardware').text
    report['httpsVerified'] = True
    report['speech'] = get('/api/speech/status').json()
    assert report['speech']['ready']
    status = get('/api/hardware/status').json()
    assert status['connected'] and status['serialErrors'] == 0, status
    for _ in range(12):
        assert get('/api/hardware/cmd?c=PING').json() == {'ok': True, 'ack': 'PONG'}
    report['hardwarePings'] = 12
    report['hardware'] = get('/api/hardware/status').json()
    assert report['hardware']['serialErrors'] == 0
    report['backend'] = get('/api/status').json()
    # Generar una frase conocida, convertirla al formato exacto que envía el celular.
    spoken = get('/api/tts?text=Hola%20como%20estas&voice=windows_local').content
    with wave.open(io.BytesIO(spoken), 'rb') as audio:
        channels, rate, width = audio.getnchannels(), audio.getframerate(), audio.getsampwidth()
        assert width == 2
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').reshape(-1, channels).mean(axis=1)
    resized = np.interp(np.arange(0, len(samples), rate/16000), np.arange(len(samples)), samples).astype('<i2')
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000); audio.writeframes(resized.tobytes())
    report['transcription'] = post('/api/transcribe', files={'audio': ('prueba.wav', output.getvalue(), 'audio/wav')}).json()
    assert report['transcription']['text'], report
    if args.chat:
        reply = post('/api/chat', json={'text': 'Dime brevemente la temperatura actual.', 'voice': 'windows_local', 'history': []}).json()
        assert reply.get('speech_text') and len(reply.get('audio_base64', '')) > 1000
        report['chat'] = {'text': reply['speech_text'], 'audioBytes': len(reply['audio_base64'])}
    if args.vision:
        try:
            assert post('/api/vision/start').json()['active']
            time.sleep(2)
            with session.get(args.url+'/api/vision/video_feed', stream=True, timeout=10) as video:
                frame = next(video.iter_content(chunk_size=16384))
                assert b'\xff\xd8' in frame, 'No llegó una imagen JPEG'
                report['videoBytes'] = len(frame)
            report['vision'] = get('/api/vision/status').json()
            assert report['vision']['running'] and report['vision']['capture_fps'] > 0
        finally:
            post('/api/vision/stop')
    report['finalHardware'] = get('/api/hardware/status').json()
    (ROOT / 'build/verificacion-web-unificada.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, indent=2, ensure_ascii=True), flush=True)

if __name__ == '__main__':
    main()
