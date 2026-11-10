#!/usr/bin/env bash
# =============================================================================
# Grabador de firmware para Arduino Uno R3 (Asistente Completo)
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="$1"

if [ -z "$PORT" ]; then
    DETECTED=$(arduino-cli board list 2>/dev/null | grep -E "ttyACM|ttyUSB" | awk '{print $1}' | head -n 1 || true)
    if [ -n "$DETECTED" ]; then
        PORT="$DETECTED"
        echo "Puerto detectado automáticamente: $PORT"
    else
        echo "=================================================="
        echo " GRABACIÓN DE ARDUINO UNO R3 (ASISTENTE COMPLETO)"
        echo "=================================================="
        echo "Puertos serie disponibles:"
        ls -1 /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo " (No se detectaron puertos activos)"
        echo ""
        read -rp "Introduce el puerto serie (ejemplo: /dev/ttyACM0 o /dev/ttyUSB0): " PORT
    fi
fi

if [ -z "$PORT" ]; then
    echo "Error: No se especificó ningún puerto serie."
    exit 1
fi

python3 "$SCRIPT_DIR/tools/grabar_firmware.py" --asistente --arduino "$PORT"

