#!/usr/bin/env python3
"""
=============================================================================
UTILIDAD OFICIAL DE GRABACIÓN DE FIRMWARE
Proyecto: Cabeza Animatrónica con IA Local
Dispositivos: Arduino Uno R3 (PCA9685/Sensores) y ESP32 DevKit V1 (Pasarela Wi-Fi)
=============================================================================
"""

import os
import sys
import json
import glob
import shutil
import argparse
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FIRMWARE_DIR = BASE_DIR / "firmware"
BIN_DIR = FIRMWARE_DIR / "binarios"

ARDUINO_SKETCH_DIR = FIRMWARE_DIR / "asistente_arduino"
ESP32_SKETCH_DIR = FIRMWARE_DIR / "asistente_esp32"
ARDUINO_ANIMATRONICO_DIR = FIRMWARE_DIR / "arduino_uno_animatronico"
ESP32_ANIMATRONICO_DIR = FIRMWARE_DIR / "esp32_puente_websocket"

ARDUINO_BIN_DIR = BIN_DIR / "arduino_uno"
ESP32_BIN_DIR = BIN_DIR / "esp32"

FQBN_ARDUINO = "arduino:avr:uno"
FQBN_ESP32 = "esp32:esp32:esp32"

def find_arduino_cli() -> str:
    """Localiza el binario de arduino-cli en el sistema."""
    cli = shutil.which("arduino-cli")
    if cli:
        return cli
    
    candidates = [
        Path.home() / ".local" / "bin" / "arduino-cli",
        Path.home() / ".local" / "bin" / "arduino-cli.exe",
        Path("/usr/local/bin/arduino-cli"),
        Path("/usr/bin/arduino-cli"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "arduino-cli" / "arduino-cli.exe",
    ]
    for c in candidates:
        if c.exists() and os.access(c, os.X_OK):
            return str(c)
    
    return "arduino-cli"

ARDUINO_CLI = find_arduino_cli()

def get_connected_ports():
    """Detecta puertos serie conectados mediante arduino-cli y enumeración del sistema."""
    ports = []
    
    # 1. Consulta a arduino-cli en formato JSON
    try:
        proc = subprocess.run(
            [ARDUINO_CLI, "board", "list", "--format", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            detected = data.get("detected_ports", [])
            for item in detected:
                port_info = item.get("port", {})
                p_address = port_info.get("address")
                p_label = port_info.get("label", p_address)
                boards = item.get("boards", [])
                b_name = boards[0].get("name", "Dispositivo Serie") if boards else "Dispositivo Serie"
                if p_address:
                    ports.append({
                        "address": p_address,
                        "label": f"{p_address} ({b_name})",
                        "board": b_name
                    })
    except Exception:
        pass

    # 2. Respaldo en Linux (/dev/ttyACM*, /dev/ttyUSB*)
    if sys.platform.startswith("linux"):
        raw_ports = sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))
        existing_addresses = {p["address"] for p in ports}
        for rp in raw_ports:
            if rp not in existing_addresses:
                ports.append({
                    "address": rp,
                    "label": f"{rp} (Puerto USB-Serial)",
                    "board": "Puerto USB-Serial"
                })

    return ports

def compilar_firmware(target: str) -> bool:
    """Compila y exporta binarios para el microcontrolador seleccionado."""
    if target in ("arduino", "all"):
        print("[COMPILANDO] Arduino Uno R3 (ATmega328P)...")
        cmd = [
            ARDUINO_CLI, "compile",
            "--fqbn", FQBN_ARDUINO,
            "--output-dir", str(ARDUINO_BIN_DIR),
            str(ARDUINO_SKETCH_DIR)
        ]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print("[ERROR] Falló la compilación de Arduino Uno.")
            return False
        print(f"[OK] Binarios de Arduino exportados en: {ARDUINO_BIN_DIR}")

    if target in ("esp32", "all"):
        print("[COMPILANDO] ESP32 DevKit V1...")
        cmd = [
            ARDUINO_CLI, "compile",
            "--fqbn", FQBN_ESP32,
            "--output-dir", str(ESP32_BIN_DIR),
            str(ESP32_SKETCH_DIR)
        ]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print("[ERROR] Falló la compilación de ESP32.")
            return False
        print(f"[OK] Binarios de ESP32 exportados en: {ESP32_BIN_DIR}")

    return True

def grabar_arduino(port: str) -> bool:
    """Graba el firmware en el Arduino Uno R3."""
    print(f"\n==================================================")
    print(f"GRABANDO ARDUINO UNO EN: {port}")
    print(f"FQBN: {FQBN_ARDUINO}")
    print(f"==================================================")

    hex_file = ARDUINO_BIN_DIR / "arduino_uno_animatronico.ino.hex"
    if not hex_file.exists():
        print("[INFO] Binarios precompilados no encontrados. Compilando...")
        if not compilar_firmware("arduino"):
            return False

    cmd = [
        ARDUINO_CLI, "upload",
        "-p", port,
        "--fqbn", FQBN_ARDUINO,
        "--input-dir", str(ARDUINO_BIN_DIR)
    ]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\n[EXITO] Firmware de Arduino Uno grabado correctamente.")
        return True
    else:
        print("\n[ERROR] Falló la grabación de Arduino Uno.")
        print("Sugerencias:")
        print("1. Verifica que el cable USB esté conectado firmemente.")
        print("2. En Linux, asegúrate de pertenecer al grupo dialout (sudo usermod -aG dialout $USER).")
        print("3. Cierra el monitor serie o cualquier otro software que ocupe el puerto.")
        return False

def grabar_esp32(port: str) -> bool:
    """Graba el firmware en el ESP32 DevKit V1."""
    print(f"\n==================================================")
    print(f"GRABANDO ESP32 DEVKIT V1 EN: {port}")
    print(f"FQBN: {FQBN_ESP32}")
    print(f"==================================================")

    bin_file = ESP32_BIN_DIR / "esp32_puente_websocket.ino.bin"
    if not bin_file.exists():
        print("[INFO] Binarios precompilados no encontrados. Compilando...")
        if not compilar_firmware("esp32"):
            return False

    print("[AVISO] Si la conexión se detiene en 'Connecting....._____.....', mantén pulsado el botón 'BOOT' en la placa ESP32.")
    
    cmd = [
        ARDUINO_CLI, "upload",
        "-p", port,
        "--fqbn", FQBN_ESP32,
        "--input-dir", str(ESP32_BIN_DIR)
    ]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\n[EXITO] Firmware de ESP32 DevKit V1 grabado correctamente.")
        return True
    else:
        print("\n[ERROR] Falló la grabación de ESP32.")
        print("Sugerencias:")
        print("1. Mantén presionado el botón 'BOOT' en el ESP32 mientras aparece 'Connecting...'.")
        print("2. Revisa que el cable microUSB soporte datos y no solo carga.")
        print("3. En Linux, revisa permisos del puerto (sudo chmod 666 " + port + ").")
        return False

def seleccionar_puerto_interactivo(mensaje: str) -> str:
    """Muestra los puertos detectados y solicita al usuario seleccionar uno."""
    ports = get_connected_ports()
    if not ports:
        print("\n[ALERTA] No se detectaron placas conectadas automáticamente.")
        manual = input(f"Ingrese manualmente el puerto serie (ejemplo: /dev/ttyUSB0 o COM3): ").strip()
        return manual
    
    print(f"\nPuertos serie detectados para {mensaje}:")
    for idx, p in enumerate(ports, start=1):
        print(f"  [{idx}] {p['label']}")
    print(f"  [M] Ingresar puerto manualmente")

    while True:
        sel = input("Seleccione una opción: ").strip()
        if sel.upper() == "M":
            return input("Ingrese el puerto manual: ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(ports):
            return ports[int(sel) - 1]["address"]
        print("Opción inválida. Intente de nuevo.")

def menu_interactivo():
    """Menú interactivo en terminal."""
    print("==================================================")
    print(" GESTOR DE GRABACIÓN DE FIRMWARE - CABEZA ANIMATRÓNICA")
    print("==================================================")
    print("1. Grabar Arduino Uno R3 (PCA9685 + Sensores)")
    print("2. Grabar ESP32 DevKit V1 (Pasarela Wi-Fi WebSocket)")
    print("3. Grabar ambos dispositivos")
    print("4. Recompilar todos los binarios")
    print("5. Listar puertos serie detectados")
    print("0. Salir")
    print("==================================================")

    opcion = input("Seleccione una opción [1-5]: ").strip()

    if opcion == "1":
        port = seleccionar_puerto_interactivo("Arduino Uno")
        if port:
            grabar_arduino(port)
    elif opcion == "2":
        port = seleccionar_puerto_interactivo("ESP32 DevKit V1")
        if port:
            grabar_esp32(port)
    elif opcion == "3":
        port_ard = seleccionar_puerto_interactivo("Arduino Uno R3")
        port_esp = seleccionar_puerto_interactivo("ESP32 DevKit V1")
        if port_ard:
            grabar_arduino(port_ard)
        if port_esp:
            grabar_esp32(port_esp)
    elif opcion == "4":
        compilar_firmware("all")
    elif opcion == "5":
        ports = get_connected_ports()
        if ports:
            print("\nPuertos conectados:")
            for p in ports:
                print(f" - {p['label']}")
        else:
            print("\nNo se encontraron puertos serie conectados.")
    elif opcion == "0":
        sys.exit(0)
    else:
        print("Opción no reconocida.")

def main():
    global ARDUINO_SKETCH_DIR, ESP32_SKETCH_DIR
    parser = argparse.ArgumentParser(description="Grabador oficial de firmware para Asistente de Escritorio y Animatrónico.")
    parser.add_argument("--arduino", "-a", metavar="PORT", help="Grabar Arduino Uno en el puerto indicado (ej. /dev/ttyACM0 o COM3)")
    parser.add_argument("--esp32", "-e", metavar="PORT", help="Grabar ESP32 en el puerto indicado (ej. /dev/ttyUSB0 o COM4)")
    parser.add_argument("--animatronico", action="store_true", help="Usar firmware original de la cabeza animatrónica en lugar del asistente")
    parser.add_argument("--compile-only", "-c", choices=["arduino", "esp32", "all"], help="Compilar binarios sin grabar")
    parser.add_argument("--list", "-l", action="store_true", help="Listar puertos serie detectados")
    args = parser.parse_args()

    if args.animatronico:
        ARDUINO_SKETCH_DIR = ARDUINO_ANIMATRONICO_DIR
        ESP32_SKETCH_DIR = ESP32_ANIMATRONICO_DIR

    if args.list:
        ports = get_connected_ports()
        for p in ports:
            print(p["label"])
        return

    if args.compile_only:
        compilar_firmware(args.compile_only)
        return

    if args.arduino:
        grabar_arduino(args.arduino)
        return

    if args.esp32:
        grabar_esp32(args.esp32)
        return

    # Si no se pasaron argumentos, ejecutar menú interactivo
    menu_interactivo()

if __name__ == "__main__":
    main()

