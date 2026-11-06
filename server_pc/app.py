#!/usr/bin/env python3
"""
Servidor Central de Inteligencia Artificial, Sincronización Labial y Enlace Móvil
Proyecto: Cabeza Animatrónica con IA Local
Plataforma: PC Local (FastAPI + Ollama / Qwen 2.5 + edge-tts + WebSockets)
"""

import os
import re
import json
import uuid
import asyncio
from pathlib import Path
from typing import Dict, Any, List

import httpx
import edge_tts
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
AUDIO_DIR = BASE_DIR / "audio"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Servidor Animatrónico Inteligente", version="1.0")

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
    light_state: int = 0       # 0: Apagada, 1: Encendida
    mouth_angle: int = 90      # 90° cerrada a 130° abierta
    eyes_angle: int = 90       # 60° a 120°
    esp32_connected: bool = False
    mobile_connected: bool = False
    esp32_socket: WebSocket = None
    mobile_sockets: List[WebSocket] = []

state = SystemState()

# -----------------------------------------------------------------------------
# MODELOS DE DATOS
# -----------------------------------------------------------------------------
class ChatRequest(BaseModel):
    text: str

class ControlRequest(BaseModel):
    mouth: int = 90
    eyes: int = 90
    blink: int = 0
    light: int = -1

# -----------------------------------------------------------------------------
# MOTOR DE INFERENCIA LLM (Ollama con fallback inteligente)
# -----------------------------------------------------------------------------
async def query_llm(user_prompt: str) -> str:
    """
    Consulta a Ollama local (qwen2.5:1.5b).
    Si Ollama no está en ejecución, responde mediante un motor heurístico local
    para que la app y el animatrónico sigan funcionando al 100%.
    """
    clean_prompt = user_prompt.lower().strip()

    # Contexto del sistema inyectando telemetría real
    system_prompt = (
        "Eres 'Cíclope', una cabeza animatrónica con inteligencia artificial local e interactiva. "
        "Tienes un microcontrolador ESP32 como pasarela y un Arduino Uno que controla tus 3 servomotores.\n"
        f"- Estado actual de tus sensores: Temperatura ambiente (LM75A): {state.temperature:.1f} °C, Humedad (DHT11): {state.humidity:.1f} %.\n"
        f"- Estado de la luz del laboratorio: {'ENCENDIDA' if state.light_state == 1 else 'APAGADA'}.\n"
        "Reglas:\n"
        "1. Responde SIEMPRE en español de forma carismática, concisa (máximo 2 a 3 oraciones).\n"
        "2. Si el usuario te pide encender la luz, incluye la etiqueta [LUZ_ON] en tu respuesta.\n"
        "3. Si el usuario te pide apagar la luz, incluye la etiqueta [LUZ_OFF] en tu respuesta.\n"
    )

    ollama_url = "http://localhost:11434/api/generate"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(
                ollama_url,
                json={
                    "model": "qwen2.5:1.5b",
                    "prompt": f"{system_prompt}\nUsuario: {user_prompt}\nCíclope:",
                    "stream": False,
                }
            )
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip()
                if answer:
                    return answer
    except Exception:
        pass  # Ollama no está activo; activar motor de respaldo local

    # Fallback inteligente local
    if any(w in clean_prompt for w in ["temperatura", "grados", "calor", "frio", "clima"]):
        return (f"Según mi sensor digital LM75A, la temperatura actual en el laboratorio es de "
                f"{state.temperature:.1f} grados Celsius, con una humedad del {state.humidity:.1f} por ciento.")
    elif any(w in clean_prompt for w in ["humedad", "ambiente"]):
        return (f"Mi sensor DHT11 reporta una humedad relativa del {state.humidity:.1f} por ciento, "
                f"y la temperatura es de {state.temperature:.1f} grados.")
    elif "enciende" in clean_prompt and "luz" in clean_prompt:
        return "[LUZ_ON] ¡Entendido! He encendido la luz del laboratorio en el pin D7."
    elif "apaga" in clean_prompt and "luz" in clean_prompt:
        return "[LUZ_OFF] Listo, acabo de apagar la luz del laboratorio."
    elif any(w in clean_prompt for w in ["quien eres", "qué eres", "que haces", "proyecto"]):
        return ("Soy la cabeza animatrónica inteligente con IA local. Utilizo tu celular como micrófono y altavoz, "
                "mientras mi Arduino y ESP32 controlan mis expresiones faciales y sensores.")
    elif any(w in clean_prompt for w in ["chiste", "broma", "gracioso"]):
        return ("¿Por qué los robots nunca tienen miedo? Porque tienen nervios de acero y corazón de silicio.")
    elif any(w in clean_prompt for w in ["hola", "buenos dias", "buenas tardes", "hey"]):
        return (f"¡Hola! Te escucho perfectamente por el micrófono del teléfono. Actualmente estamos a "
                f"{state.temperature:.1f} grados. ¿En qué te ayudo?")
    else:
        return (f"He recibido tu mensaje: '{user_prompt}'. Mis sensores reportan {state.temperature:.1f} grados "
                f"y mis 3 servomotores están calibrados y listos para actuar.")

