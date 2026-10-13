# Ficha del bloque 5: disparador de Windows

Complementa [`bloques/05_disparador.md`](../../bloques/05_disparador.md) con lo de este proyecto.

## Leer (solo esto)

- `bloques/04_carga.md`, «Comandos» y «Requisitos de la ejecución», sobre todo los códigos de salida.
- De `CLAUDE.md`, «Comandos de este proyecto»: cómo se invoca la carga. Lo agrega el bloque 4.

## Archivos

- Crea `scripts/instalar_disparador.ps1`, `scripts/desinstalar_disparador.ps1` y `scripts/estado_disparador.ps1`, más el vigilante y el barrido que el instalador registra.
- Si hacen falta tests de Python (por ejemplo, de la espera por lotes), van en `tests/test_disparador.py`.

## Interfaces

- La carga devuelve `0` (todo cargado o nada que hacer), `1` (hay PDFs nuevos en pendientes) o `2` (error del sistema), y ya tiene su propio bloqueo.
  - Si hay otra ejecución en curso, la segunda imprime «No se hizo nada…» y sale con `0`: el disparador puede lanzar la carga varias veces seguidas sin riesgo.
  - Un `1` cuenta solo los PDFs rechazados **en esa ejecución**; los que ya estaban en `pendientes/` no lo repiten.
  - La carga espera 3 s a que cada lote de PDFs deje de crecer antes de leerlo (tamaño estable y archivo que se puede abrir); un archivo que sigue cambiando 120 s queda en `entrada/` para la siguiente ejecución. El disparador no necesita esperar por su cuenta, pero sí volver a lanzar la carga si quedó algo en `entrada/`.
- Cómo se invoca: desde la raíz del proyecto, con `PYTHONPATH=src` (`$env:PYTHONPATH = "src"; .venv\Scripts\python -m facturas cargar`). El script tiene que fijar ambos.
- Con código `1`, se llama a `scripts/al_haber_pendientes.ps1` si existe. Lo crea el bloque 6.
- Los logs van a `datos/logs/`.

## Pendientes heredados

- (Bloque 4, parte B) `cargar` y `reprocesar --pendientes` respaldan solos si cargaron algo. Si el respaldo falla (la carpeta de Google Drive no existe o no está sincronizada), las facturas ya están cargadas y el comando sale con `2`: el disparador no debe reintentar la carga por eso, sino avisar. Sin `datos/config.toml`, la carga avisa y sale con `0`.

## Tests

- Del bloque: las pruebas manuales de los criterios de aceptación y, si existe, `.venv\Scripts\python -m pytest -q --tb=short tests\test_disparador.py`
- Al cerrar, todos: `.venv\Scripts\python -m pytest -q --tb=line`
