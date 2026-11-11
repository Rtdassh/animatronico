#!/usr/bin/env python3
"""
=============================================================================
GESTOR OFICIAL DE GRABACIÓN DE FIRMWARE
Proyecto: Asistente de Escritorio Autónomo ("Gran Hermano") & Cabeza Animatrónica
Placas: Arduino Uno R3 (ATmega328P) y ESP32 DevKit V1 (ESP32-WROOM-32)
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
BIN_DIR = BASE_DIR / "build" / "firmware"

# Directorios de sketches (Por defecto en esta rama: Asistente Completo)
ARDUINO_ASISTENTE_DIR = FIRMWARE_DIR / "asistente_arduino"
ESP32_ASISTENTE_DIR = FIRMWARE_DIR / "asistente_esp32"

ARDUINO_ANIMATRONICO_DIR = FIRMWARE_DIR / "arduino_uno_animatronico"
ESP32_ANIMATRONICO_DIR = FIRMWARE_DIR / "esp32_puente_websocket"

ARDUINO_SKETCH_DIR = ARDUINO_ASISTENTE_DIR
ESP32_SKETCH_DIR = ESP32_ASISTENTE_DIR

ARDUINO_BIN_DIR = BIN_DIR / "arduino_uno"
ESP32_BIN_DIR = BIN_DIR / "esp32"

ARDUINO_BIN_DIR.mkdir(parents=True, exist_ok=True)
ESP32_BIN_DIR.mkdir(parents=True, exist_ok=True)

FQBN_ARDUINO = "arduino:avr:uno"
FQBN_ESP32 = "esp32:esp32:esp32"

def find_arduino_cli() -> str:
    """Localiza el binario de arduino-cli en el sistema."""
    cli = shutil.which("arduino-cli")
    if cli:
        return cli
    
    candidates = [
        BASE_DIR / "build" / "eyemech-tools" / "arduino-cli.exe",
        BASE_DIR / "build" / "eyemech-tools" / "arduino-cli",
        Path.home() / ".local" / "bin" / "arduino-cli",
        Path.home() / ".local" / "bin" / "arduino-cli.exe",
        Path("/usr/local/bin/arduino-cli"),
        Path("/usr/bin/arduino-cli"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "arduino-cli" / "arduino-cli.exe",
    ]
    for c in candidates:
        if c.exists() and (sys.platform.startswith("win") or os.access(c, os.X_OK)):
            return str(c)
    
    return "arduino-cli"

ARDUINO_CLI = find_arduino_cli()

CONFIG_YAML = BASE_DIR / "build" / "eyemech-tools" / "arduino-cli.yaml"
CLI_BASE_ARGS = ["--config-file", str(CONFIG_YAML)] if CONFIG_YAML.exists() else []

def get_connected_ports():
    """Detecta puertos serie conectados mediante arduino-cli y enumeración del sistema."""
    ports = []
    
    # 1. Consulta a arduino-cli en formato JSON
    try:
        proc = subprocess.run(
            [ARDUINO_CLI] + CLI_BASE_ARGS + ["board", "list", "--format", "json"],
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
        sketch_name = ARDUINO_SKETCH_DIR.name
        print(f"[COMPILANDO] Arduino Uno R3 ({sketch_name})...")
        cmd = [ARDUINO_CLI] + CLI_BASE_ARGS + [
            "compile",
            "--fqbn", FQBN_ARDUINO,
            "--output-dir", str(ARDUINO_BIN_DIR),
            str(ARDUINO_SKETCH_DIR)
        ]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"[ERROR] Falló la compilación de {sketch_name}.")
            return False
        print(f"[OK] Binarios de Arduino exportados en: {ARDUINO_BIN_DIR}")

    if target in ("esp32", "all"):
        sketch_name = ESP32_SKETCH_DIR.name
        print(f"[COMPILANDO] ESP32 DevKit V1 ({sketch_name})...")
        cmd = [ARDUINO_CLI] + CLI_BASE_ARGS + [
            "compile",
            "--fqbn", FQBN_ESP32,
            "--output-dir", str(ESP32_BIN_DIR),
            str(ESP32_SKETCH_DIR)
        ]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"[ERROR] Falló la compilación de {sketch_name}.")
            return False
        print(f"[OK] Binarios de ESP32 exportados en: {ESP32_BIN_DIR}")

    return True

def grabar_arduino(port: str) -> bool:
    """Graba el firmware en el Arduino Uno R3."""
    sketch_name = ARDUINO_SKETCH_DIR.name
    print(f"\n==================================================")
    print(f"GRABANDO ARDUINO UNO EN: {port}")
    print(f"Sketch objetivo: {sketch_name}")
    print(f"FQBN:            {FQBN_ARDUINO}")
    print(f"==================================================")

    if not compilar_firmware("arduino"):
        return False

    cmd = [ARDUINO_CLI] + CLI_BASE_ARGS + [
        "upload",
        "-p", port,
        "--fqbn", FQBN_ARDUINO,
        "--input-dir", str(ARDUINO_BIN_DIR)
    ]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print(f"\n[EXITO] Firmware '{sketch_name}' grabado correctamente en Arduino Uno.")
        return True
    else:
        print(f"\n[INFO] Reintentando compilación y subida directa...")
        cmd_direct = [ARDUINO_CLI] + CLI_BASE_ARGS + [
            "compile",
            "--upload",
            "-p", port,
            "--fqbn", FQBN_ARDUINO,
            str(ARDUINO_SKETCH_DIR)
        ]
        res_direct = subprocess.run(cmd_direct)
        if res_direct.returncode == 0:
            print(f"\n[EXITO] Firmware '{sketch_name}' grabado correctamente en Arduino Uno.")
            return True

        print(f"\n[ERROR] Falló la grabación de Arduino Uno.")
        print("Sugerencias:")
        print("1. Verifica que el cable USB esté conectado firmemente.")
        print("2. En Linux, asegúrate de tener permisos: sudo usermod -aG dialout $USER o sudo chmod 666 " + port)
        print("3. Cierra el Monitor Serie de Arduino IDE o cualquier consola que bloquee el puerto.")
        return False

def grabar_esp32(port: str) -> bool:
    """Graba el firmware en el ESP32 DevKit V1."""
    sketch_name = ESP32_SKETCH_DIR.name
    print(f"\n==================================================")
    print(f"GRABANDO ESP32 DEVKIT V1 EN: {port}")
    print(f"Sketch objetivo: {sketch_name}")
    print(f"FQBN:            {FQBN_ESP32}")
    print(f"==================================================")

    if not compilar_firmware("esp32"):
        return False

    print("[AVISO] Si la consola se detiene en 'Connecting....._____.....', mantén presionado el botón 'BOOT' en la placa ESP32.")

    cmd = [ARDUINO_CLI] + CLI_BASE_ARGS + [
        "upload",
        "-p", port,
        "--fqbn", FQBN_ESP32,
        "--input-dir", str(ESP32_BIN_DIR)
    ]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print(f"\n[EXITO] Firmware '{sketch_name}' grabado correctamente en ESP32.")
        return True
    else:
        print(f"\n[INFO] Reintentando compilación y subida directa...")
        cmd_direct = [ARDUINO_CLI] + CLI_BASE_ARGS + [
            "compile",
            "--upload",
            "-p", port,
            "--fqbn", FQBN_ESP32,
            str(ESP32_SKETCH_DIR)
        ]
        res_direct = subprocess.run(cmd_direct)
        if res_direct.returncode == 0:
            print(f"\n[EXITO] Firmware '{sketch_name}' grabado correctamente en ESP32.")
            return True

        print(f"\n[ERROR] Falló la grabación de ESP32.")
        print("Sugerencias:")
        print("1. Mantén presionado el botón 'BOOT' en el ESP32 mientras aparece 'Connecting...'.")
        print("2. Revisa que el cable microUSB soporte datos y no solo carga.")
        print("3. Cierra el monitor serie o cualquier otro software que ocupe el puerto.")
        return False
        res_direct = subprocess.run(cmd_direct)
        if res_direct.returncode == 0:
            print(f"\n[EXITO] Firmware '{sketch_name}' grabado correctamente en ESP32.")
            return True

        print(f"\n[ERROR] Falló la grabación de ESP32.")
        print("Sugerencias:")
        print("1. Mantén presionado el botón 'BOOT' en el ESP32 mientras aparece 'Connecting...'.")
        print("2. Revisa que el cable microUSB admita datos y no sea un cable solo de carga.")
        print("3. En Linux, otorga permisos: sudo chmod 666 " + port)
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
    global ARDUINO_SKETCH_DIR, ESP32_SKETCH_DIR

    while True:
        modo_str = "Asistente de Escritorio (Gran Hermano)" if ARDUINO_SKETCH_DIR == ARDUINO_ASISTENTE_DIR else "Cabeza Animatrónica"
        print("\n==================================================")
        print(" GESTOR DE GRABACIÓN DE FIRMWARE")
        print(f" MODO ACTIVO: {modo_str}")
        print("==================================================")
        print("1. Grabar Arduino Uno R3")
        print("2. Grabar ESP32 DevKit V1")
        print("3. Grabar ambos dispositivos en secuencia")
        print("4. Recompilar todos los binarios")
        print(f"5. Alternar firmware activo (Actual: {ARDUINO_SKETCH_DIR.name})")
        print("6. Listar puertos serie detectados")
        print("0. Salir")
        print("==================================================")

        opcion = input("Seleccione una opción [0-6]: ").strip()

        if opcion == "1":
            port = seleccionar_puerto_interactivo("Arduino Uno")
            if port:
                grabar_arduino(port)
        elif opcion == "2":
            port = seleccionar_puerto_interactivo("ESP32 DevKit V1")
            if port:
                grabar_esp32(port)
        elif opcion == "3":
            port_ard = seleccionar_puerto_interactivo("Arduino Uno")
            port_esp = seleccionar_puerto_interactivo("ESP32 DevKit V1")
            if port_ard:
                grabar_arduino(port_ard)
            if port_esp:
                grabar_esp32(port_esp)
        elif opcion == "4":
            compilar_firmware("all")
        elif opcion == "5":
            if ARDUINO_SKETCH_DIR == ARDUINO_ASISTENTE_DIR:
                ARDUINO_SKETCH_DIR = ARDUINO_ANIMATRONICO_DIR
                ESP32_SKETCH_DIR = ESP32_ANIMATRONICO_DIR
                print("\n[MODO CAMBIADO] Ahora activo: Cabeza Animatrónica.")
            else:
                ARDUINO_SKETCH_DIR = ARDUINO_ASISTENTE_DIR
                ESP32_SKETCH_DIR = ESP32_ASISTENTE_DIR
                print("\n[MODO CAMBIADO] Ahora activo: Asistente de Escritorio Autónomo.")
        elif opcion == "6":
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
    parser = argparse.ArgumentParser(description="Gestor oficial de grabación de firmware para Asistente de Escritorio y Animatrónico.")
    parser.add_argument("--arduino", "-a", metavar="PORT", help="Grabar Arduino Uno en el puerto indicado (ej. /dev/ttyACM0 o COM3)")
    parser.add_argument("--esp32", "-e", metavar="PORT", help="Grabar ESP32 en el puerto indicado (ej. /dev/ttyUSB0 o COM4)")
    parser.add_argument("--animatronico", action="store_true", help="Usar firmware original de la cabeza animatrónica en lugar del asistente")
    parser.add_argument("--asistente", action="store_true", help="Usar firmware del Asistente de Escritorio")
    parser.add_argument("--compile-only", "-c", choices=["arduino", "esp32", "all"], help="Compilar binarios sin grabar")
    parser.add_argument("--list", "-l", action="store_true", help="Listar puertos serie detectados")
    args = parser.parse_args()

    if args.animatronico:
        ARDUINO_SKETCH_DIR = ARDUINO_ANIMATRONICO_DIR
        ESP32_SKETCH_DIR = ESP32_ANIMATRONICO_DIR
    elif args.asistente:
        ARDUINO_SKETCH_DIR = ARDUINO_ASISTENTE_DIR
        ESP32_SKETCH_DIR = ESP32_ASISTENTE_DIR

    if args.list:
        ports = get_connected_ports()
        if ports:
            for p in ports:
                print(p["label"])
        else:
            print("No se encontraron placas serie conectadas.")
        return 0

    if args.compile_only:
        return 0 if compilar_firmware(args.compile_only) else 1

    if args.arduino:
        return 0 if grabar_arduino(args.arduino) else 1

    if args.esp32:
        return 0 if grabar_esp32(args.esp32) else 1

    # Si no se pasaron argumentos, ejecutar menú interactivo
    return menu_interactivo()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except FileNotFoundError as error:
        sys.exit(f"[ERROR] No se pudo ejecutar Arduino CLI: {error}")
