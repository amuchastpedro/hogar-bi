# Bloque 6: Plan B con agente

## Objetivo

Cuando un PDF termina en `datos/pendientes/`, Claude Code (en modo no interactivo) investiga la causa y propone una corrección en una rama de git. La persona usuaria revisa la propuesta y la aprueba o la rechaza. Nada se integra sin aprobación.

## Antes de empezar

Leer `docs/estado.md` y la ficha del bloque (`docs/fichas/06_plan_b.md`), que dice qué secciones hacen falta; `CLAUDE.md` y `tarea.md` se leen siempre. Si la ficha no existe, leer las secciones «Comandos» y «Requisitos de la ejecución» del bloque 4 y, de `docs/diseno.md`, los tipos de fallo de la carga y el formato de las semillas.

El bloque se ejecuta en dos sesiones, cada una con su punto de control:

- **parte A:** lanzamiento, costo cero, aislamiento y permisos, instrucciones para el agente y el modo de simulación;
- **parte B:** aprobación, las pruebas de aprobación y rechazo con simulación, y la ejecución real.

## Lanzamiento

- `scripts/al_haber_pendientes.ps1`, al que llama el disparador del bloque 5, lanza el plan B para cada PDF pendiente que todavía no tuvo un intento automático. Va de uno en uno: si ya hay uno en curso, el resto espera al siguiente disparo.
- Hay un solo intento automático por PDF, registrado por hash. Los siguientes intentos son a pedido: `scripts/plan_b.ps1 <archivo>`.
- Cada intento tiene una duración máxima.

## Costo cero

- Antes de invocar `claude`, quitar del entorno del proceso hijo toda variable que haga que Claude Code facture por API en lugar de usar la suscripción. Como mínimo `ANTHROPIC_API_KEY`; revisar la documentación actual de Claude Code por si hay otras. Un test verifica que el proceso hijo no las recibe.
- Si `claude` no está instalado, no hay una sesión iniciada o se alcanzó el límite de uso del plan: el PDF queda pendiente, llega una notificación con el motivo y no se reintenta en bucle.

## Aislamiento y permisos

- El agente trabaja en un `git worktree` aparte, en una rama nueva `propuesta/<formato>-<AAAAMMDD-HHMM>`. Nunca toca la rama principal, ni la copia de trabajo principal, ni `datos/` (donde está la base de datos).
- Recibe la ruta del PDF pendiente y su motivo, y tiene acceso de lectura a `ejemplos/` para las pruebas de regresión.
- Las herramientas permitidas se restringen con las opciones del CLI. Consultar `claude --help`, porque las opciones cambian entre versiones. Lo permitido:
  - leer y editar archivos dentro del worktree;
  - ejecutar los tests y git dentro del worktree.

  Sin acceso a internet.

## Instrucciones para el agente

Van versionadas en `scripts/plan_b/instrucciones.md` e indican lo siguiente.

**Contexto:** `CLAUDE.md` se carga solo. Leer `docs/estado.md` y, según el fallo, solo las secciones necesarias: del archivo de caso, las del formato afectado; de `docs/diseno.md`, el contrato «factura extraída», el diccionario y la organización de `src/`; de `requisitos.md`, los requisitos que se citen. No leer archivos enteros.

**Ciclo de trabajo** (el ciclo OODA de `tarea.md`, explícito):

1. **Observar:** leer el motivo del rechazo, el PDF pendiente y, para comparar, el ejemplo del mismo formato si existe.
2. **Orientarse:** clasificar el fallo (cambio de formato, proveedor o formato nuevo, concepto nuevo, error de un parser u otra causa) y anotar esa clasificación en el informe.
3. **Decidir:** elegir una de las correcciones permitidas, o abstenerse si ninguna es segura.
4. **Actuar:** aplicar la corrección y ejecutar todos los tests.
5. Si los tests fallan, volver al paso 2 con lo aprendido. Como máximo tres vueltas: si no lo resuelve, se abstiene.

**Correcciones permitidas:**
- ajustar un parser existente (cambio de formato);
- crear un parser nuevo (proveedor o formato nuevo);
- agregar alias o conceptos a las semillas del diccionario (texto nuevo).

Si hace falta clasificar un concepto nuevo (tipo de cargo, imputación), el agente lo propone y lo marca explícitamente como decisión pendiente de la persona usuaria.

**Correcciones prohibidas:**
- cambiar el esquema;
- cambiar las tolerancias de los invariantes;
- cambiar la clasificación de conceptos existentes;
- modificar tests existentes para que pasen.

**Obligatorio:**
- agregar o ajustar tests para el caso nuevo;
- ejecutar todos los tests (los ejemplos anteriores tienen que seguir pasando);
- incrementar la versión del parser;
- hacer commit en la rama.

**Informe:** escribir `docs/propuestas/<rama>.md` con qué falló, la causa, qué cambió, el resultado de los tests, los riesgos y las decisiones pendientes. Si no encuentra una corrección segura, escribe igual el informe con el diagnóstico y no cambia código.

## Aprobación

Al terminar una propuesta llega una notificación: "Propuesta lista para <archivo>. Revisar con `scripts/revisar_propuesta.ps1 <rama>`".

Scripts en `scripts/`:

- `listar_propuestas.ps1`: las ramas `propuesta/*`, con el resumen de su informe.
- `revisar_propuesta.ps1 <rama>`: muestra el informe y el diff contra la rama principal.
- `aprobar_propuesta.ps1 <rama>`: integra la rama en la principal (merge con commit) y ejecuta todos los tests.
  - Si pasan, ejecuta `reprocesar --pendientes` y limpia la rama y el worktree.
  - Si fallan, deshace la integración y no cambia nada.
- `rechazar_propuesta.ps1 <rama>`: borra la rama y el worktree. El PDF queda pendiente y no se reintenta automáticamente.

## Criterios de aceptación

- Un modo de simulación (`-Simular`) hace todo menos invocar a `claude`: crea el worktree, la rama y un informe de prueba. Con él se prueban de punta a punta la aprobación y el rechazo.
- Una ejecución real, **solo después de pedir permiso a la persona usuaria en ese momento**, porque consume parte del cupo de la suscripción:
  1. En una copia de prueba del proyecto, quitar un alias de las semillas para que un ejemplo se rechace por texto desconocido.
  2. Lanzar el plan B.
  3. Verificar que la propuesta agrega el alias, que se puede aprobar y que el PDF se carga.
- El proceso hijo no recibe variables de facturación por API.
- La rama principal no cambia hasta la aprobación.

## Fuera de este bloque

Cualquier cambio en cómo se carga una factura válida.
