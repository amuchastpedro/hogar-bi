# Requisitos

Parte genérica de la especificación que se consulta, no se lee al empezar cada bloque: el glosario, el estándar de calidad, los requisitos R1–R43 y la revisión técnica independiente. El proceso está en [`tarea.md`](tarea.md). Los bloques de diseño (1 y 2) lo leen entero; los demás, solo los requisitos que citan.

## Glosario

| Término | Significado |
|---|---|
| Proveedor | Empresa que emite la factura, identificada por su identificador fiscal (el caso define cuál). |
| Formato | Plantilla de PDF de un proveedor. Un proveedor puede tener varias (por ejemplo, una por cada tipo de servicio que factura). Hay un parser por formato. |
| Contrato | Lo que se paga de forma recurrente a un proveedor: un punto de suministro, una línea, una póliza, una suscripción. Tiene un identificador externo (el código con el que el proveedor lo identifica; el caso indica cuál es en cada formato), pertenece a una categoría de gasto y tiene un alias visible. |
| Categoría de gasto | Agrupación que usa el dashboard para responder "¿cuánto gasté en X?". La define el caso. |
| Tipo de cargo | Clasificación que usa el dashboard para responder "¿por qué X cuesta lo que cuesta?". La define el caso. |
| Concepto | Cargo normalizado (por ejemplo, "cuota mensual"). Pertenece a una categoría y a un tipo de cargo. |
| Alias | Texto de un cargo tal como aparece en el PDF. Cada alias se traduce a un concepto. |
| Línea | Un cargo concreto de una factura: concepto, contrato, importe, cantidad, unidad, precio unitario, imputación y período. |
| Medición | Consumo físico informado en la factura, en las magnitudes y unidades que define el caso: magnitud, franja horaria si la hay, cantidad, unidad, lecturas y si son reales o estimadas. |
| Imputación | Cómo se reparte una línea en el tiempo: `periodo` (por días, a lo largo del período facturado) o `puntual` (entera en la fecha de emisión). |
| Cobertura | Para un contrato y un mes, la proporción de días esperados que están cubiertos por facturas. |

## Estándar de calidad

La base de datos tiene que estar al nivel de una diseñada por un ingeniero de datos con experiencia: el diseño se tiene que poder defender, decisión por decisión, en una revisión técnica. En la práctica, eso significa:

- cumplir todos los requisitos de la sección siguiente;
- documentar cada tabla, columna, clave, restricción, índice y vista;
- pasar una revisión técnica independiente en los bloques 1 y 2 (ver "Revisión técnica independiente").

**Fuentes.** Los requisitos no se inventaron para este proyecto: recogen prácticas establecidas.

| Fuente | Qué aporta | Requisitos |
|---|---|---|
| Teoría relacional (E. F. Codd) | Integridad de entidad, referencial y de dominio; tercera forma normal | R6–R10, R16, R35 |
| Modelado dimensional (Ralph Kimball, *The Data Warehouse Toolkit*) | Hechos y dimensiones, grano declarado, claves sustitutas, capa de lectura separada | R1, R32, R36, R37 |
| Documentación oficial de SQLite | Tablas `STRICT`, claves foráneas por conexión, `RETURNING`, índices y `EXPLAIN QUERY PLAN`, WAL, `busy_timeout`, `user_version`, API de backup | R7, R8, R17, R38–R40, R43 |
| Norma ISO 4217 | Códigos de moneda | R42 |
| Prácticas de ingeniería de datos | Dinero en enteros, transacciones atómicas, idempotencia, linaje, controles de calidad después de cada carga | R11, R14–R19, R33 |
| Auditoría de un intento anterior de este proyecto | Problemas concretos detectados en ese diseño (contaminación entre servicios, asimetría entre proveedores, desfase del diccionario, reconciliación temporal, restricciones no efectivas en SQLite), incorporados como requisitos | Gran parte de R2–R33 |

La selección es una decisión de este proyecto: se incluyó lo que aplica a una base SQLite de este tamaño y se dejó afuera lo que sería excesivo, como la gestión de usuarios y permisos, la replicación o el particionado.

