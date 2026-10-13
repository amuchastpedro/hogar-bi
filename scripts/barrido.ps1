# Barrido de respaldo: procesa lo que el vigilante no vio (PC apagada, vigilante caído). Solo lanza la carga si hay PDFs.
. "$PSScriptRoot\comun_disparador.ps1"
$n = Contar-PdfsEnEntrada
if ($n -eq 0) { exit 0 }
Escribir-Log "Barrido: $n PDFs en entrada, se lanza la carga"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "ejecutar_carga.ps1") | Out-Null
exit $LASTEXITCODE
