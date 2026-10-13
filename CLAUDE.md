# facturas-bi

Facturas en PDF → base SQLite para BI. El proceso genérico está en `tarea.md`, y lo específico del caso, en el archivo de caso (`caso_hogar.md`). El dashboard (Streamlit) se construye con `task_dashboard.md`, por etapas.

## Al empezar

- Leé primero `docs/estado.md`: la nota de traspaso, de menos de 15 líneas.
- Si vas a ejecutar un bloque, leé `tarea.md`, `bloques/NN_*.md` y su ficha `docs/fichas/NN_*.md`. La ficha dice qué secciones de otros archivos hacen falta: no leas más.
- Si vas a ejecutar una etapa del dashboard, leé su ficha `docs/fichas/dN_*.md`: dice qué secciones de `task_dashboard.md` y de `tarea.md` hacen falta (ninguno de los dos se lee entero).
- `docs/diseno.md`, el archivo de caso, `requisitos.md` y `bitacora.md` no se leen enteros. Primero el índice (`grep -n '^#' <archivo>`) y después solo la sección, con Bash:
  - `awk '/^## 11\./{p=1;print;next} p&&/^## /{exit} p' docs/diseno.md` (una sección);
  - `awk '/^### 16\.1/{p=1;print;next} p&&/^##/{exit} p' docs/diseno.md` (una subsección);
  - `awk '/^## Copias/{p=1;print;next} p&&/^## /{exit} p' caso_hogar.md` (por título).
- Sin subagentes, salvo la revisión técnica independiente que pide la especificación.
- Si te lanza el plan B, seguí `scripts/plan_b/instrucciones.md`, no los bloques.

## Estructura

```
<raíz del proyecto>/
├── CLAUDE.md                       este archivo
├── tarea.md, requisitos.md,        especificación genérica (no se modifica durante la ejecución)
│   bloques/
├── caso_*.md                       archivo de caso: lo específico (no se modifica durante la ejecución)
├── task_dashboard.md               especificación del dashboard, por etapas (no se modifica durante la ejecución)
├── bitacora.md                     registro histórico de los bloques (lo mantiene el agente)
├── README.md                       guía para personas (bloque 7)
├── docs/
│   ├── estado.md                   nota de traspaso entre sesiones
│   ├── fichas/                     qué necesita cada bloque (NN_*) o etapa del dashboard (dN_*) en este proyecto
│   └── …                           diseño, revisiones técnicas, diccionario generado,
│                                   propuestas del plan B, guías
├── src/                            código Python; su organización, en docs/diseno.md, «Organización de src/»
├── tests/
├── scripts/                        PowerShell: disparador, plan B, aprobación
├── ejemplos/                       PDFs de ejemplo (fuera de git)
└── datos/                          fuera de git
    ├── entrada/                    acá se dejan los PDFs nuevos
    ├── procesadas/                 PDFs cargados
    ├── pendientes/                 PDFs rechazados, cada uno con su motivo
    ├── duplicados/                 PDFs que ya estaban cargados
    ├── facturas.db
    ├── ajustes_manuales.json       datos cargados a mano (R41)
    ├── config.toml                 configuración local, como la carpeta de respaldo
    └── logs/
```

## Convenciones

- Nombres de tablas, columnas, funciones y archivos en español, en `snake_case`, sin tildes ni ñ.
- Documentación, mensajes y logs en español.
- Entorno virtual en `.venv/` y dependencias fijadas en un archivo de requisitos.
- Tests con `pytest`: se ejecutan todos con un solo comando y tardan segundos.
- Rutas siempre relativas a la raíz del proyecto, para que la carpeta se pueda mover o copiar.

## Comandos (PowerShell, desde la raíz)

- Mientras trabajás, solo los tests del bloque (la ficha dice cuáles): `.venv\Scripts\python -m pytest -q --tb=short tests\test_<x>.py`
- Al cerrar el bloque, todos: `.venv\Scripts\python -m pytest -q --tb=line`
- Salidas acotadas: `-x` si fallan muchos; de un log, las últimas líneas (`Get-Content <log> -Tail 30`); nunca un JSON o una tabla entera.

### Comandos de este proyecto

Los agrega cada bloque que crea un comando que usan los siguientes. Al replicar, esta sección se vacía.

- Medir tiempos (no es un test): `.venv\Scripts\python tests\rendimiento.py`
- Regenerar el diccionario: `$env:PYTHONPATH = "src"; .venv\Scripts\python -m facturas.bd.diccionario`. Después, `git diff docs/diccionario.md` no tiene que mostrar cambios.
- Carga (desde la raíz; `PYTHONPATH` apunta a `src`). Códigos de salida: 0 todo bien o nada que hacer, 1 hay PDFs nuevos en `datos/pendientes/`, 2 error del sistema:
  - `$env:PYTHONPATH = "src"; .venv\Scripts\python -m facturas cargar`: procesa `datos/entrada/`;
  - `… -m facturas reprocesar --pendientes`: reintenta `datos/pendientes/` (reconstruye antes si cambiaron las semillas);
  - `… -m facturas reprocesar --todo`: reconstruye la base desde `datos/procesadas/`;
  - `… -m facturas estado`: resumen, cobertura, pendientes y comprobación de I1 (código 2 si falla);
  - `… -m facturas diccionario`: regenera `docs/diccionario.md`;
  - `… -m facturas contratos`: lista los contratos con su alias, categoría y proveedor;
  - `… -m facturas contrato <alias> --alias <nuevo>`: cambia el alias en la base y en `datos/ajustes_manuales.json`;
  - `… -m facturas respaldar`: copia de seguridad en la carpeta de `datos/config.toml` (`carpeta_respaldo = 'ruta'`). `cargar` y `reprocesar --pendientes` la hacen solos si cargaron algo;
  - `… -m facturas restaurar <ruta de facturas_<marca>.db | marca>`: restaura la base, los datos manuales y los PDFs desde una instantánea.
- Disparador (PowerShell, desde la raíz; tareas del usuario, sin administrador): `scripts\instalar_disparador.ps1` (idempotente), `scripts\estado_disparador.ps1`, `scripts\desinstalar_disparador.ps1`. El vigilante lanza la carga 20 s después del último PDF nuevo en `datos/entrada/`; un barrido horario recoge lo que se le escape. Log: `datos/logs/disparador.log`.
- Dashboard (Streamlit): `scripts\dashboard.ps1` lanza `streamlit run` desde la raíz con `PYTHONPATH=src` (acepta las opciones de `streamlit run`, como `--server.port`). Lee `datos/facturas.db` en solo lectura. Páginas: Overview y Analysis (una pestaña por servicio: Water, Electricity, Gas y DIGI).
- Plan B, **en pausa** (la persona usuaria no quiere un agente automático; `al_haber_pendientes.ps1` no está en `scripts/`, así que el disparador no lo lanza). PowerShell, desde la raíz: `scripts\plan_b.ps1 <archivo de datos\pendientes> [-Simular] [-LimiteMinutos 30] [-Modelo sonnet]` (un intento a pedido). Rama `propuesta/<formato>-<AAAAMMDD-HHMM>`, worktree en `..\<proyecto>-propuestas\`, informe en `docs/propuestas/`. Intentos: `datos/plan_b_intentos.tsv`; log: `datos/logs/plan_b.log`. `-Simular` registra el intento: usalo en una copia del proyecto.
