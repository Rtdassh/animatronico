@echo off
title Servidor Animatronico Inteligente (Loquendo + Qwen Ollama)
cd /d "%~dp0"
echo ======================================================================
echo   INICIANDO SERVIDOR CENTRAL ANIMATRONICO CON QWEN 2.5 Y LOQUENDO
echo ======================================================================

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
