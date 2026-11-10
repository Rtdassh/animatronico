@echo off
REM =============================================================================
REM Grabador de firmware para ESP32 DevKit V1 (Asistente Completo - Windows)
REM =============================================================================
chcp 65001 >nul
title Grabador ESP32 DevKit V1 - Asistente Completo

set PORT=%~1
if "%PORT%"=="" (
    echo ==================================================
    echo  GRABACIÓN DE ESP32 DEVKIT V1 (ASISTENTE COMPLETO)
    echo ==================================================
    arduino-cli board list 2>nul
    echo.
    set /p PORT="Introduce el puerto COM (ejemplo: COM4): "
)

if "%PORT%"=="" (
    echo [ERROR] No se especificó ningún puerto.
    pause
    exit /b 1
)

python tools\grabar_firmware.py --asistente --esp32 %PORT%
if errorlevel 1 (
    echo [ERROR] Hubo un problema al grabar ESP32.
) else (
    echo [OK] Grabación finalizada exitosamente.
)
pause

