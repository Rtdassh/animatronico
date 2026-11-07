#!/usr/bin/env python3
"""
=============================================================================
LANZADOR DEL SERVIDOR ANIMATRÓNICO CON TÚNEL HTTPS Y CÓDIGO QR EN CONSOLA
Proyecto: Cabeza Animatrónica con IA Local
=============================================================================
Inicia:
  1. Verificación y liberación automática de puerto 8000.
  2. Servidor local FastAPI (Uvicorn) en el puerto 8000.
  3. Túnel seguro HTTPS con Cloudflare (para acceso inmediato del micrófono en iPhone/Android).
  4. Código QR directo en consola para escanear con la cámara del celular.
"""

import subprocess
import threading

import socket
import time
import sys
import os
import re
import atexit
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CLOUDFLARED_BIN = BASE_DIR / "bin" / "cloudflared.exe"

global_tunnel_proc = None

def cleanup():
    global global_tunnel_proc
    if global_tunnel_proc:
        try:
            global_tunnel_proc.terminate()
        except Exception:
            pass

atexit.register(cleanup)

def ensure_port_available(port: int = 8000) -> bool:
    """Verifica si el puerto 8000 está libre; si está ocupado por una instancia previa, intenta liberarlo."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", port)) != 0:
            return True  # Puerto libre

    print(f"[*] El puerto {port} está ocupado por una instancia previa. Liberando...")
    try:
        if sys.platform.startswith("win"):
            out = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True, errors="ignore")
            pids = set()
            for line in out.strip().splitlines():
                parts = line.split()
                if len(parts) >= 5 and "LISTENING" in line.upper():
                    pids.add(parts[-1])
            for pid in pids:
                if pid and pid != str(os.getpid()):
                    try:
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
        else:
            subprocess.run(f"fuser -k {port}/tcp 2>/dev/null || lsof -ti:{port} | xargs kill -9 2>/dev/null", shell=True)
        time.sleep(1.0)
    except Exception:
        pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0

def get_local_ip() -> str:
    """Descubre la dirección IP local de la computadora en la red Wi-Fi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def print_qr(url: str):
    """Imprime un código QR escaneable directamente en la terminal."""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=1, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        print("\n" + "=" * 58)
        print("  ESCANEÁ ESTE CÓDIGO QR CON LA CÁMARA DE TU CELULAR:")
        print("=" * 58 + "\n")
        qr.print_ascii(invert=True)
        print("\n" + "=" * 58)
    except Exception:
        pass

def run_uvicorn():
    """Inicia el servidor web FastAPI con Uvicorn."""
    import uvicorn
    os.chdir(str(BASE_DIR))
    try:
        uvicorn.run("app:app", host="0.0.0.0", port=8000, log_level="warning")
    except Exception as e:
        print(f"\n[!] Error crítico al ejecutar Uvicorn: {e}")

def start_cloudflare_tunnel():
    """Inicia Cloudflare Tunnel para habilitar HTTPS móvil sin configuraciones complejas."""
    global global_tunnel_proc
    if not CLOUDFLARED_BIN.exists():
        return None, None

    try:
        cmd = [str(CLOUDFLARED_BIN), "tunnel", "--url", "http://127.0.0.1:8000"]
        tunnel_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="ignore"
        )
        global_tunnel_proc = tunnel_proc

        tunnel_url = None
        start_time = time.time()
        while time.time() - start_time < 15:
            line = tunnel_proc.stdout.readline()
            if not line:
                continue
            match = re.search(r"(https://[a-zA-Z0-9-]+\.trycloudflare\.com)", line)
            if match:
                tunnel_url = match.group(1)
                break

        return tunnel_proc, tunnel_url
    except Exception as e:
        print(f"[!] No se pudo iniciar el túnel Cloudflare: {e}")
        return None, None

def main():
    print("=" * 66)
    print("  SERVIDOR CENTRAL · ANIMATRONICO")
    print("=" * 66)

    # 1. Asegurar que el puerto 8000 esté libre
    if not ensure_port_available(8000):
        print("[!] ERROR: El puerto 8000 sigue ocupado. Cierra el proceso anterior.")
        return

    print("[*] Iniciando servidor FastAPI...")

    local_ip = get_local_ip()
    local_url = f"http://{local_ip}:8000"

    # Iniciar servidor Uvicorn en hilo secundario
    server_thread = threading.Thread(target=run_uvicorn, daemon=True)
    server_thread.start()
    time.sleep(1.5)

    print("\n[+] Servidor local activo en puerto 8000.")
    print(f"    - URL Local: {local_url}")

    print("[*] Habilitando tunel HTTPS para acceso movil...")
    tunnel_proc, tunnel_url = start_cloudflare_tunnel()

    active_mobile_url = tunnel_url if tunnel_url else local_url

    print("\n" + "#" * 66)
    print("  ACCESO DESDE DISPOSITIVO MOVIL:")
    print("#" * 66)
    if tunnel_url:
        print(f"\n  Enlace HTTPS:")
        print(f"     {tunnel_url}")
        print("\n  Enlace red local:")
        print(f"     {local_url}")
    else:
        print(f"\n  Abre en tu navegador: {local_url}")

    # Imprimir código QR
    print_qr(active_mobile_url)

    print("\n" + "-" * 66)
    print(" Presiona CTRL+C para detener el servidor.")
    print("-" * 66 + "\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        cleanup()
        sys.exit(0)

if __name__ == "__main__":
    main()
