# Revisión técnica del bloque 2

Revisé `tarea.md`, `caso_hogar.md`, `bloques/02_implementacion_bd.md` y `docs/diseno.md`, incluidos los cambios B1–B5 de la sección 1.1. También revisé lo producido en el bloque: `esquema.sql`, los módulos de `bd/`, `carga/traduccion.py`, las semillas, las consultas C1–C7, `docs/diccionario.md`, los tests y su resultado.

Verifiqué ejecutando, no solo leyendo:

- **Tests del proyecto.** Corrí la suite: pasan los 161, en unos 4 s, con SQLite 3.49.1. Corrí también `tests/rendimiento.py`.
- **Escenarios propios.** Escribí 13 scripts que construyen bases propias desde las semillas e insertan facturas con los helpers de `tests/datos_prueba.py`. Cubren:
  - integridad, con valores límite en los `CHECK`;
  - rectificativas y abonos en distinto orden, y solapes;
  - cobertura: cambio de año, alta, baja, mes en curso y dos contratos de una categoría;
  - prorrateo de 305 facturas aleatorias, con importes negativos y de un céntimo;
  - mediciones con y sin franja;
  - traducción de textos plausibles que no están en los ejemplos;
  - conexión de lectura y WAL, y versión del esquema;
  - planes de C1–C7 y premisas del respaldo.
- **Correcciones propuestas.** Probé en una copia de la base que funcionan.

