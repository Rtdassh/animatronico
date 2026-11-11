@echo off
REM =============================================================================
REM Asistente interactivo de grabación de firmware (Windows)
REM =============================================================================
chcp 65001 >nul
title Grabador Firmware - Cabeza Animatronica

python "%~dp0tools\grabar_firmware.py" %*
set "GRABACION_RESULTADO=%ERRORLEVEL%"
pause
exit /b %GRABACION_RESULTADO%

