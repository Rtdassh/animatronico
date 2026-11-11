<#
.SYNOPSIS
    Activa y configura la Zona con cobertura inalámbrica móvil (Hotspot) de Windows
    en la banda de 2.4 GHz para que el ESP32 se conecte automáticamente y use
    el internet de esta laptop sin importar a qué red esté conectada la laptop.
#>

try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    [void][Windows.Networking.Connectivity.NetworkInformation, Windows.Networking.Connectivity, ContentType = WindowsRuntime]
    [void][Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager, Windows.Networking.NetworkOperators, ContentType = WindowsRuntime]

    $profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
    if ($null -eq $profile) {
        Write-Host "[HOTSPOT] Aviso: La laptop no está conectada a ninguna red de internet aún." -ForegroundColor Yellow
        exit 0
    }

    $mgr = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
    $cfg = $mgr.GetCurrentAccessPointConfiguration()

    # Asegurar banda de 2.4 GHz (compatible con ESP32)
    if ($cfg.Band -ne [Windows.Networking.NetworkOperators.TetheringWiFiBand]::TwoPointFourGigahertz) {
        try {
            $cfg.Band = [Windows.Networking.NetworkOperators.TetheringWiFiBand]::TwoPointFourGigahertz
            $asyncCfg = $mgr.ConfigureAccessPointAsync($cfg)
        } catch {}
    }

    if ($mgr.TetheringOperationalState -ne [Windows.Networking.NetworkOperators.TetheringOperationalState]::On) {
        Write-Host "[HOTSPOT] Activando Zona con cobertura móvil de Windows..." -ForegroundColor Cyan
        $asyncOp = $mgr.StartTetheringAsync()
        Start-Sleep -Seconds 2
    }

    Write-Host "[HOTSPOT] Estado: $($mgr.TetheringOperationalState) | Red: $($cfg.Ssid) | IP Gateway: 192.168.137.1" -ForegroundColor Green
} catch {
    Write-Host "[HOTSPOT] No se pudo activar automáticamente el Hotspot: $_" -ForegroundColor Yellow
}

