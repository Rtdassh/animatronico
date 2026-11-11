@echo off
REM =============================================================================
REM Grabador integral (Arduino Uno + ESP32)
REM =============================================================================
chcp 65001 >nul
title Grabador Cabeza Animatronica

set "PY_CMD=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
)

"%PY_CMD%" "%~dp0tools\grabar_firmware.py"
pause
