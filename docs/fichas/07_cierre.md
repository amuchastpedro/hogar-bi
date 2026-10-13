# Ficha del bloque 7: cierre

Complementa [`bloques/07_cierre.md`](../../bloques/07_cierre.md) con lo de este proyecto.

## Leer (solo esto)

- `caso_hogar.md`: «Contexto» (el histórico) y «Preguntas que tiene que responder el dashboard».
- `docs/diseno.md` §15, las consultas de referencia.
- Las listas de comandos y scripts:
  - `bloques/04_carga.md`, «Comandos»;
  - `bloques/05_disparador.md`, «Scripts»;
  - `bloques/06_plan_b.md`, «Aprobación».
- De la bitácora, solo el campo «Cómo verificarlo» de cada entrada, para la revisión final: `grep -n -A6 'Cómo verificarlo' bitacora.md`.

## Archivos

- Crea `README.md` y `docs/guia_carga_historica.md`.
- La prueba de punta a punta se hace en una copia del proyecto, nunca sobre `datos/`. Cómo se hizo queda en la bitácora.

## Interfaces

- Las consultas de referencia C1–C7 están en `src/facturas/bd/consultas/`.
- Los comandos, en «Comandos de este proyecto» de `CLAUDE.md`.

## Pendientes heredados (bitácora, bloque 1)

- Numeración estable del alias por defecto (D7): la persona usuaria la dejó para el final. Preguntarle si se resuelve.
  - Con el bloque 4 es concreto: `reprocesar --todo` carga por fecha de emisión y avisa si el alias por defecto de un contrato cambió; el remedio es fijarlo con `contrato`. Solo afecta a categorías con más de un contrato (hoy, `movil`).
- (Bloque 4, parte A) Para la guía de carga histórica y el README:
  - `estado` informa los meses incompletos por categoría y desde el primer hasta el último mes con gasto: no hay fechas de alta ni de baja (se quitaron en la versión 3 del esquema);
  - los comandos se ejecutan con `PYTHONPATH=src`;
  - un PDF que se vuelve a dejar en `entrada/` va a `duplicados/` con su motivo, nunca se borra;
  - cargar los PDFs históricos en cualquier orden es seguro: el lote se ordena por fecha de emisión y los solapes se reintentan al final;
  - la suite de tests tarda unos 40 s.
- En la guía de carga histórica: revisar el riesgo de Digi (una línea nueva dentro de PRODUCTOS con un período entre paréntesis se traduciría como cuota), si el bloque 3 no lo cerró.
- (Bloque 3) Verificado con los ejemplos reales: la convención del período de Digi y que el IVA por servicio sume el impreso (H12). Siguen sin verificar:
  - que ningún texto real coincida con dos alias;
  - un abono total y una rectificativa de la luz o el agua (el ajuste parcial del gas ya se lee).
- (Ampliación del bloque 3) En la guía de carga histórica, decir que Digi emite el NIF vigente aunque la factura de 2025 imprima el anterior (un solo proveedor; confirmado).
- (Bloque 4, parte B) El README tiene que documentar la copia de seguridad y la restauración (R43: «documentada y probada»):
  - `datos/config.toml` con `carpeta_respaldo = 'ruta'` (la carpeta tiene que existir; las copias contienen datos personales, así que no se comparte); `cargar` respalda solo;
  - qué hay en la carpeta (`instantaneas/facturas_<marca>.db`, `instantaneas/ajustes_<marca>.json`, `procesadas/`) y que se conservan las últimas 30 instantáneas;
  - cómo restaurar: `restaurar <marca>`; en un equipo nuevo, copiar el proyecto, crear `datos/config.toml` y restaurar (crea la base, los ajustes y los PDFs); `reprocesar --todo` reconstruye lo mismo desde los PDFs;
  - una instantánea de otra versión del esquema no se restaura: se copian a mano los PDFs y los ajustes de la copia y se ejecuta `reprocesar --todo`;
  - `contrato <alias> --alias <nuevo>` es lo único que cambia el comando (ya no hay `--alta` ni `--baja`).
- (Bloque 3) El README tiene que decir que los parsers dependen de pypdf (versión fijada) y de la sangría del texto de diseño en el agua.

- (Bloque 5) Para el README: instalar con `scripts\instalar_disparador.ps1`, ver con `estado_disparador.ps1`, quitar con `desinstalar_disparador.ps1`; log en `datos/logs/disparador.log`. Las tareas son del usuario y se inician al iniciar sesión; si se mueve la carpeta del proyecto, hay que desinstalar y reinstalar (las tareas guardan la ruta). Con otra copia del proyecto, las tareas llevan otro hash y no chocan. Sin `config.toml` la carga avisa y sigue; con la carpeta de respaldo inaccesible, el disparador notifica el error y no reintenta.

- (Bloque 6, parte A) Para el README:
  - el plan B necesita Claude Code instalado y con la sesión de la suscripción (`claude auth login`). Si no la tiene, o se alcanzó el límite de uso, avisa y el PDF queda pendiente;
  - un intento a pedido: `scripts\plan_b.ps1 <archivo>`;
  - los worktrees de las propuestas van en `..\<proyecto>-propuestas\`;
  - los intentos quedan en `datos/plan_b_intentos.tsv` y el log en `datos/logs/plan_b.log`;
  - `-Simular` solo en una copia del proyecto.

- (Carga del histórico, 2026-10-06) Para la guía de carga histórica:
  - las facturas de 2024 de Naturgy las emitía Naturgy Iberia, con otro formato y otro proveedor: son contratos aparte de los de Naturgy Clientes (2025 en adelante);
  - el contrato de luz y de gas se identifica por los 20 caracteres del CUPS, sin el punto frontera;
  - el teléfono fijo de Digi de 2025 cuenta como fibra.

- (Planificación del dashboard, 2026-10-06) Para el README:
  - cómo se lanza el dashboard (`scripts\dashboard.ps1`, lo crea la etapa 2 de `task_dashboard.md`) y qué responde cada página;
  - la etapa 4 ya se hizo: `estado` informa los meses incompletos por categoría, y ya no hay fechas de alta ni de baja.

## Tests

- Todos: `.venv\Scripts\python -m pytest -q --tb=line` (unos 2 min). Este bloque no agrega tests propios; su prueba es la de punta a punta.