## Requisitos

El bloque 1 tiene que mostrar, para cada requisito y por su número, con qué mecanismo lo cumple.

### Datos que se guardan

- **R1.** El dato crudo es la factura: una cabecera por factura y una fila por línea, tal como vienen en el documento. Todo lo demás (gasto mensual, cobertura) se deriva en vistas.
- **R2.** Cada línea guarda su contrato (y a través de él, su categoría de gasto), concepto (y a través de él, su tipo de cargo), cantidad, unidad, precio unitario, importe, imputación y período. La categoría se asigna en la línea, nunca en la cabecera, porque una misma factura puede incluir contratos de categorías distintas.
- **R3.** Se guardan las mediciones de consumo, con su franja horaria cuando la factura la informa, y si cada lectura es real o estimada.
- **R4.** Los impuestos guardan base imponible y tipo, para poder validar que cuota = base × tipo.
- **R5.** Cuando un impuesto aparece impreso solo como total, pero hay que repartirlo entre contratos de categorías distintas, el parser lo reparte usando los subtotales impresos en el documento y marca esas líneas como derivadas. La validación comprueba que su suma coincide con el total impreso.

### Integridad en la base

- **R6.** Las reglas de validez se declaran en el esquema, no solo en el código de carga. Si un dato inválido llega por cualquier vía (otro script, una corrección manual, un parser con un error), lo rechaza la propia base.
- **R7.** Tablas `STRICT`. `NOT NULL` en claves y campos obligatorios. `CHECK` para fechas en formato ISO (`col = date(col)`), períodos (`inicio <= fin`) y valores permitidos. Claves foráneas con `ON DELETE CASCADE` desde la factura hacia sus hijos.
- **R8.** Una única función de conexión que ejecuta `PRAGMA foreign_keys = ON` (SQLite lo trae desactivado y hay que activarlo en cada conexión), con un test que lo verifica.
- **R9.** La base impide que una línea use un concepto que no corresponde a la categoría de su contrato.
- **R10.** Ningún nulo ambiguo. Si una columna admite nulos, está documentado qué significan (por ejemplo, "no aplica"). Un dato que no se pudo extraer no se representa con un nulo: hace fallar la carga.

### Números

- **R11.** Importes en céntimos (`INTEGER`). Precios unitarios y tipos impositivos sin perder ningún decimal de los impresos.
- **R12.** El importe de cada línea es el impreso. Cantidad × precio solo se usa para validar, nunca para recalcular.
- **R13.** Cada magnitud tiene una unidad canónica por categoría, definida en el caso. Si el documento informa la misma magnitud en varias unidades, se guarda la canónica y el resto como atributos, incluido el factor de conversión.

### Idempotencia y trazabilidad

- **R14.** Una tabla de cargas registra:
  - el hash SHA-256 del PDF (único) y el nombre de archivo original;
  - el formato y la versión del parser;
  - la fecha y el estado (cargada o rechazada), con la etapa y el motivo si fue rechazada;
  - la salida cruda del parser en JSON, para poder reprocesar sin volver a leer el PDF.
- **R15.** Cada factura referencia su carga, de modo que cualquier número del dashboard se puede rastrear hasta su PDF.
- **R16.** La clave natural de la factura es proveedor + número de factura. Las claves naturales de las líneas no incluyen importes (por ejemplo, factura + posición en el documento).
- **R17.** Cargar dos veces el mismo PDF no cambia nada. Recargar una factura la reemplaza entera dentro de una transacción. Nunca se usa `INSERT OR REPLACE` sobre cabeceras ni `lastrowid` para obtener ids (se usa `RETURNING` o la clave natural).
- **R18.** Una factura se carga entera o no se carga: cabecera, líneas y mediciones van en una sola transacción.
- **R19.** La base es descartable. Se reconstruye desde cero con los PDFs de `datos/procesadas/`, las semillas versionadas y los datos manuales (R41), y el resultado es idéntico. Así un cambio de esquema no necesita migraciones.