No modifiqué ningún otro archivo del proyecto. Los scripts quedaron en `%TEMP%\claude\revision_b2\`: `e01_…` a `e13_…` y `comun.py`. Las bases están en `bases/` y la medición de rendimiento en `rendimiento.txt`.

## 1. Veredicto

**Apto con cambios.**

El núcleo está bien resuelto, y lo comprobé ejecutando:

- **Esquema.** Rechaza lo que dice rechazar. Los `CHECK` de fecha con `IS` ya no dejan pasar NULL, y los `CHECK` de las columnas nulables están protegidos.
- **Prorrateo.** Es exacto por línea y por mes, incluso con importes negativos y de un céntimo. El desvío mensual queda por debajo de 1 céntimo por contrato y de 2 por línea, como dice el diseño.
- **Cobertura.** Es correcta al cruzar el año y con alta, baja y dos contratos de una categoría.
- **Solapes.** El control resuelve sustituciones, cadenas de sustituciones y abonos, lleguen en el orden que lleguen.
- **Conexión.** La de lectura no bloquea a la escritura ni queda bloqueada por ella.
- **Consultas.** C1–C7 responden las preguntas del dashboard con los valores del caso.
- **Tests.** Prueban lo que dicen, y ninguno pasa por vacío: el de índices revisa las 24 claves foráneas y los cuerpos de los triggers.
- **Cambios del bloque.** B1–B5 son correctos.
- **Complejidad.** No encontré piezas que sobren: cada tabla, trigger e índice responde a un requisito o a un desvío aprobado.

Hay un hallazgo de severidad alta, que hay que corregir antes de aprobar. El modelo dice soportar abonos (R27, revisión H4 del bloque 1), pero con un abono y su refacturación el consumo se suma dos o tres veces y el precio efectivo queda en la mitad o en un tercio (H1).

Los demás hallazgos son acotados:

- dos de severidad media: los comodines del agua aceptan cargos nuevos sin avisar (H2), y la versión del esquema no detecta un cambio sin incremento ni una construcción a medias (H3);
- tres de severidad baja (H4–H6).

## 2. Cumplimiento

Algunos requisitos se completan en bloques posteriores. Esos van como "parcial (bloque N)": la evidencia dice qué está en el bloque 2 y qué falta.

| R | Estado | Evidencia |
|---|---|---|
| R1 | desvío aprobado (D2, D3) | `factura` y `linea` (una fila por línea, con el `texto` literal). Gasto mensual, prorrateo y cobertura existen solo como vistas. El canon y el alcantarillado se guardan como subtotal. |
| R2 | desvío aprobado (D1) | `linea.contrato_id`, `concepto_id`, `categoria_id` (en la línea, no en la cabecera), `importe_centimos`, `imputacion`, `fecha_inicio` y `fecha_fin`. No guarda cantidad, unidad ni precio. La factura de Digi, con dos categorías: `test_c3_y_c4_fibra_y_movil_por_separado`. |
| R3 | desvío aprobado (D5) | `medicion` guarda `franja_id` (nulo: sin desglose), `tipo_lectura` y la lectura de cierre. `tg_medicion_bi_franja` impide mezclar total y desglose. El consumo de abonos y rectificativas por diferencias no tiene regla: H1. |
| R4 | desvío aprobado (D1) | No se guardan base imponible ni tipo. |
| R5 | cumple | `linea.es_derivada`. I8 (`_i8_derivadas`) compara con `extraccion_json.totales_repartidos`: `test_i8_*`. El reparto lo hace el parser (bloque 3). |
| R6 | parcial | Las reglas se declaran en el esquema: `STRICT`, `NOT NULL`, `CHECK`, `UNIQUE`, claves foráneas compuestas y triggers. Quedan abiertas escrituras que descuadran una factura (H4) y algunas reglas de dominio (H5). |
| R7 | cumple | Todas las tablas son `STRICT`. Los `CHECK` de fecha (`IS date()`, B1) rechazan texto, entero, espacio final y fechas inexistentes: `test_rechaza_fecha_*` y `e02`. `ck_*_periodo` controla los períodos. `ON DELETE CASCADE` hacia `linea`, `medicion` y `valor_atributo`: `test_borrar_una_factura_…`. |
| R8 | cumple | `conectar()` es la única vía, también para `construir` y `diccionario`, y activa `foreign_keys` en los tres modos: `test_claves_foraneas_activas*`. |
| R9 | cumple | `fk_linea_contrato` y `fk_linea_concepto` comparten `categoria_id`: `test_rechaza_linea_con_concepto_de_otra_categoria` y `test_i5_e_i7_*`. |
| R10 | cumple | El significado de cada columna nulable está en `diseno.md` §3, y los campos obligatorios son `NOT NULL`. Que un campo no encontrado haga fallar la extracción es del bloque 3. |
| R11 | desvío aprobado (D1) | Importes `INTEGER` en céntimos, con `STRICT`: `test_rechaza_importe_con_decimales_o_en_texto`. Cantidades en milésimas y factor en texto exacto. Precios y tipos no se guardan (D1). |
| R12 | desvío aprobado (D1) | `importe_centimos` es el impreso, y nada lo recalcula. Sin validación de cantidad × precio. |
| R13 | cumple | `magnitud_categoria` define la unidad canónica y la del contador por categoría. `medicion` guarda `cantidad_contador_milesimas` y `factor_conversion`, y `tg_medicion_bi_conversion` los exige cuando las unidades difieren. La base acepta un factor 0: H5. |
| R14 | cumple | `carga` tiene `sha256` único, nombre, formato, versión, fecha y hora, estado, etapa, motivo y `extraccion_json`, con `CHECK` de coherencia: `test_coherencia_de_una_carga_rechazada`. El registro es del bloque 4. |
| R15 | cumple | `factura.carga_id` es `NOT NULL` y único, y `tg_carga_bu_cargada` impide modificar una carga con factura. Una factura puede colgar de una carga rechazada: H5. |
| R16 | cumple | `uq_factura_proveedor_numero` y `uq_linea_factura_posicion`: `test_rechaza_factura_duplicada`. |
| R17 | parcial (bloque 4) | El hash es único, hay triggers de inmutabilidad y los ids se obtienen con `RETURNING`. No hay `lastrowid` ni `INSERT OR REPLACE` en `src/`. Reemplazar una factura es del bloque 4. La inmutabilidad no cubre `DELETE` ni `REPLACE`: H4. |
| R18 | parcial (bloque 4) | La base permite cargar todo o nada: `test_tras_un_rechazo_no_queda_nada_parcial`. La transacción de la carga es del bloque 4. |
| R19 | parcial (bloque 4) | `construir()` es determinista, con volcado completo: `test_construir_dos_veces_da_el_mismo_resultado`. Las semillas llevan huella. La reconstrucción desde `procesadas/` es del bloque 4, y D7 sigue pendiente. |
| R20 | cumple | `uq_proveedor_identificador_fiscal` y `ck_proveedor_identificador_fiscal` (`[A-Z0-9]`), con la semilla `proveedor.csv`. |
| R21 | parcial (bloque 4) | `uq_contrato_proveedor_identificador_externo` y `uq_contrato_alias`. `v_dim_contrato` no expone el identificador: `test_dimension_contrato_sin_identificador_externo`. El registro automático y el alias por defecto son del bloque 4 (D7). |
| R22 | cumple | `atributo_contrato`, `valor_atributo` por factura y `v_dim_contrato_atributo`, que arma los tramos de vigencia: `test_atributos_con_vigencia`. |
| R23 | cumple | `factura` y `linea` guardan períodos con los dos extremos incluidos, y las vistas calculan días = fin − inicio + 1. La convención de cada formato es del parser (D10). |
| R24 | cumple | `calendario`, de 2000 a 2099, con `CHECK` de coherencia: `test_calendario_un_registro_por_dia`. |
| R25 | cumple | `v_prorrateo_linea` y `v_prorrateo_medicion` (prorrateo jerárquico, D6); las líneas puntuales van a la fecha de emisión. Los controles del caso coinciden: `test_reparto_mensual_…`. Con 305 facturas aleatorias, con negativos y céntimos, la suma es exacta y el desvío mensual por contrato queda por debajo de 1 céntimo (`e07`). |
| R26 | cumple | `v_hecho_cobertura_contrato_mensual` y `v_hecho_cobertura_categoria_mensual`, con los controles del caso: `test_cobertura_*`. El alta la cubre `test_cobertura_respeta_alta_y_baja`; yo probé cambio de año, baja y dos contratos (`e06`). Baja futura: H6. Factura anulada por un abono: H1. |
| R27 | parcial | `factura.tipo`, `numero_factura_corregida`, `v_factura_vigente` y el índice único de sustituciones. Sustituciones y cadenas funcionan en cualquier orden (`e09`). El consumo de abonos y rectificativas por diferencias no tiene regla: H1. |
| R28 | cumple | `tg_linea_bi_solape` e I6 cubren ordinarias, sustitución que alarga el período, abono con refacturación y facturas contiguas: `test_rechaza_solape_*`, `test_acepta_facturas_contiguas` y `e09`. |
| R29 | cumple | Semillas CSV → `concepto` y `alias_concepto`, con clave foránea compuesta a la categoría; huella en `construccion.huella_semillas`. `docs/diccionario.md` se genera desde la base y se compara con el caso: `test_diccionario_*`. |
| R30 | parcial | `normalizar()` y `traducir()` rechazan un texto sin alias o ambiguo, con el texto en el motivo: `test_texto_*`. Los comodines finales del agua traducen cargos nuevos sin avisar: H2. |
| R31 | cumple | Comodines para tramos, IVA, nombres comerciales y el período de Digi: `test_partes_variables_no_generan_conceptos_nuevos`. |
| R32 | cumple | Capa de lectura `v_*`; `importe_centimos` significa lo mismo en todas: `test_importe_con_la_misma_semantica_…`. Que el dashboard lea solo vistas depende del dashboard (fuera de alcance). |
| R33 | desvío aprobado (D1) | `verificar()` implementa I1 e I4–I8, con tolerancia 0 y un test cada uno. I2 e I3 no aplican (D1). |
| R34 | cumple | `test_sin_assert` sobre `src/`. Las validaciones lanzan `ErrorBase`, `ErrorSemillas`, `ErrorTraduccion` o `ValueError`. |
| R35 | cumple | Las desnormalizaciones están justificadas en `diseno.md` §5: `categoria_id` en `linea`, `medicion`, `valor_atributo` y `alias_concepto`, protegida por claves foráneas compuestas. La unidad vive solo en `magnitud_categoria`. |
| R36 | cumple | Dimensiones `v_dim_*` (fecha, categoría, tipo de cargo, concepto, proveedor, contrato y atributo de contrato) y hechos `v_hecho_*` (gasto, consumo y cobertura), con su grano en `diseno.md` §7. |
| R37 | cumple | Todas las tablas tienen clave sustituta entera, y las claves naturales se declaran con `UNIQUE`. Observación sin consecuencias: `ux_medicion_factura_contrato_magnitud_franja` omite el `_id` y `ux_factura_…_sustitucion` agrega un sufijo, a diferencia de los `ix_*`. |
| R38 | cumple | Cada clave foránea tiene su índice: `test_cada_clave_foranea_tiene_un_indice`. C1–C7 y los invariantes solo recorren enteras `linea` y `medicion`: `test_indices.py`, confirmado con `EXPLAIN QUERY PLAN` (`e05`). Los triggers buscan por índice. En mi medición, C4 y C5 tardan cerca de 1,0 s con 10 años (el diseño dice 0,44–0,47 s): sigue siendo aceptable. |
| R39 | cumple | WAL, `busy_timeout = 5000` y lectura con `mode=ro`: `test_modo_wal_y_lectura_durante_una_escritura`. Observación: la conexión de lectura puede escribir con un `ATTACH` del mismo archivo (`e04`), y `PRAGMA query_only = ON` lo cerraría. No lo cuento como hallazgo, porque hay que hacerlo a propósito. |
| R40 | parcial | `user_version` está en `esquema.sql` y `conectar()` lo compara: `test_detecta_otra_version_del_esquema`. No detecta un cambio de esquema sin incremento ni una construcción a medias: H3. |
| R41 | parcial (bloque 4) | `leer_ajustes()` y `aplicar_ajustes()` (B4): `test_base_reconstruida_conserva_los_datos_manuales`. El comando que escribe en la base y en el archivo es del bloque 4. |
| R42 | cumple | `moneda` solo tiene `EUR`, `factura.moneda_id` es una clave foránea `NOT NULL` y hay un `CHECK` de formato (`ck_moneda_codigo`): `test_rechaza_moneda_no_admitida`. |
| R43 | parcial (bloque 4) | No hay nada implementado todavía. Verifiqué las premisas del diseño: `VACUUM INTO` desde la conexión de lectura y el reemplazo con la API de backup con un lector abierto funcionan (`e10`). |

## 3. Hallazgos

### H1. El consumo de abonos y rectificativas por diferencias se suma sin regla: un abono con su refacturación duplica el consumo y parte el precio efectivo

- **Severidad:** alta.
- **Requisito:** R27 (también R3, R25 y R26).
- **Qué está mal:**
  - `medicion` (`esquema.sql`, línea 269) no tiene ninguna regla que dependa de `factura.tipo`. El contrato entre parser y carga (`diseno.md` §11.5) no dice qué significa una medición en un abono o en una rectificativa por diferencias.
  - `v_factura_vigente` (línea 457) deja vigentes el abono y la factura que anula, como pide el diseño para el gasto (§7.2). `v_prorrateo_medicion` y `v_hecho_consumo_diario` (líneas 547 y 599) suman las mediciones de las dos.
  - Para la cobertura, la factura anulada sigue cubriendo sus días (`periodo_cubierto`, línea 624).
  - La revisión H4 del bloque 1 (abono y refacturación) se comprobó solo sobre el gasto: `test_abono_y_refacturacion_del_mismo_periodo` no mira el consumo.
- **Escenario de falla:** reproducido en `e01` y `e12`. Se cargan tres facturas: la de gas del ejemplo (344 kWh, lectura estimada), un abono que la anula, con los importes negativos, y la refacturación con la lectura real.
  - El gasto queda bien: KJ,ZJ.
  - El consumo de gas queda en 688 kWh si el abono no trae mediciones, y en 1.032 kWh si las trae como están impresas.
  - C5 da un precio efectivo de K,XJQQ o Q,QXKJ €/kWh en lugar de J,XKXZ, y C6 muestra los mismos días como estimados y como reales.
  - El consumo solo cuadra si el parser emite cantidades negativas, y nada lo define ni lo exige. La base también acepta un consumo negativo en una factura ordinaria (H5).
  - Antes de que llegue la refacturación, mayo aparece completo con gasto 0 y 187 kWh: precio efectivo 0. La cobertura no avisa que falta una factura.

  Anular y refacturar es habitual cuando se corrige una lectura estimada, y la lectura del ejemplo de gas es estimada.
- **Acción propuesta:**
  1. Definir en §11.5 la convención. En un abono, las mediciones llevan el signo contrario al de la factura que anula, como los importes. En una rectificativa por diferencias, solo llevan la diferencia.
  2. Hacerla cumplir en la base con un trigger `BEFORE INSERT ON medicion` según `factura.tipo`: cantidad ≥ 0 en ordinarias y sustituciones, y ≤ 0 en abonos. Funciona, lo probé en `e13`. La alternativa es prohibir mediciones en abonos y en rectificativas por diferencias, y excluir del consumo las de una factura anulada.
  3. Decidir si una factura anulada por un abono de su mismo total deja de cubrir sus días, para que la cobertura avise que falta la refacturación, y documentarlo en §9.
  4. Extender el test de H4 al consumo, a C5 y a C6.

### H2. Los alias del agua con comodín final traducen cargos nuevos sin avisar

- **Severidad:** media.
- **Requisito:** R30 (también R31).
- **Qué está mal:**
  - `semillas/alias_concepto.csv`, líneas 4, 6, 7 y 8: `canon del agua*`, `tasa de alcantarillado*`, `tasa de recogida residuos municipales*` y `tasa metropolitana tratamiento residuos municipales*`.
  - El `*` final está para absorber la nota "(*)" y el organismo entre paréntesis, pero acepta cualquier texto que empiece con esas palabras.
  - El diseño resolvió este mismo riesgo para Digi con las secciones (revisión H6), pero no lo trató en el agua: §12.4 no lista estas partes como variables.
- **Escenario de falla:** reproducido en `e08`.
  - "Canon del agua - regularización 2025" se traduce a `canon_agua`, y "Tasa de alcantarillado - abono ejercicio anterior" a `alcantarillado`, los dos con imputación `periodo`.
  - Esas líneas deberían rechazarse, para que el plan B proponga concepto e imputación: el caso dice que una regularización normalmente es `puntual`. En cambio, el importe se reparte en los 60 días de la factura en curso.
  - El total cuadra, pero el reparto mensual queda mal y nadie se entera.

  El riesgo equivalente de Digi, un cargo nuevo dentro de PRODUCTOS con un período entre paréntesis, ya está documentado en §12.4 como riesgo residual. Lo confirmé y no lo cuento aparte.
- **Acción propuesta:** usar el rótulo impreso completo y dejar comodines solo en las partes que el caso reconoce como variables. Por ejemplo:
  - `canon del agua([*])`, con el `(*)` literal;
  - `tasa de recogida residuos municipales generados en los domicilios`;
  - `tasa metropolitana tratamiento residuos municipales (t.m.t.r.)`;
  - el rótulo completo del alcantarillado, con su organismo.

  Agregar a `test_texto_sin_alias_se_rechaza_…` un caso "<rótulo> - regularización" por cada concepto del agua.

### H3. La versión del esquema no garantiza que la base corresponda al código

- **Severidad:** media.
- **Requisito:** R40 (también R19).
- **Qué está mal:**
  - **Construcción a medias.** `PRAGMA user_version = 1` es la primera sentencia de `esquema.sql` (línea 4). `construir()` la ejecuta con `executescript` (`construir.py`, línea 105) antes de crear las tablas, y fuera de la transacción que carga las semillas, el calendario y `construccion` (líneas 106–114). Si la construcción se interrumpe (el proceso se termina o se corta la luz), queda una base que `conectar()` acepta, y `construir()` se niega a reemplazarla porque el archivo ya existe.
  - **Cambio sin incremento.** El número se incrementa a mano, y ningún test ni mecanismo detecta un cambio de `esquema.sql` sin incremento. La lógica del dashboard (prorrateo, cobertura) vive en vistas guardadas en la base, y los tests no lo notan porque siempre construyen desde cero.
- **Escenario de falla:** reproducido en `e04` y `e10`.
  - Una base con el esquema y sin semillas abre en modo escritura con `user_version` 1, sin proveedores y sin fila en `construccion`.
  - El bloque 4 corrige `v_hecho_cobertura_categoria_mensual` y no sube el número. La base en uso conserva la vista vieja, `conectar()` no avisa y el dashboard sigue mostrando la completitud con la lógica vieja hasta que algo fuerce una reconstrucción.
- **Acción propuesta:**
  - Guardar en `construccion` la huella de `esquema.sql` junto a la de las semillas, o incluir el archivo en `huella_semillas()`, y compararla en `conectar()`.
  - Crear el esquema, cargar las semillas y fijar `user_version` en una sola transacción. En SQLite, el DDL y `user_version` respetan el `ROLLBACK` (verificado).

  Así, una construcción a medias queda sin fila y falla, y un cambio sin incremento se detecta. Si el esquema entra en la huella, además la carga reconstruye sola (§13.2). Como mínimo, un test que asocie cada versión a la huella de `esquema.sql`.

### H4. Escrituras fuera de la carga que descuadran una factura sin que nada lo detecte

- **Severidad:** baja.
- **Requisito:** R6 (también R17 y R33).
- **Qué está mal:**
  - Los triggers de inmutabilidad (`esquema.sql`, líneas 406–413) solo cubren `UPDATE`. Se aceptan un `DELETE` de una línea, una medición o un valor de atributo sueltos, y un `REPLACE INTO linea`.
  - Los invariantes solo se verifican en la carga, y solo para la factura que se está cargando.
  - Ninguna regla limita los `UPDATE` de `contrato` a los datos manuales, como dice `diseno.md` (línea 305).
  - Ninguna regla impide los cambios directos en el diccionario, y la huella no los ve: compara los archivos, no la base.

  `diseno.md` (línea 49) afirma que "ninguna regla puede saltearse modificando una fila después de insertarla".
- **Escenario de falla:** reproducido en `e02` y `e03`.
  - Una corrección manual con `DELETE FROM linea` sobre la TMTR deja el agua en QQ,JJ frente a los ZX,KK impresos. Si después un `REPLACE` cambia la cuota (QX,XX) por K,XJ, queda en XX,KK.
  - `verificar()` lo detectaría (I1), pero nadie la vuelve a llamar después de la carga.
  - La base también acepta `UPDATE contrato SET identificador_externo = …` y `UPDATE concepto SET tipo_cargo_id = …`. El segundo reclasifica en silencio todas las líneas históricas.
- **Acción propuesta:**
  - Lo más simple: verificar todas las facturas (I1 se resuelve con un solo `GROUP BY`) desde el comando `estado` y el respaldo (bloque 4), y corregir la frase del diseño.
  - Para cerrarlo en la base, estos triggers dejan pasar el `ON DELETE CASCADE` (probado en `e13`):
    - `BEFORE DELETE ON linea WHEN EXISTS (la factura de OLD)`;
    - `BEFORE INSERT ON linea WHEN EXISTS (otra línea con la misma factura y posición)`;
    - los equivalentes para `medicion` y `valor_atributo`;
    - un `BEFORE UPDATE ON contrato` que solo admita cambios en `alias`, `fecha_alta` y `fecha_baja`.

### H5. Reglas de dominio que el esquema no declara

- **Severidad:** baja.
- **Requisito:** R6 (también R13 y R15).
- **Qué está mal y escenario de falla:** reproducido en `e02` y `e03`. La base acepta:
  - una `factura` cuya `carga` está `rechazada`, porque ninguna regla relaciona `factura.carga_id` con `carga.estado`. El dashboard mostraría números de un PDF que figura en `pendientes/`;
  - una medición de gas con franja `punta` (`medicion.franja_id`, línea 275), porque nada dice qué categorías desglosan por franja. C7 la mostraría;
  - un `factor_conversion` igual a `'0'` (`ck_medicion_factor_conversion`, línea 287), con lo que 344 kWh quedan registrados como 30 m³ × 0;
  - un consumo negativo en una factura ordinaria (ver H1);
  - un `numero_factura_corregida` vacío o con espacios (`ck_factura_numero_factura_corregida`, línea 233), a diferencia de `numero`, que exige `trim`. La rectificativa no encontraría su original. En una sustitución, el control de solapes lo haría visible; en un abono, el abono no se vincula con su original, y la refacturación se rechaza por solape sin que el motivo mencione la referencia mal escrita.
- **Acción propuesta:**
  - un trigger `BEFORE INSERT ON factura` que exija `carga.estado = 'cargada'` (probado en `e13`);
  - agregar al `CHECK` del factor la condición `CAST(factor_conversion AS REAL) > 0`;
  - exigir `numero_factura_corregida = trim(numero_factura_corregida) AND numero_factura_corregida <> ''`;
  - la regla de signo de H1;
  - para las franjas, una marca por categoría y magnitud en `magnitud_categoria.csv` con su trigger, o documentar que las controla el parser.

### H6. Una baja futura agrega meses futuros, vacíos e incompletos, a la cobertura y a C2

- **Severidad:** baja.
- **Requisito:** R26.
- **Qué está mal:** en `v_hecho_cobertura_contrato_mensual` (`esquema.sql`, línea 641), el último mes que cuenta es el de `coalesce(c.fecha_baja, hoy)`. Si la baja es posterior al mes en curso, cuentan meses que todavía no pasaron.
- **Escenario de falla:** reproducido en `e06`. El 2026-10-02 se registra una baja programada para el 2027-01-04. C2, consultada hasta `9999-12` ("todo el histórico"), devuelve 2026-11, 2026-12 y 2027-01 con importe 0 y `categoria_completa = 0`. El gráfico de evolución mostraría tres meses futuros vacíos, marcados como incompletos.
- **Acción propuesta:**
  - Tomar como límite `min(coalesce(c.fecha_baja, date('now', 'localtime')), date('now', 'localtime'))`.
  - Agregar el caso a `test_cobertura_respeta_alta_y_baja`.
  - Anotar la interpretación: R26 dice "hasta el mes de su baja" pensando en una baja ya ocurrida.

---

## 4. Resolución

La agregó el agente que implementó el bloque. Cada corrección tiene un test y está documentada en `docs/diseno.md`. Después de las correcciones pasan los 187 tests, y los controles del caso siguen coincidiendo.

| Id | Severidad | Qué se hizo | Dónde |
|---|---|---|---|
| H1 | alta | **Corregido.** Un abono es la factura que anula con el signo cambiado, también en el consumo: el parser emite sus cantidades en negativo, como los importes, y una rectificativa por diferencias informa solo la diferencia. La base lo exige con `tg_medicion_bi_signo`: nada negativo en ordinarias y sustituciones, nada positivo en abonos. La cobertura usa ahora la misma definición que el control de solapes: cubren días las ordinarias y las sustituciones que ninguna sustitución ni abono corrige. Por eso una factura anulada deja de cubrir sus días hasta que llega la refacturación. Probado con el escenario del hallazgo. Con el abono solo, el gas queda en 0, el consumo estimado en 0 y ningún mes completo. Con la refacturación, el gas vuelve a KJ,ZJ, el consumo queda en 344 kWh reales y 0 estimados, y mayo vuelve a estar completo. | `esquema.sql` (trigger y `v_hecho_cobertura_contrato_mensual`); `diseno.md` §3.3, §3.4, §9 y §11.5; `test_abono_y_refacturacion_no_duplican_gasto_ni_consumo` y tests de signo en `test_integridad.py` |
| H2 | media | **Corregido.** Los alias del agua usan el rótulo impreso completo, tomado de `agua.pdf`. Los comodines quedan solo en los umbrales de los tramos (`tramo hasta * m3`, `tramo de * a * m3`) y en el tipo de IVA. Los seis textos "<rótulo> - regularización" del hallazgo se rechazan. | `semillas/alias_concepto.csv`; `diseno.md` §12.2 y §12.4; `test_texto_sin_alias_se_rechaza_…` |
| H3 | media | **Corregido.** `construir()` crea el esquema (con `user_version`), carga las semillas y el calendario y registra la huella en una sola transacción. Una construcción interrumpida deja el archivo vacío y con la versión 0, y `conectar()` lo rechaza (`test_una_construccion_interrumpida_no_deja_una_base_valida`). Para un cambio de esquema sin incremento, `test_cada_cambio_del_esquema_sube_su_version` guarda la huella de `esquema.sql` de cada versión, así que no pasa los tests hasta que se sube la versión. Se eligió el test y no una huella del esquema en la base, porque R40 ya pide que la versión sea la señal, y con el test esa señal es confiable. | `construir.py`; `test_conexion.py`; `diseno.md` §3.2 y §14.1 |
| H4 | baja | **Corregido en parte; el resto, justificado.** Corregido: `tg_linea_bd_suelta`, `tg_medicion_bd_suelta` y `tg_valor_atributo_bd_suelta` rechazan borrar una fila cuya factura sigue en la base, y la cascada al borrar la factura sigue funcionando. `tg_contrato_bu_identidad` deja cambiar de un contrato solo el alias y las fechas. Justificado: `INSERT OR REPLACE` sigue abierto, porque cerrarlo pedía un trigger más por tabla, y R17 ya lo prohíbe en el código. También quedan abiertos los cambios directos en el diccionario, que se reconstruye desde las semillas versionadas. La frase de `diseno.md` §1 se corrigió. | `esquema.sql`; `test_las_filas_de_una_factura_no_se_borran_sueltas`; `test_de_un_contrato_solo_cambian_los_datos_manuales` |
| H5 | baja | **Corregido, salvo las franjas.** `tg_factura_bi_carga` exige que la carga esté `cargada`. El factor de conversión tiene que ser mayor que 0. `numero_factura_corregida` no puede estar vacío ni tener espacios en los extremos. El consumo negativo en una ordinaria se resolvió con H1. **Justificado:** qué categorías desglosan por franja queda a cargo del parser (bloque 3), porque declararlo en la base pedía una columna nueva en `magnitud_categoria` y otro trigger, sin ningún caso que lo justifique hoy. Está documentado en §3.4. | `esquema.sql`; `test_una_factura_sale_de_una_carga_cargada`; `test_rechaza_factor_…`; `test_rechaza_numero_de_factura_corregida_…` |
| H6 | baja | **Corregido.** El último mes que cuenta es el de la baja, sin pasar del mes en curso. | `v_hecho_cobertura_contrato_mensual`; `diseno.md` §9; `test_cobertura_no_pasa_del_mes_en_curso_con_una_baja_futura` |
| Observación (R39) | — | **Incorporada.** La conexión de lectura agrega `PRAGMA query_only = ON`: tampoco se puede escribir con un `ATTACH` del mismo archivo. | `conexion.py`; `test_lectura_no_puede_escribir` |
| Observación (R38) | — | **Documentada.** Los tiempos varían entre corridas. En `diseno.md` §6.3 quedaron como rango (C1–C5 entre 0,45 y 0,66 s, y cerca de 1 s en la medición del revisor). | `diseno.md` §6.3 |
| Observación (R37) | — | **Sin cambios.** Los nombres de dos índices únicos no siguen el mismo patrón que los `ix_*`. El revisor la marcó sin consecuencias. | — |

Como hubo un hallazgo de severidad alta, se lanza una segunda ronda de revisión sobre la versión corregida.

---

## 5. Segunda ronda

Revisé la resolución de la sección 4 sobre la versión corregida: `esquema.sql`, `bd/*.py`, `carga/traduccion.py`, las semillas, las consultas, `docs/diccionario.md`, `docs/diseno.md` (secciones 1, 3, 9, 11 y 13) y todos los tests. Corrí la suite (pasan los 187, en unos 6 s, con SQLite 3.49.1) y `tests/rendimiento.py`.

Verifiqué ejecutando. Escribí 10 scripts que construyen bases propias desde las semillas e insertan facturas con los helpers de `tests/datos_prueba.py`:

- `r01`: el escenario de H1, en tres órdenes, con y sin mediciones en el abono;
- `r02`: abono parcial y cobertura;
- `r03`: casos legítimos frente al trigger de signo;
- `r04`: borrado en cascada y `REPLACE`;
- `r05`: construcción con el proceso terminado a mitad de camino;
- `r06`: alias del agua;
- `r07`: H5, H6 y recorridos de los 14 triggers;
- `r08`: atributos de una factura anulada;
- `r09`: las correcciones que propongo abajo, probadas en bases propias;
- `r10`: sustituciones, cadenas y abonos en los 126 órdenes posibles.

Quedaron en `%TEMP%\claude\revision_b2_r2\`: `comun.py`, `r01_…` a `r10_…`, y las bases en `bases/`. No modifiqué ningún archivo del proyecto salvo este, al que solo le agregué esta sección.

### 5.1 Veredicto

**Apto con cambios.**

Las correcciones de la primera ronda funcionan, y no encontré hallazgos de severidad alta:

- **H1.** El escenario que lo motivó (abono con el consumo en negativo y refacturación) da gasto, consumo, C5, C6 y cobertura correctos en cualquier orden.
- **H2, H3, H5 y H6.** Resueltos; lo que quedó sin corregir en H5 está bien justificado.
- **H4.** Resuelto en parte, con una justificación razonable para su severidad.
- **Sin regresiones.** La cascada sigue funcionando con los triggers de borrado, la construcción en una transacción resiste un proceso terminado de verdad, los controles del caso siguen coincidiendo y el rendimiento no cambió.

Pero la corrección de H1 dejó dos problemas de severidad media:

- **H7.** El modelo da por hecho que todo abono anula entera la factura que corrige y trae su consumo en negativo, y nada lo garantiza. Si el abono no imprime el consumo, vuelve a duplicarse (la variante de H1 que no se probó). Si es parcial, la factura entera pierde la cobertura.
- **H9.** El trigger de signo rechaza la regularización de una lectura estimada, que es un caso legítimo.

Las dos correcciones se prueban en `r09` y en conjunto simplifican el esquema: el trigger de signo deja de hacer falta. Quedan además dos hallazgos de severidad baja (H8 y H10).

### 5.2 Verificación de la resolución

| Id | Estado | Evidencia |
|---|---|---|
| H1 | resuelto en parte | **Resuelto** (`r01`), con la factura de gas, su abono con el consumo en negativo y la refacturación con lectura real: gasto KJ,ZJ, 344 kWh reales y 0 estimados, C5 J,XKXZ €/kWh y mayo completo. Lo mismo con el abono antes de la original, y con la refacturación antes del abono (rechazada por solape y aceptada al reintentar). Un abono con consumo positivo se rechaza. **Sin resolver:** con un abono sin mediciones, el gas vuelve a 688 kWh y C5 a K,XJQQ €/kWh: es la variante "si el abono no trae mediciones" del hallazgo original, que la resolución no probó (H7). El trigger nuevo rechaza casos legítimos (H9). |
| H2 | resuelto | **Se traducen** (`r06` y `test_texto_sin_alias_…`): los 8 textos de los ejemplos, también en mayúsculas o con espacios de más. **Se rechazan:** los seis "<rótulo> - regularización" y variantes como "CANON DEL AGUA (*)", con un espacio, que irán al plan B. Es el comportamiento buscado. |
| H3 | resuelto | **Construcción interrumpida** (`r05`): terminé el proceso con `os._exit` después de escribir el calendario. Quedan la base (4 KB) y un WAL de 721 KB sin confirmar; al abrirla, `user_version` es 0, no hay tablas y `conectar()` la rechaza en los dos modos. **Determinismo:** dos construcciones dan el mismo volcado (36.670 sentencias). **Cambio sin incremento:** el test de huella normaliza CRLF, así que no depende de `core.autocrlf`. Elegir el test en lugar de una huella en la base es razonable. La salida de esa base a medio construir, en cambio, no tiene camino (H10). |
| H4 | resuelto en parte | **Corregido** (`r04`): un `DELETE` suelto se rechaza. La cascada borra líneas, mediciones y atributos en autocommit, dentro de una transacción y con las claves foráneas diferidas, y `foreign_key_check` queda vacío. `tg_contrato_bu_identidad` rechaza cambiar la identidad de un contrato. **Abierto:** `INSERT OR REPLACE` llega más lejos de lo que dice la justificación (ver la nota debajo). La justificación sigue siendo razonable para una severidad baja, porque hace falta un `REPLACE` manual y a propósito. |
| H5 | resuelto | **Se rechazan** (`r07`): una factura de una carga rechazada, los factores `0`, `0.000` y `00` (se acepta `0.0001`), y un número corregido vacío o con espacios. **Las franjas** quedan a cargo del parser, y la justificación es razonable: el parser del gas no tiene franjas que emitir. |
| H6 | resuelto | **Baja futura** (`r07`): con una baja dentro de 200 días, el último mes es el mes en curso; con una baja dentro del mes en curso, ese mes tiene 28 días esperados; con una baja pasada, la cobertura termina en la baja. **C2**, con "todo el histórico", termina en 2026-10. |
| Observación R39 | resuelto | `PRAGMA query_only` cierra la escritura por `ATTACH`: `test_lectura_no_puede_escribir`. |
| Observación R38 | resuelto | **Tiempos** (`tests/rendimiento.py`): C1–C3, alrededor de 0,5 s; C4, 0,91 s; C5, 0,85 s; los invariantes, 0,30 s. Están dentro del rango que documenta §6.3. **Triggers:** ninguno de los 14 recorre tablas (`r07`), pero `test_los_triggers_no_recorren_tablas` mira solo 4; los diez restantes, entre ellos los siete nuevos, quedan fuera del test que cita §6.3. |
| Observación R37 | sin cambios | Aceptable. Los triggers nuevos siguen la convención. |

**Nota sobre H4.** `INSERT OR REPLACE` no necesita "un trigger más por tabla" para hacer daño: borra la fila en conflicto sin disparar los triggers de borrado (SQLite solo los dispara en un `REPLACE` con `recursive_triggers`), así que también saltea los triggers nuevos. En `r04`:

- **En `linea`:** cambia la cuota del agua a K,XJ, y las líneas pasan a sumar XJ,KQ frente a un total de ZX,KK.
- **En `factura`:** con la misma carga y el mismo número, borra en cascada las líneas y la medición del gas y deja una cabecera de JJ,KJ sin líneas. El gas desaparece del dashboard sin error.
- **En `contrato`:** cambia el identificador externo, que `tg_contrato_bu_identidad` prohíbe cambiar.

Sin agregar triggers, lo que la primera ronda proponía como lo más simple, y la resolución no tomó, lo detectaría: que el comando `estado` del bloque 4 verifique I1 en todas las facturas. Conviene también precisar §1, donde dice que queda abierto `INSERT OR REPLACE`: que diga que esa vía saltea todos los triggers.

**Observación para el bloque 4** (`r10`, sin hallazgo). Con una factura, dos sustituciones encadenadas, un abono de la última y la refacturación, en algunos órdenes de llegada hacen falta hasta tres reintentos y no uno. En todos los órdenes en que todo se carga, el resultado es el mismo. El orden por fecha de emisión de §13.2 lo evita en la práctica, y el lote siguiente vuelve a reintentar.

### 5.3 Cumplimiento

| R | Estado | Evidencia |
|---|---|---|
| R3 | parcial, además del desvío aprobado D5 | Una factura ordinaria que regulariza una lectura estimada, con consumo negativo en total o en una franja, no se puede guardar: H9. |
| R26 | parcial | **Abono parcial:** la factura entera deja de cubrir sus días, en todos sus contratos y para siempre (H7). **Primera factura anulada:** sus meses dejan de contar en lugar de marcarse incompletos (H8). Con facturas ordinarias, sustituciones, cadenas y bajas futuras, la cobertura es correcta (`r01`, `r07`, `r10`) y los controles del caso coinciden. |
| R28 | parcial | Después de un abono parcial, una segunda ordinaria del mismo período se acepta y se suma: en `r02`, el móvil de julio pasa de Z,KJ a Z,XX. El control de solapes da por hecho que todo abono anula la factura entera (H7). |
| R30 | cumple | H2 resuelto: `r06` y `test_texto_sin_alias_se_rechaza_con_el_texto_en_el_motivo`. |
| R40 | cumple | H3 resuelto: `r05`, `test_una_construccion_interrumpida_no_deja_una_base_valida` y `test_cada_cambio_del_esquema_sube_su_version`. Cómo reemplazar una base con otra versión queda para el bloque 4 (H10). |

### 5.4 Hallazgos nuevos

#### H7. La base trata todo abono como anulación total, pero nada garantiza que lo sea

- **Severidad:** media.
- **Requisito:** R27 (también R26, R28, R22 y R3).
- **Qué está mal:**
  - **Definición contradictoria.** `diseno.md` §11.5 y §9 definen el abono como "la factura que anula con el signo cambiado, también en el consumo". En cambio, §3.4 (último punto de "Qué cubre y qué no el control de solapes") admite abonos parciales que "se suman". La base no exige ninguna de las dos lecturas.
  - **Cobertura y solapes.** La cobertura (`periodo_cubierto`, `esquema.sql` líneas 669–679) y el control de solapes (`tg_linea_bi_solape`, líneas 357–360 y 371–374) tratan cualquier abono como la anulación de toda la factura, en todos sus contratos.
  - **Consumo y atributos.** El consumo (`v_hecho_consumo_diario`, línea 641) y los atributos (`v_dim_contrato_atributo`, línea 513) siguen sumando la factura anulada. El consumo solo se cancela si el abono trae sus mediciones en negativo, y nada exige que las traiga.
- **Escenario de falla:** reproducido en `r01`, `r02` y `r08`.
  1. **Abono sin consumo** (`r01`, escenario 3). El abono de la factura de gas no imprime el consumo, así que no trae mediciones, y llega la refacturación con lectura real. La base acepta las dos. El gas queda en 688 kWh (344 estimados más 344 reales), C5 da K,XJQQ €/kWh en lugar de J,XKXZ, y C6 muestra los mismos días como estimados y como reales.
  2. **Abono parcial** (`r02`, escenario 1). Digi emite un abono de Q,JZ € a la cuota del móvil de la factura de julio-agosto, con líneas solo del móvil.
     - Pierden la cobertura el móvil y también la fibra: agosto pasa de 31/31 a 17/31, julio deja de contar, y así queda para siempre, porque no habrá refacturación.
     - Una segunda ordinaria de julio-agosto con otro número se acepta, y el gasto del móvil en julio pasa de Z,KJ a Z,XX.
  3. **Atributos** (`r08`). Una factura de luz se anula y se refactura con 3,45 kW. `v_dim_contrato_atributo` da, para el mismo período, 4,4 kW y 3,45 kW, tanto en P1 como en P2.

  No hay ejemplos de abonos, así que no se sabe si los reales imprimen el consumo ni si Digi emite abonos parciales. Si los abonos de Naturgy no imprimen el consumo, el escenario 1 es el mismo de severidad alta que motivó H1.
- **Acción propuesta:** probada en `r09`.
  1. **Definir.** Un abono anula entera la factura que corrige. Un crédito parcial es una rectificativa por diferencias. Quitar de §3.4 la frase del abono parcial y anotar la definición en §11.
  2. **Hacerlo cumplir con un invariante (I9).** Si el abono y la factura que corrige están los dos en la base, sus líneas suman 0 por contrato. Se evalúa al cargar cualquiera de las dos, así que no depende del orden. En `r09`, I9 señala el abono parcial de Digi y acepta un abono total, llegue antes o después de la original.
  3. **Excluir la factura anulada y su abono** de `v_hecho_consumo_diario` y `v_dim_contrato_atributo`, con la misma condición que la cobertura. Así el consumo no depende de que el abono imprima las mediciones: en `r09` quedan 344 kWh reales, con o sin mediciones en el abono, y los controles del caso no cambian. Además, `tg_medicion_bi_signo` deja de hacer falta (H9).
  4. **Tests.** Extender `test_abono_y_refacturacion_no_duplican_gasto_ni_consumo` con un abono sin mediciones, y agregar el abono parcial.

#### H8. Si se anula la primera factura de un contrato, sus meses salen de la cobertura en lugar de marcarse incompletos

- **Severidad:** baja.
- **Requisito:** R26.
- **Qué está mal:** `primera_factura` (`esquema.sql`, líneas 680–684) se calcula sobre `periodo_cubierto`, que desde H1 excluye las facturas anuladas.
  - Si la anulada es la primera del contrato, el contrato empieza a contar después, y los meses de esa factura no aparecen como incompletos.
  - Si es la única, el contrato desaparece de la cobertura.

  R26 dice que el contrato cuenta "desde el mes de su primera factura".
- **Escenario de falla:** reproducido en `r02` (escenario 2). Hay dos contratos de gas con facturas del mismo período. Se anula la del segundo, y la refacturación todavía no llegó.
  - `v_hecho_cobertura_categoria_mensual` da mayo de 2026 con un solo contrato, completo.
  - C2 marca el gas de mayo como completo, aunque al segundo contrato le falta la factura.

  Con un solo contrato, C2 no lo muestra mal por casualidad: `coalesce(…, 0)` marca como incompleto un mes que no tiene fila de cobertura.
- **Acción propuesta:**
  - Calcular `primera_factura` con todas las ordinarias y sustituciones del contrato que tengan líneas `periodo`, estén anuladas o no.
  - Calcular `dia_cubierto` solo con las que cuentan.

  Probado en `r09`: mayo queda con 2 contratos y 1 completo, y los controles del caso no cambian.

#### H9. El trigger de signo rechaza la regularización de una lectura estimada

- **Severidad:** media.
- **Requisito:** R3 (también R27).
- **Qué está mal:** `tg_medicion_bi_signo` (`esquema.sql`, líneas 403–411) rechaza cualquier cantidad negativa en una ordinaria o una sustitución.
  - Cuando la lectura real queda por debajo de la estimada anterior, la factura ordinaria siguiente regulariza con un consumo negativo, del total o de una franja.
  - Con D5, que guarda solo la lectura de cierre, eso es exactamente lo que informa el documento.
  - El caso prevé lecturas estimadas en gas y luz (el gas del ejemplo cierra con una estimada) y regularizaciones.

  La primera ronda (H5) pedía rechazar el consumo negativo en una ordinaria sin considerar este caso.
- **Escenario de falla:** reproducido en `r03`.
  - **Gas.** La factura siguiente a la del ejemplo cierra con una lectura real de 15.575 m³, 2 m³ por debajo de la estimada de 15.577: el consumo es de −23 kWh. La base la rechaza.
  - **Luz.** Una factura con 81 kWh en total y −5 kWh en punta también se rechaza.

  La factura entera va a `pendientes/`, y el plan B no tiene una corrección posible: tipificarla como rectificativa por diferencias exigiría inventar un `numero_factura_corregida` (R10). Mientras tanto falta todo su gasto, y el mes figura incompleto.
- **Acción propuesta:**
  - Quitar la condición sobre ordinarias y sustituciones. Si se adopta la acción 3 de H7, quitar el trigger entero: el consumo de los abonos deja de sumarse, así que su signo no importa.
  - Documentar en §11.5 que un consumo negativo en una ordinaria es una regularización.

  Probado en `r09`.

#### H10. Una base con otra versión del esquema no se puede reemplazar por el camino previsto

- **Severidad:** baja.
- **Requisito:** R40 (también R19 y R8).
- **Qué está mal:**
  - **Lo que permite `conectar()`** (`conexion.py`, líneas 54–65): abre una base existente solo si su versión coincide con la del código, y el modo "nueva" exige que el archivo no exista.
  - **Lo que necesita la reconstrucción** (`diseno.md` §13.4, paso 3): reemplaza la base en uso con `sqlite3.connect(temporal).backup(conexion_escritura)`, así que tiene que abrir para escritura justamente la base que `conectar()` rechaza.
- **Escenario de falla:** reproducido en `r05`. Una construcción interrumpida deja un archivo con la versión 0 (H3).
  - `conectar()` lo rechaza con "hay que reconstruirla desde los PDFs procesados".
  - `construir()` lo rechaza porque "ya existe".
  - `reprocesar --todo`, tal como lo describe §13.4, fallaría en el paso 3 con el mismo error.

  Pasaría lo mismo cuando el bloque 4 suba la versión del esquema, que es justo el caso para el que existe R40. La única salida sería borrar el archivo a mano o abrir la base sin `conectar()`, que R8 no permite.
- **Acción propuesta:** antes del bloque 4, elegir una de dos:
  - agregar a `conectar()` un modo de reemplazo que abra para escritura una base existente sin verificar su versión, solo como destino del backup;
  - documentar en §13.4 qué hace la reconstrucción cuando la base en uso tiene otra versión o quedó a medio construir.

---

## 6. Resolución de la segunda ronda

La agregó el agente que implementó el bloque. Es la última ronda, porque `tarea.md` permite dos como máximo. No hay hallazgos de severidad alta. Los medios (H7 y H9) se corrigieron siguiendo la propuesta del revisor, que la probó en `r09`; los bajos se corrigieron o se justificaron. Pasan los 188 tests, los controles del caso siguen coincidiendo y el rendimiento no cambió (§6.3).

| Id | Severidad | Qué se hizo | Dónde |
|---|---|---|---|
| H7 | media | **Corregido.** **Definición:** un abono anula entera la factura que corrige; un crédito parcial es una rectificativa por diferencias. **Regla:** la hace cumplir el invariante I9, que exige que el abono y su original sumen 0 en cada contrato y se verifica al cargar cualquiera de los dos. **Vistas:** `v_factura_vigente` excluye la factura anulada y su abono, así que no aportan gasto, consumo ni atributos, traiga o no el abono su consumo. **Escenarios del hallazgo, ahora en tests:** un abono sin consumo deja el gas en 344 kWh reales; un abono parcial de Digi se rechaza por I9; la potencia de una factura anulada no aparece en los tramos. Esto reemplaza la corrección de H1 de la primera ronda: el trigger de signo se quitó (H9), y la sección 4 lo describe como era entonces. | `esquema.sql` (`v_factura_vigente`); `invariantes.py` (I9); `diseno.md` §1, §3.4, §7.2, §10 y §11.5; `test_abono_y_refacturacion_…` (con y sin consumo), `test_los_atributos_de_una_factura_anulada_no_cuentan` y `test_i9_*` |
| H8 | baja | **Corregido.** `primera_factura` se calcula con todas las ordinarias y sustituciones del contrato, anuladas o no, y `periodo_cubierto` solo con las vigentes. Si se anula la primera factura, sus meses siguen contando, como incompletos. | `v_hecho_cobertura_contrato_mensual`; `diseno.md` §9; `test_abono_y_refacturacion_…` (mayo con 0 de 31 días antes de la refacturación) |
| H9 | media | **Corregido.** Se quitó `tg_medicion_bi_signo`: una cantidad negativa en una ordinaria es una regularización. Con H7, el signo de las mediciones de un abono deja de importar, porque no cuentan. | `esquema.sql`; `diseno.md` §3.3 y §11.5; `test_una_ordinaria_puede_regularizar_un_consumo_negativo` (gas −23 kWh; luz −5 kWh en punta) |
| H10 | baja | **Justificado y anotado para el bloque 4.** La reconstrucción todavía no existe: la implementa el bloque 4. El modo de reemplazo de `conectar()` se escribe junto con ella, así puede probarse con una reconstrucción real. Queda documentado en §13.4 qué hace con una base de otra versión o a medio construir, y anotado como pendiente en la bitácora. | `diseno.md` §13.4; `bitacora.md` |
| Nota sobre H4 | — | **Corregida la documentación.** §1 dice ahora que `INSERT OR REPLACE` saltea todos los triggers. Que el comando `estado` verifique I1 en todas las facturas queda pendiente para el bloque 4, en la bitácora. | `diseno.md` §1; `bitacora.md` |
| Observación R38 | — | **Corregido.** `test_los_triggers_no_recorren_tablas` revisa ahora todos los triggers de la base (13), no solo 4. El test detectó, además, que la primera versión de I9 recorría `factura` entera; se reescribió como la unión de dos búsquedas por índice. | `test_indices.py`; `invariantes.py` |
| Observación para el bloque 4 (`r10`) | — | **Anotada en la bitácora:** con sustituciones encadenadas más un abono, algunos órdenes de llegada necesitan más de un reintento. | `bitacora.md` |

**Estado final:** no queda ningún hallazgo de severidad alta ni media abierto. Quedan justificados y pendientes para el bloque 4 la parte abierta de H4 (`INSERT OR REPLACE`, que detectará el comando `estado`) y H10 (modo de reemplazo de `conectar()`).

**Después de la revisión (punto de control):** la persona usuaria decidió que los alias del agua, el gas y la luz reconozcan las palabras clave de cada concepto y toleren cualquier detalle alrededor. Así **queda revertida la corrección de H2**. Un cargo nuevo cuyo texto contiene una palabra clave conocida ("Canon del agua - regularización 2025") se traduce a ese concepto en lugar de rechazarse. El total de la factura no cambia; a lo sumo, cambia el concepto o el mes de ese importe dentro del desglose. Los cargos sin ninguna palabra clave conocida siguen rechazándose (R30). Está documentado en `diseno.md` §1.1 (B6) y §12.2, y lo prueban `test_partes_variables_no_generan_conceptos_nuevos` y `test_texto_sin_alias_se_rechaza_con_el_texto_en_el_motivo`.
