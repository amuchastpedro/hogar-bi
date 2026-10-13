# Lanza la carga, notifica el resultado y llama al punto de extensión del plan B.
# Lo usan el vigilante y el barrido. Es seguro lanzarlo varias veces: espera su turno y la carga es idempotente.
. "$PSScriptRoot\comun_disparador.ps1"

$mutex = New-Object System.Threading.Mutex($false, "Local\facturas-bi-carga-$IdProyecto")
$tengoTurno = $false
try {
    try { $tengoTurno = $mutex.WaitOne([TimeSpan]::FromMinutes(15)) } catch [System.Threading.AbandonedMutexException] { $tengoTurno = $true }
    if (-not $tengoTurno) { Escribir-Log "Otra carga sigue en curso después de 15 minutos: no se lanza esta."; exit 0 }

    $python = Join-Path $Raiz ".venv\Scripts\python.exe"
    $cargadas = 0; $rechazadas = 0; $codigo = 0; $detalleError = ""
    $env:PYTHONPATH = Join-Path $Raiz "src"
    Set-Location $Raiz

    # Un archivo que seguía cambiando queda en entrada/ ("omitida"): se vuelve a lanzar, con un tope.
    for ($vuelta = 1; $vuelta -le 5; $vuelta++) {
        $salida = Join-Path $env:TEMP "facturas-bi-$PID-salida.txt"
        $errores = Join-Path $env:TEMP "facturas-bi-$PID-errores.txt"
        $proceso = Start-Process -FilePath $python -ArgumentList "-m", "facturas", "cargar" -WorkingDirectory $Raiz `
            -NoNewWindow -Wait -PassThru -RedirectStandardOutput $salida -RedirectStandardError $errores
        $codigo = $proceso.ExitCode
        $texto = (Get-Content $salida -Raw -Encoding UTF8) + ""
        $detalleError = ((Get-Content $errores -Raw -Encoding UTF8) + "").Trim()
        Remove-Item $salida, $errores -ErrorAction SilentlyContinue

        $omitidas = 0
        if ($texto -match "Resumen: (\d+) cargadas, (\d+) duplicadas, (\d+) rechazadas, (\d+) omitidas") {
            $cargadas += [int]$Matches[1]; $rechazadas += [int]$Matches[3]; $omitidas = [int]$Matches[4]
        }
        Escribir-Log ("Carga (vuelta {0}): código {1}. {2}" -f $vuelta, $codigo, (($texto -split "`r?`n" | Where-Object { $_ -like "Resumen:*" }) -join " "))
        # Con 2 (error del sistema, incluso un respaldo fallido) no se reintenta: se avisa.
        if ($codigo -eq 2 -or $omitidas -eq 0 -or (Contar-PdfsEnEntrada) -eq 0) { break }
        Start-Sleep -Seconds 5
    }

    if ($codigo -eq 2) {
        $resumen = if ($detalleError) { $detalleError } else { "error del sistema; ver datos\logs\facturas.log" }
        if ($cargadas -gt 0) { $resumen = "$cargadas cargadas, pero: $resumen" }
        Escribir-Log "ERROR: $resumen"
        Notificar "Facturas: error" $resumen
    } elseif ($cargadas -gt 0 -or $rechazadas -gt 0) {
        $partes = @()
        if ($cargadas -gt 0) { $partes += "$cargadas $(if ($cargadas -eq 1) { 'factura cargada' } else { 'facturas cargadas' })" }
        if ($rechazadas -gt 0) { $partes += "$rechazadas $(if ($rechazadas -eq 1) { 'pendiente' } else { 'pendientes' })" }
        Notificar "Facturas" ($partes -join ", ")
    }

    # Punto de extensión del plan B (bloque 6): solo si esta ejecución rechazó algo.
    $extension = Join-Path $PSScriptRoot "al_haber_pendientes.ps1"
    if ($rechazadas -gt 0 -and (Test-Path $extension)) {
        Escribir-Log "Pendientes nuevos: se llama a al_haber_pendientes.ps1"
        try { & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $extension } catch { Escribir-Log "al_haber_pendientes.ps1 falló: $($_.Exception.Message)" }
    }
    exit $codigo
} finally {
    if ($tengoTurno) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
