#!/usr/bin/env python3
"""
=============================================================================
MÓDULO DE VISIÓN COMPUTACIONAL Y SEGUIMIENTO FACIAL DE ALTO RENDIMIENTO
Proyecto: Cabeza Animatrónica con IA Local
Hardware: Cámara PC Local + Mecanismo Ocular ε3.2 / PCA9685
=============================================================================
Arquitectura optimizada:
  1. Captura desacoplada en hilo independiente (CameraCaptureWorker) con
     política Latest-Frame-Wins (cero acumulación de latencia ni frames viejos).
  2. Inferencia asíncrona con seguimiento por Región de Interés (ROI Tracking):
     - Búsqueda local en el entorno del rostro previo (<3 ms por frame).
     - Búsqueda global únicamente si se pierde el objetivo.
  3. Codificación JPEG bajo demanda: Compresión desactivada si no hay
     clientes visualizando la transmisión web (ahorro masivo de CPU).
  4. Cinemática suavizada con filtro exponencial (EMA) y zona muerta (Deadband)
     para eliminar temblores parásitos del sensor.
=============================================================================
"""

import cv2
import time
import math
import threading
from typing import Optional, Callable, Dict, Any, Tuple


class CameraCaptureWorker:
    """Hilo dedicado exclusivamente a la captura de fotogramas del sensor."""

    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[any] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.capture_fps = 0.0
        self._frame_count = 0

    def start(self) -> bool:
        # En Windows DirectShow (CAP_DSHOW) inicializa instantáneamente sin bloquear
        self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            self._cap = cv2.VideoCapture(self.camera_index)

        if not self._cap.isOpened():
            return False

        # Configurar resolución estándar 640x480
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Buffer interno mínimo para evitar latencia de cola
        try:
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="CamCaptureWorker")
        self._thread.start()
        return True

    def _loop(self):
        last_t = time.perf_counter()
        while self._running:
            ret, frame = self._cap.read()
            now = time.perf_counter()
            dt = now - last_t
            last_t = now

            if ret and frame is not None:
                with self._lock:
                    self._latest_frame = frame
                    self._frame_count += 1
                if dt > 0:
                    current_fps = 1.0 / dt
                    self.capture_fps = (self.capture_fps * 0.9) + (current_fps * 0.1)
            else:
                time.sleep(0.005)

    def get_latest_frame(self):
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        if self._cap and self._cap.isOpened():
            self._cap.release()
            self._cap = None
        with self._lock:
            self._latest_frame = None


