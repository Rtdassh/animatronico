@echo off
REM =============================================================================
REM Grabador de firmware para Arduino Uno R3 (Windows)
REM =============================================================================
chcp 65001 >nul
title Grabador Arduino Uno R3

set "PY_CMD=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
)

set PORT=%~1
if "%PORT%"=="" (
    echo ==================================================
    echo  GRABACIÓN DE ARDUINO UNO R3
    echo ==================================================
    "%PY_CMD%" "%~dp0tools\grabar_firmware.py" --list 2>nul
    echo.
    set /p PORT="Introduce el puerto COM (ejemplo: COM7): "
)

if "%PORT%"=="" (
    echo [ERROR] No se especificó ningún puerto.
    pause
    exit /b 1
)

"%PY_CMD%" "%~dp0tools\grabar_firmware.py" --arduino "%PORT%"
if errorlevel 1 (
    echo [ERROR] Hubo un problema al grabar.
    pause
    exit /b 1
)
echo [OK] Grabación finalizada.
pause
exit /b 0