# -----------------------------------------------------------------------------
# MOTOR DE SÍNTESIS DE VOZ Y LIP-SYNC (edge-tts)
# -----------------------------------------------------------------------------
async def synthesize_speech(text: str) -> str:
    """
    Sintetiza la voz en español neutro de alta fidelidad con edge-tts
    y guarda el archivo en formato MP3 para streaming móvil.
    """
    # Limpiar etiquetas de control antes de pronunciar
    spoken_text = re.sub(r'\[LUZ_ON\]|\[LUZ_OFF\]', '', text).strip()
    if not spoken_text:
        spoken_text = "Comando ejecutado."

    audio_filename = f"speech_{uuid.uuid4().hex[:8]}.mp3"
    audio_path = AUDIO_DIR / audio_filename

    # Voz en español enérgica y clara (Jorge de México o Álvaro de España)
    communicate = edge_tts.Communicate(spoken_text, "es-MX-JorgeNeural", rate="+5%")
    await communicate.save(str(audio_path))

    return audio_filename

# -----------------------------------------------------------------------------
# RUTAS DE LA API HTTP
# -----------------------------------------------------------------------------
@app.get("/api/status")
async def get_status():
    """Devuelve el estado completo de sensores y conexiones."""
    return {
        "temperature": state.temperature,
        "humidity": state.humidity,
        "light_state": state.light_state,
        "mouth_angle": state.mouth_angle,
        "eyes_angle": state.eyes_angle,
        "esp32_connected": state.esp32_connected,
        "mobile_connected": len(state.mobile_sockets) > 0,
    }

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Recibe la transcripción de voz desde el celular, procesa con IA,
    genera audio para el altavoz del celular y prepara los comandos físicos.
    """
    user_text = req.text.strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Texto vacío")

    # 1. Obtener respuesta de la IA
    ai_response = await query_llm(user_text)

    # 2. Verificar si hay órdenes de luz
    light_updated = False
    if "[LUZ_ON]" in ai_response:
        state.light_state = 1
        light_updated = True
    elif "[LUZ_OFF]" in ai_response:
        state.light_state = 0
        light_updated = True

    # Si cambió la luz y el ESP32 está conectado, enviar comando directo
    if light_updated and state.esp32_socket:
        cmd = f"CMD:M={state.mouth_angle},E={state.eyes_angle},B=0,L={state.light_state}\n"
        try:
            await state.esp32_socket.send_text(cmd)
        except Exception:
            pass

    # 3. Generar audio para el altavoz del celular
    clean_ai_text = re.sub(r'\[LUZ_ON\]|\[LUZ_OFF\]', '', ai_response).strip()
    audio_file = await synthesize_speech(clean_ai_text)

    return {
        "user_query": user_text,
        "ai_response": clean_ai_text,
        "audio_url": f"/audio/{audio_file}",
        "light_state": state.light_state,
    }

@app.post("/api/control")
async def manual_control(req: ControlRequest):
    """Control manual de los servomotores y luz desde el panel móvil."""
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
    """Sirve los archivos de audio sintetizados hacia el altavoz del celular."""
    file_path = AUDIO_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio no encontrado")
    return FileResponse(file_path, media_type="audio/mpeg")

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

    # Notificar a la app móvil del celular
    await broadcast_to_mobile({"type": "esp32_status", "connected": True})

    try:
        while True:
            data = await websocket.receive_text()
            data = data.strip()
            print(f"[WS ESP32 -> PC] {data}")

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
                
                # Reenviar telemetría en tiempo real a la interfaz móvil del celular
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

            # Control manual desde sliders del teléfono
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
    """Transmite eventos a todos los celulares conectados."""
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
# MONTAR ARCHIVOS ESTÁTICOS DE LA APP MÓVIL
# -----------------------------------------------------------------------------
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

