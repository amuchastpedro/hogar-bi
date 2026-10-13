<#
Plan B (bloque 6): un agente (Claude Code, no interactivo) investiga un PDF pendiente y propone
una corrección en una rama `propuesta/<formato>-<AAAAMMDD-HHMM>`, en un worktree aparte.

  scripts\plan_b.ps1 <archivo>      un intento a pedido (nombre en datos\pendientes\ o ruta)
  scripts\plan_b.ps1 -Automatico    los pendientes sin intento, de a uno (lo usa al_haber_pendientes.ps1)
  -Simular                          hace todo menos invocar a claude: worktree, rama e informe de prueba
  -LimiteMinutos                    duración máxima de cada intento (30)
  -Modelo                           modelo del agente (sonnet)

Un solo plan B a la vez: si ya hay uno en curso, termina sin hacer nada.
Códigos de salida: 0 bien (o nada que hacer), 1 el intento terminó sin propuesta utilizable,
2 no se pudo lanzar (sin claude, sin sesión, límite de uso) o error.
#>
param(
    [Parameter(Position = 0)][string]$Archivo,
    [switch]$Simular,
    [switch]$Automatico,
    [double]$LimiteMinutos = 30,
    [string]$Modelo = "sonnet"
)
. "$PSScriptRoot\comun_plan_b.ps1"

# Costo cero: nada de lo que se lance desde acá (git, python, claude) recibe variables de facturación por API.
Quitar-VariablesDeFacturacion

function Fallo-Entorno([string]$Motivo, [string]$NombrePdf) {
    Escribir-Log "No se lanza el plan B para ${NombrePdf}: $Motivo"
    Notificar "Plan B: no se pudo lanzar" "$Motivo. $NombrePdf queda pendiente."
    return "entorno"
}

# Comprueba que claude esté instalado y con una sesión de la suscripción. Devuelve la ruta o un motivo.
function Buscar-Claude {
    # Solo ejecutables de Windows: npm instala también un script de sh sin extensión que Start-Process no lanza.
    $comando = Get-Command claude -CommandType Application -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in ".exe", ".cmd", ".bat" } | Select-Object -First 1
    if (-not $comando) { return @{ Motivo = "Claude Code no está instalado (no se encontró claude)" } }
    $estado = $null
    try { $estado = (& $comando.Source auth status 2>$null | Out-String) | ConvertFrom-Json } catch { }
    if (-not $estado -or -not $estado.loggedIn) {
        return @{ Motivo = "no hay una sesión iniciada en Claude Code (ejecutá claude auth login)" }
    }
    if ($estado.authMethod -ne "claude.ai") {
        return @{ Motivo = "Claude Code no usa la suscripción (método: $($estado.authMethod)); no se lanza para no facturar por API" }
    }
    return @{ Ruta = $comando.Source }
}

function Escribir-Informe([string]$Ruta, [string]$Titulo, [string]$NombrePdf, [string]$Etapa, [string]$Motivo, [string]$Cuerpo) {
    New-Item -ItemType Directory -Force (Split-Path $Ruta) | Out-Null
    $texto = @"
# $Titulo

- **PDF pendiente:** ``ejemplos/plan_b/$NombrePdf`` (copia local, fuera de git)
- **Etapa del rechazo:** $Etapa
- **Motivo:** $Motivo

$Cuerpo
"@
    [IO.File]::WriteAllText($Ruta, $texto, (New-Object Text.UTF8Encoding $false))
}

