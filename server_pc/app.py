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
import time
import base64
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ollama_client import query_qwen, clean_for_speech, check_ollama, get_best_model
from tts_loquendo import generate_loquendo_speech, VOICES, AUDIO_DIR
from stt_engine import transcribe_audio_bytes
from voicebox_client import generate_voicebox_speech, is_voicebox_running, get_voicebox_profiles
from vision_tracker import FaceTracker, get_face_tracker

try:
    from agent_tools import (
        get_current_datetime_info,
        get_agenda_summary_for_today,
        load_agenda,
        add_agenda_item,
        delete_agenda_item,
        process_agent_actions
    )
except ImportError:
    from server_pc.agent_tools import (
        get_current_datetime_info,
        get_agenda_summary_for_today,
        load_agenda,
        add_agenda_item,
        delete_agenda_item,
        process_agent_actions
    )

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# Referencia global al bucle de eventos para callbacks asíncronos desde hilos de visión
main_loop: Optional[asyncio.AbstractEventLoop] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    print("[Servidor] Event loop asíncrono capturado para el módulo de visión computacional.")
    yield
    tracker = get_face_tracker()
    if tracker.is_running:
        tracker.stop()
    print("[Servidor] Cámara y recursos de visión liberados correctamente.")

app = FastAPI(
    title="animatronico · Servidor Inteligente con Visión Computacional",
    description="Servidor local con Ollama (Qwen 2.5), TTS, seguimiento facial con OpenCV y control cinemático ESP32/Arduino.",
    version="2.1",
    lifespan=lifespan
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
    eyes_angle: int = 90       # Pan / Horizontal (60° a 120°)
    eyes_vertical_angle: int = 90  # Tilt / Vertical (70° a 110°)
    vision_tracking_active: bool = False  # Estado del tracking con cámara
    face_detected: bool = False  # Rostro detectado en el encuadre
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
    eyes_v: int = 90
    blink: int = 0
    light: int = -1

class VisionConfigRequest(BaseModel):
    invert_x: Optional[bool] = None
    invert_y: Optional[bool] = None
    smooth_factor: Optional[float] = None
    deadband: Optional[float] = None
    return_to_center_delay: Optional[float] = None

class AgendaItemRequest(BaseModel):
    title: str
    date: Optional[str] = None
    time: Optional[str] = None
    category: str = "general"

# -----------------------------------------------------------------------------
# HELPERS DE CONTROL DE HARDWARE Y VISIÓN ARTIFICIAL
# -----------------------------------------------------------------------------
# Variables para rate-limiting y eliminación de duplicados
last_mobile_servo_broadcast = 0.0
last_sent_eh = -1
last_sent_ev = -1

async def _dispatch_vision_servo(eh: int, ev: int):
    """Reenvía la instrucción de seguimiento calculada por la cámara al ESP32 y a la web de forma optimizada."""
    global last_mobile_servo_broadcast, last_sent_eh, last_sent_ev

    # 1. Enviar al ESP32 sólo si hubo cambio en los ángulos discretos (eliminación de jitter)
    if state.esp32_socket and (eh != last_sent_eh or ev != last_sent_ev):
        last_sent_eh = eh
        last_sent_ev = ev
        # Trama concisa para el mecanismo ε3.2 (Arduino Uno ignora 'M=', enviamos sólo los ejes activos)
        cmd = f"CMD:EH={eh},EV={ev}\n"
        try:
            await state.esp32_socket.send_text(cmd)
        except Exception:
            pass

    # 2. Rate-limiting hacia el frontend móvil (máximo 10 Hz) para no saturar el canal ni la CPU del móvil
    now = time.time()
    if now - last_mobile_servo_broadcast >= 0.10:
        last_mobile_servo_broadcast = now
        tracker = get_face_tracker()
        await broadcast_to_mobile({
            "type": "servo_position",
            "eyes": eh,
            "eyes_v": ev,
            "mouth": state.mouth_angle,
            "face_detected": tracker.face_detected,
            "fps": round(tracker.fps, 1),
            "infer_ms": round(tracker.inference_ms, 1)
        })

def on_vision_servo_update(eh: int, ev: int):
    """Callback invocado por el hilo del FaceTracker cuando cambian los ángulos requeridos."""
    global main_loop
    state.eyes_angle = eh
    state.eyes_vertical_angle = ev
    tracker = get_face_tracker()
    state.face_detected = tracker.face_detected

    if main_loop and main_loop.is_running():
        asyncio.run_coroutine_threadsafe(_dispatch_vision_servo(eh, ev), main_loop)

# Registrar el callback en el rastreador facial
vision_tracker = get_face_tracker()
vision_tracker.on_servo_update = on_vision_servo_update

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
        cmd = f"CMD:EH={state.eyes_angle},EV={state.eyes_vertical_angle},B={blink},L={state.light_state}\n"
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
    """Elimina etiquetas de control de hardware y de acciones de agente para que no se pronuncien por voz."""
    clean = re.sub(r'\[LUZ_ON\]|\[LUZ_OFF\]|\[BLINK\]|\[SERVO_[^\]]+\]|\[AGREGAR_AGENDA:[^\]]+\]', '', text)
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
        "eyes_vertical_angle": state.eyes_vertical_angle,
        "vision_active": vision_tracker.is_running,
        "face_detected": vision_tracker.face_detected,
        "vision_fps": round(vision_tracker.fps, 1),
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

        # 1. Reconocimiento de voz a texto (STT) en hilo no bloqueante
        transcription = await asyncio.to_thread(transcribe_audio_bytes, audio_content)

        # 2. Historial de conversación
        try:
            history = json.loads(history_json)
        except Exception:
            history = []

        # 3. Consulta al modelo local Qwen 2.5 vía Ollama en hilo secundario (no congela WebSockets)
        raw_response = await asyncio.to_thread(
            query_qwen,
            prompt=transcription,
            history=history,
            temperature=state.temperature,
            humidity=state.humidity,
            light_state=state.light_state
        )

        # 4. Procesar comandos físicos (Luz, parpadeo, etc.) y acciones de agente (agenda)
        await apply_hardware_tags(raw_response)
        _, agent_act = process_agent_actions(raw_response)
        if agent_act:
            print(f"[Agente V de Venganza] Acción ejecutada: {agent_act}")

        # 5. Limpieza de texto para voz
        speech_text = sanitize_ai_reply(raw_response)
        if not speech_text:
            speech_text = "Comando ejecutado correctamente."

        # 6. Síntesis de voz (Loquendo o Voicebox Dom) en hilo secundario
        audio_bytes, audio_filename, media_type = await asyncio.to_thread(
            synthesize_speech, speech_text, voice_key=voice
        )
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
        # 1. Consulta al modelo local en Ollama en hilo secundario (no congela WebSockets)
        raw_response = await asyncio.to_thread(
            query_qwen,
            prompt=user_text,
            history=req.history,
            temperature=state.temperature,
            humidity=state.humidity,
            light_state=state.light_state
        )

        # 2. Procesar etiquetas de control físico
        await apply_hardware_tags(raw_response)

        # 2.1 Procesar acciones de agente (agenda, recordatorios)
        _, agent_act = process_agent_actions(raw_response)
        if agent_act:
            print(f"[Agent Action /api/chat] {agent_act}")

        # 3. Limpieza de texto
        speech_text = sanitize_ai_reply(raw_response)
        if not speech_text:
            speech_text = "Comando procesado."

        # 4. Generación de voz (Loquendo o Voicebox Dom) en hilo secundario
        audio_bytes, audio_filename, media_type = await asyncio.to_thread(
            synthesize_speech, speech_text, voice_key=req.voice
        )
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

        return {
            "user_query": user_text,
            "response": raw_response,
            "speech_text": speech_text,
            "agent_action": agent_act,
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
    state.eyes_vertical_angle = max(70, min(110, req.eyes_v))
    if req.light in (0, 1):
        state.light_state = req.light

    cmd = f"CMD:EH={state.eyes_angle},EV={state.eyes_vertical_angle},B={req.blink},L={state.light_state}\n"
    if state.esp32_socket:
        try:
            await state.esp32_socket.send_text(cmd)
            return {"status": "ok", "sent_cmd": cmd.strip()}
        except Exception as e:
            return {"status": "error", "detail": str(e)}
    return {"status": "buffered", "note": "ESP32 no conectado aún"}

# -----------------------------------------------------------------------------
# RUTAS DE VISIÓN COMPUTACIONAL (CÁMARA LOCAL & SEGUIMIENTO FACIAL)
# -----------------------------------------------------------------------------
@app.get("/api/vision/status")
async def get_vision_status():
    """Devuelve la telemetría completa de visión computacional y servos."""
    info = vision_tracker.get_status()
    info["esp32_connected"] = state.esp32_connected
    info["light_state"] = state.light_state
    info["mouth_angle"] = state.mouth_angle
    return info

@app.post("/api/vision/toggle")
async def toggle_vision():
    """Alterna el estado encendido/apagado del seguimiento de rostros."""
    if vision_tracker.is_running:
        vision_tracker.stop()
        state.vision_tracking_active = False
        state.eyes_angle = 90
        state.eyes_vertical_angle = 90
        if state.esp32_socket:
            try:
                await state.esp32_socket.send_text(
                    f"CMD:EH=90,EV=90,B=0,L={state.light_state}\n"
                )
            except Exception:
                pass
        await broadcast_to_mobile({
            "type": "vision_status",
            "active": False,
            "eyes": 90,
            "eyes_v": 90,
            "face_detected": False
        })
        return {"status": "stopped", "active": False}
    else:
        started = vision_tracker.start()
        state.vision_tracking_active = started
        await broadcast_to_mobile({
            "type": "vision_status",
            "active": started,
            "face_detected": False
        })
        return {"status": "started" if started else "failed", "active": started}

@app.post("/api/vision/start")
async def start_vision():
    """Inicia el seguimiento de rostros con la cámara local."""
    started = vision_tracker.start()
    state.vision_tracking_active = started
    await broadcast_to_mobile({"type": "vision_status", "active": started})
    return {"status": "started" if started else "failed", "active": started}

@app.post("/api/vision/stop")
async def stop_vision():
    """Detiene el seguimiento de rostros y recentra los servos a 90°."""
    vision_tracker.stop()
    state.vision_tracking_active = False
    state.eyes_angle = 90
    state.eyes_vertical_angle = 90
    if state.esp32_socket:
        try:
            await state.esp32_socket.send_text(
                f"CMD:EH=90,EV=90,B=0,L={state.light_state}\n"
            )
        except Exception:
            pass
    await broadcast_to_mobile({
        "type": "vision_status",
        "active": False,
        "eyes": 90,
        "eyes_v": 90,
        "face_detected": False
    })
    return {"status": "stopped", "active": False}

@app.post("/api/vision/config")
async def config_vision(req: VisionConfigRequest):
    """Actualiza la calibración de visión (inversión de ejes, suavizado, etc.)."""
    vision_tracker.set_config(
        invert_x=req.invert_x,
        invert_y=req.invert_y,
        smooth_factor=req.smooth_factor,
        deadband=req.deadband,
        return_to_center_delay=req.return_to_center_delay
    )
    return {"status": "ok", "config": vision_tracker.get_status()}

@app.get("/api/vision/video_feed")
async def video_feed():
    """
    Transmisión de video en vivo (MJPEG) con registro de visor activo
    para habilitar la codificación JPEG bajo demanda sin gastar CPU innecesaria.
    """
    async def frame_stream():
        vision_tracker.register_viewer()
        try:
            while True:
                if not vision_tracker.is_running:
                    await asyncio.sleep(0.2)
                    continue
                frame_bytes = vision_tracker.get_latest_jpeg()
                if frame_bytes:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                    )
                await asyncio.sleep(0.04)
        finally:
            vision_tracker.unregister_viewer()

    return StreamingResponse(
        frame_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """Sirve archivos MP3, WAV y MP4 con soporte de streaming HTTP Range para navegadores móviles."""
    safe_name = os.path.basename(filename)
    file_path = AUDIO_DIR / safe_name
    if not file_path.exists():
        file_path = STATIC_DIR / safe_name
        if not file_path.exists() and (STATIC_DIR / "audio" / safe_name).exists():
            file_path = STATIC_DIR / "audio" / safe_name

    if file_path.exists():
        if safe_name.endswith(".wav"):
            media_type = "audio/wav"
        elif safe_name.endswith(".mp4") or safe_name.endswith(".m4a"):
            media_type = "audio/mp4"
        else:
            media_type = "audio/mpeg"
        return FileResponse(file_path, media_type=media_type, headers={"Accept-Ranges": "bytes"})
    raise HTTPException(status_code=404, detail="Audio no encontrado")

@app.get("/api/tts")
async def get_tts(text: str, voice: str = "jorge"):
    """Generación rápida directa de audio para cualquier texto arbitrario sin bloquear el event loop."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Texto vacío")
    cleaned = clean_for_speech(text)
    audio_bytes, _, media_type = await asyncio.to_thread(synthesize_speech, cleaned, voice_key=voice)
    return Response(content=audio_bytes, media_type=media_type)

# -----------------------------------------------------------------------------
# ENDPOINTS DE AGENTE: AGENDA Y FECHA/HORA
# -----------------------------------------------------------------------------
@app.get("/api/datetime")
async def get_datetime_endpoint():
    """Devuelve la fecha y hora actual del sistema y efemérides."""
    return get_current_datetime_info()

@app.get("/api/agenda")
async def get_agenda_endpoint():
    """Devuelve las tareas y eventos de la agenda actual y el resumen para hoy."""
    items = load_agenda()
    dt_info = get_current_datetime_info()
    summary = get_agenda_summary_for_today()
    return {
        "status": "ok",
        "datetime": dt_info,
        "summary": summary,
        "items": items
    }

@app.post("/api/agenda")
async def create_agenda_item(req: AgendaItemRequest):
    """Agrega un nuevo elemento o recordatorio a la agenda del asistente."""
    new_item = add_agenda_item(
        title=req.title,
        date_str=req.date,
        time_str=req.time,
        category=req.category
    )
    return {
        "status": "created",
        "item": new_item,
        "summary": get_agenda_summary_for_today()
    }

@app.delete("/api/agenda/{item_id}")
async def remove_agenda_item(item_id: str):
    """Elimina un elemento de la agenda por su ID."""
    success = delete_agenda_item(item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Elemento de agenda no encontrado")
    return {
        "status": "deleted",
        "id": item_id,
        "summary": get_agenda_summary_for_today()
    }


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

            # Parsear trama de telemetría de sensores: SENS:T=23.5,H=58.2 o S,235,582,15,...
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

            elif data.startswith("S,"):
                parts = data.split(",")
                if len(parts) >= 3:
                    try:
                        t10 = int(parts[1])
                        h10 = int(parts[2])
                        if t10 > -3000:
                            state.temperature = round(t10 / 10.0, 1)
                        if h10 >= 0:
                            state.humidity = round(h10 / 10.0, 1)
                    except ValueError:
                        pass
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
        "eyes_angle": state.eyes_angle,
        "eyes_vertical_angle": state.eyes_vertical_angle,
        "vision_active": vision_tracker.is_running,
        "face_detected": vision_tracker.face_detected,
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

            # El celular reproduce audio y calcula el ángulo de mandíbula en vivo para el avatar web
            if event_type == "lipsync_frame":
                mouth_angle = int(msg.get("mouth", 90))
                state.mouth_angle = max(90, min(130, mouth_angle))
                # NOTA: En la arquitectura física ε3.2 con PCA9685, el audio se reproduce exclusivamente
                # en el smartphone (asistente manos libres). No existe servo de boca en el Arduino.
                # Desacoplado: NO se satura el ESP32 ni el puerto serial a 22 Hz con tramas de boca.

            # Notificación de palabra clave Wake-Word ("Oye Robot", "Alexa")
            elif event_type == "wake_alert":
                state.eyes_angle = 90
                state.eyes_vertical_angle = 90
                state.light_state = 1
                if state.esp32_socket:
                    cmd = f"CMD:EH=90,EV=90,B=1,L=1\n"
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
                ev = msg.get("eyes_v", state.eyes_vertical_angle)
                b = msg.get("blink", 0)
                l = msg.get("light", state.light_state)
                state.mouth_angle = max(90, min(130, m))
                state.eyes_angle = max(60, min(120, e))
                state.eyes_vertical_angle = max(70, min(110, ev))
                state.light_state = l

                if state.esp32_socket:
                    cmd = f"CMD:EH={state.eyes_angle},EV={state.eyes_vertical_angle},B={b},L={state.light_state}\n"
                    try:
                        await state.esp32_socket.send_text(cmd)
                    except Exception:
                        pass

            # Alternar visión artificial desde el cliente WebSocket
            elif event_type == "vision_toggle":
                if vision_tracker.is_running:
                    vision_tracker.stop()
                    state.vision_tracking_active = False
                    state.eyes_angle = 90
                    state.eyes_vertical_angle = 90
                    if state.esp32_socket:
                        try:
                            await state.esp32_socket.send_text(
                                f"CMD:EH=90,EV=90,B=0,L={state.light_state}\n"
                            )
                        except Exception:
                            pass
                else:
                    started = vision_tracker.start()
                    state.vision_tracking_active = started

                await broadcast_to_mobile({
                    "type": "vision_status",
                    "active": vision_tracker.is_running,
                    "eyes": state.eyes_angle,
                    "eyes_v": state.eyes_vertical_angle,
                    "face_detected": vision_tracker.face_detected
                })

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
