@echo off
REM =============================================================================
REM Gestor Interactivo de Grabación de Firmware (Asistente Completo - Windows)
REM =============================================================================
chcp 65001 >nul
title Gestor Grabación - Asistente Completo
python tools\grabar_firmware.py --asistente %*
pause