# Un intento sobre un PDF pendiente. Devuelve: propuesta, sin_correccion, tiempo_agotado, error o entorno.
function Intentar([IO.FileInfo]$Pdf) {
    $sha = Hash-De $Pdf.FullName
    $archivoMotivo = Join-Path $Pdf.DirectoryName ($Pdf.BaseName + ".motivo.txt")
    $lineasMotivo = if (Test-Path $archivoMotivo) { Get-Content $archivoMotivo -Encoding UTF8 } else { @() }
    $etapa = [string]($lineasMotivo | Where-Object { $_ -like "Etapa:*" } | Select-Object -First 1) -replace "^Etapa:\s*", ""
    $motivo = [string]($lineasMotivo | Where-Object { $_ -like "Motivo:*" } | Select-Object -First 1) -replace "^Motivo:\s*", ""
    if (-not $etapa) { $etapa = "desconocida" }
    if (-not $motivo) { $motivo = "sin archivo de motivo" }

    $claude = $null
    if (-not $Simular) {
        $busqueda = Buscar-Claude
        if (-not $busqueda.Ruta) { return (Fallo-Entorno $busqueda.Motivo $Pdf.Name) }
        $claude = $busqueda.Ruta
    }

    # Formato y extracción guardada, de la tabla `carga` (solo lectura).
    $python = Join-Path $Raiz ".venv\Scripts\python.exe"
    $extraccionTemporal = Join-Path $env:TEMP "facturas-bi-plan-b-$PID.json"
    Remove-Item $extraccionTemporal -ErrorAction SilentlyContinue
    $formato = ([string](& $python (Join-Path $Raiz "scripts\plan_b\carga_pendiente.py") $sha $extraccionTemporal 2>$null | Select-Object -Last 1)).Trim()
    if (-not $formato) { $formato = "desconocido" }

    # Rama y worktree.
    $sufijo = "$formato-" + (Get-Date -Format "yyyyMMdd-HHmm")
    $base = $sufijo; $n = 2
    while (git -C $Raiz branch --list "propuesta/$sufijo") { $sufijo = "$base-$n"; $n++ }
    $rama = "propuesta/$sufijo"
    $worktree = Join-Path $CarpetaWorktrees $sufijo
    $principal = (git -C $Raiz symbolic-ref --short HEAD).Trim()
    $antes = (git -C $Raiz rev-parse "refs/heads/$principal").Trim()
    New-Item -ItemType Directory -Force $CarpetaWorktrees | Out-Null
    $salidaGit = git -C $Raiz worktree add -q -b $rama $worktree $antes 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        Escribir-Log "ERROR: no se pudo crear el worktree $worktree para ${rama}: $($salidaGit.Trim())"
        Notificar "Plan B: error" "No se pudo crear el worktree para $($Pdf.Name). Ver datos\logs\plan_b.log"
        Remove-Item $extraccionTemporal -ErrorAction SilentlyContinue
        Registrar-Intento $sha $Pdf.Name $rama "error"
        return "error"
    }
    Escribir-Log "Intento para $($Pdf.Name) ($etapa): rama $rama, worktree $worktree$(if ($Simular) { ' (simulación)' })"

    # Lo que el agente necesita y no está en git: el entorno virtual (enlace), los ejemplos y el pendiente.
    # El PDF pendiente se copia con un nombre sin identificadores, en ejemplos/plan_b/, que el glob de los tests no ve.
    if (Test-Path (Join-Path $Raiz ".venv")) { cmd /c mklink /J "$worktree\.venv" "$Raiz\.venv" | Out-Null }
    $ejemplos = Join-Path $worktree "ejemplos"
    if (Test-Path (Join-Path $Raiz "ejemplos")) { Copy-Item (Join-Path $Raiz "ejemplos") $worktree -Recurse -Force }
    $carpetaPendiente = Join-Path $ejemplos "plan_b"
    New-Item -ItemType Directory -Force $carpetaPendiente | Out-Null
    Copy-Item -LiteralPath $Pdf.FullName (Join-Path $carpetaPendiente "$sufijo.pdf")
    if (Test-Path $archivoMotivo) { Copy-Item -LiteralPath $archivoMotivo (Join-Path $carpetaPendiente "$sufijo.motivo.txt") }
    $hayExtraccion = Test-Path $extraccionTemporal
    if ($hayExtraccion) { Move-Item $extraccionTemporal (Join-Path $carpetaPendiente "$sufijo.extraccion.json") -Force }
    $archivoTexto = Join-Path $carpetaPendiente "$sufijo.texto.txt"
    $texto = & $python (Join-Path $Raiz "scripts\plan_b\texto_pdf.py") (Join-Path $carpetaPendiente "$sufijo.pdf") 2>&1 | Out-String
    [IO.File]::WriteAllText($archivoTexto, $texto, (New-Object Text.UTF8Encoding $false))

    $informeRelativo = "docs/propuestas/$sufijo.md"
    $informe = Join-Path $worktree $informeRelativo
    $resultado = "propuesta"

    if ($Simular) {
        Escribir-Informe $informe "Propuesta $rama (SIMULACIÓN)" "$sufijo.pdf" $etapa $motivo @"
## Simulación

Informe de prueba generado por ``plan_b.ps1 -Simular``: no se invocó a Claude Code y no hay cambios de código.
Sirve para probar de punta a punta la revisión, la aprobación y el rechazo.

## Decisiones pendientes

Ninguna.
"@
        git -C $worktree add -- $informeRelativo 2>&1 | Out-Null
        git -C $worktree commit -q -m "plan B (simulación): informe de prueba para $rama" 2>&1 | Out-Null
    } else {
        $prompt = @"
Sos el agente del plan B de este proyecto. Seguí scripts/plan_b/instrucciones.md al pie de la letra.

- PDF pendiente: ejemplos/plan_b/$sufijo.pdf
- Texto que ven los parsers: ejemplos/plan_b/$sufijo.texto.txt
- Etapa del rechazo: $etapa
- Motivo del rechazo: $motivo
- Extracción guardada: $(if ($hayExtraccion) { "ejemplos/plan_b/$sufijo.extraccion.json" } else { "no hay (el rechazo fue antes de extraer)" })
- Formato: $formato
- Rama, ya creada y activa en este worktree: $rama
- Informe a escribir: $informeRelativo
"@
        New-Item -ItemType Directory -Force $CarpetaSalidas | Out-Null
        $archivoPrompt = Join-Path $CarpetaSalidas "$sufijo.prompt.txt"
        $archivoSalida = Join-Path $CarpetaSalidas "$sufijo.salida.json"
        $archivoErrores = Join-Path $CarpetaSalidas "$sufijo.errores.txt"
        [IO.File]::WriteAllText($archivoPrompt, $prompt, (New-Object Text.UTF8Encoding $false))
        $permisos = Join-Path $worktree "scripts\plan_b\permisos.json"
        # Herramientas: leer, editar, buscar y Bash (los permisos limitan Bash a los tests, git y texto_pdf.py).
        # Sin web, sin servidores MCP, sin skills y sin la configuración del usuario.
        $argumentos = @(
            "-p", "--model", $Modelo, "--output-format", "json",
            "--permission-mode", "dontAsk", "--settings", "`"$permisos`"", "--setting-sources", "project",
            "--tools", "Read,Edit,Write,Glob,Grep,Bash", "--strict-mcp-config", "--disable-slash-commands"
        ) -join " "
        $proceso = Start-Process -FilePath $claude -ArgumentList $argumentos -WorkingDirectory $worktree -WindowStyle Hidden -PassThru `
            -RedirectStandardInput $archivoPrompt -RedirectStandardOutput $archivoSalida -RedirectStandardError $archivoErrores
        $null = $proceso.Handle  # sin esto, PowerShell 5.1 no guarda el código de salida
        if (-not $proceso.WaitForExit([int]($LimiteMinutos * 60000))) {
            taskkill /PID $proceso.Id /T /F 2>&1 | Out-Null
            $proceso.WaitForExit(10000) | Out-Null
            $resultado = "tiempo_agotado"
            Escribir-Log "Tiempo agotado ($LimiteMinutos min): se detuvo al agente"
        }
        $salida = ((Get-Content $archivoSalida -Raw -Encoding UTF8) + "") + ((Get-Content $archivoErrores -Raw -Encoding UTF8) + "")
        if ($resultado -ne "tiempo_agotado") {
            $limite = $salida -match "(?i)usage limit|limit reached|hit your limit|out of extra usage|rate limit"
            $sinSesion = $salida -match "(?i)not logged in|please run /login|invalid api key|authentication_error"
            if ($limite -or $sinSesion) {
                Quitar-Worktree $worktree $rama
                $texto = if ($limite) { "se alcanzó el límite de uso del plan" } else { "Claude Code no tiene una sesión válida" }
                return (Fallo-Entorno $texto $Pdf.Name)
            }
            if ($proceso.ExitCode -ne 0) { $resultado = "error"; Escribir-Log "claude terminó con código $($proceso.ExitCode)" }
        }
    }

    # Siempre queda algo que revisar: si el agente no dejó informe o cambios sin commit, se completan acá.
    if (-not (Test-Path $informe)) {
        $detalle = if ($resultado -eq "tiempo_agotado") { "El agente superó la duración máxima ($LimiteMinutos min) y se detuvo." } else { "El agente terminó sin escribir el informe (resultado: $resultado)." }
        Escribir-Informe $informe "Propuesta $rama (sin informe del agente)" "$sufijo.pdf" $etapa $motivo @"
## Qué pasó

$detalle La salida de Claude Code está en ``datos/logs/plan_b/$sufijo.salida.json`` y ``.errores.txt``.
Lo que haya cambiado en el código está en esta rama, sin revisar: no aprobar sin mirarlo.

## Decisiones pendientes

Decidir si se vuelve a intentar a pedido (``scripts\plan_b.ps1 <archivo>``) o se corrige a mano.
"@
        if ($resultado -eq "propuesta") { $resultado = "error" }
    }
    if (git -C $worktree status --porcelain) {
        git -C $worktree add -A 2>&1 | Out-Null
        git -C $worktree commit -q -m "plan B: cambios que el agente no llegó a commitear ($rama)" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Escribir-Log "ERROR: no se pudo hacer commit en $rama (¿el hook de datos personales?)"; $resultado = "error" }
    }

    # La rama principal no puede haber cambiado.
    $despues = (git -C $Raiz rev-parse "refs/heads/$principal").Trim()
    if ($despues -ne $antes) {
        Escribir-Log "ALERTA: la rama $principal cambió durante el plan B ($antes -> $despues)"
        Notificar "Plan B: ALERTA" "La rama $principal cambió durante el plan B. Revisar antes de seguir."
        $resultado = "error"
    }

    $cambiados = @(git -C $Raiz diff --name-only $antes $rama)
    $codigo = @($cambiados | Where-Object { $_ -and $_ -notlike "docs/propuestas/*" })
    if ($resultado -eq "propuesta" -and -not $Simular -and $codigo.Count -eq 0) { $resultado = "sin_correccion" }
    if ($Simular) { $resultado = "simulacion" }

    Registrar-Intento $sha $Pdf.Name $rama $resultado
    Escribir-Log "Resultado para $($Pdf.Name): $resultado ($($cambiados.Count) archivos cambiados en $rama)"
    $revisar = "Rama ${rama}: cómo revisarla, en el README (Plan B)"
    switch ($resultado) {
        { $_ -in "propuesta", "simulacion" } { Notificar "Plan B" "Propuesta lista para $($Pdf.Name). $revisar" }
        "sin_correccion" { Notificar "Plan B" "Sin corrección segura para $($Pdf.Name): el informe tiene el diagnóstico. $revisar" }
        default { Notificar "Plan B: revisar" "El intento para $($Pdf.Name) terminó con: $resultado. $revisar" }
    }
    return $resultado
}

