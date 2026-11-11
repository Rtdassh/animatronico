# Tarea sin desencadenadores automáticos: se inicia y detiene a petición.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\pythonw.exe'
$working = Join-Path $repo 'server_pc'
if (-not (Test-Path -LiteralPath $python)) { throw 'Falta el entorno .venv del proyecto.' }
$loggedUser = (Get-CimInstance Win32_ComputerSystem).UserName
if (-not $loggedUser) { throw 'No se encontró un usuario con sesión iniciada.' }
$action = New-ScheduledTaskAction -Execute $python -Argument '-u run_unified.py --connect-wifi --service' -WorkingDirectory $working
$principal = New-ScheduledTaskPrincipal -UserId $loggedUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
$definition = New-ScheduledTask -Action $action -Principal $principal -Settings $settings -Description 'Web HTTPS del asistente sobre el Wi-Fi del ESP32. Inicio y detención manual; sin acceso público.'
Register-ScheduledTask -TaskName 'Animatronico-Web-Unificada' -InputObject $definition -Force -ErrorAction Stop | Out-Null
Start-ScheduledTask -TaskName 'Animatronico-Web-Unificada' -ErrorAction Stop
Write-Output 'Servidor registrado e iniciado con permisos normales del usuario.'
