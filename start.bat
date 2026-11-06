@echo off
title Servidor Animatronico Inteligente (Loquendo + Qwen Ollama)
cd /d "%~dp0\server_pc"
echo ======================================================================
echo   INICIANDO SERVIDOR CENTRAL ANIMATRONICO CON QWEN 2.5 Y LOQUENDO
echo ======================================================================
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" run_server.py
) else (
    python run_server.py
)
pause

