@echo off
title Servidor Animatronico Inteligente (Loquendo + Qwen Ollama)

echo ======================================================================
echo   VERIFICANDO ZONA CON COBERTURA MOVIL (HOTSPOT PARA ESP32)
echo ======================================================================
powershell -ExecutionPolicy Bypass -File "%~dp0tools\iniciar_hotspot.ps1"

cd /d "%~dp0\server_pc"
echo ======================================================================
echo   INICIANDO SERVIDOR CENTRAL ANIMATRONICO CON QWEN 2.5 Y LOQUENDO
echo ======================================================================

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" run_server.py
    goto end
)

if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" run_server.py
    goto end
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3.13 run_server.py
    goto end
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    python run_server.py
    goto end
)

echo [ERROR] No se pudo encontrar Python 3.13 en tu sistema.
pause

:end
