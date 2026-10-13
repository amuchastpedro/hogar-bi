# Revisión técnica del bloque 1

Revisión independiente de [`docs/diseno.md`](diseno.md), incluidos sus apéndices A (esquema) y B (consultas de referencia), contra [`tarea.md`](../tarea.md), [`caso_hogar.md`](../caso_hogar.md) y [`bloques/01_diseno_bd.md`](../bloques/01_diseno_bd.md). El revisor no participó del diseño.

**Cómo se verificó.**
- Ejecuté el esquema del apéndice A y las consultas C1–C7 en SQLite 3.49.1 (Python 3.12), con las semillas de la sección 12 y las cuatro facturas de ejemplo armadas a partir de los valores esperados del caso.
- Reproduje los controles del caso: totales por categoría, los 12 repartos mensuales y la cobertura de mayo y junio de 2026. Coinciden al céntimo.
- Después probé escenarios de falla:
  - rectificativas y abonos en distinto orden;
  - solapes;
  - mediciones con y sin franja;
  - cargas rechazadas;
  - traducción de textos nuevos;
  - prorrateo en períodos de tres meses;
  - cobertura con alta, baja y cambio de año;
  - WAL con conexión de solo lectura, `VACUUM INTO` y restauración;
  - rendimiento con 10 años simulados.
- Contrasté el diseño con el texto de los PDFs de `ejemplos/`.

