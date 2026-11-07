#!/usr/bin/env bash
# =============================================================================
# Asistente interactivo de grabación de firmware (Linux)
# =============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/tools/grabar_firmware.py" "$@"

