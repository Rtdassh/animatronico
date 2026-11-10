@echo off
REM =============================================================================
REM Asistente interactivo de grabación de firmware (Windows)
REM =============================================================================
chcp 65001 >nul
title Grabador Firmware - Cabeza Animatronica

python tools\grabar_firmware.py --asistente %*
pause