Los scripts quedaron fuera del proyecto, en `%TEMP%\claude\revision_b1\`.

---

## 1. Veredicto

**Apto con cambios.**

El modelo es sólido. Reproduce todos los controles del caso, las reglas centrales funcionan como se describen y el rendimiento es el declarado. Las reglas probadas son R9 con claves foráneas compuestas, `STRICT`, los `CHECK`, la inmutabilidad, el prorrateo exacto y la cobertura.

Antes del bloque 2 hay que resolver dos hallazgos de severidad alta:
- **H1.** La convención de período del agua no está verificada, y lo que imprime el PDF indica que dos facturas consecutivas comparten un día. Si se confirma, el control de solapes rechazaría alrededor de la mitad de las facturas de agua.
- **H2.** La restauración por copia de archivo, con un lector abierto, deja la base sin restaurar y pasa `integrity_check`.

Ninguno obliga a rediseñar el modelo. Los hallazgos medios (H3–H7) también hay que corregirlos antes de implementar.

---

## 2. Cumplimiento

| R | Estado | Evidencia |
|---|---|---|
| R1 | parcial | `factura` (una fila por factura) y `linea` (una por línea). Gasto, consumo y cobertura salen de vistas `v_hecho_*`. **Desvío aprobado D2:** el canon se guarda como su subtotal en una línea, no como las dos líneas impresas. D3, presentado sin desvío, hace lo mismo con la tasa de alcantarillado: guarda el subtotal en lugar de sus líneas de tramo, así que con más consumo varias líneas del documento quedan en una. |
| R2 | parcial | **Desvío aprobado D1.** `linea` guarda contrato, concepto, importe, imputación y período, con la categoría en la línea y no en la cabecera (`linea.categoria_id`, FK compuestas). No guarda cantidad, unidad ni precio unitario. |
| R3 | parcial | **Desvío aprobado D5.** `medicion` guarda `franja_id` y `tipo_lectura`, pero solo de la lectura de cierre. La lectura anterior y su tipo no se guardan. Ver además H5. |
| R4 | no cumple | **Desvío aprobado D1.** No se guardan ni base imponible ni tipo. |
| R5 | cumple | `linea.es_derivada`. El total repartido queda en `carga.extraccion_json` e I8 se valida sobre la extracción (11.3, 11.6, sección 10). Ver H12. |
| R6 | parcial | Reglas declaradas en el esquema: `STRICT`, `CHECK`, FK compuestas, `tg_linea_bi_solape` y los triggers de inmutabilidad. Probado que la base rechaza un concepto de otra categoría, un período invertido, una fecha inválida y un `UPDATE` sobre `linea`. Quedan reglas documentadas que la base no hace cumplir: mezclar mediciones con y sin franja (H5), una factura cuya carga está rechazada (H10), y la equivalencia entre etapa de rechazo y nulos de `carga` (3.3). |
| R7 | cumple | Todas las tablas son `STRICT`, con `NOT NULL` en claves y obligatorios. `CHECK` `col = date(col)` e inicio ≤ fin en `factura`, `linea`, `contrato` y `medicion`. `ON DELETE CASCADE` de `factura` a `linea`, `medicion` y `valor_atributo`. |
| R8 | cumple | `conectar(modo)` ejecuta `PRAGMA foreign_keys = ON` en los dos modos (14.1). El test lo escribe el bloque 2. |
| R9 | cumple | `fk_linea_contrato` y `fk_linea_concepto` comparten `linea.categoria_id`. Probado: se rechaza una línea de agua con un concepto de gas, y también cambiar la categoría de un contrato que ya tiene líneas. |
| R10 | parcial | Cada columna nulable tiene su significado documentado (3.2–3.3), y un campo obligatorio ausente hace fallar la extracción (11.6). Pero los campos opcionales que dependen del formato aceptan nulo también cuando el dato existía y no se encontró (H14). |
| R11 | parcial | **Desvío aprobado D1.** Importes en `*_centimos INTEGER`, cantidades en milésimas y factor de conversión como decimal exacto en texto (sección 4). Precios unitarios y tipos impositivos no se guardan. |
| R12 | cumple | `linea.importe_centimos` es el impreso y nada lo recalcula. La validación cantidad × precio desaparece con D1 (ver R33). |
| R13 | cumple | `magnitud_categoria.unidad_canonica_id` y `unidad_contador_id`. `medicion.cantidad_milesimas` está en la unidad canónica; `cantidad_contador_milesimas` y `factor_conversion` son atributos. La unidad no se repite por fila. |
| R14 | cumple | `carga` guarda `sha256` (único, con `CHECK` de formato), `nombre_archivo`, `formato`, `version_parser`, `fecha_hora`, `estado`, `etapa_rechazo`, `motivo_rechazo` y `extraccion_json` (`json_valid`). |
| R15 | cumple | `factura.carga_id` es `NOT NULL` y único. Ver H10: una factura puede quedar apuntando a una carga rechazada. |
| R16 | cumple | `uq_factura_proveedor_numero`. Las líneas usan `uq_linea_factura_posicion`, sin importes. |
| R17 | cumple | Hash único: un PDF ya cargado va a `duplicados/`. Ids con `RETURNING`, sin `INSERT OR REPLACE`, con triggers de inmutabilidad. El reemplazo de una factura cargada solo existe a través de `reprocesar --todo`; el paso 6.2 del flujo no tiene un camino que llegue a él (H10). |
| R18 | cumple | `BEGIN IMMEDIATE` … `COMMIT` con cabecera, contratos, líneas, mediciones y atributos (13.2, paso 6). Probado que un rechazo no deja nada parcial. |
| R19 | parcial | **Desvío aprobado D7:** el alias por defecto no se persiste. Mecanismo en 13.4. Además, la reconstrucción puede abortar por el orden de una rectificativa y su original (H3) o por una colisión de alias (H9). |
| R20 | cumple | `proveedor.identificador_fiscal` es único, con `CHECK` `[A-Z0-9]`. La normalización la hace el parser. |
| R21 | cumple | Los contratos se registran en la transacción de carga (13.2, paso 6.3) con el identificador y la categoría del parser. `v_dim_contrato` no expone el identificador. Numeración: D7 y H9. |
| R22 | cumple | `atributo_contrato` y `valor_atributo` por factura; `v_dim_contrato_atributo` arma los tramos de vigencia. Probado: P1 y P2 = 4400, del 2026-05-27 al 2026-06-28. |
| R23 | parcial | La convención por formato vive en el parser (11.1) y la línea hereda el período (`linea.fecha_inicio`, `fecha_fin`). Pero la convención inclusiva del agua no está verificada y el PDF indica lo contrario (H1). |
| R24 | cumple | `calendario` de 2000 a 2099, con `CHECK` de coherencia de las columnas derivadas. |
| R25 | cumple | Prorrateo jerárquico en `v_hecho_gasto_diario` y `v_hecho_consumo_diario`. Probado: suma exacta por línea y por medición, y los 12 controles del caso. Las líneas `puntual` van a la fecha de emisión. Límite ya documentado en 8.1: una línea de 1 céntimo en un período de tres meses puede recibir −1 céntimo en el mes del medio. |
| R26 | cumple | `v_hecho_cobertura_contrato_mensual` y `v_hecho_cobertura_categoria_mensual`. Probado con mayo y junio del caso, con alta y baja, y con un período que cruza el año. Ver H11. |
| R27 | parcial | `factura.tipo`, `numero_factura_corregida` y `v_factura_vigente`. Probado que una sustitución saca de las vistas a la sustituida. Pero la original no se puede cargar después de su sustitución (H3), un abono seguido de refacturación no se puede representar (H4) y dos sustituciones de una misma factura se suman (H8). |
| R28 | parcial | `tg_linea_bi_solape` e I6. Probado que rechaza los solapes entre ordinarias y acepta los huecos. Pero rechaza casos legítimos (H1, H4) y no controla las rectificativas (H8). |
| R29 | parcial | Semillas CSV (12.5) que se cargan en `concepto` y `alias_concepto`, con FK compuesta, y diccionario generado desde la base. Contenido: **desvío aprobado D2** (el canon es un solo concepto). Falta el mecanismo que lleva un cambio de semillas a la base en uso (H7). |
| R30 | parcial | Normalización NFKD y `GLOB`; un texto sin alias o ambiguo se rechaza (12.3). Probado: "Llamadas" se rechaza. Pero `* (* - *)` funciona como concepto genérico (H6). |
| R31 | cumple | Comodines en `alias_concepto.patron` para umbrales, tipos de IVA, nombres comerciales y períodos (12.4). Probado con textos nuevos ("Tramo de 15 a 18 m³", "Fibra 1 Gb (…)"). |
| R32 | cumple | C1–C7 leen solo vistas `v_*`. `importe_centimos` tiene la misma semántica en todas (sección 7). El dashboard usa una conexión `mode=ro`. |
| R33 | parcial | **Desvío aprobado D1:** I2 e I3 no aplican. I1 e I4–I8 tienen tolerancia 0 y revierten la carga si fallan. I4 da un falso rechazo con facturas sustituidas (H3). |
| R34 | cumple | Excepciones explícitas y un test con `ast` que verifica que no hay `assert` (sección 14). |
| R35 | cumple | Sección 5: tercera forma normal, salvo `categoria_id` repetida en `linea`, `medicion`, `valor_atributo` y `alias_concepto` (controlada por las FK compuestas) y `calendario`. Las dos excepciones están justificadas. |
| R36 | cumple | Dimensiones `v_dim_*` (fecha, categoría, tipo de cargo, concepto, contrato, proveedor, atributo) y hechos `v_hecho_*` (gasto, consumo, cobertura), cada una con su grano (7.1–7.3). |
| R37 | cumple | `INTEGER PRIMARY KEY` en todas las tablas, claves naturales con `UNIQUE` y convención documentada en la sección 2. Los índices que crean los `UNIQUE` se llaman `sqlite_autoindex_*` (H13). |
| R38 | cumple | Un índice por clave foránea (6.1), índices de consulta (6.2) y recorridos completos justificados (6.3). Verificado: C1–C7 tardan entre 0,08 y 0,73 s con 10 años simulados (360 facturas, 2.280 líneas). |
| R39 | cumple | WAL, `busy_timeout = 5000` y `mode=ro` para los lectores (14.1). Probado: un lector `mode=ro` abre la base sin `-wal` ni `-shm` y lee mientras la carga tiene una transacción abierta. |
| R40 | cumple | `PRAGMA user_version = 1` en el esquema y comparación al conectar (14.1). Solo versiona el esquema, no las semillas (H7). |
| R41 | cumple | Comando `contrato` y `ajustes_manuales.json` por (identificador fiscal, identificador externo), que se vuelven a aplicar al registrar cada contrato (14.2). Ver H9. |
| R42 | cumple | Tabla `moneda` (semilla `EUR`, `CHECK` de tres mayúsculas) y `factura.moneda_id` `NOT NULL` con FK. |
| R43 | parcial | `VACUUM INTO` después de cada carga que cambió algo, con los ajustes y los PDFs, y 30 instantáneas (14.2). Probado que `VACUUM INTO` funciona desde una conexión de solo lectura y durante una escritura. La restauración por copia de archivo es incorrecta en WAL (H2). |

---

## 3. Hallazgos

**Exceso de complejidad:** no encontré piezas sin un requisito que las pida. Los triggers de inmutabilidad, que tarea.md no exige, evitan tener que escribir triggers de `UPDATE` para R9 y R28, así que simplifican.

| Id | Severidad | Requisito | Resumen |
|---|---|---|---|
| H1 | alta | R23, R28 | Las facturas de agua consecutivas probablemente comparten el día de lectura y el trigger rechazaría la segunda. |
| H2 | alta | R43 | Restaurar copiando el archivo con un `-wal` presente reaplica el WAL viejo; `integrity_check` da `ok`. |
| H3 | media | R27, R33, R19 | I4 rechaza una original que llega después de su sustitución; la reconstrucción depende del orden. |
| H4 | media | R27, R28 | Abono más refacturación: se rechaza la refacturación y el mes queda completo con gasto 0. |
| H5 | media | R6, R3, R13 | La base acepta una medición total sin franja junto con su desglose por franja: kWh duplicados. |
| H6 | media | R30 | `* (* - *)` traduce cualquier cargo nuevo de Digi como cuota, sin rechazo. |
| H7 | media | R29, R40 | Un alias nuevo en las semillas no llega a la base en uso; `reprocesar --pendientes` vuelve a fallar. |
| H8 | baja | R27, R28 | Dos sustituciones de la misma factura quedan vigentes; las rectificativas no se controlan contra solapes. |
| H9 | baja | R19, R21, R41 | El alias por defecto puede colisionar con un ajuste manual y abortar la reconstrucción. |
| H10 | baja | R15, R17, R6 | El reemplazo de una factura cargada no tiene camino definido y su fallo deja una factura con carga rechazada. |
| H11 | baja | R26 | La cobertura usa los períodos de las líneas: una línea con período propio oculta una factura faltante. |
| H12 | baja | R5, R33 | No hay regla para un descuadre de 1 céntimo entre el IVA por servicio y el IVA impreso de Digi. |
| H13 | baja | R37 | Los errores de FK no dicen qué regla falló, y los índices `UNIQUE` no siguen la convención de nombres. |
| H14 | baja | R10 | Un nulo opcional ("el formato no lo imprime") puede guardar un dato que existía y no se extrajo. |

### H1. Las facturas de agua consecutivas probablemente comparten un día

- **Severidad:** alta.
- **Requisito:** R23 y R28, y los controles de agua del caso.
- **Qué está mal:**
  - La sección 18 (línea 1120) da R23 por cumplido aplicando a todos los formatos la convención del caso: extremos inclusivos, "verificado en los ejemplos: los días impresos coinciden con fin − inicio + 1" (`caso_hogar.md`, línea 27). Pero `agua.pdf` no imprime el número de días, así que para el agua esa verificación no existe.
  - Lo que el PDF sí imprime apunta a lo contrario. El período empieza el día de la lectura anterior y termina el día de la lectura actual: inicio = fecha de la lectura anterior = 2026-04-09, y fin = fecha de la lectura actual = 2026-06-08.
  - La lectura anterior de una factura es la lectura de cierre de la previa, que es la misma premisa de D5. Por lo tanto, dos facturas de agua consecutivas comparten la fecha de lectura.
  - En el gas no pasa: la lectura "desde" es del día anterior al inicio (2026-04-29 frente a 2026-04-30).
  - `tg_linea_bi_solape` (líneas 1466–1484) compara extremos inclusivos, sin tolerancia.
- **Escenario de falla (reproducido):**
  - La factura A va del 2026-02-08 al 2026-04-09 y la factura B, la del ejemplo, del 2026-04-09 al 2026-06-08.
  - Al cargar B: `solape: el periodo se superpone con otra factura ordinaria del mismo contrato`.
  - En la carga histórica de dos años, en orden cronológico, se rechaza aproximadamente una factura de agua de cada dos. Cada una va a `pendientes/` y dispara el plan B, y la cobertura del agua se llena de huecos.
  - Si en cambio se aceptaran, el día compartido se prorratearía dos veces.
- **Acción propuesta:**
  1. Antes del bloque 3, comprobar con dos facturas de agua consecutivas del histórico si la fecha de lectura actual de una coincide con la fecha de inicio de la siguiente.
  2. Si coinciden, plantearlo en el punto de control como un error del caso (la especificación no se edita). Proponer para `aigues_agua` la convención "inicio exclusivo": el parser normaliza inicio = fecha impresa + 1, como permite R23 por formato. Cambiarían los 61 días y el reparto de abril de los controles del agua.
  3. En el diseño (11.1 o sección 12), documentar para cada formato de qué dato del PDF sale cada extremo del período y cómo se verificó.

### H2. Restaurar copiando el archivo no restaura cuando hay un lector abierto

- **Severidad:** alta.
- **Requisito:** R43.
- **Qué está mal:**
  - La sección 14.2 (línea 919) dice que `restaurar` "copia una instantánea y sus ajustes, con el bloqueo tomado, y verifica `PRAGMA integrity_check`".
  - La base está en WAL (R39). Si queda un `facturas.db-wal` de la base anterior, SQLite aplica ese WAL sobre el archivo copiado. Basta con que el dashboard tenga una conexión abierta, lo normal en Streamlit con una conexión cacheada, y el bloqueo de la carga no lo impide.
- **Escenario de falla (reproducido):**
  - Una base con 200 filas genera una instantánea con `VACUUM INTO`.
  - El dashboard abre una conexión de solo lectura. La carga agrega 300 filas y modifica 100.
  - `restaurar` copia la instantánea sobre la base. En Windows, la copia sobre el archivo abierto no da error.
  - Al reabrir, la base "restaurada" tiene 500 filas y 100 modificadas: el estado posterior, no el de la instantánea. Aun así, `integrity_check` devuelve `ok`.
  - La restauración no restaura y la verificación del diseño no lo detecta.
- **Acción propuesta:**
  - Restaurar con la API de backup en sentido inverso, con el bloqueo tomado: `sqlite3.connect(instantanea).backup(conexion_escritura)`. Probado con un lector abierto: la base queda exactamente igual a la instantánea y el lector la ve.
  - Verificar el resultado comparando contenido (por ejemplo, conteos por tabla o un volcado canónico como el de 13.4), no solo con `integrity_check`.
  - El test del bloque 4 ("`restaurar` reproduce exactamente el contenido respaldado") tiene que incluir un lector abierto y escrituras posteriores a la instantánea.

### H3. I4 rechaza una factura original que llega después de su rectificativa

- **Severidad:** media.
- **Requisito:** R27, R33 (I4) y R19.
- **Qué está mal:**
  - I4 (sección 10, línea 553) compara cada línea con la suma de `v_hecho_gasto_diario`. Esa vista se construye sobre `v_linea`, que filtra con `v_factura_vigente`.
  - Una factura sustituida no aparece en esas vistas, así que su prorrateo suma 0.
  - El diseño afirma que "una rectificativa puede llegar antes que la factura que corrige" (línea 286), pero en ese orden la original nunca se puede cargar.
- **Escenario de falla (reproducido):**
  - Se carga R-1, una rectificativa por sustitución de F-1. Después llega F-1.
  - I4 para su línea: importe 1000, prorrateo 0. F-1 se rechaza en la etapa `invariantes`, va a `pendientes/` y el plan B no tiene nada que corregir.
  - Lo mismo pasa al reconstruir (13.4, línea 836: "en orden de ruta"). Si en la base en uso F-1 se cargó antes que R-1, las dos están en `procesadas/`. Si la ruta de R-1 ordena antes que la de F-1 (por número o por año de emisión), F-1 falla y `reprocesar --todo` aborta.
- **Acción propuesta:**
  - Calcular I4 sobre un prorrateo sin filtro de vigencia. Por ejemplo, separar el cálculo en una vista `v_prorrateo_linea` sobre todas las líneas y filtrar las vigentes en `v_hecho_gasto_diario`. Lo mismo para las mediciones.
  - Agregar tests con la rectificativa antes de la original y con la reconstrucción en los dos órdenes.

### H4. Un abono seguido de refacturación no se puede representar

- **Severidad:** media.
- **Requisito:** R27 y R28.
- **Qué está mal:**
  - `tg_linea_bi_solape` (líneas 1466–1484) e I6 comparan contra cualquier otra factura ordinaria del contrato, aunque ya no esté vigente o la haya anulado un abono.
  - Una forma habitual de corregir una factura de suministro es un abono que la anula entera más una factura nueva por el mismo período. Esa factura nueva suele ser ordinaria.
- **Escenario de falla (reproducido):**
  - F-1 es la factura ordinaria de enero (ZX,XX). A-1 es un abono de F-1 (−ZX,XX). F-2 es la refacturación ordinaria de enero (J,ZK).
  - F-2 se rechaza por solape.
  - Las vistas quedan con gasto de enero 0,00 y cobertura de enero 31/31 (`es_completo = 1`). El dashboard muestra un mes completo con gasto nulo.
  - Variante: una rectificativa por sustitución corrige el período de F-1 (del 1–31 al 1–20 de enero). La factura siguiente (21 de enero – 20 de febrero) se rechaza porque F-1, que ya no está vigente, sigue bloqueando.
- **Acción propuesta:**
  - Que el control de solapes (trigger e I6) ignore las facturas que ya no cuentan:
    - las sustituidas, que son las que excluye `v_factura_vigente`;
    - las anuladas por un abono que las referencia por su importe total.
  - Decidir con la persona usuaria cómo se reconoce una anulación. Por ejemplo, un abono con `importe_total_centimos` igual al de la factura referenciada con el signo cambiado.
  - Documentarlo en 3.4 y en I6, y agregar el escenario a los tests del bloque 2.

### H5. La base acepta una medición total junto con su desglose por franja

- **Severidad:** media.
- **Requisito:** R6, R3 y R13.
- **Qué está mal:**
  - Nada impide que una factura tenga, para el mismo contrato y la misma magnitud, una medición sin franja y otras con franja.
  - `ux_medicion_factura_contrato_magnitud_franja` (línea 1458) usa `ifnull(franja_id, 0)`, así que las admite juntas. El contrato del parser (11.5, línea 630) tampoco lo prohíbe.
  - `luz.pdf` imprime el consumo por franja y además "Total consumo 81 kWh", así que el error del parser es plausible.
- **Escenario de falla (reproducido):**
  - El parser de luz emite las tres franjas (20 + 21 + 40 kWh) y además el total sin franja (81 kWh).
  - La base lo acepta. C5 suma 162 kWh y el precio efectivo baja de Q,XKZX a J,XQJJ €/kWh.
  - Ningún invariante lo detecta: R33 no controla las mediciones, salvo su prorrateo.
- **Acción propuesta:**
  - Declarar la regla en la base: un trigger `BEFORE INSERT ON medicion` que rechace mezclar `franja_id` nulo y no nulo para la misma factura, contrato y magnitud.
  - Agregarla también a la validación de forma (11.6).
  - Documentar que, cuando hay desglose, el total impreso no se guarda como medición.

### H6. El alias `* (* - *)` funciona como concepto genérico

- **Severidad:** media.
- **Requisito:** R30 (y R31).
- **Qué está mal:**
  - Los alias `* (* - *)` de fibra y de móvil (líneas 707 y 709) aceptan cualquier texto que termine en un período entre paréntesis. En la práctica son un concepto genérico, lo que R30 prohíbe.
  - El riesgo está anotado (línea 737), pero solo para cargos fijos como el alquiler de un router, y se posterga a "las facturas históricas".
  - El caso sugería usar la sección del documento para identificar el concepto, y D4 la quitó del contrato. El PDF de Digi tiene secciones claras: "TOTAL CUOTAS", "TOTAL CONSUMO" y "TOTAL CONSUMO ADICIONAL".
- **Escenario de falla** (probado con la normalización de 12.3 y `GLOB` sobre las semillas de 12.2):

  | Categoría | Texto | Se traduce a |
  |---|---|---|
  | movil | Descuento promoción (15 Ago - 14 Sep) | `cuota_plan` |
  | movil | Datos adicionales (01 Sep - 14 Sep) | `cuota_plan`, tipo `fijo`, aunque es consumo |
  | movil | Roaming zona 1 (20 Ago - 22 Ago) | `cuota_plan` |
  | fibra | Penalización permanencia (15 Ago - 14 Sep) | `cuota_fibra` |

  Ninguno se rechaza: la factura se carga y el total cuadra, pero el desglose de "¿por qué cuesta lo que cuesta?" queda mal sin aviso. Un descuento negativo, por ejemplo, reduce la cuota del mes en lugar de aparecer como descuento.
- **Acción propuesta:**
  - Volver a incluir la sección del documento en las líneas de la factura extraída: el bloque 1 la pide en la lista de campos del contrato.
  - Que el alias pueda exigir una sección, de modo que solo las líneas de la sección de cuotas se traduzcan a cuota.
  - Con eso, el patrón del producto deja de necesitar el comodín inicial para distinguir la cuota de otros cargos.

### H7. Los cambios de semillas no llegan a la base en uso

- **Severidad:** media.
- **Requisito:** R29 (y R40).
- **Qué está mal:**
  - Las semillas solo se cargan al construir la base desde cero (12.5, línea 741; `construir.py`, línea 864), y la traducción consulta las tablas de la base (12.3).
  - El diseño no dice cómo llega a la base en uso un alias o un concepto nuevo. Sin embargo:
    - el bloque 6 aprueba justamente eso, alias nuevos en las semillas, y después ejecuta `reprocesar --pendientes`;
    - el bloque 4 lo exige como test: "Después de agregar el alias, `reprocesar --pendientes` la carga".
  - `PRAGMA user_version` versiona el esquema, no las semillas.
- **Escenario de falla:**
  - Un PDF de Digi con "Llamadas" se rechaza por texto sin alias.
  - El plan B agrega el alias a `alias_concepto.csv`, la persona usuaria aprueba y el script ejecuta `reprocesar --pendientes`.
  - La carga consulta `alias_concepto` en la base, que no cambió, y vuelve a rechazar la factura con el mismo motivo.
  - Si la carga leyera los CSV en lugar de la base, la base y las semillas divergirían. Es el "desfase del diccionario" que la auditoría citada en tarea.md quería evitar.
- **Acción propuesta:**
  - Guardar en la base una huella de las semillas, por ejemplo el SHA-256 de los CSV en una tabla de metadatos.
  - Al conectar en modo escritura, compararla con la de los archivos, igual que `user_version`. Si difiere, reconstruir (`reprocesar --todo`) antes de cargar o reintentar.
  - Documentarlo en el flujo (sección 13) y en la fila R29 de la trazabilidad.

### H8. Rectificativas que se suman o no se controlan contra solapes

- **Severidad:** baja.
- **Requisito:** R27 y R28.
- **Qué está mal:**
  - Si dos rectificativas por sustitución referencian la misma factura, `v_factura_vigente` (líneas 1557–1567) deja vigentes a las dos.
  - Las rectificativas nunca se controlan contra solapes.
- **Escenario de falla (reproducido):**
  - F-1 (ZX,XX) tiene dos rectificativas por sustitución, R-1 (J,ZK) y R-2 (K,KQ), que la referencian. Las dos quedan vigentes y enero suma ZQ,QQ.
  - F-1 va del 1 al 20 de enero y R-1 la sustituye con período del 1 al 31. F-2, del 21 de enero al 20 de febrero, se acepta: los días del 21 al 31 de enero se cuentan dos veces.
- **Acción propuesta:**
  - Un índice único parcial, que es declarativo y simple: `CREATE UNIQUE INDEX ux_factura_proveedor_numero_factura_corregida ON factura (proveedor_id, numero_factura_corregida) WHERE tipo = 'rectificativa_sustitucion'`.
  - Opcionalmente, extender el control de solapes a las rectificativas por sustitución contra las ordinarias vigentes distintas de la que sustituyen.

### H9. El alias por defecto puede colisionar con un ajuste manual

- **Severidad:** baja.
- **Requisito:** R19, R21 y R41. Agrava D7.
- **Qué está mal:**
  - D7 (línea 42) reconoce que una reconstrucción puede intercambiar los números de los alias por defecto, pero no que puede producir colisiones.
  - `uq_contrato_alias` (línea 1329) exige un alias único, el alias por defecto depende del orden de registro, y los ajustes manuales se aplican "al registrar cada contrato" (14.2).
  - No está definido cómo se elige `n` en "<categoría> <n>".
- **Escenario de falla (reproducido el error de unicidad):**
  - Tres líneas móviles A, B y C se registran en ese orden como "movil 1", "movil 2" y "movil 3".
  - La persona usuaria renombra A a "personal" y B a "movil 1". C no tiene ajuste manual.
  - En la reconstrucción, la primera factura de C ordena antes por ruta: por ejemplo, está en `movil/` y las otras en `fibra_movil/`. C recibe "movil 1".
  - Al registrar B con su ajuste "movil 1": `UNIQUE constraint failed: contrato.alias`. La factura falla y `reprocesar --todo` conserva la base anterior.
  - En la carga normal pasa algo parecido si la persona usuaria elige un alias con la forma de uno por defecto ("movil 3") y después aparece un contrato al que le toca ese número.
- **Acción propuesta:** guardar el alias por defecto en `ajustes_manuales.json` en el momento en que se genera. Resuelve D7 y la colisión, sin tablas nuevas. Como mínimo, elegir `n` como el menor número libre.

### H10. El reemplazo de una factura cargada no tiene un camino definido

- **Severidad:** baja.
- **Requisito:** R15, R17 y R6.
- **Qué está mal:**
  - El paso 6.2 del flujo (línea 804) prevé borrar la factura que "proviene de este mismo PDF (un reprocesamiento)". Pero por el paso 2, un hash ya cargado va a `duplicados/`, y ningún comando del bloque 4 reprocesa un PDF cargado: el paso no tiene un camino que llegue a él.
  - Si el bloque 4 lo implementa tal como está escrito, falla de dos maneras:
    1. Si la nueva extracción trae otro número de factura (por ejemplo, un error del parser ya corregido), buscar la factura existente por clave natural no encuentra nada, y la inserción falla por `uq_factura_carga`. Reproducido: `UNIQUE constraint failed: factura.carga_id`.
    2. Si el reprocesamiento falla, el paso 8 (líneas 811–815) marca la carga como `rechazada` y mueve el PDF a `pendientes/`, pero la factura anterior sigue en la base porque el `ROLLBACK` la restauró.
  - El esquema no lo impide: `ck_carga_estado` (línea 1309) solo mira la propia fila.
- **Escenario de falla (reproducido el estado final):**
  - Tras un upsert como el del paso 8.2, la carga del agua queda `rechazada / invariantes`.
  - Su factura sigue vigente y suma ZX,KK en el gasto, y `foreign_key_check` no devuelve nada.
  - El PDF ya no está en `procesadas/`, así que la próxima reconstrucción pierde esa factura.
- **Acción propuesta:**
  - Elegir una de estas opciones:
    - quitar el paso 6.2 y declarar que el único reemplazo es `reprocesar --todo`, que cubre R17;
    - definir el reemplazo borrando por `carga_id` y, si falla, dejar la carga y el PDF como estaban.
  - En cualquier caso, agregar un trigger `BEFORE UPDATE ON carga` que impida pasar a `rechazada` una carga que referencia una factura.

### H11. La cobertura usa los períodos de las líneas

- **Severidad:** baja.
- **Requisito:** R26.
- **Qué está mal:**
  - La cobertura (sección 9, línea 537; CTE `periodo_cubierto` de `v_hecho_cobertura_contrato_mensual`, línea 1690) usa los períodos de las líneas.
  - El control de solapes, en cambio, usa los de las facturas.
  - Una línea con período propio, que R23 permite cuando el documento lo indica (una regularización, un consumo facturado con retraso), marca como cubiertos días que corresponden a otra factura.
- **Escenario de falla:**
  - Falta la factura de luz de enero.
  - La de marzo trae "Regularización (01/01/2026 - 31/03/2026)" con imputación `periodo` y ese período.
  - Enero aparece completo, aunque falta su factura.
- **Acción propuesta:** contar como cubiertos los días del período de la factura (`v_factura_vigente.fecha_inicio` y `fecha_fin`) para cada contrato con al menos una línea `periodo` en ella. Así cobertura y solapes usan la misma definición.

### H12. No hay regla para un descuadre de redondeo en el IVA de Digi

- **Severidad:** baja.
- **Requisito:** R5 y R33 (I8 e I1).
- **Qué está mal:**
  - I8 exige igualdad exacta entre la suma de las líneas derivadas y el IVA impreso (sección 10, línea 557; caso, línea 167).
  - El diseño no prevé el caso en que los totales por servicio no suman el total impreso. Eso pasa si Digi redondea el IVA de cada servicio por separado y el de la factura sobre la base total.
- **Escenario de falla (aritmético):**

  | Servicio | Base | Total con IVA | IVA derivado |
  |---|---|---|---|
  | móvil | X,ZQ | J,KX | Q,JX |
  | fibra | QK,KQ | ZX,ZJ | X,ZZ |
  | **suma** | **XX,ZZ** | | **X,QK** |

  El IVA de una base de XX,ZZ es X,KZ. I8 e I1 fallan por 1 céntimo, la factura va a `pendientes/` y el plan B no la puede corregir, porque tiene prohibido cambiar tolerancias. En el ejemplo cuadra, con bases de Z,KQ y QK,KQ.
- **Acción propuesta:** comprobar con el histórico de Digi si los totales por servicio siempre suman el total. Si no, decidir con la persona usuaria una regla de reparto del céntimo (por ejemplo, al servicio con mayor base) y documentarla en 11.3.

### H13. Los errores de clave foránea no dicen qué regla falló

- **Severidad:** baja.
- **Requisito:** R37, y el diagnóstico de los rechazos (13.3).
- **Qué está mal:**
  - La sección 2 (línea 74) dice que los nombres de las restricciones aparecen en los mensajes de error, y 13.3 que el motivo lleva "el mensaje de la restricción". Eso solo es cierto para los `CHECK`:
    - una violación de FK, incluidas las de R9 y R42, da `FOREIGN KEY constraint failed`, sin nombre ni columnas;
    - un `UNIQUE` nombra las columnas, no la restricción.
  - Además, los índices que crean los `UNIQUE` se llaman `sqlite_autoindex_*`, no `uq_*`. Son los nombres que muestra `EXPLAIN QUERY PLAN`, aunque las secciones 6.1 y 6.2 los citen como `uq_…`.
- **Escenario de falla (reproducido):** una línea de agua con un concepto de gas da `FOREIGN KEY constraint failed`. El `.motivo.txt` y el plan B no saben qué regla falló.
- **Acción propuesta:**
  - En la transacción de carga, ejecutar `PRAGMA defer_foreign_keys = ON`. Así I7 (`PRAGMA foreign_key_check`), antes del `COMMIT`, devuelve la tabla, la fila y la clave foránea que fallan. Probado: devuelve `('linea', 26, 'concepto', 0)`, que se traduce a `fk_linea_concepto` con `PRAGMA foreign_key_list`.
  - Para los nombres de índice, declarar las claves naturales con `CREATE UNIQUE INDEX ux_…`, o documentar la excepción.

### H14. Nulos opcionales que pueden esconder un dato no extraído

- **Severidad:** baja.
- **Requisito:** R10.
- **Qué está mal:**
  - Varios campos opcionales tienen un nulo que significa "el formato no lo imprime" o "no hay desglose": `fecha_vencimiento` (11.1, línea 591), `franja` (11.5, línea 630), y `cantidad_contador` y `factor_conversion` (11.5).
  - Nada dice qué formatos sí los imprimen. Si el parser no encuentra el dato, la validación de forma (11.6) acepta el nulo y la base lo guarda con el significado documentado, aunque el dato existía.
- **Escenario de falla:**
  - Digi cambia la maquetación y el parser deja de encontrar el vencimiento.
  - La factura se carga con `fecha_vencimiento` nula, que según la documentación significa "el formato no la imprime".
  - Es el nulo ambiguo que R10 prohíbe. Lo mismo pasaría con los m³ del gas.
- **Acción propuesta:**
  - Que cada parser declare qué campos opcionales imprime su formato, y que la validación de forma los exija para ese formato.
  - Para el gas, además, una regla en la base: si la unidad de contador de `magnitud_categoria` difiere de la canónica, `cantidad_contador_milesimas` es obligatoria (trigger).


---

## 4. Resolución

Agregada por el agente diseñador. Cada corrección está en `docs/diseno.md` y se probó en el prototipo (sección 17 del diseño), con un escenario por hallazgo. Las consultas de referencia siguen devolviendo los valores del caso, y los 12 controles de prorrateo coinciden.

| Id | Severidad | Qué se hizo | Dónde |
|---|---|---|---|
| H1 | alta | **Corregido en el diseño; requiere confirmación en el punto de control.** El hallazgo se confirmó con el propio PDF: "250 litros por día" (15.000 l / 60) y "J,KZ €/día" (ZX,KK € / 60) corresponden a 60 días, no a los 61 del caso. Se propone que el período del agua no cuente su primer día (inicio = fecha impresa + 1), la misma lógica de lectura a lectura que se ve en el gas. Se documentó, para cada formato, de qué dato sale cada extremo y cómo se verificó. Con la propuesta, dos facturas de agua consecutivas se cargan sin solape. Como contradice el caso (los 61 días y los controles del agua), no se edita la especificación: se plantea en el punto de control. Pendiente: confirmarlo con dos facturas consecutivas del histórico (bloque 3). | D10; 11.7; 17 |
| H2 | alta | **Corregido.** `restaurar` usa la API de backup en sentido inverso, con el bloqueo tomado; nunca copia el archivo. Se verifica comparando el volcado canónico con el de la instantánea, no solo con `integrity_check`. El test del bloque 4 restaura con un lector abierto y con escrituras posteriores a la instantánea. | 14.2 |
| H3 | media | **Corregido.** El prorrateo se separó en `v_prorrateo_linea` y `v_prorrateo_medicion`, que incluyen todas las facturas; las vistas de hechos filtran las vigentes. I4 usa las vistas de prorrateo. Probado: la original que llega después de su rectificativa se carga y queda no vigente. | 7.2; 10; apéndice A |
| H4 | media | **Corregido.** El control de solapes (trigger e I6) ignora las ordinarias que una rectificativa por sustitución o un abono del mismo proveedor corrige, sean la nueva o la existente. Además, la carga ordena el lote por fecha de emisión y reintenta una vez los rechazos de la etapa `insercion` del mismo lote. Probado: un abono más la refacturación del mismo período se cargan, y el gasto del período es el de la refacturación. No hizo falta distinguir abonos totales de parciales: un abono parcial seguido de una ordinaria por el mismo período suma las dos, que es lo que dicen los documentos (límite documentado en 3.4). | 3.4; 10; 13.2 |
| H5 | media | **Corregido.** Trigger `tg_medicion_bi_franja` y regla equivalente en la validación de forma: no se mezclan mediciones con y sin franja. Probado. | 3.3; 3.4; 11.5; 11.6 |
| H6 | media | **Corregido.** La sección del documento vuelve a la factura extraída (`seccion`) y el alias tiene `patron_seccion`. En Digi, la cuota exige la sección PRODUCTOS y los consumos se identifican por su sección, como sugiere el caso. Probado: un descuento, una penalización o un producto fuera de PRODUCTOS se rechazan; los datos adicionales y el roaming en CONSUMO ADICIONAL se traducen bien. Riesgo residual documentado: una línea nueva dentro de PRODUCTOS con un período entre paréntesis. | D4; 3.2; 11.4; 12.2–12.4 |
| H7 | media | **Corregido.** Nueva tabla `construccion`, de una sola fila, con la huella SHA-256 de las semillas. Antes de cada lote, la carga la compara con los archivos y, si difiere, reconstruye la base antes de procesar. | 3.2; 13.2; 13.4 |
| H8 | baja | **Corregido.** Índice único parcial `ux_factura_proveedor_id_numero_factura_corregida_sustitucion`. Probado. No se controlan los solapes de las rectificativas: es un límite documentado, porque una sustitución pisa legítimamente el período de la que sustituye. | 3.3; 3.4 |
| H9 | baja | **Corregido.** El alias por defecto usa el menor número libre, sin contar los alias de la base ni los reservados en `ajustes_manuales.json`. El comando `contrato` rechaza un alias ya usado o reservado. Sigue pendiente D7 (la numeración puede cambiar al reconstruir), por decisión de la persona usuaria. | 14.2 |
| H10 | baja | **Corregido.** Se quitó el paso 6.2: una factura cargada solo se reemplaza al reconstruir la base (13.4). Trigger `tg_carga_bu_cargada`: una carga con factura no se modifica. Probado. | 3.3; 13.2; 13.4 |
| H11 | baja | **Corregido.** La cobertura usa el período de cada factura vigente en la que el contrato tiene líneas `periodo`, la misma definición que el control de solapes. Probado. | 9; apéndice A |
| H12 | baja | **Justificado y pendiente para el bloque 3.** I8 sigue exigiendo igualdad exacta, así que un descuadre de 1 céntimo se rechaza y nunca se acepta en silencio. El bloque 3 verificará con las facturas históricas de Digi si ocurre; si ocurre, la regla de reparto del céntimo se decide con la persona usuaria. | 10 |
| H13 | baja | **Corregido.** La transacción de carga difiere las FK (`PRAGMA defer_foreign_keys = ON`). I7 traduce cada fila de `foreign_key_check` a la FK y sus columnas. Probado: "linea → contrato (contrato_id, categoria_id)". Los nombres `sqlite_autoindex_*` quedan como excepción documentada de la convención. | 2; 10 |
| H14 | baja | **Corregido.** Cada parser declara qué campos opcionales imprime su formato, y la validación de forma los exige (tabla en 11.6). Para el gas, además, el trigger `tg_medicion_bi_conversion` exige la cantidad en m³ y el factor. Probado. | 3.3; 11.6 |

Como hubo hallazgos de severidad alta, se lanza una segunda ronda de revisión sobre la versión corregida.

---

## 5. Segunda ronda

Revisión independiente de la versión corregida de [`docs/diseno.md`](diseno.md), contra los hallazgos H1–H14 y su resolución (sección 4).

**Cómo se verificó.**
- Ejecuté el apéndice A y las consultas C1–C7 en SQLite 3.49.1 (Python 3.12), en memoria. Usé las semillas de la sección 12, con los patrones de sección, y las cuatro facturas de ejemplo, con el agua en las dos convenciones: el inicio impreso y D10.
- Los totales por categoría, los 12 repartos mensuales y la cobertura de mayo y junio coinciden con el caso. Con D10, el agua queda en abril ZZ,JK, mayo ZK,KX y junio X,KJ, como dice la sección 17.
- Reproduje los escenarios de la primera ronda. Probé las piezas nuevas:
  - las excepciones del control de solapes;
  - el lote ordenado con reintento final;
  - el reemplazo de la base al reconstruir, con un lector abierto en otro proceso;
  - las vistas de prorrateo sin filtro de vigencia;
  - la traducción por sección;
  - los triggers nuevos.
- Rendimiento con 10 años simulados (360 facturas, 2.280 líneas): C1–C7 entre 0,06 y 0,59 s; I4 de una factura, 0,28 s; la carga de una factura con sus invariantes, 0,31 s.
- Contrasté D10 y los rótulos de sección con el texto de `agua.pdf` y `fibra_movil.pdf`.

Los scripts quedaron fuera del proyecto, en `%TEMP%\claude\revision_b1_r2\`.

### 5.1 Veredicto

**Apto con cambios.**

Las correcciones resuelven los dos hallazgos altos y los cinco medios de la primera ronda: los escenarios originales ya no fallan. No queda ningún hallazgo de severidad alta.

Queda un hallazgo medio, **H15**, que hay que resolver en el diseño antes del bloque 4. Con H7, la reconstrucción se ejecuta sola después de cada cambio de semillas, pero el diseño no dice cómo reemplaza la base. Las dos formas obvias fallan en Windows con el dashboard abierto, y una de ellas sin dar error. Los demás hallazgos nuevos (H16–H19) son bajos.

**D10:** la evidencia es correcta y la solución, coherente (detalle en la fila H1). Sigue pendiente de confirmar en el punto de control, porque contradice el caso.

### 5.2 Verificación de la resolución

| Id | Estado | Evidencia |
|---|---|---|
| H1 | resuelto (D10 pendiente de confirmar en el punto de control) | Una factura de agua que empieza el mismo día en que termina la anterior se rechaza por solape con el inicio impreso, y se carga con D10 (inicio impreso + 1); abril queda cubierto 30/30. Evidencia de D10, verificada en el texto del PDF: 15.000 l / 60 = 250 ("250 litros por día"; con 61 días serían 246) y ZX,KK / 60 = Q,ZQX ("J,KZ €/día"; con 61, J,KQ). Hay una tercera cifra que el diseño no cita: JK,ZZ / 60 = K,KZK ("J,JK €/día" del suministro; con 61, Z,ZX). El período impreso coincide con las fechas de las dos lecturas, y la convención es la misma que en el gas, donde la lectura "desde" es la del día anterior al inicio. Sugerencia: que el parser de `aigues_agua` verifique los días de cada factura con esos promedios impresos, como prevé 11.1 ("cuando lo imprime"), en lugar de depender de un solo ejemplo. |
| H2 | resuelto | `restaurar` usa la API de backup y verifica por volcado (14.2). Probado con el lector en otro proceso, como el dashboard: el escritor ve la instantánea, el lector también desde su siguiente lectura, e `integrity_check` da `ok`. El mismo defecto reaparece al reemplazar la base en la reconstrucción (H15). |
| H3 | resuelto | `v_prorrateo_linea` y `v_prorrateo_medicion` no filtran la vigencia. La original que llega después de su sustitución pasa I4, en líneas y en mediciones, y queda no vigente. En lote, con las dos rutas en los dos órdenes, el gasto es el de la sustitución (J,ZK). |
| H4 | resuelto dentro de un mismo lote | Con abono y refacturación, la refacturación se carga y enero suma J,ZK. En la variante de una sustitución que acorta el período, la factura siguiente se carga. Si la refacturación ordena antes que el abono en el mismo lote, el reintento final la carga. Si llegan en lotes distintos, refacturación primero, no se carga (H17). La corrección introdujo H16. |
| H5 | resuelto | `tg_medicion_bi_franja` rechaza el total de luz junto con sus franjas, en los dos órdenes de inserción. |
| H6 | resuelto | Con `patron_seccion`, los textos de la primera ronda se rechazan: un descuento en otro bloque, una penalización en OTROS CONCEPTOS, un producto sin período y "Llamadas" sin sección. Los consumos de Digi se traducen por su sección. Riesgo residual ya documentado (12.4): "Descuento promoción (…)" dentro de PRODUCTOS se traduce a `cuota_plan`. Los rótulos subrayados de Digi se pueden limpiar: con pdfplumber, descartando los caracteres `_`, salen "PRODUCTOS", "CONSUMO INCLUIDO EN EL PLAN" y "CONSUMO ADICIONAL", con sus espacios. |
| H7 | parcialmente resuelto | La huella de `construccion` y la comparación antes del lote (13.2) detectan el cambio de semillas. Pero, con el dashboard abierto, el reemplazo de la base falla o no surte efecto, y el PDF pendiente se vuelve a rechazar con el mismo motivo. El escenario original sigue ocurriendo en la configuración normal (H15). |
| H8 | parcialmente resuelto | El índice parcial rechaza una segunda sustitución de la misma factura y admite la cadena en la que R-2 sustituye a R-1. La segunda parte sigue igual: R-1 (del 1 al 31 de enero) sustituye a F-1 (del 1 al 20) y F-2 (del 21 de enero al 20 de febrero) se acepta, con 11 días contados dos veces. La justificación ("una sustitución pisa legítimamente el período de la que sustituye") no cubre el caso: el doble conteo es entre la sustitución y otra ordinaria (H16). |
| H9 | resuelto | Escenario de la primera ronda con la regla de 14.2: C se registra primero y recibe "movil 2", porque "movil 1" está reservado; B recibe su "movil 1" sin colisión. |
| H10 | resuelto | Se quitó el paso 6.2. `tg_carga_bu_cargada` impide pasar a `rechazada` la carga del agua, y una carga rechazada sin factura se reintenta y queda cargada. |
| H11 | resuelto | Falta la factura de enero y la de marzo trae una regularización del 1 de enero al 31 de marzo: la cobertura empieza en febrero y enero no aparece cubierto. |
| H12 | resuelto (justificado) | I8 sigue con tolerancia 0, así que un descuadre se rechaza y nunca se acepta en silencio. La verificación con el histórico de Digi queda para el bloque 3. |
| H13 | resuelto | Con `defer_foreign_keys`, `foreign_key_check` devuelve `('linea', 26, 'concepto', 0)` y la FK se puede nombrar. Detalle a corregir: con las FK diferidas, una violación de R9 se detecta en la etapa `invariantes` (I5 o I7), no en `insercion` como dice la tabla de 13.3 (línea 904). |
| H14 | resuelto | `tg_medicion_bi_conversion` rechaza una medición de gas sin m³ ni factor y acepta la del agua. La tabla de campos opcionales por formato está en 11.6. |

### 5.3 Cumplimiento

Solo figuran los requisitos cuyo estado cambió respecto de la primera ronda. El resto sigue igual:
- R1, R2, R3, R4, R11 y R33 siguen en parcial o no cumple, ahora solo por los desvíos aprobados (D1, D2, D3 y D5).
- R6 sigue en parcial por H19.
- R19 sigue en parcial por D7, H15 y H18.
- R28 sigue en parcial por H16 y H17.
- R29 sigue en parcial por D2 y H15.

| R | Antes | Ahora | Evidencia |
|---|---|---|---|
| R10 | parcial | cumple | Los campos opcionales que un formato imprime son obligatorios para ese formato (11.6) y, en el gas, también los exige la base (`tg_medicion_bi_conversion`). Probado (H14). |
| R23 | parcial | cumple, si se confirma D10 | La convención de cada formato está documentada en 11.7, con el dato del PDF del que sale cada extremo y cómo se verificó. La del agua tiene tres cifras impresas a favor (H1). Contradice el caso, que se corregiría en el punto de control. |
| R27 | parcial | cumple | La original se carga después de su sustitución (H3), un abono con refacturación se puede representar (H4) y una factura se sustituye una sola vez (H8). |
| R30 | parcial | cumple | La sección acota los comodines de Digi: un cargo nuevo fuera de sus bloques se rechaza con su texto (H6). |
| R43 | parcial | cumple | La restauración usa la API de backup y se verifica por volcado (14.2), probada con un lector en otro proceso (H2). |

### 5.4 Hallazgos nuevos

**Exceso de complejidad:** no encontré piezas que sobren. Todo lo que agregó la resolución responde a un hallazgo y es chico: la tabla `construccion`, el índice parcial, tres triggers y el orden del lote. El orden por fecha de emisión no es redundante con el reintento: en la carga histórica, que es un solo lote, carga los documentos en el orden en que se emitieron, y hace más estable la numeración de D7 entre la carga normal y la reconstrucción.

| Id | Severidad | Requisito | Resumen |
|---|---|---|---|
| H15 | media | R19, R29 | La reconstrucción, que con H7 se ejecuta sola, no dice cómo reemplaza la base. Con el dashboard abierto, `os.replace` falla y copiar el archivo no surte efecto. |
| H16 | baja | R28, R27 | Las sustituciones quedan fuera del control de solapes. Desde H4, el período de una factura sustituida no tiene control. |
| H17 | baja | R27, R28, R26 | El reintento final solo cubre el mismo lote: una refacturación que llega antes que su abono queda pendiente, y el mes figura completo con gasto 0. |
| H18 | baja | R19 | `construccion.fecha_hora` hace que dos reconstrucciones nunca den el mismo volcado. |
| H19 | baja | R6 | `ck_carga_estado` no hace cumplir las equivalencias entre etapa de rechazo y nulos que documenta 3.3. |

#### H15. La reconstrucción automática no dice cómo reemplaza la base

- **Severidad:** media.
- **Requisito:** R19 y R29, en la situación que R39 prevé: el dashboard lee mientras la carga escribe.
- **Qué está mal:**
  - 13.4, paso 3 (línea 916): "Si todos se cargan, reemplaza la base anterior". No dice cómo. 14.2 (línea 1005) prohíbe copiar el archivo para restaurar, por el WAL, pero esa regla no alcanza a la reconstrucción.
  - Con H7, la reconstrucción dejó de ser un comando manual y poco frecuente. Se ejecuta sola antes de cualquier lote cuando cambia la huella de las semillas (13.2, línea 868). Eso pasa al aprobar una propuesta del plan B: `aprobar_propuesta.ps1` integra la rama y ejecuta `reprocesar --pendientes`, normalmente con el dashboard de Streamlit abierto.
  - 13.4, paso 2 (línea 915), carga "como un lote (sección 13.2)", y en 13.2 un fallo mueve el PDF a `pendientes/` (línea 891). Si un PDF de `procesadas/` falla al reconstruir, se conserva la base anterior, que sigue teniendo esa factura, pero su PDF ya no está en `procesadas/`. La siguiente reconstrucción la pierde.
  - No está definido qué hace el lote si la reconstrucción automática falla. Si sigue, carga con un diccionario distinto del versionado, que es el desfase que H7 quería evitar. Además, cada lote siguiente, incluido el barrido periódico, vuelve a intentar la reconstrucción completa.
- **Escenario de falla** (reproducido en Windows 11, con el lector en otro proceso):
  - El dashboard tiene abierta una conexión `mode=ro`. La carga escribe y cierra; queda un `facturas.db-wal` de 2,3 MB.
  - La reconstrucción termina la base nueva en un archivo temporal y la pone en lugar de la anterior:
    - Con `os.replace`: `PermissionError [WinError 5]`. Se conserva la base anterior, y el PDF pendiente se vuelve a rechazar por "texto sin alias" aunque el alias ya está aprobado.
    - Con `shutil.copyfile`: no da error, pero al reabrir, SQLite aplica el WAL viejo y la base tiene el contenido anterior (500 filas, 100 de ellas modificadas, y ninguna de la base nueva), con `integrity_check` en `ok`. La reconstrucción no ocurrió, `construccion` conserva la huella vieja y cada lote siguiente reconstruye otra vez, sin efecto.
  - Con la API de backup (del archivo temporal a la conexión de escritura), la base queda igual a la nueva y el lector la ve desde su siguiente lectura.
- **Acción propuesta:**
  - En 13.4, paso 3: reemplazar con la API de backup, igual que `restaurar`: `sqlite3.connect(temporal).backup(conexion_escritura)`, con el bloqueo tomado. Nunca renombrar ni copiar el archivo. Verificar con el volcado canónico.
  - Que la reconstrucción no mueva ni renombre PDFs: lee `procesadas/` y, si algo falla, solo informa.
  - Definir qué pasa si la reconstrucción automática falla: el lote no procesa nada, termina con error del sistema (código 2) y avisa. Nunca se carga con un diccionario distinto del versionado.
  - En el bloque 6, que `aprobar_propuesta.ps1` haga una reconstrucción de prueba en un archivo temporal antes de confirmar la integración, y la deshaga si falla. Los tests solo cubren `ejemplos/`, y la reconstrucción vuelve a extraer todo `procesadas/` con el parser de la propuesta.

#### H16. Las sustituciones quedan fuera del control de solapes

- **Severidad:** baja.
- **Requisito:** R28 (y R27). Es lo que queda de H8, más una regresión de la corrección de H4.
- **Qué está mal:**
  - `tg_linea_bi_solape` (líneas 1578–1604) e I6 solo comparan facturas ordinarias: `nueva.tipo = 'ordinaria'` (línea 1585) y `otra.tipo = 'ordinaria'` (línea 1597). Desde H4, además, una ordinaria corregida por una sustitución deja de contar.
  - Juntas, las dos reglas dejan el período de una factura sustituida sin ningún control: la original ya no cuenta, y su sustituta no se compara con ninguna otra factura.
  - El límite de 3.4 (línea 384) lo justifica con que "una sustitución pisa legítimamente el período de la que sustituye". Eso vale frente a la factura sustituida, no frente a las demás ordinarias del contrato.
- **Escenarios de falla** (reproducidos):
  - Regresión: con F-1 (enero, ZX,XX) cargada, una ordinaria X-1 del mismo período se rechaza por solape. Después de cargar R-1, que sustituye a F-1 (J,ZK), la misma X-1 se acepta y enero suma QX,KJ.
  - Resto de H8: R-1 sustituye a F-1 (del 1 al 20 de enero) con período del 1 al 31. F-2 (del 21 de enero al 20 de febrero) se acepta, y 11 días de enero se cuentan dos veces.
- **Acción propuesta:**
  - En el trigger y en I6, controlar las sustituciones como las ordinarias: `tipo IN ('ordinaria', 'rectificativa_sustitucion')`, tanto en `nueva` como en `otra`. La exclusión de las facturas corregidas, que ya existe, saca de la comparación a la factura sustituida.
  - Probado con esa variante: los dos escenarios se rechazan, y siguen funcionando H3 (original después de su sustitución), H4 (abono y refacturación), la sustitución del mismo período y la cadena R-2 → R-1.
  - Actualizar el límite documentado en 3.4.

#### H17. El reintento final solo cubre el mismo lote

- **Severidad:** baja.
- **Requisito:** R27 y R28 (y R26). Es lo que queda de H4.
- **Qué está mal:** 13.2, "Al final del lote" (línea 894), reintenta solo los PDFs que rechazó ese mismo lote. Si la refacturación llega en un lote y su abono en otro posterior, nada la vuelve a intentar.
- **Escenario de falla** (reproducido):
  - F-1 (enero) está cargada.
  - La refacturación F-2 llega primero: se rechaza por solape y va a `pendientes/`. El plan B hace su único intento automático, sin nada que corregir.
  - En un lote posterior llega el abono A-1 de F-1 y se carga. F-2 sigue en `pendientes/`.
  - Enero queda con gasto 0,00 y cobertura 31/31, como completo: el síntoma original de H4. Solo se corrige si la persona usuaria ejecuta `reprocesar --pendientes` por su cuenta.
- **Acción propuesta:** al final de cada lote que cargó un abono o una sustitución, reintentar también los PDFs de `pendientes/` rechazados por solape en la etapa `insercion`, sean de ese lote o de uno anterior. Es el mismo mecanismo, aplicado a más PDFs.

#### H18. La fila de `construccion` impide una reconstrucción idéntica

- **Severidad:** baja.
- **Requisito:** R19.
- **Qué está mal:** `construccion.fecha_hora` (línea 244) registra cuándo se construyó la base. El volcado canónico de 13.4 (líneas 920–923) solo excluye `carga.fecha_hora` y las cargas rechazadas.
- **Escenario de falla** (reproducido): dos construcciones con las mismas semillas y los mismos PDFs dan volcados que difieren solo en esa columna (`2026-10-02 12:00:00` frente a `2026-10-02 19:07:41`). El test del bloque 4 "`reprocesar --todo` produce exactamente el mismo contenido" falla, o el bloque 4 agrega una excepción que el diseño no documenta.
- **Acción propuesta:** excluir `construccion.fecha_hora` del volcado, igual que `carga.fecha_hora`, o quitar la columna, que ningún requisito ni consulta usa.

#### H19. `ck_carga_estado` no hace cumplir las equivalencias de 3.3

- **Severidad:** baja.
- **Requisito:** R6. Ya figuraba en la evidencia de R6 de la primera ronda, sin un id propio.
- **Qué está mal:** 3.3 documenta que `formato` es nulo si y solo si el rechazo fue en la etapa `formato` (línea 258), y que `extraccion_json` es nula si y solo si fue en `formato` o `extraccion` (línea 264). `ck_carga_estado` (línea 1417) y `ck_carga_extraccion_json` no lo exigen.
- **Escenario de falla** (reproducido): la base acepta una carga rechazada en la etapa `traduccion` sin formato ni extracción, y otra rechazada en `formato` con formato. Si el bloque 4 registra mal un rechazo, la carga queda sin la salida del parser, que R14 pide guardar para reprocesar sin volver a leer el PDF.
- **Acción propuesta:** agregar un `CHECK` con las dos equivalencias: `(coalesce(etapa_rechazo, '') = 'formato') = (formato IS NULL)` y `(coalesce(etapa_rechazo, '') IN ('formato', 'extraccion')) = (extraccion_json IS NULL)`. Probado con las cargadas y con cada etapa de rechazo: acepta las combinaciones válidas y rechaza las demás.


---

## 6. Resolución de la segunda ronda

Agregada por el agente diseñador. Es la última ronda: `tarea.md` permite dos como máximo. Las correcciones están en `docs/diseno.md`, y las de esquema se probaron en el prototipo. Siguen coincidiendo los controles del caso.

| Id | Severidad | Qué se hizo | Dónde |
|---|---|---|---|
| H15 | media | **Corregido.** La reconstrucción pasa la base nueva a la base en uso con la API de backup, con el bloqueo tomado, y lo verifica con el volcado canónico; nunca renombra ni copia el archivo. Solo lee `procesadas/`, sin mover ningún PDF. Si falla, conserva la base anterior e informa. Si la reconstrucción automática por cambio de semillas falla, el lote no procesa nada y termina con código 2. Para el bloque 6 queda anotada la sugerencia de que la aprobación de una propuesta haga una reconstrucción de prueba antes de integrar. | 13.2; 13.4; bitácora |
| H16 | baja | **Corregido.** El trigger e I6 controlan `tipo IN ('ordinaria', 'rectificativa_sustitucion')`, en la factura nueva y en la existente. Probado: una ordinaria que pisa los días que agregó una sustitución y una ordinaria del mismo período que una factura ya sustituida se rechazan. Una factura contigua y una cadena de sustituciones se cargan, y H3 y H4 siguen funcionando. Se actualizó el texto de 3.4. | 3.4; 10; apéndice A |
| H17 | baja | **Corregido.** Al final de cada lote que cargó algo se reintentan los PDFs de `pendientes/` rechazados por solape, sean de ese lote o de uno anterior. | 13.2 |
| H18 | baja | **Corregido.** Se quitó `construccion.fecha_hora`, que ningún requisito usa. | 3.2; apéndice A |
| H19 | baja | **Corregido.** `ck_carga_formato` y `ck_carga_extraccion_json` exigen las dos equivalencias. Probado: se rechazan las tres combinaciones inválidas y se aceptan las seis etapas de rechazo válidas y las cargas exitosas. | 3.3; apéndice A |
| H13 (detalle) | — | **Corregido.** En la tabla 13.3, una violación de clave foránea (R9, R42) ahora figura en la etapa `invariantes`, porque las FK están diferidas. | 13.3 |
| H1 (sugerencia) | — | **Incorporada.** Se citan los tres promedios impresos (250 l/día, J,KZ €/día y J,JK €/día), y el parser del agua verifica los días de cada factura con ellos. D10 sigue pendiente de confirmar en el punto de control. | 11.7 |

**Estado final:** no queda ningún hallazgo de severidad alta ni media abierto. H12 (baja) queda justificado y pendiente para el bloque 3.

**Punto de control (2026-10-02):** la persona usuaria confirmó D10. La factura de agua anterior a la del ejemplo termina el 09-abr-2026, el día en que empieza la del ejemplo. Con su autorización se corrigió `caso_hogar.md`.