### Proveedores y contratos

- **R20.** El proveedor se identifica por su identificador fiscal, normalizado según la regla que define el caso, con restricción de unicidad.
- **R21.** Los contratos se registran solos la primera vez que aparecen. El parser informa el identificador externo y la categoría (que conoce por el formato), y la carga genera un alias por defecto, con la regla que define el caso, que después se puede cambiar. El dashboard muestra el alias, nunca el identificador.
- **R22.** Los atributos de contrato que determinan el coste se guardan con fecha de vigencia. El caso indica cuáles son.

### Tiempo

- **R23.** El caso define, para cada formato, si el período de facturación incluye sus dos extremos, y los días del período se calculan con esa convención. Cada línea hereda el período de la factura, salvo que el documento indique otro.
- **R24.** Hay una tabla calendario con un registro por día.
- **R25.** Prorrateo:
  - Las líneas con imputación `periodo` se reparten por días; las `puntual` van enteras a la fecha de emisión.
  - El reparto se hace en céntimos y asigna los restos de forma que la suma de los días (y de los meses) de una línea sea exactamente su importe.
  - Las mediciones se prorratean igual.
- **R26.** Cobertura:
  - Por contrato y mes: días cubiertos por facturas sobre días esperados. Los días esperados son todos los días del mes, salvo que el contrato tenga registrada una fecha de alta o de baja; en ese caso se cuentan solo los días dentro de ese rango.
  - Un contrato cuenta desde el mes de su primera factura hasta el mes de su baja o, si no tiene baja, hasta el mes en curso.
  - Las líneas puntuales no cuentan para la cobertura.
  - El mes de una categoría está completo solo si todos los contratos que cuentan ese mes tienen cobertura total. Los meses incompletos se marcan, no se excluyen.
- **R27.** Rectificativas: la factura guarda su tipo (ordinaria, rectificativa por sustitución, rectificativa por diferencias o abono) y la referencia a la factura que corrige. Una vista de facturas vigentes excluye las sustituidas. Los ejemplos son todos ordinarios, pero el modelo tiene que soportar los demás tipos.
- **R28.** Si dos facturas ordinarias del mismo contrato tienen períodos que se solapan, se rechaza la segunda, porque el gasto se contaría dos veces. Los huecos entre facturas no se rechazan: se ven en la cobertura.

### Diccionario

- **R29.** La correspondencia alias → concepto → (categoría, tipo de cargo, imputación por defecto) se versiona en archivos de semillas y se carga en tablas de la base, donde se hace cumplir. Desde la base se genera `docs/diccionario.md`: para cada categoría, qué concepto va a qué tipo de cargo. Es un mapa, sin justificaciones.
- **R30.** Los alias se comparan normalizados (minúsculas, sin tildes, espacios colapsados). Si un texto no tiene alias, la factura se rechaza con ese texto en el motivo. Nunca se descarta en silencio ni se asigna a un concepto genérico del tipo "otros".
- **R31.** Las partes variables de un texto (fechas, nombres comerciales de productos, umbrales de tramos) no generan conceptos nuevos. El caso indica dónde aparecen.

### Lectura y control

- **R32.** El dashboard lee solo vistas, nunca tablas. Las vistas dan una semántica única: "importe" significa lo mismo en todas las categorías.
- **R33.** En cada carga, antes de confirmar la transacción, se verifican estos invariantes:
  - la suma de las líneas es igual al total de la factura;
  - cantidad × precio ≈ importe;
  - base × tipo ≈ cuota;
  - la suma del prorrateo es igual al importe;
  - cada concepto es coherente con la categoría de su contrato;
  - no hay solapes;
  - `PRAGMA foreign_key_check` no devuelve nada.

  Cada tolerancia es explícita y está documentada. Si un invariante falla, se revierte la carga de esa factura.
- **R34.** Las validaciones usan excepciones explícitas, nunca la sentencia `assert` de Python (desaparece al ejecutar con `python -O`).

### Calidad del diseño

