# Funciones comunes del disparador. Se incluye con `. "$PSScriptRoot\comun_disparador.ps1"`.
# Las rutas se derivan de la ubicación de este script: no hay rutas fijas.

$Raiz = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CarpetaEntrada = Join-Path $Raiz "datos\entrada"
$CarpetaLogs = Join-Path $Raiz "datos\logs"
$ArchivoLog = Join-Path $CarpetaLogs "disparador.log"
$LimiteLog = 1MB

# Un identificador corto de la carpeta del proyecto, para que dos copias del proyecto no compartan mutex ni tareas.
$Sha = [System.Security.Cryptography.SHA1]::Create()
$IdProyecto = (($Sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Raiz.ToLowerInvariant())) | Select-Object -First 4 | ForEach-Object { $_.ToString("x2") }) -join "")
$NombreTareaVigilante = "facturas-bi vigilante $IdProyecto"
$NombreTareaBarrido = "facturas-bi barrido $IdProyecto"

function Escribir-Log([string]$Mensaje) {
    New-Item -ItemType Directory -Force $CarpetaLogs | Out-Null
    if ((Test-Path $ArchivoLog) -and (Get-Item $ArchivoLog).Length -gt $LimiteLog) {
        Move-Item -Force $ArchivoLog "$ArchivoLog.1"
    }
    $linea = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Mensaje
    Add-Content -Path $ArchivoLog -Value $linea -Encoding UTF8
}

function Contar-PdfsEnEntrada {
    if (-not (Test-Path $CarpetaEntrada)) { return 0 }
    return @(Get-ChildItem -Path $CarpetaEntrada -Filter *.pdf -File -ErrorAction SilentlyContinue).Count
}

# Notificación de Windows (toast), sin módulos ni administrador. Si falla, no interrumpe la carga.
# Queda también en el log. Con FACTURAS_SIN_AVISOS=1 (los tests) no se muestra.
function Notificar([string]$Titulo, [string]$Texto) {
    Escribir-Log "Aviso: ${Titulo}: $Texto"
    if ($env:FACTURAS_SIN_AVISOS -eq "1") { return }
    try {
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $t = [Security.SecurityElement]::Escape($Titulo)
        $c = [Security.SecurityElement]::Escape($Texto)
        $xml.LoadXml("<toast><visual><binding template=""ToastGeneric""><text>$t</text><text>$c</text></binding></visual></toast>")
        $idApp = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
        $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($idApp).Show($toast)
    } catch {
        Escribir-Log "No se pudo mostrar la notificación: $($_.Exception.Message)"
    }
}
