# Vigila datos\entrada\ y lanza la carga cuando pasan $EsperaSegundos sin archivos nuevos (un lote, una ejecución).
# Lo inicia el Programador de tareas al iniciar sesión. Una sola instancia por proyecto.
param([int]$EsperaSegundos = 20)
. "$PSScriptRoot\comun_disparador.ps1"

$instancia = New-Object System.Threading.Mutex($false, "Local\facturas-bi-vigilante-$IdProyecto")
$esMia = $false
try { $esMia = $instancia.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $esMia = $true }
if (-not $esMia) { exit 0 }

try {
    New-Item -ItemType Directory -Force $CarpetaEntrada | Out-Null
    $vigia = New-Object System.IO.FileSystemWatcher $CarpetaEntrada
    $vigia.InternalBufferSize = 64KB
    $vigia.NotifyFilter = [IO.NotifyFilters]'FileName, LastWrite, Size'
    $vigia.EnableRaisingEvents = $true
    Escribir-Log "Vigilante iniciado (espera de $EsperaSegundos s) en $CarpetaEntrada"

    # Lo que ya estaba en la carpeta al arrancar cuenta como novedad.
    $hayNovedad = (Contar-PdfsEnEntrada) -gt 0
    $ultimaNovedad = Get-Date
    while ($true) {
        $cambio = $vigia.WaitForChanged([IO.WatcherChangeTypes]::All, 2000)
        if (-not $cambio.TimedOut) {
            $hayNovedad = $true
            $ultimaNovedad = Get-Date
            continue
        }
        if ($hayNovedad -and ((Get-Date) - $ultimaNovedad).TotalSeconds -ge $EsperaSegundos) {
            $hayNovedad = $false
            Escribir-Log "Lote listo: se lanza la carga"
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "ejecutar_carga.ps1") | Out-Null
            # Si la carpeta fue borrada y recreada, el vigilante dejaría de ver: termina y la tarea lo reinicia.
            if (-not (Test-Path $CarpetaEntrada)) { Escribir-Log "La carpeta de entrada desapareció: el vigilante termina."; exit 1 }
        }
    }
} finally {
    Escribir-Log "Vigilante detenido"
    if ($esMia) { $instancia.ReleaseMutex() }
    $instancia.Dispose()
}
