#!/usr/bin/env python3
"""
=============================================================================
LANZADOR DEL SERVIDOR ANIMATRÓNICO CON TÚNEL HTTPS Y CÓDIGO QR EN CONSOLA
Proyecto: Cabeza Animatrónica con IA Local
=============================================================================
Inicia:
  1. Servidor local FastAPI (Uvicorn) en el puerto 8000.
  2. Túnel seguro HTTPS con Cloudflare (para acceso inmediato del micrófono en iPhone/Android).
  3. Código QR directo en consola para escanear con la cámara del celular.
"""

import subprocess
import threading
import socket
import time
import sys
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CLOUDFLARED_BIN = BASE_DIR / "bin" / "cloudflared.exe"

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
    except Exception as e:
        pass

def run_uvicorn():
    """Inicia el servidor web FastAPI con Uvicorn."""
    import uvicorn
    os.chdir(str(BASE_DIR))
    uvicorn.run("app:app", host="0.0.0.0", port=8000, log_level="warning")

def start_cloudflare_tunnel():
    """Inicia Cloudflare Tunnel para habilitar HTTPS móvil sin configuraciones complejas."""
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
    print("  🤖 SERVIDOR CENTRAL · CABEZA ANIMATRÓNICA CON IA LOCAL 🎙️")
    print("=" * 66)
    print("[*] Iniciando servidor FastAPI y verificando entorno...")

    local_ip = get_local_ip()
    local_url = f"http://{local_ip}:8000"

    # Iniciar servidor Uvicorn en hilo secundario
    server_thread = threading.Thread(target=run_uvicorn, daemon=True)
    server_thread.start()
    time.sleep(2)

    print("\n[+] Servidor local activo en puerto 8000.")
    print(f"    - IP Local: {local_url}")

    print("[*] Habilitando túnel HTTPS para permisos de micrófono en teléfonos móviles...")
    tunnel_proc, tunnel_url = start_cloudflare_tunnel()

    active_mobile_url = tunnel_url if tunnel_url else local_url

    print("\n" + "#" * 66)
    print("  🚀 CÓMO CONECTARTE DESDE TU CELULAR (MICRÓFONO & ALTAVOZ):")
    print("#" * 66)
    if tunnel_url:
        print(f"\n  👉 ENLACE HTTPS (Recomendado para iPhone / Android):")
        print(f"     {tunnel_url}")
        print("\n  👉 ENLACE LOCAL (Misma red Wi-Fi):")
        print(f"     {local_url}")
    else:
        print(f"\n  👉 Abre en el navegador de tu celular: {local_url}")

    # Imprimir código QR
    print_qr(active_mobile_url)

    print("\n" + "-" * 66)
    print(" [MICRÓFONO] Habla presionando el botón central de la app móvil.")
    print(" [ALTAVOZ]   El teléfono reproduce la voz de Loquendo.")
    print(" [LIP-SYNC]  La mandíbula del robot se modula físicamente en vivo.")
    print(" [ESP32]     WebSocket listo para recibir al microcontrolador.")
    print("-" * 66)
    print("\nPresiona CTRL+C para detener el servidor.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        if tunnel_proc:
            tunnel_proc.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