class FaceTracker:
    """
    Controlador de visión artificial multihilo de alto rendimiento para
    seguimiento facial con soporte para 30+ FPS y transmisión condicional.
    """

    def __init__(
        self,
        camera_index: int = 0,
        on_servo_update: Optional[Callable[[int, int], None]] = None,
        invert_x: bool = True,
        invert_y: bool = False,
        smooth_factor: float = 0.25,
        deadband: float = 0.035,
        rate_limit_hz: float = 25.0,
        return_to_center_delay: float = 2.5
    ):
        self.camera_index = camera_index
        self.on_servo_update = on_servo_update

        # Configuración de límites angulares físicos del mecanismo ε3.2 / PCA9685
        self.EYE_H_MIN = 60
        self.EYE_H_MAX = 120
        self.EYE_H_NEUTRAL = 90

        self.EYE_V_MIN = 70
        self.EYE_V_MAX = 110
        self.EYE_V_NEUTRAL = 90

        # Parámetros de control
        self.invert_x = invert_x
        self.invert_y = invert_y
        self.smooth_factor = smooth_factor
        self.deadband = deadband
        self.rate_limit_hz = rate_limit_hz
        self.return_to_center_delay = return_to_center_delay

        # Estado cinemático actual
        self.current_eh = float(self.EYE_H_NEUTRAL)
        self.current_ev = float(self.EYE_V_NEUTRAL)
        self.target_eh = float(self.EYE_H_NEUTRAL)
        self.target_ev = float(self.EYE_V_NEUTRAL)

        # Últimos ángulos discretos enteros enviados
        self.last_sent_eh = self.EYE_H_NEUTRAL
        self.last_sent_ev = self.EYE_V_NEUTRAL

        # Estado del detector
        self.is_running = False
        self.face_detected = False
        self.face_box: Optional[Tuple[int, int, int, int]] = None
        self.last_face_time = 0.0
        self.fps = 0.0
        self.inference_ms = 0.0

        # ROI Tracking (coordenadas relativas en escala 0.5x)
        self._prev_roi_scaled: Optional[Tuple[int, int, int, int]] = None
        self._roi_miss_count = 0

        # Control de codificación JPEG bajo demanda
        self._stream_viewers = 0
        self._latest_jpeg: Optional[bytes] = None
        self._last_jpeg_time = 0.0

        # Hilo de procesamiento
        self._cam_worker: Optional[CameraCaptureWorker] = None
        self._process_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Cargar clasificadores Haar de OpenCV
        cascade_front = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade_profile = cv2.data.haarcascades + "haarcascade_profileface.xml"

        self.face_cascade = cv2.CascadeClassifier(cascade_front)
        self.profile_cascade = cv2.CascadeClassifier(cascade_profile)

        if self.face_cascade.empty():
            print("[FaceTracker] ADVERTENCIA: No se pudo cargar clasificador frontal de rostros.")

    def register_viewer(self):
        """Registra un cliente visualizando el streaming de video."""
        with self._lock:
            self._stream_viewers += 1

    def unregister_viewer(self):
        """Desregistra un cliente de visualización."""
        with self._lock:
            self._stream_viewers = max(0, self._stream_viewers - 1)

    @property
    def has_viewers(self) -> bool:
        with self._lock:
            return self._stream_viewers > 0

    def start(self) -> bool:
        """Inicia el pipeline desacoplado de captura y procesamiento."""
        with self._lock:
            if self.is_running:
                return True

            self._stop_event.clear()
            self._cam_worker = CameraCaptureWorker(self.camera_index)
            if not self._cam_worker.start():
                print(f"[FaceTracker] ERROR: No se pudo abrir la cámara índice {self.camera_index}.")
                self._cam_worker = None
                return False

            self._process_thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="FaceTrackerInference"
            )
            self._process_thread.start()
            self.is_running = True
            print(f"[FaceTracker] Pipeline desacoplado iniciado con éxito en cámara {self.camera_index}.")
            return True

    def stop(self):
        """Detiene el pipeline y libera los recursos de hardware."""
        with self._lock:
            if not self.is_running:
                return
            self._stop_event.set()

        if self._process_thread and self._process_thread.is_alive():
            self._process_thread.join(timeout=2.0)

        if self._cam_worker:
            self._cam_worker.stop()
            self._cam_worker = None

        with self._lock:
            self.is_running = False
            self.face_detected = False
            self.face_box = None
            self._latest_jpeg = None
            self._prev_roi_scaled = None
            print("[FaceTracker] Pipeline detenido y recursos liberados correctamente.")

    def set_config(
        self,
        invert_x: Optional[bool] = None,
        invert_y: Optional[bool] = None,
        smooth_factor: Optional[float] = None,
        deadband: Optional[float] = None,
        return_to_center_delay: Optional[float] = None
    ):
        """Actualiza parámetros dinámicamente sin reiniciar la cámara."""
        with self._lock:
            if invert_x is not None:
                self.invert_x = bool(invert_x)
            if invert_y is not None:
                self.invert_y = bool(invert_y)
            if smooth_factor is not None:
                self.smooth_factor = max(0.05, min(0.9, float(smooth_factor)))
            if deadband is not None:
                self.deadband = max(0.005, min(0.2, float(deadband)))
            if return_to_center_delay is not None:
                self.return_to_center_delay = max(0.5, min(10.0, float(return_to_center_delay)))

    def get_status(self) -> Dict[str, Any]:
        """Devuelve la telemetría del seguimiento visual y métricas de rendimiento."""
        with self._lock:
            cap_fps = self._cam_worker.capture_fps if self._cam_worker else 0.0
            return {
                "running": self.is_running,
                "face_detected": self.face_detected,
                "camera_index": self.camera_index,
                "current_eh": round(self.current_eh, 1),
                "current_ev": round(self.current_ev, 1),
                "target_eh": round(self.target_eh, 1),
                "target_ev": round(self.target_ev, 1),
                "fps": round(self.fps, 1),
                "capture_fps": round(cap_fps, 1),
                "inference_ms": round(self.inference_ms, 2),
                "has_viewers": self._stream_viewers > 0,
                "invert_x": self.invert_x,
                "invert_y": self.invert_y,
                "smooth_factor": self.smooth_factor,
                "deadband": self.deadband,
                "return_to_center_delay": self.return_to_center_delay,
                "face_box": [int(x) for x in self.face_box] if self.face_box else None,
            }

    def get_latest_jpeg(self) -> Optional[bytes]:
        """Devuelve el último fotograma JPEG anotado para el streaming MJPEG."""
        with self._lock:
            return self._latest_jpeg

    def _worker_loop(self):
        """Bucle principal de inferencia asíncrona y seguimiento de alta velocidad."""
        min_send_interval = 1.0 / self.rate_limit_hz if self.rate_limit_hz > 0 else 0.04
        last_send_time = 0.0

        prev_loop_time = time.perf_counter()
        fps_smoothing = 0.85

        while not self._stop_event.is_set():
            t_start = time.perf_counter()
            frame = self._cam_worker.get_latest_frame() if self._cam_worker else None

            if frame is None:
                time.sleep(0.005)
                continue

            now = time.perf_counter()
            dt = now - prev_loop_time
            prev_loop_time = now
            if dt > 0:
                current_fps = 1.0 / dt
                self.fps = (self.fps * fps_smoothing) + (current_fps * (1.0 - fps_smoothing))

            h, w = frame.shape[:2]
            cx_frame = w // 2
            cy_frame = h // 2

            # Preprocesamiento rápido: reducción 0.5x a escala de grises
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
            sh, sw = gray.shape[:2]

            detected = False
            primary_face = None

            t_infer_start = time.perf_counter()

            # 1. Estrategia de búsqueda local con ROI si había rostro previo
            if self._prev_roi_scaled is not None and self._roi_miss_count < 3:
                rx, ry, rw, rh = self._prev_roi_scaled
                # Expandir la región de interés un 40% para abarcar movimiento
                pad_x = int(rw * 0.4)
                pad_y = int(rh * 0.4)
                x1 = max(0, rx - pad_x)
                y1 = max(0, ry - pad_y)
                x2 = min(sw, rx + rw + pad_x)
                y2 = min(sh, ry + rh + pad_y)

                roi_gray = gray[y1:y2, x1:x2]
                if roi_gray.shape[0] > 30 and roi_gray.shape[1] > 30:
                    faces_roi = self.face_cascade.detectMultiScale(
                        roi_gray,
                        scaleFactor=1.18,
                        minNeighbors=4,
                        minSize=(25, 25),
                        flags=cv2.CASCADE_SCALE_IMAGE
                    )
                    if len(faces_roi) > 0:
                        best = max(faces_roi, key=lambda f: f[2] * f[3])
                        fx = (best[0] + x1) * 2
                        fy = (best[1] + y1) * 2
                        fw = best[2] * 2
                        fh = best[3] * 2
                        primary_face = (fx, fy, fw, fh)
                        self._prev_roi_scaled = (best[0] + x1, best[1] + y1, best[2], best[3])
                        self._roi_miss_count = 0
                        detected = True

            # 2. Búsqueda global si no se detectó en ROI o no había rostro previo
            if not detected:
                faces = self.face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.2,
                    minNeighbors=4,
                    minSize=(25, 25),
                    flags=cv2.CASCADE_SCALE_IMAGE
                )

                if len(faces) == 0 and not self.profile_cascade.empty():
                    # Solo escanear perfil si el frontal no arrojó nada
                    faces = self.profile_cascade.detectMultiScale(
                        gray,
                        scaleFactor=1.25,
                        minNeighbors=4,
                        minSize=(25, 25)
                    )

                if len(faces) > 0:
                    best = max(faces, key=lambda f: f[2] * f[3])
                    primary_face = (int(best[0] * 2), int(best[1] * 2), int(best[2] * 2), int(best[3] * 2))
                    self._prev_roi_scaled = (best[0], best[1], best[2], best[3])
                    self._roi_miss_count = 0
                    detected = True
                else:
                    self._roi_miss_count += 1
                    if self._roi_miss_count >= 3:
                        self._prev_roi_scaled = None

            t_infer_end = time.perf_counter()
            self.inference_ms = (t_infer_end - t_infer_start) * 1000.0

            # 3. Lógica cinemática de orientación
            now_sec = time.time()
            if detected and primary_face is not None:
                self.last_face_time = now_sec
                self.face_detected = True
                self.face_box = primary_face
                fx, fy, fw, fh = primary_face

                face_cx = fx + (fw // 2)
                face_cy = fy + (fh // 2)

                # Desviación normalizada con respecto al centro [-1.0, 1.0]
                nx = (face_cx - cx_frame) / cx_frame
                ny = (face_cy - cy_frame) / cy_frame

                # Zona muerta (Deadband)
                if abs(nx) < self.deadband:
                    nx = 0.0
                if abs(ny) < self.deadband:
                    ny = 0.0

                dir_x = -1.0 if self.invert_x else 1.0
                dir_y = -1.0 if self.invert_y else 1.0

                delta_eh = dir_x * nx * (self.EYE_H_MAX - self.EYE_H_NEUTRAL)
                delta_ev = dir_y * ny * (self.EYE_V_MAX - self.EYE_V_NEUTRAL)

                self.target_eh = self.EYE_H_NEUTRAL + delta_eh
                self.target_ev = self.EYE_V_NEUTRAL + delta_ev

            else:
                self.face_box = None
                # Si transcurre tiempo sin rostro, retornar suavemente al centro neutro
                if (now_sec - self.last_face_time) > self.return_to_center_delay:
                    self.face_detected = False
                    self.target_eh = float(self.EYE_H_NEUTRAL)
                    self.target_ev = float(self.EYE_V_NEUTRAL)

            # Acotar a rangos mecánicos seguros ε3.2
            self.target_eh = max(float(self.EYE_H_MIN), min(float(self.EYE_H_MAX), self.target_eh))
            self.target_ev = max(float(self.EYE_V_MIN), min(float(self.EYE_V_MAX), self.target_ev))

            # Suavizado cinemático exponencial (Filtro paso bajo / EMA)
            alpha = self.smooth_factor
            self.current_eh += alpha * (self.target_eh - self.current_eh)
            self.current_ev += alpha * (self.target_ev - self.current_ev)

            eh_int = int(round(self.current_eh))
            ev_int = int(round(self.current_ev))

            # 4. Transmisión con Rate-Limiting y filtrado de repeticiones
            if (now_sec - last_send_time) >= min_send_interval:
                if (eh_int != self.last_sent_eh) or (ev_int != self.last_sent_ev):
                    self.last_sent_eh = eh_int
                    self.last_sent_ev = ev_int
                    last_send_time = now_sec

                    if self.on_servo_update:
                        try:
                            self.on_servo_update(eh_int, ev_int)
                        except Exception as ex:
                            print(f"[FaceTracker Callback Error] {ex}")

            # 5. Codificación JPEG bajo demanda (Solo si hay viewers conectados o intervalo de 50ms)
            viewers_active = self.has_viewers
            if viewers_active and (now_sec - self._last_jpeg_time >= 0.04):
                self._last_jpeg_time = now_sec
                annotated = frame.copy()

                # Retícula central
                cv2.line(annotated, (cx_frame - 15, cy_frame), (cx_frame + 15, cy_frame), (100, 100, 100), 1)
                cv2.line(annotated, (cx_frame, cy_frame - 15), (cx_frame, cy_frame + 15), (100, 100, 100), 1)

                if detected and primary_face is not None:
                    fx, fy, fw, fh = primary_face
                    cv2.rectangle(annotated, (fx, fy), (fx + fw, fy + fh), (0, 255, 128), 2)
                    cv2.circle(annotated, (fx + fw // 2, fy + fh // 2), 4, (0, 200, 255), -1)

                status_color = (0, 255, 128) if self.face_detected else (80, 80, 240)
                status_label = "SIGUIENDO ROSTRO" if self.face_detected else "BUSCANDO..."

                cv2.rectangle(annotated, (0, 0), (w, 32), (18, 18, 18), -1)
                cv2.putText(
                    annotated,
                    f"{status_label} | FPS: {self.fps:.1f} ({self.inference_ms:.1f}ms)",
                    (10, 22),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    status_color,
                    2
                )
                cv2.putText(
                    annotated,
                    f"PAN: {eh_int} deg | TILT: {ev_int} deg",
                    (w - 230, 22),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.50,
                    (255, 255, 255),
                    1
                )

                success, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 65])
                if success:
                    with self._lock:
                        self._latest_jpeg = buffer.tobytes()

            # Ceder brevemente ciclo de CPU (1 ms)
            time.sleep(0.002)


# Instancia singleton predeterminada
_global_face_tracker: Optional[FaceTracker] = None


def get_face_tracker() -> FaceTracker:
    """Devuelve la instancia global del rastreador facial."""
    global _global_face_tracker
    if _global_face_tracker is None:
        _global_face_tracker = FaceTracker()
    return _global_face_tracker
