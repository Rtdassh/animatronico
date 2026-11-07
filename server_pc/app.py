#!/usr/bin/env python3
"""
=============================================================================
SERVIDOR CENTRAL DE INTELIGENCIA ARTIFICIAL, VOZ Y HARDWARE ANIMATRÓNICO
Proyecto: Cabeza Animatrónica con IA Local
Plataforma: PC Local (FastAPI + Ollama / Qwen 2.5 + Loquendo TTS + WebSockets)
=============================================================================
"""

import os
import re
import json
import uuid
import base64
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ollama_client import query_qwen, clean_for_speech, check_ollama, get_best_model
from tts_loquendo import generate_loquendo_speech, VOICES, AUDIO_DIR
from stt_engine import transcribe_audio_bytes
from voicebox_client import generate_voicebox_speech, is_voicebox_running, get_voicebox_profiles

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="animatronico · Servidor Inteligente",
    description="Servidor local con Ollama (Qwen 2.5), TTS y control cinemático ESP32/Arduino.",
    version="2.0"
)

# Permitir CORS para conexiones desde la red local y túneles seguros HTTPS (Cloudflare)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# ESTADO GLOBAL DEL SISTEMA EN MEMORIA
# -----------------------------------------------------------------------------
class SystemState:
    temperature: float = 23.5  # Lectura LM75A (°C)
    humidity: float = 55.0     # Lectura DHT11 (% RH)
    light_state: int = 0       # 0: Apagada, 1: Encendida (Pin D7)
    mouth_angle: int = 90      # 90° cerrada a 130° abierta
    eyes_angle: int = 90       # 60° a 120°
    esp32_connected: bool = False
    mobile_connected: bool = False
    esp32_socket: Optional[WebSocket] = None
    mobile_sockets: List[WebSocket] = []

state = SystemState()

# -----------------------------------------------------------------------------
# MODELOS DE DATOS PYDANTIC
# -----------------------------------------------------------------------------
class ChatRequest(BaseModel):
    text: str
    voice: str = "jorge"
    history: List[Dict[str, str]] = []

class ControlRequest(BaseModel):
    mouth: int = 90
    eyes: int = 90
    blink: int = 0
    light: int = -1

# -----------------------------------------------------------------------------
# HELPERS DE CONTROL DE HARDWARE
# -----------------------------------------------------------------------------
async def apply_hardware_tags(text: str) -> bool:
    """Detecta etiquetas como [LUZ_ON], [LUZ_OFF], [BLINK] en la respuesta de la IA y actualiza hardware."""
    changed = False
    blink = 0

    if "[LUZ_ON]" in text:
        state.light_state = 1
        changed = True
    elif "[LUZ_OFF]" in text:
        state.light_state = 0
        changed = True

    if "[BLINK]" in text:
        blink = 1

    if state.esp32_socket and (changed or blink == 1):
        cmd = f"CMD:M={state.mouth_angle},E={state.eyes_angle},B={blink},L={state.light_state}\n"
        try:
            await state.esp32_socket.send_text(cmd)
        except Exception:
            pass

    if changed:
        await broadcast_to_mobile({
            "type": "telemetry",
            "temperature": state.temperature,
            "humidity": state.humidity,
            "light_state": state.light_state
        })

    return changed

def sanitize_ai_reply(text: str) -> str:
    """Elimina etiquetas de control de hardware para que no se pronuncien por voz."""
    clean = re.sub(r'\[LUZ_ON\]|\[LUZ_OFF\]|\[BLINK\]|\[SERVO_[^\]]+\]', '', text)
    return clean_for_speech(clean)

