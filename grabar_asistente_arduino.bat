@echo off
REM =============================================================================
REM Grabador de firmware para Arduino Uno R3 (Asistente Completo - Windows)
REM =============================================================================
chcp 65001 >nul
title Grabador Arduino Uno R3 - Asistente Completo

set PORT=%~1
if "%PORT%"=="" (
    echo ==================================================
    echo  GRABACIÓN DE ARDUINO UNO R3 (ASISTENTE COMPLETO)
    echo ==================================================
    arduino-cli board list 2>nul
    echo.
    set /p PORT="Introduce el puerto COM (ejemplo: COM3): "
)

if "%PORT%"=="" (
    echo [ERROR] No se especificó ningún puerto.
    pause
    exit /b 1
)

python tools\grabar_firmware.py --asistente --arduino %PORT%
if errorlevel 1 (
    echo [ERROR] Hubo un problema al grabar Arduino Uno.
) else (
    echo [OK] Grabación finalizada exitosamente.
)
pause

