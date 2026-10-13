# De facturas en PDF a una base de datos para BI

Especificación de un proceso para convertir facturas en PDF en una base de datos analítica que alimente un dashboard de business intelligence.

El proceso es genérico. Todo lo específico de un caso concreto (categorías de gasto, proveedores, clasificación de cargos, facturas de ejemplo) está en el **archivo de caso**. Este proyecto usa [`caso_hogar.md`](caso_hogar.md): los gastos de servicios de una vivienda.

## Cómo se usa

- El trabajo está dividido en 7 bloques, en la carpeta [`bloques/`](bloques/). Se ejecutan de a uno y en orden. Cada uno termina en un **punto de control** donde la persona usuaria valida el resultado antes de seguir.
- Para ejecutar un bloque: abrir Claude Code en esta carpeta y pedir *"Ejecutá el bloque N de tarea.md"*. Cada bloque se ejecuta en una sesión nueva; los bloques 4 y 6, en dos (parte A y parte B).
- Antes y durante la sesión, la persona usuaria:
  - elige con `/model` y `/effort` el modelo sugerido en la tabla de bloques, y no lo cambia a mitad del bloque, porque cambiarlo invalida la caché. Si el agente falla dos veces en lo mismo o hay un error que no logra diagnosticar, sube de modelo;
  - evita las pausas largas en medio de un bloque (la caché caduca a los pocos minutos) e itera dentro de la misma sesión;
  - después del commit del bloque, ejecuta `/clear` o abre otra sesión. Si una sesión se alarga, usa `/compact`;
  - antes del bloque 3, revisa con `/context` que no haya servidores MCP o conectores que el proyecto no usa, y los desactiva con `/mcp`.
- Al empezar un bloque, el agente lee: [`CLAUDE.md`](CLAUDE.md) (se carga solo), [`docs/estado.md`](docs/estado.md) (la nota de traspaso), este archivo, el archivo del bloque y su ficha en [`docs/fichas/`](docs/fichas/), que indica qué secciones del caso, del diseño y de [`requisitos.md`](requisitos.md) hacen falta. Esos archivos y [`bitacora.md`](bitacora.md) (el registro histórico) no se leen enteros: se consultan por secciones.
- Para replicar el proceso con otros datos (por ejemplo, las facturas de proveedores de una pequeña empresa):
  1. Copiar `tarea.md`, `requisitos.md`, `CLAUDE.md` (vaciando su sección «Comandos de este proyecto»), `bloques/` y una `bitacora.md` con solo su encabezado a una carpeta nueva.
  2. Escribir un archivo de caso con la misma estructura que `caso_hogar.md`.
  3. Poner los PDFs de ejemplo en `ejemplos/`.
  4. Ejecutar los bloques desde el 1. `docs/estado.md` y las fichas los crean los propios bloques, en su punto de control.

## Objetivo

Construir:

1. Una **base de datos SQLite** que sea la fuente única de verdad de los gastos documentados en las facturas, diseñada para alimentar un dashboard.
2. Un **proceso de carga automático**: los PDFs que se dejan en una carpeta se procesan solos, se validan y se cargan en la base.
3. Un **mecanismo de recuperación**: cuando una factura no se puede cargar (formato nuevo, proveedor nuevo, concepto desconocido), un agente propone la corrección y la persona usuaria la aprueba o la rechaza.

**Fuera de alcance:** el dashboard en sí. Se construirá después, leyendo esta base, con la herramienta que indique el caso. Las preguntas que tendrá que responder están en el archivo de caso y guían el diseño.

## Arquitectura

```
datos/entrada/*.pdf
   │   disparador de Windows (bloque 5)
   ▼
carga (bloque 4)
   ├─► parser del formato (bloque 3) ──► "factura extraída" (estructura común)
   ├─► traduce textos a conceptos con el diccionario de la base
   ├─► valida
   ├─► inserta en una transacción ──► base SQLite (bloque 2) ──► vistas ──► dashboard (fuera de alcance)
   ├─► si todo va bien: mueve el PDF a datos/procesadas/
   └─► si algo falla:   mueve el PDF a datos/pendientes/
                           └─► plan B (bloque 6): un agente propone un cambio en una rama de git
                                                  y la persona usuaria lo aprueba o lo rechaza
```

Los componentes se comunican por contratos explícitos, para poder cambiar uno sin tocar los demás:

