# Lanza el dashboard (Streamlit) desde la raíz del proyecto, con PYTHONPATH=src.
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz
$env:PYTHONPATH = "src"
& "$raiz\.venv\Scripts\python" -m streamlit run src\facturas\dashboard\app.py @args