$mutex = New-Object System.Threading.Mutex($false, $NombreMutexPlanB)
$tengoTurno = $false
try {
    try { $tengoTurno = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $tengoTurno = $true }
    if (-not $tengoTurno) { Escribir-Log "Ya hay un plan B en curso: no se lanza otro."; exit 0 }

    if ($Automatico) {
        # Vuelve a mirar después de cada intento, para recoger los pendientes que llegaron mientras tanto.
        $codigo = 0
        while ($pdf = Siguiente-PdfSinIntento) {
            if ((Intentar $pdf) -eq "entorno") { $codigo = 2; break }
        }
        exit $codigo
    }

    if (-not $Archivo) { Write-Output "Uso: scripts\plan_b.ps1 <archivo de datos\pendientes> [-Simular]"; exit 2 }
    $ruta = if (Test-Path -LiteralPath $Archivo -PathType Leaf) { $Archivo } else { Join-Path $CarpetaPendientes $Archivo }
    if (-not (Test-Path -LiteralPath $ruta -PathType Leaf)) { Write-Output "No existe $Archivo en datos\pendientes\"; exit 2 }
    $pdf = Get-Item -LiteralPath $ruta
    if ($pdf.DirectoryName -ne (Get-Item $CarpetaPendientes).FullName) { Write-Output "$Archivo no está en datos\pendientes\"; exit 2 }

    $resultado = Intentar $pdf
    Write-Output "Plan B para $($pdf.Name): $resultado"
    switch ($resultado) {
        { $_ -in "propuesta", "simulacion" } { exit 0 }
        "entorno" { exit 2 }
        default { exit 1 }
    }
} finally {
    if ($tengoTurno) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