- Los **parsers** solo conocen PDFs. Devuelven una "factura extraída" con los textos tal como aparecen en el documento. No saben nada de la base ni del diccionario.
- La **carga** solo conoce la factura extraída y la base. No sabe nada de PDFs.
- El **dashboard** solo conoce las vistas.

## Calidad

La base de datos tiene que estar al nivel de una diseñada por un ingeniero de datos con experiencia. El estándar, sus fuentes, los requisitos R1–R43 y la revisión técnica independiente de los bloques 1 y 2 están en [`requisitos.md`](requisitos.md).

## Restricciones

- **Costo cero.** No se usa ninguna API ni servicio de pago, ni de Anthropic ni de terceros. Todo el software es gratuito. El plan B usa Claude Code con la suscripción de la persona usuaria y se asegura de que Claude Code no facture por API (ver bloque 6).
- **Entorno.** Windows 11, Python, SQLite (≥ 3.37 por las tablas `STRICT`; ≥ 3.35 por `RETURNING`), PowerShell y git.
- **Datos personales.**
  - Ningún archivo versionado contiene datos personales: nombres, documentos de identidad, direcciones, teléfonos, emails ni datos bancarios, como tampoco identificadores de contratos, clientes o facturas. El caso detalla qué patrones hay que buscar. Los identificadores fiscales de las empresas sí pueden versionarse.
  - Los PDFs, la base y los logs quedan fuera de git.
  - Un test que necesite un identificador valida su formato o lee el valor esperado de un archivo local ignorado por git.
- **Sin extracción con LLM.** Los datos se extraen con parsers deterministas, uno por formato. El agente interviene solo en el plan B, para proponer cambios de código.
- **Copias de seguridad.** Van a la carpeta que define el caso (R43). Contienen datos personales, así que esa carpeta tiene que ser privada.

## Bloques

| # | Bloque | Entregable principal | Depende de | Modelo sugerido |
|---|---|---|---|---|
| 1 | [Diseño de la base de datos](bloques/01_diseno_bd.md) | `docs/diseno.md`, revisión técnica y proyecto inicializado | — | Opus, esfuerzo alto |
| 2 | [Implementación de la base](bloques/02_implementacion_bd.md) | Esquema, vistas, semillas, invariantes, diccionario generado y revisión técnica | 1 | Sonnet, esfuerzo alto |
| 3 | [Parsers](bloques/03_parsers.md) | Un parser por formato, con tests sobre los ejemplos | 1 | Sonnet, esfuerzo medio |
| 4 | [Carga](bloques/04_carga.md) (partes A y B) | Comandos para cargar, reprocesar, consultar el estado, editar datos manuales y respaldar | 2, 3 | Sonnet, esfuerzo alto |
| 5 | [Disparador de Windows](bloques/05_disparador.md) | Carga automática al aparecer PDFs en `datos/entrada/` | 4 | Sonnet, esfuerzo medio |
| 6 | [Plan B](bloques/06_plan_b.md) (partes A y B) | Propuestas de corrección con agente y aprobación con git | 4, 5 | Opus, esfuerzo medio |
| 7 | [Cierre](bloques/07_cierre.md) | README, guía de carga histórica, revisión final y prueba de punta a punta | 1–6 | Sonnet, esfuerzo medio |

## Forma de trabajo

Cada bloque sigue, de forma liviana, el ciclo OODA: observar, orientarse, decidir y actuar.

1. **Observar.** Leer lo que indica «Cómo se usa» (el estado, este archivo, el bloque, su ficha y las secciones que cita) y mirar la realidad: los archivos que ya existen, las herramientas instaladas, los PDFs de ejemplo.
2. **Orientarse.** Antes de cambiar nada, escribir en pocas líneas, en la conversación (no en un archivo):
   - qué entendió que hay que hacer;
   - las discrepancias entre la especificación y la realidad;
   - el plan, en pasos;
   - cómo va a saber que terminó, es decir, la definición de terminado aplicada a este bloque.

   Si hay discrepancias que afectan el diseño, se detiene y pregunta; si no, sigue. En el bloque 1, la orientación siempre espera el OK de la persona usuaria.
3. **Decidir y actuar en incrementos chicos.** Cada paso del plan se verifica, con un test o un comando, antes de pasar al siguiente. No se construye todo para probarlo al final.
4. **Reorientarse.** Si lo que observa contradice el plan (un dato no está donde la especificación dice, o un enfoque no funciona), se detiene y replantea en lugar de forzar la solución. Si el cambio de plan afecta el diseño, pregunta.

