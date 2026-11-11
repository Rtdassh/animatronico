# Ejecutar como administrador. Solo permite acceso desde el Wi-Fi del ESP32.
$ErrorActionPreference = 'Stop'
$ruleName = 'Animatronico Web ESP32'
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443,8001 -RemoteAddress 192.168.4.0/24 -Profile Any -ErrorAction Stop | Out-Null
}
Write-Output 'Acceso HTTPS y configuración habilitados solo para 192.168.4.0/24.'
