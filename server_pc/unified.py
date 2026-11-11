"""Rutas compartidas: panel de hardware y salud de la integración local."""
import asyncio
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from stt_engine import speech_status, transcribe

def create_router(bridge_getter):
    from stt_engine import engine_order
    if 'whisper' in engine_order():
        import whisper_local
        whisper_local.preload_in_background()
    router = APIRouter()

    @router.get('/setup')
    def setup_help(request: Request):
        return RedirectResponse(f'http://{request.url.hostname}:8001/setup')

    @router.get('/hardware', response_class=HTMLResponse)
    def hardware_panel():
        source = (Path(__file__).parents[1] / 'firmware/asistente_esp32/panel.h').read_text(encoding='utf-8')
        page = source.split('R"HTML(', 1)[1].rsplit(')HTML"', 1)[0]
        page = page.replace('/api/status', '/api/hardware/status').replace('/api/cmd', '/api/hardware/cmd')
        return HTMLResponse(page, headers={'Cache-Control': 'no-store'})

    @router.get('/api/hardware/status')
    def hardware_status():
        bridge = bridge_getter()
        return bridge.snapshot() if bridge else {'connected': False, 'received': False, 'frameAgeMs': 0}

    @router.get('/api/hardware/cmd')
    async def hardware_command(c: str):
        bridge = bridge_getter()
        if not bridge:
            return {'ok': False, 'ack': 'ESP32_DESCONECTADO'}
        return await asyncio.to_thread(bridge.request_command, c)

    @router.get('/api/speech/status')
    def speech_health():
        return speech_status()

    @router.get('/api/network')
    def network_status():
        return {'shared': os.getenv('ANIMATRONICO_INTERNET_SHARED') == '1', 'via': 'esp32'}

    @router.post('/api/transcribe')
    async def transcribe_mobile(audio: UploadFile = File(...)):
        content = await audio.read(2_000_001)
        try:
            text, engine = await asyncio.to_thread(transcribe, content)
            return {'text': text, 'engine': engine, 'local': engine == 'vosk'}
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc

    return router
