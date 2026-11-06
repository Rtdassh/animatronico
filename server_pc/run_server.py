#!/usr/bin/env python3
"""
Lanzador del Servidor Animatrónico con Generador de Código QR en Terminal
Proyecto: Cabeza Animatrónica con IA Local
"""

import sys
import socket
from pathlib import Path
import qrcode
import uvicorn

def get_local_ip():
    """Descubre la dirección IP local del equipo en la red Wi-Fi o Ethernet."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No necesita conectarse a internet realmente, solo resuelve la interfaz primaria
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def print_banner(url):
    print("=" * 64)
    print("   🤖 SERVIDOR CENTRAL · CABEZA ANIMATRÓNICA CON IA LOCAL")
    print("=" * 64)
    print(f"\n[URL MÓVIL] Abre esta dirección en el navegador de tu CELULAR:\n")
    print(f"       👉  {url}  👈\n")
    print("O ESCANEA EL SIGUIENTE CÓDIGO QR DIRECTO DESDE TU TELÉFONO:\n")

    # Generar código QR en terminal ASCII
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)

    print("\n" + "-" * 64)
    print(" [MICRÓFONO] Habla presionando el botón central de la app.")
    print(" [ALTAVOZ]   El teléfono reproducirá la respuesta de voz.")
    print(" [LIP-SYNC]  La mandíbula física del robot modulará con la voz.")
    print("-" * 64 + "\n")

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000
    mobile_url = f"http://{local_ip}:{port}"

    print_banner(mobile_url)

    # Iniciar servidor Uvicorn apuntando a app.py en server_pc
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True, app_dir=str(Path(__file__).parent))

