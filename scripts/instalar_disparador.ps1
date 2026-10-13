# Instala (o reinstala: es idempotente) el vigilante y el barrido como tareas del usuario actual. No pide administrador.
# El vigilante se inicia al iniciar sesión; el barrido, al iniciar sesión y cada hora.
param([int]$MinutosBarrido = 60)
. "$PSScriptRoot\comun_disparador.ps1"
$ErrorActionPreference = "Stop"

$usuario = "$env:USERDOMAIN\$env:USERNAME"
# conhost --headless evita que aparezca una ventana de consola (Windows 11). La política de ejecución se pasa solo en esta línea.
function Nueva-Accion([string]$Script) {
    $argumentos = "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$(Join-Path $PSScriptRoot $Script)`""
    New-ScheduledTaskAction -Execute "conhost.exe" -Argument $argumentos -WorkingDirectory $Raiz
}
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
$alIniciarSesion = New-ScheduledTaskTrigger -AtLogOn -User $usuario

$ajustesVigilante = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $NombreTareaVigilante -Action (Nueva-Accion "vigilante.ps1") -Trigger $alIniciarSesion `
    -Settings $ajustesVigilante -Principal $principal -Description "Vigila datos\entrada de facturas-bi ($Raiz)" -Force | Out-Null

$cadaHora = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $MinutosBarrido) -RepetitionDuration (New-TimeSpan -Days 3650)
$ajustesBarrido = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $NombreTareaBarrido -Action (Nueva-Accion "barrido.ps1") -Trigger @($alIniciarSesion, $cadaHora) `
    -Settings $ajustesBarrido -Principal $principal -Description "Barrido de datos\entrada de facturas-bi ($Raiz)" -Force | Out-Null

# Arranca el vigilante ya, sin esperar al próximo inicio de sesión (si ya corre, la instancia nueva termina sola).
Start-ScheduledTask -TaskName $NombreTareaVigilante
Escribir-Log "Disparador instalado (tareas '$NombreTareaVigilante' y '$NombreTareaBarrido')"
Write-Host "Disparador instalado para $Raiz. Estado: scripts\estado_disparador.ps1"
