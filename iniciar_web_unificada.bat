@echo off
schtasks /Query /TN "Animatronico-Web-Unificada" >nul 2>nul
if %errorlevel% equ 0 (
  schtasks /Run /TN "Animatronico-Web-Unificada"
  echo Conecta el celular a Asistente-ESP32.
  echo Abre http://192.168.4.1 y usa sus enlaces de configuracion y aplicacion.
  echo La computadora debe permanecer en el Wi-Fi del ESP32.
  pause
  exit /b 0
)
cd /d "%~dp0server_pc"
if not exist "..\.venv\Scripts\python.exe" (
  echo Ejecuta primero: py -3.13 -m venv --system-site-packages .venv
  echo y despues: .venv\Scripts\python.exe -m pip install -r server_pc\requirements.txt
  pause
  exit /b 1
)
"..\.venv\Scripts\python.exe" run_unified.py --connect-wifi
pause