def synthesize_speech(text: str, voice_key: str = "jorge") -> tuple[bytes, str, str]:
    """
    Sintetiza la voz utilizando Voicebox (esqueleto dinámico) o Loquendo (Jorge, Carlos, Carmen).
    Retorna: (audio_bytes, audio_filename, media_type).
    """
    vk = voice_key.lower().strip()
    if vk.startswith("voicebox") or vk == "dom":
        profile_id = None
        if "_" in vk:
            profile_id = vk.split("_", 1)[1]
        audio_bytes, audio_filename = generate_voicebox_speech(text, profile_id=profile_id)
        return audio_bytes, audio_filename, "audio/wav"
    else:
        audio_bytes, audio_filename = generate_loquendo_speech(text, voice_key=vk)
        return audio_bytes, audio_filename, "audio/mpeg"

# -----------------------------------------------------------------------------
# RUTAS DE LA API HTTP
# -----------------------------------------------------------------------------
@app.get("/api/status")
async def get_status():
    """Devuelve el estado completo del servidor, telemetría, Ollama y voces disponibles."""
    ollama_info = check_ollama()
    vb_ready = is_voicebox_running()
    voices_dict = {k: v["name"] for k, v in VOICES.items()}
    if vb_ready:
        profiles = get_voicebox_profiles()
        if profiles:
            for p in profiles:
                p_id = p.get("id")
                p_name = p.get("name", "Voz Clonada")
                voices_dict[f"voicebox_{p_id}"] = f"{p_name} (Voicebox IA)"
        else:
            voices_dict["voicebox"] = "Voz Clonada (Voicebox IA)"

    return {
        "status": "online",
        "temperature": state.temperature,
        "humidity": state.humidity,
        "light_state": state.light_state,
        "mouth_angle": state.mouth_angle,
        "eyes_angle": state.eyes_angle,
        "esp32_connected": state.esp32_connected,
        "mobile_connected": len(state.mobile_sockets) > 0,
        "ollama_ready": ollama_info["ready"],
        "voicebox_ready": vb_ready,
        "model": ollama_info["model"],
        "available_models": ollama_info["available_models"],
        "voices": voices_dict
    }

@app.post("/api/process-audio")
async def process_audio(
    audio: UploadFile = File(...),
    voice: str = Form("jorge"),
    history_json: str = Form("[]")
):
    """
    Recibe el archivo de audio WAV (16kHz PCM) grabado desde el celular,
    lo transcribe (STT en español), consulta a Qwen 2.5 en Ollama con el contexto
    de telemetría del robot, acciona comandos de hardware si corresponde, y sintetiza
    la respuesta con la voz seleccionada (Loquendo o Voicebox Dom).
    """
    try:
        audio_content = await audio.read()
        if not audio_content:
            raise HTTPException(status_code=400, detail="Archivo de audio vacío.")

        # 1. Reconocimiento de voz a texto (STT)
        transcription = transcribe_audio_bytes(audio_content)

        # 2. Historial de conversación
        try:
            history = json.loads(history_json)
        except Exception:
            history = []

        # 3. Consulta al modelo local Qwen 2.5 vía Ollama
        raw_response = query_qwen(
            prompt=transcription,
            history=history,
            temperature=state.temperature,
            humidity=state.humidity,
            light_state=state.light_state
        )

        # 4. Procesar comandos físicos (Luz, parpadeo, etc.)
        await apply_hardware_tags(raw_response)

        # 5. Limpieza de texto para voz
        speech_text = sanitize_ai_reply(raw_response)
        if not speech_text:
            speech_text = "Comando ejecutado correctamente."

        # 6. Síntesis de voz (Loquendo o Voicebox Dom)
        audio_bytes, audio_filename, media_type = synthesize_speech(speech_text, voice_key=voice)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        return {
            "transcription": transcription,
            "response": raw_response,
            "speech_text": speech_text,
            "audio_url": f"/audio/{audio_filename}",
            "audio_base64": f"data:{media_type};base64,{audio_b64}",
            "light_state": state.light_state
        }

    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        print(f"[Error /api/process-audio] {e}")
        raise HTTPException(status_code=500, detail=f"Error en el servidor: {str(e)}")

