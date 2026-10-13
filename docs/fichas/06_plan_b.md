# Ficha del bloque 6: plan B

Complementa [`bloques/06_plan_b.md`](../../bloques/06_plan_b.md) con lo de este proyecto. El bloque va en dos sesiones, la parte A y la parte B, cada una con su punto de control.

## Leer (solo esto)

- `bloques/04_carga.md`, «Comandos» y «Requisitos de la ejecución».
- `docs/diseno.md`:
  - §13.3, cada tipo de fallo;
  - §12.5, el formato de las semillas, que es lo que el agente edita para agregar un alias.
- `docs/diseno.md` §14, solo las reglas de dependencia: lo que el agente no puede romper.
- `claude --help`, para las opciones vigentes de herramientas y permisos.

## Archivos

- Parte A:
  - crea `scripts/al_haber_pendientes.ps1` y `scripts/plan_b.ps1`, con `-Simular`;
  - crea `scripts/plan_b/instrucciones.md`;
  - crea `tests/test_plan_b.py`, que verifica que el proceso hijo no recibe variables de facturación por API.
- Parte B:
  - crea `scripts/listar_propuestas.ps1`, `revisar_propuesta.ps1`, `aprobar_propuesta.ps1` y `rechazar_propuesta.ps1`;
  - las propuestas quedan en `docs/propuestas/`.

## Interfaces

- El bloque 5 llama a `scripts/al_haber_pendientes.ps1` cuando la carga termina con código `1`.
- La carga: `reprocesar --pendientes` (después de aprobar) y `reprocesar --todo`. La sintaxis está en «Comandos de este proyecto» de `CLAUDE.md`.
- Los motivos de rechazo están en `datos/pendientes/<nombre>.motivo.txt` (el nombre del PDF sin extensión; tres líneas: `Etapa:`, `Motivo:` y `Fecha:`) y en la tabla de cargas (`etapa_rechazo`, `motivo_rechazo`).
  - En la etapa `traduccion`, `invariantes`, `insercion` y `duplicado`, `carga.extraccion_json` guarda la extracción: el agente puede proponer un alias sin volver a leer el PDF. En `formato` y `extraccion` no hay extracción, solo el PDF.
  - `formato` es nulo en la etapa `formato`; en `extraccion` dice qué parser lo reconoció.
- Si cambian las semillas (por ejemplo, un alias aprobado), `cargar` y `reprocesar --pendientes` reconstruyen la base antes de procesar. Si la reconstrucción falla, salen con `2` y la base anterior queda intacta; el mensaje lista los PDFs que no se pudieron cargar.
- `reprocesar --todo` con otro parser puede cambiar el alias por defecto de los contratos de una categoría con más de uno (D7); avisa cuáles.

## Notas

- `claude -p` también carga `CLAUDE.md`, que remite a `scripts/plan_b/instrucciones.md`.
- Para que el agente no reciba herramientas que no usa (y gaste menos cupo), conviene lanzarlo con `--strict-mcp-config`, sin servidores MCP. Verificarlo en `claude --help`.

## Pendientes heredados (bitácora, bloque 1)

- Parte B: `aprobar_propuesta.ps1` hace una reconstrucción de prueba en un archivo temporal antes de confirmar la integración, porque la reconstrucción vuelve a extraer todo `procesadas/` con el parser de la propuesta (H15).
- (Bloque 3) Los parsers tienen versión (`VERSION`, a incrementar en cada cambio) y comparten `parsers/comun.py`. El gas lee el ajuste parcial (rectificativa por diferencias); los demás rechazan las rectificativas y los abonos con un error explícito: hasta que haya un ejemplo real, esos PDFs llegan a `pendientes/` y el plan B los ve como un formato sin parser. Los tests de parsers son la red de seguridad: corren en unos 2 s.

- (Bloque 5) `ejecutar_carga.ps1` llama a `scripts/al_haber_pendientes.ps1` sin argumentos, de forma síncrona y con el bloqueo del disparador tomado, cuando esa ejecución rechazó algo. Tiene que lanzar el trabajo largo (el agente) desacoplado, p. ej. con `Start-Process`, y volver enseguida; si no, las cargas siguientes esperan (hasta 15 min). Con varias llamadas seguidas no debe lanzar dos agentes a la vez.

## Parte A hecha (2026-10-06): lo que la parte B usa

Detalle en la bitácora («Bloque 6, parte A»). Para la parte B, leer solo esto y `scripts/comun_plan_b.ps1`:

- `scripts/comun_plan_b.ps1`: `$Raiz`, `$CarpetaWorktrees` (`..\<proyecto>-propuestas\`), `$ArchivoIntentos`, `Escribir-Log` (a `datos/logs/plan_b.log`), `Notificar`, `Intento-Registrado` y **`Quitar-Worktree <ruta> <rama>`**, que quita primero el enlace `.venv` del worktree (es una junction al `.venv` real: borrar el worktree sin quitarla podría vaciar el entorno virtual). Los scripts de aprobación y rechazo la usan; nunca `Remove-Item -Recurse` sobre un worktree.
- Rama `propuesta/<sufijo>`, con `<sufijo>` = `<formato>-<AAAAMMDD-HHMM>`; worktree en `$CarpetaWorktrees\<sufijo>`; informe en `docs/propuestas/<sufijo>.md`, con las líneas `- **Clasificación del fallo:**` y `- **Resultado:**` (formato en `scripts/plan_b/instrucciones.md`, «Informe»). El de `-Simular` dice «SIMULACIÓN».
- Un rechazo no tiene que borrar la línea de `datos/plan_b_intentos.tsv`: así el PDF no se reintenta automáticamente.

## Pendientes para la parte B

- `aprobar_propuesta.ps1`: antes de quitar el worktree, copiar `ejemplos/plan_b/<sufijo>.pdf` del worktree a `ejemplos/plan_b/` del proyecto. Sin eso, los tests nuevos que leen el PDF pendiente se saltan después de aprobar.
- `aprobar_propuesta.ps1`: la reconstrucción de prueba en un archivo temporal (H15, abajo).
- Las pruebas de aprobación y rechazo con `-Simular`, en una copia del proyecto: `-Simular` registra el intento y la aprobación ejecuta `reprocesar --pendientes`.
- La ejecución real (con permiso de la persona usuaria en ese momento). Verificar ahí lo que la parte A no pudo:
  - que `claude` 2.1.x acepta las opciones juntas;
  - que en `dontAsk`, con `permisos.json`, el agente puede leer y buscar en el worktree y ejecutar pytest y git, y nada fuera;
  - que `datos/logs/plan_b/<sufijo>.salida.json` no muestra facturación por API.
- Que el proceso que crea `al_haber_pendientes.ps1` (por WMI) sobrevive al final de la tarea programada: dejar un PDF inválido en `datos/entrada/` de una copia con el disparador instalado.
- Decisión de la persona usuaria (punto de control de la parte A): qué hacer con los PDFs que ya estaban en `datos/pendientes/` antes del plan B.

## Tests

- Del bloque: `.venv\Scripts\python -m pytest -q --tb=short tests\test_plan_b.py` (12 en la parte A, unos 40 s), más las pruebas con `-Simular`.
- Al cerrar cada parte, todos: `.venv\Scripts\python -m pytest -q --tb=line`
