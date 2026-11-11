"""Un único enlace ESP32 USB: confirmaciones, telemetría y cola acotada."""
import os
import re
import threading
import time
from collections import OrderedDict
import serial
from serial.tools import list_ports

class SerialHardwareBridge:
    def __init__(self, baudrate=115200, preferred_port=None, on_telemetry=None, on_status_change=None):
        self.baudrate = baudrate
        self.preferred_port = preferred_port or os.getenv("ANIMATRONICO_PORT")
        self.on_telemetry = on_telemetry
        self.on_status_change = on_status_change
        self._conn = None
        self._running = False
        self._condition = threading.Condition(threading.RLock())
        self._write_lock = threading.Lock()
        self._command_lock = threading.Lock()
        self._queue = OrderedDict()
        self._result = None
        self._last_frame = 0.0
        self._hardware = {}

    @property
    def is_connected(self):
        with self._condition:
            return bool(self._conn and self._conn.is_open)

    @property
    def current_port(self):
        with self._condition:
            return self._conn.port if self._conn else None

    def snapshot(self):
        with self._condition:
            age = int((time.monotonic() - self._last_frame) * 1000) if self._last_frame else 0
            return {**self._hardware, "received": bool(self._last_frame),
                    "connected": self.is_connected and bool(self._last_frame) and age < 6000,
                    "frameAgeMs": age, "port": self.current_port}

    def find_available_ports(self):
        if self.preferred_port:
            return [self.preferred_port]
        ports = []
        for p in list_ports.comports():
            if p.vid in (0x2341, 0x1A86, 0x0403):
                # Arduino Uno directo o clones USB
                ports.insert(0, p.device)
            elif p.vid in (0x10C4, 0x303A):
                # ESP32 CP210x o nativo
                ports.append(p.device)
        return ports

    def start(self):
        self._running = True
        threading.Thread(target=self._manager, daemon=True, name="ESP32Serial").start()
        threading.Thread(target=self._writer, daemon=True, name="HardwareCommands").start()

    def stop(self):
        self._running = False
        with self._condition:
            if self._conn:
                self._conn.close()
            self._conn = None
            self._condition.notify_all()

    def request_command(self, command, timeout=4.0):
        if not re.fullmatch(r"[A-Z0-9_:,=\-]{1,31}", command):
            return {"ok": False, "ack": "COMANDO_INVALIDO"}
        with self._command_lock:
            if not self.is_connected:
                return {"ok": False, "ack": "ESP32_DESCONECTADO"}
            with self._condition:
                self._result = None
            try:
                with self._write_lock:
                    self._conn.write((command + "\n").encode())
                deadline = time.monotonic() + timeout
                with self._condition:
                    while self._result is None and self.is_connected:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        self._condition.wait(remaining)
                    ack = self._result or "SIN_CONFIRMACION"
                return {"ok": ack in {"PONG", "SCAN_OK", "BEEP_OK", "AUTO_ON", "AUTO_OFF",
                                       "CMD_OK", "PWM_ENVIADO", "ALL_PWM_OK", "LIGHT_OK", "BLINK_OK"}, "ack": ack}
            except (OSError, serial.SerialException, AttributeError):
                return {"ok": False, "ack": "ESP32_DESCONECTADO"}

    @staticmethod
    def normalize(command):
        command = command.strip()
        if not command.startswith("CMD:"):
            return [command]
        values = dict(re.findall(r"(EH|EV|M|B|L)=(-?\d+)", command))
        orders = []
        eyes = [f"{key}={values[key]}" for key in ("EH", "EV") if key in values]
        if eyes:
            orders.append("CMD:" + ",".join(eyes))
        if "M" in values:
            orders.append(f"S6:{max(30, min(150, int(values['M'])))}")
        if values.get("B") == "1":
            orders.append("BLINK")
        if values.get("L") in ("0", "1"):
            orders.append("LIGHT:" + values["L"])
        return orders

    def write_command(self, command):
        if not self.is_connected:
            return False
        with self._condition:
            for order in self.normalize(command):
                key = order.split(":", 1)[0]
                self._queue[key] = order
            while len(self._queue) > 24:
                self._queue.popitem(last=False)
            self._condition.notify_all()
        return True

    def _writer(self):
        while self._running:
            with self._condition:
                if not self._queue:
                    self._condition.wait(0.2)
                    continue
                _, command = self._queue.popitem(last=False)
            self.request_command(command)

    def _manager(self):
        while self._running:
            for port in self.find_available_ports():
                if not self._running:
                    break
                try:
                    conn = serial.Serial(port=None, baudrate=self.baudrate, timeout=0.2, write_timeout=1)
                    conn.port = port
                    conn.dtr = False
                    conn.rts = False
                    conn.open()
                    with self._condition:
                        self._conn = conn
                    if self.on_status_change:
                        self.on_status_change(True, port)
                    while self._running and conn.is_open:
                        line = conn.readline().decode("utf-8", errors="replace").strip()
                        if line:
                            self._process_line(line, port)
                except (OSError, serial.SerialException):
                    pass
                finally:
                    with self._condition:
                        if self._conn:
                            self._conn.close()
                        self._conn = None
                        self._condition.notify_all()
                    if self.on_status_change:
                        self.on_status_change(False, None)
            time.sleep(1)

    def _process_line(self, line, port=None):
        if line.startswith("RESULT UNO: "):
            with self._condition:
                self._result = line.removeprefix("RESULT UNO: ")
                self._condition.notify_all()
        elif line.startswith("ACK: "):
            with self._condition:
                self._result = line.removeprefix("ACK: ")
                self._condition.notify_all()

        telemetry_str = None
        if line.startswith("TELEMETRIA UNO: S,"):
            telemetry_str = line.split("S,", 1)[1]
        elif line.startswith("TX UART: S,"):
            telemetry_str = line.split("S,", 1)[1]
        elif line.startswith("S,"):
            telemetry_str = line.split("S,", 1)[1]

        if not telemetry_str:
            return
        try:
            data = list(map(int, telemetry_str.split(",")))
            if len(data) != 12:
                return
            t, h, flags, s0, s1, auto, uptime, de, se, lm, lcd, pca = data
        except ValueError:
            return
        with self._condition:
            self._last_frame = time.monotonic()
            self._hardware = dict(temp10=t, hum10=h, lm=bool(flags & 1), dht=bool(flags & 2),
                                  lcd=bool(flags & 4), pca=bool(flags & 8), s0=s0, s1=s1,
                                  auto=bool(auto), uptime=uptime, dhtErrors=de, serialErrors=se,
                                  lmAddr=lm, lcdAddr=lcd, pcaAddr=pca, ack=self._result or "")
        if self.on_telemetry:
            self.on_telemetry(t / 10 if t > -3000 else None, h / 10 if h >= 0 else None)