@app.post("/api/chat")
async def chat_text(req: ChatRequest):
    """
    Procesa consultas de texto directo o Web Speech API desde la interfaz móvil.
    Consulta al modelo local en Ollama y devuelve la respuesta sintetizada con Loquendo o Voicebox Dom.
    """
    user_text = req.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Texto vacío.")

    try:
        # 1. Consulta al modelo local en Ollama
        raw_response = query_qwen(
            prompt=user_text,
            history=req.history,
            temperature=state.temperature,
            humidity=state.humidity,
            light_state=state.light_state
        )

        # 2. Procesar etiquetas de control físico
        await apply_hardware_tags(raw_response)

        # 3. Limpieza de texto
        speech_text = sanitize_ai_reply(raw_response)
        if not speech_text:
            speech_text = "Comando procesado."

        # 4. Generación de voz (Loquendo o Voicebox Dom)
        audio_bytes, audio_filename, media_type = synthesize_speech(speech_text, voice_key=req.voice)
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        return {
            "user_query": user_text,
            "response": raw_response,
            "speech_text": speech_text,
            "audio_url": f"/audio/{audio_filename}",
            "audio_base64": f"data:{media_type};base64,{audio_b64}",
            "light_state": state.light_state
        }
    except Exception as e:
        print(f"[Error /api/chat] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/control")
async def manual_control(req: ControlRequest):
    """Control manual directo de servomotores y luz desde los deslizadores móviles."""
    state.mouth_angle = max(90, min(130, req.mouth))
    state.eyes_angle = max(60, min(120, req.eyes))
    if req.light in (0, 1):
        state.light_state = req.light

    cmd = f"CMD:M={state.mouth_angle},E={state.eyes_angle},B={req.blink},L={state.light_state}\n"
    if state.esp32_socket:
        try:
            await state.esp32_socket.send_text(cmd)
            return {"status": "ok", "sent_cmd": cmd.strip()}
        except Exception as e:
            return {"status": "error", "detail": str(e)}
    return {"status": "buffered", "note": "ESP32 no conectado aún"}

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """Sirve archivos MP3 cacheados con soporte de streaming HTTP Range para navegadores móviles."""
    safe_name = os.path.basename(filename)
    file_path = AUDIO_DIR / safe_name
    if file_path.exists():
        media_type = "audio/wav" if safe_name.endswith(".wav") else "audio/mpeg"
        return FileResponse(file_path, media_type=media_type, headers={"Accept-Ranges": "bytes"})
    raise HTTPException(status_code=404, detail="Audio no encontrado")

