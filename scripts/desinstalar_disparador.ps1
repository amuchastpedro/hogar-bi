# Quita las tareas y detiene el vigilante y cualquier carga lanzada por el disparador. Si no hay nada instalado, no hace nada.
. "$PSScriptRoot\comun_disparador.ps1"

foreach ($nombre in $NombreTareaVigilante, $NombreTareaBarrido) {
    if (Get-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $nombre -Confirm:$false
    }
}
# Procesos del disparador de este proyecto (el vigilante, el barrido y la carga), por línea de comandos.
$propios = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $_.CommandLine -and $_.CommandLine -like "*$PSScriptRoot*" -and
    $_.CommandLine -match "vigilante\.ps1|barrido\.ps1|ejecutar_carga\.ps1"
}
foreach ($p in $propios) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Escribir-Log "Disparador desinstalado"
Write-Host "Disparador desinstalado."
