"""
serial_bridge.py - Puente de Comunicación Serie Bidireccional para ESP32 / Arduino
==================================================================================
Maneja la conexión automática, lectura asíncrona de telemetría y envío de comandos
cinemáticos a través del puerto serie USB (/dev/ttyUSB0, /dev/ttyACM0 o COMx).
"""

import sys
import glob
import time
import threading
from typing import Optional, Callable

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class SerialHardwareBridge:
    def __init__(
        self,
        baudrate: int = 115200,
        preferred_port: Optional[str] = None,
        on_telemetry: Optional[Callable[[float, float], None]] = None,
        on_status_change: Optional[Callable[[bool, Optional[str]], None]] = None
    ):
        self.baudrate = baudrate
        self.preferred_port = preferred_port
        self.on_telemetry = on_telemetry
        self.on_status_change = on_status_change

        self.serial_conn: Optional[serial.Serial] = None
        self.current_port: Optional[str] = None
        self.is_connected = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.last_rx_time = 0.0

    def find_available_ports(self):
        """Busca puertos serie disponibles en Linux o Windows."""
        if not SERIAL_AVAILABLE:
            return []
        
        ports = []
        if self.preferred_port:
            ports.append(self.preferred_port)

        # Buscar dispositivos ttyUSB y ttyACM en Linux
        if sys.platform.startswith("linux"):
            for pattern in ["/dev/ttyUSB*", "/dev/ttyACM*"]:
                for p in sorted(glob.glob(pattern)):
                    if p not in ports:
                        ports.append(p)
        else:
            # En Windows o macOS
            try:
                for p in serial.tools.list_ports.comports():
                    if p.device not in ports:
                        ports.append(p.device)
            except Exception:
                pass

        return ports

    def start(self):
        """Inicia el hilo de monitoreo y comunicación serie."""
        if not SERIAL_AVAILABLE:
            print("[SerialBridge] ADVERTENCIA: pyserial no está disponible.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="SerialBridgeWorker")
        self._thread.start()
        print("[SerialBridge] Subproceso de puente serie iniciado.")

    def stop(self):
        """Detiene el hilo y cierra la conexión serie."""
        self._running = False
        self._close_connection()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        print("[SerialBridge] Subproceso detenido y puerto liberado.")

    def write_command(self, cmd: str) -> bool:
        """Envía un comando formateado hacia el microcontrolador de forma segura."""
        with self._lock:
            if not self.serial_conn or not self.is_connected:
                return False
            try:
                data = cmd.strip() + "\n"
                self.serial_conn.write(data.encode("utf-8", errors="ignore"))
                self.serial_conn.flush()
                return True
            except Exception as e:
                print(f"[SerialBridge] Error al escribir comando: {e}")
                self._handle_disconnect()
                return False

    def _worker_loop(self):
        """Bucle principal de detección, conexión y recepción de tramas."""
        while self._running:
            if not self.is_connected:
                self._attempt_connection()
                if not self.is_connected:
                    time.sleep(2.0)
                    continue

            # Conectado: leer líneas continuas
            try:
                conn = self.serial_conn
                if conn and conn.is_open:
                    line = conn.readline()
                    if line:
                        text = line.decode("utf-8", errors="replace").strip()
                        if text:
                            self._process_line(text)
                            self.last_rx_time = time.time()
                else:
                    if self._running:
                        self._handle_disconnect()
            except Exception as e:
                if not self._running:
                    break
                print(f"[SerialBridge] Error en lectura serie ({self.current_port}): {e}")
                self._handle_disconnect()
                time.sleep(1.0)

    def _attempt_connection(self):
        """Intenta abrir cualquiera de los puertos serie candidatos."""
        candidates = self.find_available_ports()
        for port in candidates:
            try:
                s = serial.Serial()
                s.port = port
                s.baudrate = self.baudrate
                s.timeout = 0.5
                s.write_timeout = 0.5
                s.dtr = False
                s.rts = False
                s.open()

                # Esperar estabilización mínima tras la apertura del puerto
                time.sleep(0.5)
                s.reset_input_buffer()

                # Enviar PING de sondeo
                s.write(b"PING\n")
                time.sleep(0.1)

                with self._lock:
                    self.serial_conn = s
                    self.current_port = port
                    self.is_connected = True
                    self.last_rx_time = time.time()

                print(f"[SerialBridge] Conexión serie establecida exitosamente en: {port} ({self.baudrate} bps)")
                if self.on_status_change:
                    self.on_status_change(True, port)
                return
            except Exception:
                continue

    def _handle_disconnect(self):
        """Gestiona el cierre limpio tras desconexión física."""
        self._close_connection()
        if self.is_connected:
            self.is_connected = False
            prev_port = self.current_port
            self.current_port = None
            print(f"[SerialBridge] Dispositivo desconectado en {prev_port}.")
            if self.on_status_change:
                self.on_status_change(False, prev_port)

    def _close_connection(self):
        with self._lock:
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except Exception:
                    pass
                self.serial_conn = None

    def _process_line(self, line: str):
        """Analiza la trama recibida y despacha los datos a los callbacks."""
        # 1. Trama estándar de telemetría compacta de Arduino / ESP32: S,temp10,hum10,flags...
        # Puede venir como 'S,235,582...' o 'TELEMETRIA UNO: S,235,582...'
        if "S," in line:
            idx = line.find("S,")
            sub = line[idx + 2:]
            parts = sub.split(",")
            if len(parts) >= 2:
                try:
                    t10 = int(parts[0])
                    h10 = int(parts[1])
                    temp = round(t10 / 10.0, 1) if t10 > -3000 else None
                    hum = round(h10 / 10.0, 1) if h10 >= 0 else None
                    if temp is not None and hum is not None and self.on_telemetry:
                        self.on_telemetry(temp, hum)
                except ValueError:
                    pass

        # 2. Trama de telemetría explícita: SENS:T=23.5,H=58.2 o HEARTBEAT:OK,T=23.5,H=58.2
        elif ("SENS:" in line) or ("HEARTBEAT:OK" in line):
            temp = None
            hum = None
            pairs = line.replace("SENS:", "").replace("HEARTBEAT:OK,", "").split(",")
            for p in pairs:
                if "=" in p:
                    k, v = p.split("=", 1)
                    try:
                        if k.strip() == "T":
                            temp = float(v.strip())
                        elif k.strip() == "H":
                            hum = float(v.strip())
                    except ValueError:
                        pass
            if temp is not None and hum is not None and self.on_telemetry:
                self.on_telemetry(temp, hum)

        # 3. Notificación de sincronismo / Confirmación de comandos
        elif line.startswith("ACK") or line == "PONG":
            pass
