# Funciones comunes del plan B (bloque 6). Se incluye con `. "$PSScriptRoot\comun_plan_b.ps1"`.
. "$PSScriptRoot\comun_disparador.ps1"

$ArchivoLog = Join-Path $CarpetaLogs "plan_b.log"
$CarpetaPendientes = Join-Path $Raiz "datos\pendientes"
$ArchivoIntentos = Join-Path $Raiz "datos\plan_b_intentos.tsv"
$CarpetaSalidas = Join-Path $CarpetaLogs "plan_b"
# Los worktrees van al lado del proyecto, no dentro: así la copia de trabajo principal no cambia
# y Claude Code no carga el CLAUDE.md del proyecto dos veces.
$CarpetaWorktrees = Join-Path (Split-Path $Raiz -Parent) ((Split-Path $Raiz -Leaf) + "-propuestas")
$NombreMutexPlanB = "Local\facturas-bi-plan-b-$IdProyecto"

# Variables que harían que Claude Code facture por API (o por un proveedor externo) en lugar de
# usar la suscripción. Se quitan por prefijo, para cubrir también las que se agreguen en el futuro.
$PatronesFacturacion = @("ANTHROPIC_*", "CLAUDE_CODE_USE_*", "AWS_BEARER_TOKEN_BEDROCK")

function Quitar-VariablesDeFacturacion {
    foreach ($patron in $PatronesFacturacion) {
        Get-ChildItem Env: | Where-Object { $_.Name -like $patron } | ForEach-Object {
            Remove-Item "Env:$($_.Name)"
        }
    }
}

function Hash-De([string]$Ruta) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Ruta).Hash.ToLowerInvariant()
}

function Intento-Registrado([string]$Sha) {
    if (-not (Test-Path $ArchivoIntentos)) { return $false }
    return [bool](Get-Content $ArchivoIntentos -Encoding UTF8 | Where-Object { $_.StartsWith("$Sha`t") })
}

# Una línea por intento: hash, fecha, archivo, rama y resultado, separados por tabuladores.
function Registrar-Intento([string]$Sha, [string]$Archivo, [string]$Rama, [string]$Resultado) {
    New-Item -ItemType Directory -Force (Split-Path $ArchivoIntentos) | Out-Null
    $linea = @($Sha, (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Archivo, $Rama, $Resultado) -join "`t"
    Add-Content -Path $ArchivoIntentos -Value $linea -Encoding UTF8
}

# El PDF pendiente más antiguo que todavía no tuvo un intento; $null si no hay.
function Siguiente-PdfSinIntento {
    if (-not (Test-Path $CarpetaPendientes)) { return $null }
    foreach ($pdf in (Get-ChildItem -Path $CarpetaPendientes -Filter *.pdf -File | Sort-Object LastWriteTime)) {
        if (-not (Intento-Registrado (Hash-De $pdf.FullName))) { return $pdf }
    }
    return $null
}

# Quita un worktree y su rama. El .venv del worktree es un enlace (junction) al del proyecto:
# se quita primero el enlace, para que el borrado nunca entre en el entorno virtual real.
function Quitar-Worktree([string]$Ruta, [string]$Rama) {
    $venv = Join-Path $Ruta ".venv"
    if (Test-Path $venv) { cmd /c rmdir "$venv" | Out-Null }
    if (Test-Path $Ruta) { git -C $Raiz worktree remove --force $Ruta 2>&1 | Out-Null }
    if (Test-Path $Ruta) { Remove-Item -Recurse -Force $Ruta -ErrorAction SilentlyContinue }
    git -C $Raiz worktree prune 2>&1 | Out-Null
    if ($Rama) { git -C $Raiz branch -D $Rama 2>&1 | Out-Null }
}
