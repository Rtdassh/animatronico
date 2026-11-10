"""
serial_bridge.py - Puente de Comunicación Serie Multi-Dispositivo (ESP32 y Arduino Uno)
========================================================================================
Detecta y gestiona conexiones serie simultáneas (/dev/ttyUSB0, /dev/ttyACM0, COMx).
Despacha comandos cinemáticos de servomotores PCA9685 y recibe telemetría de sensores.
"""

import sys
import glob
import time
import threading
from typing import Optional, Callable, Dict

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

        self.connections: Dict[str, serial.Serial] = {}
        self.reader_threads: Dict[str, threading.Thread] = {}
        self._running = False
        self._lock = threading.Lock()
        self._manager_thread: Optional[threading.Thread] = None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return len(self.connections) > 0

    @property
    def current_port(self) -> Optional[str]:
        with self._lock:
            if not self.connections:
                return None
            return ", ".join(self.connections.keys())

    def find_available_ports(self):
        """Busca puertos serie disponibles en Linux o Windows."""
        if not SERIAL_AVAILABLE:
            return []

        ports = []
        if self.preferred_port:
            ports.append(self.preferred_port)

        if sys.platform.startswith("linux"):
            for pattern in ["/dev/ttyUSB*", "/dev/ttyACM*"]:
                for p in sorted(glob.glob(pattern)):
                    if p not in ports:
                        ports.append(p)
        else:
            try:
                for p in serial.tools.list_ports.comports():
                    if p.device not in ports:
                        ports.append(p.device)
            except Exception:
                pass

        return ports

    def start(self):
        """Inicia el monitor de puertos serie en segundo plano."""
        if not SERIAL_AVAILABLE:
            print("[SerialBridge] ADVERTENCIA: pyserial no está disponible.")
            return

        self._running = True
        self._manager_thread = threading.Thread(target=self._port_manager_loop, daemon=True, name="SerialManager")
        self._manager_thread.start()
        print("[SerialBridge] Monitor multi-puerto iniciado.")

    def stop(self):
        """Detiene todos los hilos y cierra ordenadamente todas las conexiones."""
        self._running = False
        with self._lock:
            for port, conn in list(self.connections.items()):
                try:
                    conn.close()
                except Exception:
                    pass
            self.connections.clear()

        print("[SerialBridge] Todas las conexiones serie fueron liberadas.")

    def write_command(self, cmd: str) -> bool:
        """Transmite el comando a todos los microcontroladores conectados."""
        data = (cmd.strip() + "\n").encode("utf-8", errors="ignore")
        sent_any = False

        with self._lock:
            for port, conn in list(self.connections.items()):
                try:
                    if conn.is_open:
                        conn.write(data)
                        conn.flush()
                        sent_any = True
                except Exception as e:
                    print(f"[SerialBridge] Error al escribir en {port}: {e}")
                    self._close_single(port)

        return sent_any

    def _port_manager_loop(self):
        """Monitorea puertos disponibles y conecta automáticamente nuevos dispositivos."""
        while self._running:
            candidates = self.find_available_ports()
            for port in candidates:
                with self._lock:
                    already_connected = port in self.connections

                if not already_connected and self._running:
                    self._connect_port(port)

            time.sleep(2.0)

    def _connect_port(self, port: str):
        """Intenta abrir un puerto serie específico e inicia su hilo lector."""
        try:
            s = serial.Serial()
            s.port = port
            s.baudrate = self.baudrate
            s.timeout = 0.5
            s.write_timeout = 0.5
            s.dtr = False
            s.rts = False
            s.open()

            time.sleep(0.3)
            s.reset_input_buffer()
            s.write(b"PING\n")

            with self._lock:
                self.connections[port] = s

            t = threading.Thread(target=self._reader_loop, args=(port, s), daemon=True, name=f"SerialReader-{port}")
            self.reader_threads[port] = t
            t.start()

            print(f"[SerialBridge] Enlace serie conectado en: {port} ({self.baudrate} bps)")
            if self.on_status_change:
                self.on_status_change(True, self.current_port)
        except Exception:
            pass

    def _reader_loop(self, port: str, s: serial.Serial):
        """Hilo de lectura continua para un puerto determinado."""
        while self._running:
            try:
                if not s.is_open:
                    break
                line = s.readline()
                if line:
                    text = line.decode("utf-8", errors="replace").strip()
                    if text:
                        self._process_line(text, port)
            except Exception:
                break

        self._close_single(port)

    def _close_single(self, port: str):
        """Cierra un puerto individual tras desconexión física."""
        with self._lock:
            conn = self.connections.pop(port, None)
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            still_connected = len(self.connections) > 0
            cur = self.current_port

        if self.on_status_change:
            self.on_status_change(still_connected, cur)

    def _process_line(self, line: str, port: str):
        """Parsea tramas de telemetría y confirma ejecución."""
        # 1. Telemetría estándar: S,temp10,hum10...
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

        # 2. Telemetría explícita o Heartbeat con datos
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