El plan B (bloque 6) aplica el mismo ciclo de forma explícita, porque es el único lugar donde el agente trabaja sin supervisión.

La estructura de carpetas está en `CLAUDE.md`; la organización interna de `src/` la decide el bloque 1. Cualquier cambio a esa estructura se anota en la bitácora.

Si durante un bloque el agente encuentra un error o una omisión en la especificación, no la edita: lo plantea en el punto de control.

## Definición de terminado

Un bloque está terminado, y el agente puede presentarlo en el punto de control, cuando se cumple todo esto:

1. **Criterios de aceptación con evidencia.** Cada criterio del bloque está cumplido y acompañado de su evidencia: el test que lo cubre o la salida de un comando. Lo que no se pudo verificar se informa como no verificado; nunca se da por bueno.
2. **Tests.** Pasan todos los tests del proyecto, no solo los del bloque. Ninguno se saltó ni se desactivó para que pase, salvo los casos que prevé la especificación.
3. **Especificación intacta.** No se modificó la especificación ni se debilitaron tests de bloques anteriores.
4. **Simplicidad.** Es la solución más simple que cumple los requisitos: cada tabla, módulo, capa u opción de configuración existe porque un requisito la pide. Lo que sobra se quita.
5. **Nada escondido.** No quedan `TODO`, stubs ni partes a medias sin registrar: todo lo pendiente figura en la bitácora y en la ficha del bloque que lo tiene que resolver.
6. **Límites respetados.** No hay datos personales en lo versionado, y lo específico del caso vive solo en el archivo de caso, las semillas y los parsers.
7. **Documentación al día.** `docs/`, la bitácora y `docs/estado.md` reflejan lo que se construyó, incluidas las decisiones y los desvíos.

**Qué cuenta como prueba de que algo es correcto.** Un test que pasa demuestra poco si lo escribió el mismo agente para que pase. La corrección se mide contra referencias independientes del trabajo del agente:

- los valores esperados y los controles del archivo de caso, que salen de facturas reales;
- las consultas de referencia, que tienen que responder las preguntas del dashboard;
- la revisión técnica independiente;
- la validación de la persona usuaria.

**Quién decide.** La definición de terminado es la condición mínima para presentar un bloque; no reemplaza la aprobación. El agente propone y la persona usuaria decide.

**Proyecto resuelto.** El proyecto completo está resuelto cuando pasa la prueba de punta a punta del bloque 7.

## Punto de control

Al terminar cada bloque (o cada parte, en los bloques 4 y 6), el agente:

1. Verifica la definición de terminado: ejecuta todos los tests del proyecto y reúne la evidencia de cada criterio de aceptación.
2. En los bloques 1 y 2, completa la revisión técnica independiente (ver [`requisitos.md`](requisitos.md)).
3. Agrega una entrada en `bitacora.md`, con el formato indicado ahí.
4. Reescribe `docs/estado.md` en menos de 15 líneas: qué está hecho, cuál es el bloque siguiente y su modelo sugerido, las decisiones vigentes que se apartan de la especificación, el resultado de los tests y las preguntas abiertas.
5. Agrega cada pendiente a la ficha del bloque que lo tiene que resolver y completa la ficha del bloque siguiente, creándolas si no existen (`docs/fichas/NN_<nombre>.md`). Una ficha dice qué leer (secciones, no archivos enteros), qué archivos crear o modificar, qué interfaces usa y dónde están, los pendientes heredados, los tests y el comando que ejecuta solo esos.
6. Presenta a la persona usuaria:
   - qué se hizo;
   - cada criterio de aceptación con su evidencia, y cómo verificarlo con comandos concretos;
   - en los bloques 1 y 2, el veredicto de la revisión técnica y qué se hizo con cada hallazgo;
   - las decisiones que no estaban en la especificación;
   - los desvíos respecto de la especificación;
   - las preguntas abiertas;
   - el bloque siguiente, con su modelo sugerido y el recordatorio de ejecutar `/clear` después del commit.
7. Se detiene. No empieza el bloque siguiente.
8. Con la aprobación, hace un commit: `bloque N: <resumen>` (en los bloques partidos, `bloque Na:` y `bloque Nb:`). Si la persona usuaria pide cambios, los aplica y vuelve al paso 1.

Durante el bloque, si aparece una decisión que la especificación no cubre y que cambia el diseño, el agente pregunta antes de seguir. Si es una decisión menor, elige la opción más simple y la anota en la bitácora.