@app.get("/api/tts")
async def get_tts(text: str, voice: str = "jorge"):
    """Generación rápida directa de audio para cualquier texto arbitrario."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Texto vacío")
    cleaned = clean_for_speech(text)
    audio_bytes, _, media_type = synthesize_speech(cleaned, voice_key=voice)
    return Response(content=audio_bytes, media_type=media_type)

# -----------------------------------------------------------------------------
# WEBSOCKET 1: COMUNICACIÓN CON ESP32 DEVKIT V1
# -----------------------------------------------------------------------------
@app.websocket("/ws/animatronic")
async def websocket_esp32_endpoint(websocket: WebSocket):
    """
    Canal de comunicación ultrarrápido con el ESP32 DevKit V1.
    Recibe lecturas 'SENS:T=...,H=...' y envía 'CMD:M=...,E=...,B=...,L=...'.
    """
    await websocket.accept()
    state.esp32_connected = True
    state.esp32_socket = websocket
    print("[WS ESP32] ¡ESP32 DevKit V1 conectado al servidor!")

    await broadcast_to_mobile({"type": "esp32_status", "connected": True})

    try:
        while True:
            data = await websocket.receive_text()
            data = data.strip()

            # Parsear trama de telemetría de sensores: SENS:T=23.5,H=58.2
            if data.startswith("SENS:"):
                raw = data[5:]
                pairs = raw.split(",")
                for p in pairs:
                    if "=" in p:
                        k, v = p.split("=")
                        try:
                            if k == "T":
                                state.temperature = float(v)
                            elif k == "H":
                                state.humidity = float(v)
                        except ValueError:
                            pass

                # Transmitir telemetría en vivo a las aplicaciones móviles
                await broadcast_to_mobile({
                    "type": "telemetry",
                    "temperature": state.temperature,
                    "humidity": state.humidity,
                    "light_state": state.light_state,
                })

    except WebSocketDisconnect:
        state.esp32_connected = False
        state.esp32_socket = None
        print("[WS ESP32] ESP32 desconectado.")
        await broadcast_to_mobile({"type": "esp32_status", "connected": False})

# -----------------------------------------------------------------------------
# WEBSOCKET 2: COMUNICACIÓN CON EL CELULAR (Móvil)
# -----------------------------------------------------------------------------
@app.websocket("/ws/mobile")
async def websocket_mobile_endpoint(websocket: WebSocket):
    """
    Canal de tiempo real con la app web del celular.
    Recibe la energía acústica (Web Audio API) mientras el celular reproduce
    la respuesta por su bocina para modular la mandíbula física en tiempo real.
    """
    await websocket.accept()
    state.mobile_sockets.append(websocket)
    print(f"[WS MÓVIL] Celular conectado. Total móviles: {len(state.mobile_sockets)}")

    # Enviar estado inicial inmediato al teléfono
    await websocket.send_json({
        "type": "init_state",
        "temperature": state.temperature,
        "humidity": state.humidity,
        "light_state": state.light_state,
        "esp32_connected": state.esp32_connected,
    })

    try:
        while True:
            raw_msg = await websocket.receive_text()
            try:
                msg = json.loads(raw_msg)
            except Exception:
                continue

            event_type = msg.get("event")

            # El celular reproduce audio y calcula el ángulo de mandíbula en vivo
            if event_type == "lipsync_frame":
                mouth_angle = int(msg.get("mouth", 90))
                state.mouth_angle = max(90, min(130, mouth_angle))

                # Reenviar al ESP32 sin demora
                if state.esp32_socket:
                    cmd = f"CMD:M={state.mouth_angle},E={state.eyes_angle},B=0,L={state.light_state}\n"
                    try:
                        await state.esp32_socket.send_text(cmd)
                    except Exception:
                        pass

            # Notificación de palabra clave Wake-Word ("Oye Robot", "Alexa")
            elif event_type == "wake_alert":
                state.eyes_angle = 90
                state.light_state = 1
                if state.esp32_socket:
                    cmd = f"CMD:E=90,EV=90,B=1,L=1\n"
                    try:
                        await state.esp32_socket.send_text(cmd)
                    except Exception:
                        pass
                await broadcast_to_mobile({
                    "type": "telemetry",
                    "temperature": state.temperature,
                    "humidity": state.humidity,
                    "light_state": state.light_state
                })

            # Control manual desde deslizadores del teléfono
            elif event_type == "manual_move":
                m = msg.get("mouth", state.mouth_angle)
                e = msg.get("eyes", state.eyes_angle)
                b = msg.get("blink", 0)
                l = msg.get("light", state.light_state)
                state.mouth_angle = max(90, min(130, m))
                state.eyes_angle = max(60, min(120, e))
                state.light_state = l

                if state.esp32_socket:
                    cmd = f"CMD:M={state.mouth_angle},E={state.eyes_angle},B={b},L={state.light_state}\n"
                    try:
                        await state.esp32_socket.send_text(cmd)
                    except Exception:
                        pass

    except WebSocketDisconnect:
        if websocket in state.mobile_sockets:
            state.mobile_sockets.remove(websocket)
        print(f"[WS MÓVIL] Celular desconectado. Restantes: {len(state.mobile_sockets)}")

async def broadcast_to_mobile(payload: Dict[str, Any]):
    """Transmite eventos a todos los clientes móviles conectados."""
    disconnected = []
    for ws in state.mobile_sockets:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in state.mobile_sockets:
            state.mobile_sockets.remove(ws)

# -----------------------------------------------------------------------------
# MONTAR APLICACIÓN WEB ESTÁTICA
# -----------------------------------------------------------------------------
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
