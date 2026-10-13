# Muestra si el disparador está instalado, si el vigilante corre y cómo terminó la última carga.
. "$PSScriptRoot\comun_disparador.ps1"

foreach ($nombre in $NombreTareaVigilante, $NombreTareaBarrido) {
    $tarea = Get-ScheduledTask -TaskName $nombre -ErrorAction SilentlyContinue
    if (-not $tarea) { Write-Host "$nombre : NO instalada"; continue }
    $info = Get-ScheduledTaskInfo -TaskName $nombre
    $ultima = if ($info.LastRunTime.Year -gt 2000) { $info.LastRunTime.ToString("yyyy-MM-dd HH:mm:ss") } else { "nunca" }
    Write-Host ("{0} : instalada ({1}); última ejecución {2}, resultado {3}" -f $nombre, $tarea.State, $ultima, $info.LastTaskResult)
}
$vigilantes = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine -like "*$PSScriptRoot*vigilante.ps1*" })
Write-Host ("Vigilante: {0}" -f $(if ($vigilantes.Count -gt 0) { "corriendo (PID $($vigilantes[0].ProcessId))" } else { "no está corriendo" }))
Write-Host ("PDFs esperando en entrada: {0}" -f (Contar-PdfsEnEntrada))
$ultimaCarga = if (Test-Path $ArchivoLog) { Get-Content $ArchivoLog -Tail 200 | Where-Object { $_ -match " Carga \(|ERROR:" } | Select-Object -Last 1 }
Write-Host ("Última carga: {0}" -f $(if ($ultimaCarga) { $ultimaCarga } else { "ninguna registrada" }))