- **R35.** Normalización: la capa cruda está en tercera forma normal. Cada dato vive en un solo lugar y no hay dependencias transitivas (por ejemplo, la unidad de una magnitud no se repite como texto libre en cada fila). Cualquier desnormalización se hace en las vistas o queda justificada en el diseño.
- **R36.** Modelo dimensional en la capa de lectura: las vistas se organizan como hechos (gasto, consumo, cobertura) y dimensiones (fecha, categoría, tipo de cargo, concepto, contrato, proveedor), cada una con su grano declarado.
- **R37.** Claves y nombres: cada tabla tiene una clave primaria sustituta entera, y las entidades que tienen una clave natural la declaran con `UNIQUE`. Hay una convención de nombres documentada para tablas, columnas, claves primarias y foráneas, índices y vistas, y se aplica sin excepciones.
- **R38.** Índices en todas las claves foráneas y en las columnas por las que filtran o agrupan las consultas de referencia. Se verifica con `EXPLAIN QUERY PLAN`; los recorridos completos que queden están justificados.
- **R39.** Concurrencia: modo WAL y `busy_timeout`, para que el dashboard pueda leer mientras la carga escribe. Solo la carga escribe; los demás consumidores, incluido el dashboard, usan una conexión de solo lectura.
- **R40.** La versión del esquema se guarda en `PRAGMA user_version`. Al conectar se verifica que coincide con la del código; si no coincide, se avisa que hay que reconstruir la base (R19).
- **R41.** Datos manuales: lo que la persona usuaria carga a mano (alias de contratos, fechas de alta y de baja) se modifica con un comando que lo escribe en la base y, a la vez, en un archivo local fuera de git (`datos/ajustes_manuales.json`). La reconstrucción de la base (R19) lo vuelve a aplicar, así que nada se pierde.
- **R42.** Moneda explícita: cada factura guarda su moneda (código ISO 4217). El caso define cuál se admite, y la base rechaza cualquier otra.
- **R43.** Copias de seguridad en la carpeta que define el caso, después de cada carga que cambió algo. Incluyen los PDFs procesados, los datos manuales y una instantánea consistente de la base, hecha con la API de backup de SQLite o con `VACUUM INTO` (nunca copiando el archivo en uso). Las instantáneas rotan: se conservan las últimas N. La restauración está documentada y probada.

## Revisión técnica independiente

En los bloques 1 y 2, antes del punto de control, el agente lanza un **subagente revisor** con contexto limpio. Como no participó del diseño, no lo defiende.

- **Qué recibe:** `tarea.md`, `requisitos.md`, el archivo de caso y lo producido en el bloque. En el bloque 1, `docs/diseno.md`; en el bloque 2, además, el esquema, el código, las semillas y el resultado de los tests. No recibe la conversación ni las justificaciones del agente que diseñó.
- **Rol:** un ingeniero de datos con experiencia que revisa el diseño antes de aprobarlo para producción. Busca problemas reales, con escenarios de falla concretos, y también exceso de complejidad: piezas que ningún requisito pide. No se ocupa de preferencias de estilo.
- **Salida:** `docs/revision_bloque_N.md`, con tres partes:
  1. Veredicto: apto, apto con cambios o no apto.
  2. Cumplimiento: una tabla de R1 a R43, cada uno marcado como "cumple", "parcial" o "no cumple", con la evidencia (tabla, columna, vista o test).
  3. Hallazgos. Cada uno lleva un identificador, su severidad (alta, media o baja), el requisito afectado, qué está mal (con referencia exacta), un escenario de falla concreto y la acción propuesta.
- **Resolución:**
  - El agente corrige todos los hallazgos de severidad alta y media, y corrige o justifica los de severidad baja.
  - En el mismo archivo agrega una sección "Resolución" que dice qué hizo con cada hallazgo.
  - Si hubo hallazgos de severidad alta, vuelve a lanzar el revisor una vez sobre la versión corregida. Son dos rondas como máximo: lo que siga abierto se presenta en el punto de control.

