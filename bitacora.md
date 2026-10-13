# Bitácora

Registro de la ejecución de los bloques de [`tarea.md`](tarea.md) y de las etapas del dashboard ([`task_dashboard.md`](task_dashboard.md)). La mantiene el agente: una entrada por bloque, al llegar al punto de control, y se actualiza el estado cuando la persona usuaria aprueba o pide cambios. No incluye datos personales.

Es el registro histórico: no se lee al empezar un bloque. El traspaso entre sesiones está en [`docs/estado.md`](docs/estado.md), y los pendientes de cada bloque, también en su ficha de [`docs/fichas/`](docs/fichas/).

## Formato de cada entrada

```
### Bloque N: <título> (AAAA-MM-DD)
- Estado: pendiente de aprobación | aprobado | cambios pedidos (cuáles)
- Qué se hizo:
- Decisiones no previstas en la especificación:
- Desvíos respecto de la especificación, y por qué:
- Cómo verificarlo: comandos
- Pendiente para los bloques siguientes:
```

---

<!-- Las entradas empiezan acá. -->

### Bloque 1: Diseño de la base de datos (2026-10-02)
- Estado: aprobado (2026-10-02), con D10 confirmada y el caso corregido
- Qué se hizo:
  - **Entorno verificado:** Python 3.12.10; SQLite 3.49.1 (la de Python, ≥ 3.37); git 2.54.0.windows.1; Claude Code 2.1.287; Windows PowerShell 5.1 (no está PowerShell 7, que no hace falta).
  - **Proyecto inicializado:**
    - git en la rama `main`;
    - `.gitignore`: `datos/`, `ejemplos/`, `.venv/`, bases, logs y temporales de Python;
    - `.gitattributes`: el hook conserva los saltos de línea LF;
    - estructura de carpetas de `tarea.md`; `datos/` y sus subcarpetas solo existen localmente.
  - **Hook `pre-commit`** en `scripts/git_hooks/`, activado con `git config core.hooksPath scripts/git_hooks`.
    - Busca los patrones del caso (DNI/NIE, IBAN, CUPS, teléfonos y emails) y los valores literales de `datos/datos_privados.txt`, una lista local fuera de git armada con los datos de los PDFs de ejemplo.
    - Deja pasar los identificadores fiscales de `src/facturas/semillas/proveedor.csv`.
    - Probado en un repositorio temporal: bloquea un DNI, un NIE, un IBAN entero y uno enmascarado, un CUPS, un teléfono, un email y un valor de la lista local, todos ficticios. Deja pasar los NIF de los proveedores, incluido un NIF con formato de DNI que figura en `proveedor.csv`.
  - **`docs/diseno.md`:**
    - modelo de 19 tablas `STRICT`, con diagrama entidad-relación;
    - convención de nombres, normalización e índices;
    - 17 vistas: 7 dimensiones, 4 auxiliares y 6 hechos;
    - prorrateo jerárquico, cobertura e invariantes;
    - contrato parser → carga y diccionario inicial (24 conceptos, 24 alias);
    - flujo de carga y organización de `src/`;
    - consultas de referencia C1–C7, ejemplo resuelto de `fibra_movil.pdf` y trazabilidad R1–R43;
    - esquema SQL completo (apéndice A).
  - **Verificación:** el esquema y las consultas se probaron en un prototipo (scratchpad, no versionado) con los 4 ejemplos. Coinciden totales, los 12 controles de prorrateo y la cobertura del caso. Con 10 años simulados, C1–C7 tardan ≤ 0,8 s.
  - **Revisión técnica independiente** en `docs/revision_bloque_1.md`.
    - Primera ronda: apto con cambios, con 14 hallazgos (2 altos, 5 medios y 7 bajos). Todos se corrigieron, salvo H12, que queda justificado y pendiente para el bloque 3.
    - Segunda ronda: apto con cambios, sin hallazgos altos y con 5 nuevos (H15 medio; H16–H19 bajos). Todos se corrigieron.
    - Estado final: no queda ningún hallazgo alto ni medio abierto. H12 (bajo) queda justificado y pendiente para el bloque 3.
  - **`src/facturas/semillas/proveedor.csv`** se creó adelantado del bloque 2, porque el hook lo usa como lista de permitidos.
- Decisiones no previstas en la especificación (detalle en `docs/diseno.md`, sección 1):
  - Prorrateo jerárquico (D6): cada mes de un contrato queda a menos de 1 céntimo de lo exacto, sea cual sea el número de líneas. Con los datos del caso coincide exactamente con los controles; el redondeo línea por línea se desvía 1 céntimo en algunos meses. La primera justificación (ZX,KZ frente a QX,JX) valía solo con la versión original del caso, de 61 días y con el canon en dos líneas, y se corrigió en el diseño.
  - El diccionario traduce (sección, texto) → concepto dentro de la categoría del contrato, con comodines `GLOB`. La sección solo la usa Digi (D4).
  - Un PDF distinto de una factura ya cargada se rechaza como duplicado y va a `datos/duplicados/` (D8). Una factura cargada solo se reemplaza reconstruyendo la base.
  - Hook con lista local de valores privados; semillas en `src/facturas/semillas/` (D9).
  - Los hechos no se editan: triggers de inmutabilidad sobre facturas, líneas, mediciones y valores de atributo.
  - Tabla `construccion` con la huella de las semillas: si cambian, la carga reconstruye la base antes de procesar. Si la reconstrucción falla, el lote no procesa nada (código 2).
  - El control de solapes cubre las ordinarias y las sustituciones. Una factura corregida por una sustitución o un abono no bloquea. Una factura se sustituye una sola vez.
  - El lote se carga por fecha de emisión. Al final, se reintentan los rechazos por solape que haya en `pendientes/`, de ese lote o de uno anterior.
  - La restauración y la reconstrucción pasan la base con la API de backup, nunca copiando ni renombrando el archivo, y se verifican por contenido. La reconstrucción no mueve PDFs.
  - Claves foráneas diferidas en la carga, para que el motivo de un rechazo nombre la FK que falló.
  - El alias por defecto usa el menor número libre.
  - Calendario de 2000 a 2099.
  - Definición de "reconstrucción idéntica" (sección 13.4).
- Desvíos respecto de la especificación, y por qué:
  - **D1** (aprobado): las líneas guardan solo texto e importe. Afecta R2 (cantidad, unidad, precio), R4, R11 (precios y tipos), R12 y dos invariantes de R33 (cantidad × precio y base × tipo). Por qué: el dashboard no los usa.
  - **D2 y D3** (aprobados): el canon y el alcantarillado del agua se guardan como su subtotal impreso, y el canon es un solo concepto (`canon_agua`). Afecta R1 y la clasificación del caso, que separa el canon fijo del variable.
  - **D5** (aprobado): cada medición guarda solo la lectura de cierre; la anterior es la de cierre de la factura previa. El caso lista las lecturas anteriores entre los valores esperados.
  - **D10** (confirmada): el período del agua se normaliza a 60 días (inicio = fecha impresa + 1).
    - Por qué: el PDF imprime "250 litros por día", "J,KZ €/día" y "J,JK €/día" de suministro, que corresponden a 60 días.
    - La persona usuaria confirmó que la factura anterior a la del ejemplo termina el 09-abr-2026: dos facturas consecutivas comparten el día de lectura.
    - **Error del caso, corregido con autorización de la persona usuaria** en `caso_hogar.md`: la convención del período del agua, el período del ejemplo (del 2026-04-10 al 2026-06-08, 60 días) y los controles del agua (abril 21 días ≈ ZZ,JK, mayo ≈ ZK,KX, junio ≈ X,KJ).
- Cómo verificarlo:
  - `git config --get core.hooksPath` → `scripts/git_hooks`
  - Hook, con un DNI ficticio armado en dos partes para no escribirlo literal:
    `printf 'DNI %s%s\n' 1234 5678Z > prueba_hook.txt && git add prueba_hook.txt && git commit -m prueba`
    Tiene que decir "Commit bloqueado". Después: `git rm --cached prueba_hook.txt` y borrar el archivo.
  - Leer `docs/diseno.md` (secciones 1, 8, 15, 16 y 18) y `docs/revision_bloque_1.md`.
- Pendiente para los bloques siguientes:
  - **Bloque 2:**
    - implementar el esquema del apéndice A;
    - escribir las semillas CSV (sección 12);
    - test de que ningún texto de los ejemplos es ambiguo;
    - `EXPLAIN QUERY PLAN` sobre la implementación;
    - tiempo de I4 por factura.
  - **Bloque 3:**
    - confirmar la convención del período de Digi con dos facturas consecutivas del histórico;
    - comprobar si el IVA por servicio de Digi siempre suma el impreso (H12);
    - limpiar los rótulos de sección de Digi, que vienen subrayados;
    - que cada parser declare sus campos opcionales impresos (11.6).
  - **Bloque 3, además:** que el parser del agua verifique los días de cada factura con los promedios impresos (l/día y €/día).
  - **Bloque 4:**
    - restauración y reconstrucción con la API de backup, probadas con un lector abierto en otro proceso;
    - orden del lote y reintento final de los rechazos por solape en `pendientes/`;
    - reconstrucción por cambio de semillas, y código 2 si falla;
    - alias por defecto con el menor número libre.
  - **Bloque 6:** que `aprobar_propuesta.ps1` haga una reconstrucción de prueba en un archivo temporal antes de confirmar la integración, porque la reconstrucción vuelve a extraer todo `procesadas/` con el parser de la propuesta (sugerencia de la revisión, H15).
  - **Al final del proyecto:** numeración estable del alias por defecto (D7), que la persona usuaria dejó para después.
  - **Riesgo a revisar con el histórico de Digi:** una línea nueva dentro de PRODUCTOS con un período entre paréntesis se traduciría como cuota.

### Bloque 2: Implementación de la base de datos (2026-10-03)
- Estado: aprobado (2026-10-03), con B1 (corrección de R7), la regla del abono y el criterio de alias por palabras clave (B6) aprobados por la persona usuaria
- Qué se hizo:
  - **Entorno:**
    - `.venv` con Python 3.12.10 y SQLite 3.49.1;
    - `requirements.txt` con pytest 9.1.1 y sus dependencias, fijadas;
    - `pyproject.toml`, solo con la configuración de pytest (`pythonpath = src`).
  - **`src/facturas/bd/`:**
    - `esquema.sql`: 19 tablas `STRICT`, 17 vistas y 13 triggers;
    - `conexion.py`: `conectar(ruta, modo)` con los modos lectura, escritura y nueva;
    - `construir.py`: la base en una sola transacción, más `leer_ajustes()` y `aplicar_ajustes()`;
    - `invariantes.py`: `verificar()` con I1 e I4–I9;
    - `diccionario.py`;
    - `consultas/`: C1–C7, un `.sql` cada una.
  - **Semillas:** 10 CSV nuevos (`proveedor.csv` ya estaba), con 24 conceptos y 24 alias.
  - **`src/facturas/carga/traduccion.py`:** `normalizar()` y `traducir()`, adelantados del bloque 4 (B5).
  - **`docs/diccionario.md`:** generado desde la base.
  - **Tests:** 198, que tardan unos 4 s.
    - `tests/datos_prueba.py`: las 4 facturas del caso, escritas a mano.
    - `tests/caso.py`: lee de `caso_hogar.md` la clasificación y los controles.
    - `tests/rendimiento.py`: no es un test, sino una medición con 10 años simulados.
    - Coinciden con el caso los totales por categoría, los 12 controles de reparto, la cobertura de mayo y junio y C1–C7.
  - **Índices (R38):**
    - cada clave foránea tiene su índice;
    - C1–C7 y los invariantes recorren enteras solo `linea` y `medicion`, por el prorrateo;
    - los triggers y las búsquedas de la carga van por índice.

    Con 10 años simulados, C1–C5 tardan entre 0,45 y 0,66 s (el revisor midió hasta 1 s), C6 y C7 alrededor de 0,1 s, y los invariantes de una factura 0,3 s.
  - **`docs/diseno.md`:**
    - sección 1.1, con los cambios de la implementación;
    - §6.3 y §14, con lo verificado;
    - las correcciones de la revisión;
    - los apéndices A y B ahora apuntan al código en lugar de copiar el SQL.
  - **Revisión técnica independiente** en `docs/revision_bloque_2.md`.
    - Primera ronda: apto con cambios, con 6 hallazgos (1 alto, 2 medios y 3 bajos). El alto, H1: un abono y su refacturación duplicaban el consumo.
    - Segunda ronda: apto con cambios, sin hallazgos altos, con 4 nuevos (H7 y H9 medios; H8 y H10 bajos).
    - Estado final: no queda ningún hallazgo alto ni medio abierto. Quedan justificados y pendientes para el bloque 4 la parte de `INSERT OR REPLACE` de H4 y H10.
- Decisiones no previstas en la especificación:
  - **Un abono anula entera la factura que corrige** (aprobada por la persona usuaria), y los dos dejan de contar en todas las vistas: gasto, consumo, atributos y cobertura. Un crédito parcial es una rectificativa por diferencias. Lo exige el invariante I9 (el abono y su original suman 0 en cada contrato), que no está en R33. Viene de la revisión (H1 y H7): antes, el consumo de un abono y su refacturación se sumaba dos veces.
  - **Cobertura:** cubren días solo las ordinarias y las sustituciones vigentes. Si se anula una factura, sus meses quedan incompletos hasta que llega la refacturación, y una baja futura no agrega meses que todavía no pasaron.
  - **Reglas nuevas en la base**, todas por la revisión:
    - las líneas, mediciones y atributos solo se borran junto con su factura;
    - de un contrato solo cambian el alias y las fechas;
    - una factura sale de una carga `cargada`;
    - el factor de conversión es mayor que 0;
    - el número de factura corregida no puede estar vacío ni tener espacios;
    - la conexión de lectura usa `query_only`.
  - **Una cantidad negativa en una factura ordinaria se acepta:** es la regularización de una lectura estimada.
  - **Los alias del agua, el gas y la luz reconocen palabras clave** (`*canon*`, `*termino fijo*`, `iva*`…) y toleran cualquier detalle alrededor. Lo decidió la persona usuaria en el punto de control: el dashboard responde "cuánto gasto en cada factura", y un cambio menor en un rótulo no debe detener la carga. Un cargo sin ninguna palabra clave conocida sigue rechazándose (R30). Esto revierte la corrección de H2 de la revisión, que exigía el rótulo completo.
  - **Versión del esquema:** la construcción va en una sola transacción, y un test guarda la huella de `esquema.sql` de cada versión. Si el esquema cambia sin subir `user_version`, ese test falla.
  - **B2:** la cobertura calcula los días cubiertos desde los períodos. Da el mismo resultado y C2 pasa de 0,79 a 0,53 s.
  - **B3:** la huella de las semillas incluye el nombre de cada archivo y normaliza los saltos de línea, porque git tiene `core.autocrlf = true`.
  - **Conexión:** `conectar()` tiene un modo "nueva", que solo usa `construir`.
  - **`ajustes_manuales.json`:** es una lista de objetos con `identificador_fiscal`, `identificador_externo` y, opcionalmente, `alias`, `fecha_alta` y `fecha_baja`.
  - **Recorridos completos:** se detectan en el bytecode (`EXPLAIN`), porque los alias que muestra `EXPLAIN QUERY PLAN` se repiten entre vistas.
- Desvíos respecto de la especificación, y por qué:
  - **B1, error de la especificación (R7):** la fórmula `CHECK (col = date(col))` deja pasar textos que no son fechas. `date()` devuelve NULL, y SQLite da por cumplido un `CHECK` que da NULL. Se usa `col IS date(col)`. El mismo hueco tenía `ck_carga_estado`, con la etapa o el motivo nulos, y se cerró. No se editó `tarea.md`. Aprobado por la persona usuaria en el punto de control.
  - **B4:** el bloque 2 pide que la creación de la base aplique los datos manuales, pero una base recién creada no tiene contratos. Se aplican con `aplicar_ajustes()` al registrar los contratos, como ya decía el diseño (§13.4).
- Cómo verificarlo (PowerShell, desde la raíz):
  - `.venv\Scripts\python -m pytest`: 198 tests.
  - `.venv\Scripts\python tests\rendimiento.py`: los tiempos de §6.3.
  - `$env:PYTHONPATH = "src"; .venv\Scripts\python -m facturas.bd.diccionario`, y después `git diff docs/diccionario.md`, que no tiene que mostrar cambios.
  - Leer `docs/revision_bloque_2.md` (secciones 1, 4, 5.1 y 6) y `docs/diseno.md` (secciones 1.1 y 6.3).
- Pendiente para los bloques siguientes:
  - **Bloque 3:**
    - cada parser emite las cantidades como las imprime el documento;
    - un crédito parcial se tipifica como `rectificativa_diferencias`, no como abono. La persona usuaria confirmó que Naturgy (gas) emitió abonos parciales al corregir una lectura estimada sobreestimada: pedirle uno del histórico para el parser del gas;
    - solo la luz emite franjas (revisión H5);
    - verificar con el histórico que ningún texto real coincide con dos alias, que es lo que podría pasar con las palabras clave. `traducir()` lo rechaza como ambiguo.
  - **Bloque 4:**
    - usar `traducir()`;
    - registrar los contratos con el alias por defecto y aplicar `aplicar_ajustes()`;
    - la transacción de carga con `PRAGMA defer_foreign_keys = ON` y `verificar()`;
    - un modo de reemplazo en `conectar()` para que la reconstrucción pueda escribir sobre una base de otra versión o a medio construir (revisión H10, §13.4);
    - que el comando `estado` verifique I1 en todas las facturas, para detectar un `INSERT OR REPLACE` manual (revisión H4);
    - con sustituciones encadenadas más un abono, algunos órdenes de llegada necesitan más de un reintento (observación de la revisión, `r10`).
  - Siguen vigentes los pendientes del bloque 1 para los bloques 3, 4 y 6, y el de D7.

### Bloque 3: Parsers (2026-10-03)
- Estado: aprobado (2026-10-03), con los identificadores esperados y la convención del período de Digi confirmados por la persona usuaria; la ampliación de abajo se trató aparte
- Qué se hizo:
  - **Biblioteca de PDF: `pypdf` 6.19.0** (Python puro, sin dependencias del sistema, gratuita), fijada en `requirements.txt`. Se leen dos vistas del mismo PDF: el texto en orden de lectura y el texto «de diseño» (por columnas, con sangría).
  - **`src/facturas/extraccion.py`:** tipos de la factura extraída (§11), validación de forma al construirlos (§11.6), `a_json()`/`desde_json()` para que la carga la lea, y `verificar_opcionales()`. No importa nada del proyecto.
  - **`src/facturas/parsers/`:** `pdf.py` (`leer()` → `Documento`), `comun.py`, el registro en `__init__.py` (`reconocer()`, `extraer(ruta)`; error si ningún parser o más de uno reconoce) y `aigues_agua.py`, `naturgy_gas.py`, `naturgy_luz.py`, `digi_convergente.py`, todos en versión 1.0.0. Cada uno expone `FORMATO`, `VERSION`, `reconoce()` y `extraer()`.
  - **Tests:** `tests/test_extraccion.py` (33) y `tests/test_parsers.py` (48), más `caso.valores_esperados()` en `tests/caso.py`, que lee del caso las tablas de «Valores esperados». Las líneas se comparan con el caso por importe, tipo de cargo y concepto (el concepto lo da `traducir()` con las semillas, independiente de los parsers). Total del proyecto: 295 tests, unos 8 s; los de parsers, unos 2 s.
  - **`ejemplos/identificadores_esperados.json`** (fuera de git): número de factura e identificador de cada contrato, leídos de los PDFs. La persona usuaria tiene que confirmarlos en el punto de control.
- Decisiones no previstas en la especificación:
  - Se agregó `parsers/comun.py` (números y fechas en formato español, búsqueda con error que nombra campo y formato, filas del detalle de Naturgy), para no repetir lo mismo en cuatro parsers. Cambio a la estructura de `src/`, anotado en `docs/diseno.md` §14.
  - Un parser recibe un `Documento` (texto y diseño), no una ruta; así los tests pueden alterar un texto y comprobar el error.
  - Todos los parsers verifican, además de lo pedido, que las líneas emitidas sumen el total a pagar impreso. Así una línea omitida o mal leída no pasa en silencio.
  - Agua: cada subtotal se verifica contra la suma de su desglose, y los días del período contra los tres promedios impresos (tolerancia de redondeo). Si el documento no imprime esos promedios, el parser falla.
  - Gas y luz: el rótulo de una fila que sigue en minúscula en la línea siguiente se une con la anterior («Impuesto Especial sobre» + «hidrocarburos»).
  - Una rectificativa o un abono (el documento dice «rectificativa» o «abono») se rechaza en lugar de cargarse como ordinaria: no hay ningún ejemplo para escribir ese parser. Todos los parsers emiten `tipo = ordinaria`.
  - Moneda `EUR` fija en los cuatro: el documento imprime solo `€` y el caso admite solo `EUR`.
  - El identificador externo del gas y la luz es el CUPS; el del agua, el nº de contrato; en Digi, el nº de línea (móvil) y el identificador de fibra, que se distinguen por la primera página («EN EL MÓVIL», «Identificador Fibra»).
- Desvíos respecto de la especificación, y por qué:
  - Ninguno nuevo. Se aplican los ya aprobados: D2/D3 (canon y alcantarillado como su subtotal) y D5 (solo la lectura de cierre), por lo que los tests no comparan la parte fija y variable del canon ni las lecturas anteriores del caso.
- Cómo verificarlo:
  - `.venv\Scripts\python -m pytest -q --tb=short tests\test_extraccion.py tests\test_parsers.py tests\test_codigo.py`
  - `.venv\Scripts\python -m pytest -q --tb=line`
  - Sin los PDFs, los tests de parsers se saltan con mensaje (se comprobó moviendo `ejemplos/`).
- Pendiente para los bloques siguientes:
  - **No verificado:** la convención del período de Digi (inicio y fin incluidos, del 15 al 14) con dos facturas consecutivas; solo hay un ejemplo. Tampoco se pudo comprobar con el histórico que el IVA por servicio siempre suma el impreso (H12): el parser lo exige y falla si no.
  - **No verificado:** que ningún texto real coincida con dos alias; y el comportamiento con más de una línea móvil (el código lo admite, sin ejemplo).
  - Abonos y rectificativas: hace falta un ejemplo real (Naturgy emitió abonos parciales) para escribir su parser; hasta entonces van a `pendientes/`, y el plan B (bloque 6) los verá como un formato sin parser.
  - Bloque 4: la carga lee la factura con `FacturaExtraida.desde_json()` y no importa `parsers`.

### Ampliación del bloque 3: Digi 2025 y ajuste de gas (2026-10-03)
- Estado: aprobada (2026-10-03): la persona usuaria confirmó las tres decisiones de abajo
- Qué se hizo:
  - Con tres PDFs nuevos de `ejemplos/` (el Digi de septiembre de 2025, la factura de gas del ejemplo y su ajuste) se encontraron y corrigieron tres límites de los parsers:
    - **Digi con el NIF anterior:** ningún parser reconocía la factura de 2025, que imprime `B-84919760`.
    - **Digi con dos líneas móviles:** el parser solo leía la primera.
    - **Gas, ajuste parcial:** se rechazaba por el formato (no dice «rectificativa» ni «abono»). Ahora es una `rectificativa_diferencias`.
  - **Resuelve pendientes del bloque 3:**
    - IVA por servicio de Digi (H12): suma lo impreso también en 2025, con tres servicios (Z,ZQ + X,XQ + X,ZZ = X,XK €);
    - convención del período de Digi: confirmada por la persona usuaria; 2025 imprime 16/08 a 15/09, 31 días con los extremos incluidos;
    - varias líneas móviles: ya hay ejemplo y se prueba;
    - el pendiente del abono de Naturgy: el ejemplo real era un ajuste parcial, ya cubierto. Un abono total sigue sin ejemplo.
  - **Tests:** `tests/test_parsers_ampliacion.py` (18), con las facturas reales. Total del proyecto: 313 en unos 14 s. Con los dos PDFs de gas cargados en la base en cualquier orden, los invariantes pasan, el gasto neto es QJ,KX € (KJ,ZJ − XJ,XZ) y el consumo, 138 kWh (344 − 206).
  - Los PDFs se copiaron con nombres neutros (`digi_2025_dos_moviles.pdf`, `gas_ajuste.pdf`) porque los originales llevan números de factura; los tests no los citan. Los identificadores exactos se agregaron a `ejemplos/identificadores_esperados.json` (fuera de git).
- Decisiones no previstas en la especificación (detalle en `docs/diseno.md` §1.2):
  - **Digi se emite con el NIF vigente (`A84919760`)** aunque el documento imprima el anterior (`B84919760`): es la misma empresa y así comparte proveedor, sin tocar las semillas. **Confirmado:** un solo proveedor. (La alternativa, dos proveedores, habría sido agregar `B84919760` a `proveedor.csv`.)
  - **Ajuste de gas = `rectificativa_diferencias`**, con la medición como diferencia de energía. Los m³ netos son un dato derivado (los m³ acreditados salen de los kWh y el factor), no impreso; el parser verifica que sean enteros y que reproduzcan los kWh. **Confirmado.**
  - **Lectura `Cliente` = `real`:** la informó la persona usuaria; no es una estimación. **Confirmado.**
- Desvíos respecto de la especificación, y por qué: ninguno nuevo.
- Cómo verificarlo: `.venv\Scripts\python -m pytest -q --tb=short tests\test_parsers_ampliacion.py` y, al cerrar, todos (`--tb=line`).
- Pendiente para los bloques siguientes:
  - **Bloque 4:** la carga ya recibe rectificativas por diferencias reales; la ficha 04 quedó actualizada. Un ajuste que anule la factura entera sería un abono y no tiene ejemplo.
  - **Dashboard (fuera de alcance):** C6 muestra la original como estimada y el ajuste como real (negativo); el total del mes es correcto.
  - Luz y agua: sin ejemplo de ajuste; sus parsers siguen rechazándolos.

### Bloque 4, parte A: Carga (2026-10-03)
- Estado: aprobado (2026-10-04). La persona usuaria comprobó contra sus facturas los totales de la carga de los ejemplos sobre una copia: agua, luz, fibra, móvil y gas (KJ,ZJ € menos el abono de XJ,XZ € = QJ,KX €).
- Qué se hizo:
  - **`python -m facturas`** con `cargar`, `reprocesar --pendientes`, `reprocesar --todo`, `estado` y `diccionario`. Códigos de salida: 0 (todo cargado o nada que hacer), 1 (PDFs rechazados en esa ejecución), 2 (error del sistema). Se ejecuta con `PYTHONPATH=src`.
  - **`carga/insercion.py`:** una factura extraída en una transacción `BEGIN IMMEDIATE` con `defer_foreign_keys`: resuelve y traduce todo antes de escribir, registra los contratos nuevos (alias por defecto con el menor número libre que no choca con un alias reservado en `ajustes_manuales.json`, más los ajustes manuales), inserta carga, cabecera, líneas, mediciones y atributos, y llama a `verificar()` antes del `COMMIT`. Un fallo revierte todo y lanza `ErrorCarga(etapa, motivo)`; `registrar_rechazo()` deja la carga rechazada (un reintento actualiza su fila).
  - **`operacion/proceso.py`:** espera a que cada archivo deje de crecer (3 s, hasta 120 s) y se pueda abrir; hash; duplicado por hash (también dentro del lote); extracción; el lote se carga por fecha de emisión y, a igual fecha, por ruta; destino `procesadas/<categorías>/<año>/<inicio>_<fin>_<formato>_<nº>.pdf`; rechazos a `pendientes/` (o `duplicados/`) con su `.motivo.txt`; un PDF con problemas no detiene el lote. Al final del lote, si cargó algo, reintenta los rechazos por solape hasta que una vuelta no cargue ninguno.
  - **`operacion/reconstruccion.py`:** antes de cada lote compara la huella de las semillas con la de la base y reconstruye si difiere (o si la base no existe, tiene otra versión o está a medio construir). Construye en un archivo temporal, carga `procesadas/` y reemplaza la base **con la API de backup** (modo nuevo `reemplazo` en `conectar()`); verifica `integrity_check` y el volcado canónico. Si un PDF falla, la base anterior queda intacta y sale con 2. Nunca mueve ni borra PDFs.
  - **`bd/volcado.py`:** el volcado canónico de §13.4 (claves naturales, sin `fecha_hora` ni cargas rechazadas).
  - **`operacion/estado.py`:** gasto y facturas vigentes por categoría, último período por contrato, meses incompletos, PDFs pendientes con su motivo, y I1 en todas las facturas.
  - **`operacion/bloqueo.py`:** bloqueo del sistema operativo sobre `datos/ejecucion.lock`; lo libera el sistema aunque el proceso muera. **`operacion/registro.py`:** `datos/logs/facturas.log`, 1 MB y 5 copias.
  - **Tests:** `test_carga.py` (30), `test_operacion.py` (16), 2 en `test_conexion.py` y los de `test_codigo.py` para los módulos nuevos. Total del proyecto: 379 (eran 313), unos 40 s (los de carga leen los PDFs reales). Siempre sobre copias de los ejemplos en carpetas temporales, nunca sobre `datos/`.
- Decisiones no previstas en la especificación (detalle en `docs/diseno.md` §1.3, C1 a C8):
  - Tres módulos fuera del árbol de §14: `bd/volcado.py`, `operacion/reconstruccion.py` y `operacion/estado.py`; y `Rutas` en `proceso.py`.
  - Una moneda desconocida se rechaza en la etapa `traduccion` (la tabla de §13.3 decía `invariantes`; el diagrama de §13.1 decía `traduccion`).
  - Más de 3 decimales en una cantidad se detecta en la carga y se rechaza en la etapa `extraccion`: `extraccion.py` no cuenta decimales.
  - Al reconstruir, `carga.nombre_archivo` se conserva de la base anterior por hash. Sin la base anterior queda el nombre normalizado de `procesadas/`.
  - `estado` sale con 2 si alguna factura no cumple I1. El log va solo al archivo.
  - `ejemplos/` tiene 9 archivos pero 6 PDFs distintos; «una factura por ejemplo» da 6 cargadas y 3 duplicadas.
  - Un archivo que no se estabiliza en 120 s no se procesa ni se rechaza: queda en `entrada/` y el resumen lo cuenta como «omitida».
- Desvíos respecto de la especificación, y por qué: los de arriba. Ninguno cambia el modelo ni la especificación.
- Cómo verificarlo:
  - `.venv\Scripts\python -m pytest -q --tb=short tests\test_carga.py tests\test_operacion.py tests\test_codigo.py`
  - `.venv\Scripts\python -m pytest -q --tb=line` (379 pasan)
  - Prueba manual sobre una copia (la de `datos/` va al final de la parte B): poner los ejemplos en una carpeta `datos\entrada\` de una raíz temporal y ejecutar `cargar`, `estado` y `reprocesar --todo`; ver los tests `test_con_todos_los_ejemplos…` y `test_estado_muestra_los_totales…`.
  - `$env:PYTHONPATH = "src"; .venv\Scripts\python -m facturas diccionario` no cambia `docs/diccionario.md` (lo comprueba `test_el_comando_diccionario_reproduce_el_versionado`).
- Pendiente para los bloques siguientes:
  - **No verificado:** que `restaurar` funcione con un lector abierto y escrituras posteriores a la instantánea (parte B). La reconstrucción sí se probó con un lector abierto en otro proceso.
  - **No verificado:** que `estado` y la carga rindan con años de histórico; la suite no mide tiempos de la carga. La carga abre una conexión de escritura y una transacción por factura.
  - **Excepción conocida (D7):** `reprocesar --todo` puede renumerar el alias por defecto de los contratos de una categoría con más de uno (hoy, `movil`); lo avisa. Se fija con `contrato` (parte B). Pendiente de decisión de la persona usuaria, en el bloque 7.
  - **Parte B:** `cargar` tiene que llamar a `respaldar`; ver la ficha 04. Bloque 5: el disparador invoca `python -m facturas cargar` (ficha 05). Bloque 6: formato de `.motivo.txt` y qué guarda `carga` en cada etapa (ficha 06).

### Bloque 4, parte B: Datos manuales y copias de seguridad (2026-10-04)
- Estado: aprobado (2026-10-04)
- Qué se hizo:
  - **`operacion/ajustes.py`:** `contratos` (alias, categoría, proveedor, alta y baja) y `contrato <alias> [--alias] [--alta] [--baja]`, que escribe en la base y en `datos/ajustes_manuales.json` a la vez (R41). Rechaza un alias que usa otro contrato o que el archivo reserva para otro, una fecha inválida y un alta posterior a la baja; en esos casos no cambia nada.
  - **`operacion/respaldo.py`:** `respaldar` (instantánea con `VACUUM INTO`, copia de los ajustes con la misma marca, PDFs de `procesadas/` que faltan, rotación a 30) y `restaurar` (base con la API de backup, ajustes y PDFs). `cargar` y `reprocesar --pendientes` respaldan solos si cargaron algo, con el bloqueo tomado.
  - **`datos/config.toml`** con `carpeta_respaldo = 'G:\My Drive\facturas-bi-respaldo'` (la carpeta que definió la persona usuaria). Verificado en la carpeta real: se puede escribir, `VACUUM INTO` (desde un temporal local) y la copia de PDFs funcionan, y `restaurar` sobre la base real reproduce el contenido.
  - **`reconstruccion.reemplazar_base`** (antes `_reemplazar`) es ahora pública: la usan la reconstrucción y `restaurar`.
  - **Tests:** `test_ajustes.py` (18) y `test_respaldo.py` (28), todos sobre carpetas temporales. Total del proyecto: 429 (eran 379), unos 90 s.
- Decisiones no previstas en la especificación (detalle en `docs/diseno.md` §1.3, C9 a C13):
  - Sin `datos/config.toml`, `cargar` avisa y sigue (código 0); con la configuración y un respaldo que falla, la carga queda hecha y sale con 2. `reprocesar --todo` no respalda.
  - La instantánea se arma y verifica en `datos/respaldo_*` (local) y se copia a Drive con nombre provisional `.parcial` y verificación de hash: SQLite nunca abre una base dentro de Drive.
  - Carpeta de respaldo: `instantaneas/facturas_<marca>.db`, `instantaneas/ajustes_<marca>.json` (`[]` si no había) y `procesadas/`.
  - `restaurar` acepta la ruta de la instantánea o su marca, y rechaza una instantánea dañada, de otra versión del esquema o sin sus ajustes. Si no hay base, la crea. Avisa cuántos PDFs de `procesadas/` no están en la copia.
  - `contrato --alta ninguna` / `--baja ninguna` quita una fecha. Un cambio inválido sale con 2 y «No se cambió nada».
- Desvíos respecto de la especificación, y por qué:
  - §14.1 decía `query_only` para el respaldo; `query_only` impide `VACUUM INTO`, así que el respaldo usa solo `mode=ro` (C10).
  - Una instantánea de otra versión del esquema no se restaura (la especificación pide verificar la versión): se recupera con los PDFs y los ajustes y `reprocesar --todo`.
- Cómo verificarlo:
  - `.venv\Scripts\python -m pytest -q --tb=short tests\test_ajustes.py tests\test_respaldo.py`
  - `.venv\Scripts\python -m pytest -q --tb=line` (429 pasan)
  - Prueba manual (hecha, con los 9 ejemplos en `datos\entrada\`): `cargar` → 6 cargadas, 3 duplicadas, respaldo en Drive; después `estado`, `contratos`, `respaldar`, `restaurar <marca>` y `reprocesar --todo`. `datos/` quedó con esa carga (son facturas reales y se conservan) y Drive tiene 2 instantáneas con el mismo contenido.
- Pendiente para los bloques siguientes:
  - **No verificado:** un respaldo concurrente con una carga real en otro proceso (los tests usan una escritura sin confirmar en otra conexión); cómo trata Google Drive para escritorio los archivos `.parcial` mientras se suben (el nombre definitivo solo aparece con la copia completa).
  - Bloque 5: `cargar` sale con 2 también cuando falla el respaldo, con las facturas ya cargadas (ficha 05).
  - Bloque 7: documentar la restauración en el README (R43: «documentada y probada»; ficha 07). D7 sigue abierto.

### Bloque 5: Disparador de Windows (2026-10-04)
- Estado: aprobado (2026-10-06). La persona usuaria comprobó sobre el proyecto real los cinco puntos del punto de control (tareas instaladas, carga con aviso de Windows, vigilante tras cerrar sesión, barrido tras suspender, log) y confirmó las decisiones de abajo y la de reinstalar si se mueve la carpeta
- Qué se hizo:
  - **Scripts** en `scripts/`: `instalar_disparador.ps1` (idempotente: `Register-ScheduledTask -Force`), `desinstalar_disparador.ps1`, `estado_disparador.ps1`, y los que las tareas ejecutan: `vigilante.ps1`, `barrido.ps1`, `ejecutar_carga.ps1` y `comun_disparador.ps1` (rutas, log, notificación). Las rutas salen de la ubicación del script; los nombres de tarea y de mutex llevan un hash de la ruta del proyecto.
  - **Vigilante:** `FileSystemWatcher` sobre `datos/entrada/`; lanza la carga cuando pasan 20 s sin novedades (un lote, una ejecución). Al arrancar cuenta como novedad lo que ya hubiera. Una sola instancia (mutex). Tarea al iniciar sesión, sin límite de tiempo, con reintentos.
  - **Barrido:** al iniciar sesión y cada hora; lanza la carga solo si hay PDFs en `entrada/`.
  - **`ejecutar_carga.ps1`:** espera su turno (mutex, hasta 15 min), fija `PYTHONPATH` y llama a `python -m facturas cargar`; vuelve a lanzarla (máximo 5 veces) si quedaron archivos «omitidos» en `entrada/`; con código 2 no reintenta y avisa; notifica con un toast de Windows solo si cargó o rechazó algo («3 facturas cargadas, 1 pendiente») o si hubo error; si esa ejecución rechazó algo y existe `scripts/al_haber_pendientes.ps1`, lo llama. Logs en `datos/logs/disparador.log` (rotación a 1 MB).
  - **Sin ventana y sin administrador:** las tareas son del usuario (`RunLevel Limited`) y ejecutan `conhost.exe --headless powershell.exe -ExecutionPolicy Bypass -File …`; la política del sistema no se toca.
- Decisiones no previstas en la especificación:
  - Espera por lotes de 20 s (parámetro `-EsperaSegundos` del vigilante); barrido de 60 min (`-MinutosBarrido` del instalador).
  - El punto de extensión se llama si la ejecución rechazó algo (se lee del resumen), no por el código de salida, para que un respaldo fallido (código 2) no lo oculte.
  - Notificación con la API de toast de Windows desde PowerShell 5.1, sin módulos; usa el identificador de aplicación de PowerShell.
  - Sin tests de Python: la lógica está en PowerShell y se probó con las tareas reales (ficha 05 lo preveía como opcional).
- Desvíos respecto de la especificación, y por qué: ninguno.
- Cómo verificarlo:
  - `powershell -File scripts\instalar_disparador.ps1`, luego `scripts\estado_disparador.ps1`; dejar un PDF en `datos\entrada\` y mirar `datos\logs\disparador.log` y la notificación.
  - `.venv\Scripts\python -m pytest -q --tb=line`
  - Pruebas hechas (en una copia del proyecto en el scratchpad, con `datos/` vacío y sus propias tareas, para no tocar las facturas reales): un PDF → «Lote listo» y 1 cargada en ~5 s; los 9 ejemplos copiados a la vez → un solo lote y una sola carga (5 cargadas, 4 duplicadas); un archivo que no es PDF válido → código 1, va a `pendientes/` y se llama al punto de extensión de prueba; el barrido, lanzado con el vigilante detenido, procesó un PDF; tras desinstalar no quedó ninguna tarea ni proceso de esa copia.
- Pendiente para los bloques siguientes:
  - **Verificado por la persona usuaria en el punto de control** (el agente no podía): que el toast se ve en pantalla, que el vigilante arranca tras cerrar sesión o reiniciar y que el barrido recoge lo que quedó con la PC suspendida.
  - Bloque 6: `al_haber_pendientes.ps1` se ejecuta con el bloqueo del disparador tomado, así que debe lanzar el trabajo largo desacoplado y volver enseguida (ficha 06).
  - Bloque 7: documentar la instalación, el estado y la desinstalación del disparador en el README (ficha 07).

### Bloque 6, parte A: Plan B, lanzamiento y aislamiento (2026-10-06)
- Estado: en pausa. La persona usuaria no quiere un agente automático: todo tiene que correr en Python. Se versiona el código, pero `al_haber_pendientes.ps1` se quitó de `scripts/`, así que el disparador no lo llama. Primero se carga el histórico; qué hacer con el plan B se decide después
- Qué se hizo:
  - **`scripts/plan_b.ps1 <archivo>`** (un intento a pedido) y **`-Automatico`** (los pendientes sin intento, de a uno, volviendo a mirar después de cada intento). Un solo plan B a la vez (mutex con el hash del proyecto). Por cada intento: hash SHA-256, motivo (`.motivo.txt`), formato y extracción de la tabla `carga` (solo lectura, `scripts/plan_b/carga_pendiente.py`), rama `propuesta/<formato>-<AAAAMMDD-HHMM>` (`desconocido` si no hay formato; `-2`, `-3` si se repite el minuto) y `git worktree` en `..\<proyecto>-propuestas\<sufijo>`.
  - **Lo que el agente recibe en el worktree** (fuera de git): `ejemplos/` copiado; en `ejemplos/plan_b/` el PDF pendiente con un nombre neutro (`<sufijo>.pdf`, sin el número de factura del nombre original), su motivo, su texto tal como lo ven los parsers (`scripts/plan_b/texto_pdf.py`) y la extracción si la hay; `.venv` como enlace (junction) al del proyecto. `ejemplos/plan_b/` no lo ve el `glob("*.pdf")` de los tests.
  - **Costo cero:** el script quita de su propio entorno, antes de lanzar nada, toda variable `ANTHROPIC_*`, `CLAUDE_CODE_USE_*` y `AWS_BEARER_TOKEN_BEDROCK` (la documentación actual de Claude Code nombra, además de la clave de API, el token, la URL base o pasarela, Bedrock, Vertex, Foundry, la federación de identidad y los perfiles; casi todas empiezan por `ANTHROPIC_`). Además, `claude auth status` tiene que decir `loggedIn` y `authMethod = claude.ai`; si no, no se lanza (cubre también un `apiKeyHelper` en la configuración).
  - **Permisos:** `claude -p --permission-mode dontAsk --settings scripts/plan_b/permisos.json --setting-sources project --tools Read,Edit,Write,Glob,Grep,Bash --strict-mcp-config --disable-slash-commands --output-format json --model sonnet`, con el mensaje por la entrada estándar y la carpeta del worktree como directorio de trabajo. `permisos.json` permite leer y editar `./**` (salvo `scripts/`, `ejemplos/`, `.venv/` y `.claude/`) y en Bash solo pytest con el `.venv`, `texto_pdf.py` y `git status|diff|log|show|add|rm|mv|commit`. Sin web ni MCP; lo no permitido se rechaza solo (`dontAsk`).
  - **Duración máxima** (`-LimiteMinutos`, 30): se mata el árbol de procesos (`taskkill /T`).
  - **Siempre queda algo que revisar:** si el agente no escribió el informe (tiempo agotado, error), el script escribe uno con lo que pasó; si dejó cambios sin commit, los commitea en la rama. Después comprueba que la rama principal no cambió (si cambió: alerta). Notifica «Propuesta lista para <archivo>. Revisar con `scripts\revisar_propuesta.ps1 <rama>`», o «sin corrección segura» si la rama solo trae el informe.
  - **Sin `claude` utilizable** (no instalado, sin sesión, sin suscripción, límite de uso): notificación con el motivo, no cuenta como intento, se borran la rama y el worktree y el modo automático se detiene (no prueba los demás). El próximo disparo vuelve a intentarlo una vez: no hay bucle.
  - **`scripts/al_haber_pendientes.ps1`:** si hay pendientes sin intento, lanza `plan_b.ps1 -Automatico` en un proceso aparte, creado por WMI (`Win32_Process.Create`) con el entorno actual y la ventana oculta, y vuelve enseguida. Así no retiene el turno de la carga ni depende de la tarea programada que lo llamó (el barrido tiene un límite de 1 h).
  - **`scripts/plan_b/instrucciones.md`:** contexto por secciones (con Grep y Read, porque el agente no tiene `awk`), ciclo OODA con tres vueltas como máximo, correcciones permitidas y prohibidas, lo obligatorio, datos personales y el formato del informe.
  - **Tests:** `tests/test_plan_b.py` (12, unos 40 s), sobre una copia mínima del proyecto con su propio repositorio git y un `claude` falso primero en el PATH.
  - **Cambios en código de bloques anteriores:** el hook de datos personales, en un worktree, lee `datos/datos_privados.txt` de la copia de trabajo principal (`git rev-parse --git-common-dir`); `Notificar` (bloque 5) anota también cada aviso en el log y no muestra el toast si `FACTURAS_SIN_AVISOS=1` (lo usan los tests).
- Decisiones no previstas en la especificación:
  - Los worktrees van al lado del proyecto (`..\facturas-bi-propuestas\`), no dentro: así la copia de trabajo principal no cambia y Claude Code no carga dos veces el `CLAUDE.md` del proyecto.
  - Modelo del agente: `sonnet` por defecto (`-Modelo`), para gastar menos cupo.
  - Git limitado a subcomandos concretos y no a `git *`: con `git *` el agente podría mover la rama principal (`git update-ref`).
  - Un fallo de entorno no cuenta como intento; un tiempo agotado o un error sí (queda la rama con el informe del script).
  - Registro de intentos en `datos/plan_b_intentos.tsv` (hash, fecha, archivo, rama, resultado); salida de cada ejecución de `claude` en `datos/logs/plan_b/<sufijo>.*`.
  - `-Simular` registra el intento (resultado `simulacion`), como uno real: por eso se usa en una copia del proyecto y no sobre los pendientes reales.
  - Dos ayudantes en Python en `scripts/plan_b/` (`texto_pdf.py`, `carga_pendiente.py`), fuera de `src/`, porque son herramientas del plan B y no parte del paquete.
- Desvíos respecto de la especificación, y por qué:
  - El informe va en `docs/propuestas/<formato>-<AAAAMMDD-HHMM>.md`, sin el prefijo `propuesta/` de la rama: con él, la barra crearía una subcarpeta.
- Cómo verificarlo:
  - `.venv\Scripts\python -m pytest -q --tb=short tests\test_plan_b.py`: el proceso hijo no recibe las variables de facturación (y sí el resto del entorno); `claude` se lanza en el worktree con los permisos restringidos; la propuesta queda en su rama y la principal no cambia; `-Simular` hace todo menos invocar a `claude`; un solo intento automático por PDF; sin `claude`, sin sesión, con clave de API o con el límite de uso no se lanza, avisa y no cuenta como intento; la duración máxima; no hay dos planes B a la vez; `al_haber_pendientes.ps1` vuelve enseguida y el plan B corre aparte.
  - El hook en un worktree: en un repositorio temporal con un valor en `datos/datos_privados.txt` de la copia principal, un commit hecho desde un worktree con ese valor queda bloqueado.
  - `.venv\Scripts\python -m pytest -q --tb=line` → 441 pasan.
- Pendiente para los bloques siguientes:
  - **No verificado (parte B, con la ejecución real):** que la versión instalada de `claude` acepta estas opciones juntas y que los permisos se comportan como se espera (leer y buscar dentro del worktree, pytest y git sí; fuera del worktree, no). Y que el proceso creado por WMI sigue vivo cuando la tarea programada termina (se probó lanzándolo a mano, no desde la tarea).
  - Riesgo residual: los tests que escribe el agente se ejecutan antes de la revisión y pueden hacer cualquier cosa que haga Python; los permisos no lo impiden. Se acepta porque el agente trabaja con la cuenta de la persona usuaria y nada se integra sin revisión.
  - Carrera conocida: un PDF rechazado justo mientras el modo automático termina su última vuelta espera al disparo siguiente.
  - Parte B: lo de la ficha 06.

### Corrección de parsers con facturas reales de 2025 (2026-10-06)
- Estado: aprobado (2026-10-06). La pidió la persona usuaria después de estudiar los rechazos, en la sesión de la parte A del bloque 6.
- Qué se hizo: de los 4 PDFs distintos que había en `pendientes/`, 3 eran variantes de formatos conocidos que los ejemplos de 2026 no tenían.
  - **Gas, cambio de precio** (`naturgy_gas` 1.2.0, `naturgy_luz` 1.1.0): si el precio cambia dentro del período, Naturgy parte el consumo y el término fijo en una fila por tramo («Del 26/08/2025 al 30/09/2025 …»), debajo de su rótulo. Antes el parser tomaba la fecha como concepto y la traducción lo rechazaba. Ahora `comun.lineas_de_detalle` (antes `filas_de_detalle`, compartida con la luz) da a cada fila el rótulo como texto y el tramo como `periodo` de la línea (§11.4), y verifica que el tramo esté dentro del período de la factura.
  - **Agua, litros truncados** (`aigues_agua` 1.1.0): la factura imprime los litros por día truncados (10.000 l / 61 días → «163»). La tolerancia era de medio litro; ahora acepta menos de un litro. Los promedios en euros, que van redondeados, siguen con medio céntimo.
  - **Agua sin el mensaje de litros:** un aviso sobre la parte fija del canon de 2026 ocupa el lugar del mensaje. Los litros por día pasan a ser opcionales; los dos promedios en euros siguen siendo obligatorios y fijan los días del período.
  - Los tres PDFs se copiaron a `ejemplos/` (fuera de git) como `gas_2025_cambio_precio.pdf`, `agua_2025_litros_truncados.pdf` y `agua_2026_aviso_canon.pdf`. `apoyo_carga.DISTINTOS` pasa de 6 a 9, y el test que carga todos los ejemplos ajusta sus carpetas de destino; no se debilitó ninguna comprobación. Tests nuevos: `tests/test_parsers_variantes.py` (5).
  - Sobre el proyecto real, `reprocesar --pendientes` cargó las 3 y las respaldó. La copia repetida del PDF de 2024 fue a `duplicados/`.
- Queda pendiente: la luz de oct–nov 2024 es un formato anterior de Naturgy, emitido por Naturgy Iberia (A08431090), sin «Período electricidad». Necesita un parser nuevo, si la persona usuaria decide que vale la pena.
- Cómo verificarlo: `.venv\Scripts\python -m pytest -q --tb=short tests\test_parsers_variantes.py tests\test_carga.py`; `… -m facturas estado`.

### Carga del histórico: variantes y formato de 2024 (2026-10-06)
- Estado: aprobado (2026-10-06). La persona usuaria cargó todas las facturas viejas: 39 entraron y 25 se rechazaron. Se estudiaron los rechazos por grupo y ella decidió los casos de clasificación.
- Qué se hizo:
  - **Luz 2025** (`naturgy_luz` 1.2.0): lecturas con «(hasta)»/«(desde)» (6 facturas); fechas con el año en dos cifras (3); tramo de un día, «1 día x» (1).
  - **Agua** (`aigues_agua` 1.2.0): la primera factura del contrato cuenta también el día del alta (63 días, no 62); los promedios impresos deciden entre D10 y ese caso.
  - **Gas** (`naturgy_gas` 1.3.0): cargos sin cuenta bajo «Otros conceptos» (inspección periódica). `comun.lineas_de_detalle` los lee, con el rótulo en una o varias líneas.
  - **Digi** (`digi_convergente` 1.2.0): cantidades con unidad («210,57 MB»); el teléfono fijo «DIGI tel» del bloque «EN CASA» cuenta como `fibra` (decisión de la persona usuaria).
  - **Formato de 2024 de Naturgy Iberia** (A08431090): `naturgy_iberia_luz` y `naturgy_iberia_gas` 1.0.0 (6 facturas). Todo se lee del texto por columnas con `comun.lineas_por_columnas`, porque el texto en orden de lectura sale palabra por palabra. Proveedor nuevo en `semillas/proveedor.csv`.
  - **CUPS** (`comun.cups_suministro`): el contrato se identifica por los 20 caracteres del CUPS. La luz de 2025 imprimía el punto frontera («…0F») y la de 2026 no, y el mismo suministro había quedado en dos contratos. Al reconstruir quedó uno.
  - **Diccionario:** conceptos nuevos de gas `inspeccion_periodica` (fijo, **puntual**; aprobado) y `otros_servicios` (fijo, periodo; propuesto, para «ServiElectric Xpress» de 2024); alias «total iva*» para luz y gas. `caso_hogar.md` suma esas dos filas a la clasificación (la referencia de los tests), con una nota. `test_diccionario` admite la inspección como el único concepto puntual; `test_construir` actualiza los conteos de las semillas.
  - Ocho ejemplos más en `ejemplos/` (fuera de git); `apoyo_carga.DISTINTOS` = 17. `tests/test_parsers_variantes.py` tiene 15 tests.
  - Sobre el proyecto real, `reprocesar --pendientes` reconstruyó la base (cambiaron las semillas) y cargó todo: 63 facturas, I1 en todas, 1 pendiente.
- Decisiones de la persona usuaria: el fijo de Digi cuenta como fibra; la inspección del gas es un concepto nuevo; el formato de 2024 tiene parser. También aclaró que la clasificación fijo/variable debería vivir en la capa semántica, no en la base: hoy `concepto.tipo_cargo` es obligatorio en el esquema, así que se cargó igual y queda como pregunta para el dashboard.
- **Desvío: I8 con margen de 10 céntimos.** En el Digi de jul 2025, los servicios suman XK,ZJ € sin impuestos y la base impresa es XJ,XK €; el IVA derivado por servicio (Q,KK €) no daba el impreso (J,XJ €). La persona usuaria decidió que I8 admita hasta 10 céntimos de diferencia (`extraccion.TOLERANCIA_REPARTO_CENTIMOS`, usada por la validación de forma y por `bd/invariantes.py`). I1 sigue exacta. Los tests de I8 pasan a una diferencia de 11 céntimos y hay otros que aceptan 1 y 10. Desvío respecto de R5 y R33 (tolerancia 0), anotado en `docs/diseno.md` §10 y §18.
  - Resultado final: 64 facturas, 0 pendientes, I1 en todas.
- **Criterio de la persona usuaria: la interpretación va a la capa semántica.** Además de fijo/variable, la clasificación de meses completos o incompletos (cobertura, R26) va en la capa semántica, no en la base. Por eso no se cargan fechas de baja. Hoy `concepto.tipo_cargo` y las vistas de cobertura están en la base: llevarlos a la capa semántica se decide al armar el dashboard.
- Queda pendiente: la luz y el gas de 2024 son contratos aparte («luz 2», «gas 2»), porque el proveedor es otro; `estado` marca como incompletos los meses de los contratos terminados, hasta que se decida lo de la capa semántica. Confirmar `otros_servicios` (ServiElectric).
- Cómo verificarlo: `.venv\Scripts\python -m pytest -q --tb=short tests\test_parsers_variantes.py tests\test_carga.py`; `… -m facturas estado`; `… -m facturas contratos`.

### Planificación del dashboard (2026-10-06)
- Estado: aprobado (2026-10-06). La persona usuaria definió la fase del dashboard respondiendo preguntas, y pidió que siga los mismos estándares que los bloques.
- Qué se hizo:
  - **`task_dashboard.md`:** la especificación del dashboard en Streamlit, en 4 etapas: capa semántica y datos; Overview; Analysis (3a Water, 3b Electricity y Gas, 3c DIGI); y sacar la interpretación de la base. Tiene la misma estructura que `tarea.md` y sus bloques: modelo sugerido por etapa, OODA, definición de terminado, punto de control con aprobación y commit `dashboard N:`. Sin revisión técnica independiente, por decisión de la persona usuaria.
  - **Uso eficiente de tokens** (a pedido, según `buenas_pract.md`): cada etapa lee solo sus secciones de `task_dashboard.md` (la lista está en «Etapas»), el agente verifica con `AppTest` sin abrir la app ni tomar capturas, `dataviz` se carga solo en las etapas 2 y 3a, y la etapa 4 lista los archivos afectados con un `grep`.
  - Ficha de la etapa 1: `docs/fichas/d1_capa_semantica.md`. Referencias a la tarea en `CLAUDE.md`, `docs/estado.md` y la ficha del bloque 7. `tarea.md` no se toca, porque es la especificación genérica que se copia al replicar el proceso.
- Decisiones de la persona usuaria (detalle en `task_dashboard.md`):
  - Overview por mes con el gasto prorrateado; Analysis por factura.
  - Agrupaciones en un TOML de la capa semántica, no en la base.
  - Grupos de cada servicio. En el agua, ciclo del agua (w₁) y residuos (w₂), con el IVA dentro del ciclo; en luz y gas, los impuestos como grupo propio.
  - Cascada de efecto volumen y efecto precio, que compara por defecto con el mismo período del año anterior.
  - Meses incompletos marcados, con la opción de excluirlos.
  - Selector de período arbitrario.
  - Interfaz en inglés.
  - Trabajo por etapas, iterando sobre la app en las etapas visuales.
- Desvíos respecto de la especificación, y por qué:
  - Respecto del caso: los desgloses del Analysis usan los grupos de la capa semántica en lugar de `tipo_cargo`, y la cobertura se calcula en la capa semántica, por el criterio de la persona usuaria (la interpretación no va en la base).
  - Respecto de `tarea.md`, definición de terminado, punto 6: lo específico del caso también puede vivir en `src/facturas/dashboard/semantica.toml`.
- Pendiente: la etapa 1 (ficha `d1`). La etapa 4 modifica `caso_hogar.md` y `requisitos.md` solo con autorización expresa.

### Dashboard, etapa 1: capa semántica y datos (2026-10-06)
- Estado: aprobado (2026-10-06), con un cambio en el consumo de las rectificativas
- Qué se hizo:
  - **`src/facturas/dashboard/`:** `semantica.toml` (grupos, conceptos variables y magnitud de cada categoría, con los nombres en inglés para la interfaz), `semantica.py` (`cargar`, `validar`, `meses_completos`) y `datos.py` (`gasto_mensual`, `cobertura_mensual`, `importes_por_factura`, `consumo_por_factura`, `facturas` y `cascada`). Solo biblioteca estándar; lee solo vistas.
  - **Tests:** `tests/test_dashboard_semantica.py` (16) y `tests/test_dashboard_datos.py` (19). Arman en el test un segundo período de agua (con otro contrato) y de gas, y una rectificativa por diferencias del gas. La cascada del agua se calculó a mano. `test_codigo.py`: `"dashboard": {"bd"}`; se comprobó en una copia que un `import facturas.carga` en `dashboard` lo hace fallar.
  - `docs/diseno.md` §14: el árbol, los tests, la regla de dependencias y `semantica.toml` como lugar de lo específico del caso.
  - **Evidencia sobre la base real:**
    - la suma de todos los meses (Q.JKQ,KZ €) es igual a la de `v_factura_vigente`, y también por categoría contra el grano por factura;
    - I1 en las 63 facturas del grano por factura (la rectificativa se suma a su original);
    - las 40 cascadas entre facturas consecutivas de agua, gas y luz cuadran exactas;
    - ningún concepto sin clasificar.
- Decisiones no previstas en la especificación:
  - **Conceptos variables** (propuesta, con evidencia de las facturas reales): agua `consumo_agua`, `canon_agua` y `alcantarillado`; gas `consumo_gas` e `impuesto_hidrocarburos`; luz `consumo_electricidad`.
    - El alcantarillado sale a K,JZZZ–X,KZQX €/m³ en las 10 facturas.
    - El canon, a J,XK €/m³ hasta 2025 (con 10 m³ cobra 12), y en 2026 suma una parte fija.
    - El impuesto de hidrocarburos, a Z,XJZZ €/kWh hasta 2025 y X,JXZQ en 2026.
    - **El IVA no es variable en ningún servicio:** en el agua es el 10 % de la cuota y el consumo (por ejemplo, Q,ZZ = 10 % × (QX,XX + JQ,KK)), y más de la mitad grava la cuota fija. El precio unitario es sin IVA.
  - **Cobertura:** un día está cubierto si cae en el período de una factura vigente con alguna línea `periodo` de la categoría, con cualquier contrato, sin fechas de alta ni de baja. Una rectificativa por diferencias no cubre días. `cobertura_mensual` devuelve todas las categorías y meses del rango pedido, también los que no tienen facturas (0 días).
  - **Grano por factura:** factura vigente × contrato. Una rectificativa por diferencias toma el `factura_id`, las fechas y los días de la que corrige (la relación sale de `numero_factura_corregida` en SQL; los números no salen de `datos.py`).
  - **Cascada:** el efecto volumen se redondea al céntimo y el efecto precio es la diferencia: cada efecto queda a menos de medio céntimo de su fórmula y la cascada cuadra exacta en céntimos. Cada grupo aporta la diferencia de su parte no variable; un grupo sin conceptos fijos (la energía de luz y gas) no tiene paso.
  - **Validaciones:** los errores de estructura del TOML y los códigos que no existen en la base lanzan `ErrorSemantica`, con el concepto y la categoría. Un concepto de la base sin grupo no es un error: `validar` lo devuelve para que la interfaz avise y va al grupo `sin_clasificar` («Unclassified»).
  - **Nombres en inglés** de categorías, grupos y conceptos en el TOML, porque la interfaz va en inglés y la base los tiene en español.
  - El consumo incluido en el plan móvil (siempre 0 €) va en el grupo de la cuota.
- Desvíos respecto de la especificación, y por qué:
  - «Los grupos y los códigos del TOML existen en la base»: los grupos no están en la base. Se verifican las categorías y los conceptos (contra `v_dim_concepto`) y la magnitud (contra las mediciones de la categoría, porque no hay vista de magnitudes; sin mediciones no se puede comprobar).
  - «Cobertura por servicio» en `semantica.py`: la consulta está en `datos.py` (es una tabla por mes) y la regla que combina varios servicios en `semantica.py`.
  - R32 se verifica con un test estático: los `FROM`/`JOIN` de `datos.py` y `semantica.py` son vistas o sus CTE. El autorizador de SQLite no servía, porque informa como lecturas de primer nivel las tablas de las vistas que aplana.
- Cómo verificarlo: `.venv\Scripts\python -m pytest -q --tb=short tests\test_dashboard_semantica.py tests\test_dashboard_datos.py tests\test_codigo.py`.
- Al aprobar, la persona usuaria:
  - confirmó `otros_servicios` (ServiElectric, 2024, Q,QZ €) en «Other fixed» del gas;
  - decidió que una factura estimada que se rectifica suma los consumos y queda con lectura real. `consumo_por_factura` suma en una sola fila por franja con el tipo de lectura de la rectificativa: el gas de abr–jun 2026 queda con 138 kWh reales (344 estimados − 206). La base sigue guardando las dos facturas (el PDF de la rectificativa es un hecho); la unión es del grano por factura del dashboard, que ya tomaba el `factura_id`, las fechas y los días de la original.
- Pendiente: ninguno de la etapa.

### Dashboard, etapa 2: esqueleto y Overview (2026-10-06)
- Estado: aprobado (2026-10-06), tras una ronda de cambios de estilo (ver «Cambios tras ver la app»)
- Qué se hizo:
  - **App:** `app.py` (navegación Overview / Analysis), `paginas/overview.py`, `paginas/analysis.py` (vacía, con las pestañas Water, Electricity, Gas y DIGI) y `graficos.py` (color de cada servicio, formato de importes, barras apiladas por mes y reparto por servicio).
  - **`datos.py`:** `abrir()`, `meses_entre`, `meses_del_periodo`, `quitar_incompletos`, `serie_mensual`, `total_por_categoria` y `gasto_medio`.
  - `scripts\dashboard.ps1`; `streamlit 1.65.0` y `plotly 7.1.0` instalados y `requirements.txt` regenerado con `pip freeze` (sus dependencias incluidas); `CLAUDE.md` y `docs/diseno.md` §14 al día.
  - **Tests:** `tests/test_dashboard_app.py` (5, con `AppTest` sobre una base de prueba) y 5 nuevos en `tests/test_dashboard_datos.py` (períodos, casilla, serie, gasto medio).
  - **Evidencia sobre la base real** (`AppTest`, solo lectura): «All history» con todos los servicios da Q.JKQ,KZ € (QZQKZQ céntimos), igual a la suma de `v_factura_vigente`; ZZQ,KK €/mes sobre 25 meses; 8 meses incompletos (ago–dic 2024 y jun–ago 2026), y con la casilla, Z.ZQK,KK € en 17 meses.
- Decisiones no previstas en la especificación:
  - **Histórico** = del primer al último mes con gasto: los meses futuros (hoy, sept–oct 2026) no cuentan como meses con gasto 0. «Year to date» llega hasta el último mes con datos; «Last 12 months» son los 12 que terminan en el mes de hoy, dentro del histórico (hoy, nov 2025–ago 2026, 10 meses).
  - **Gasto medio mensual** = total / meses del período (tras excluir los incompletos si la casilla está marcada). Un mes sin gasto dentro del histórico cuenta como 0.
  - **Formato de importes** (propuesta): `1.234,56 €`; los meses, `Aug 2026`. Cambiarlo es tocar `formato_importe` y `formato_mes`.
  - **Colores:** las cinco primeras ranuras de la paleta de referencia, en orden fijo: agua azul, luz naranja, gas aguamarina, fibra amarillo, móvil rosa. Validadas en claro y oscuro (adyacentes: CVD 9,1 / 8,4, visión normal 19,6 / 19,3). Tres colores claros quedan por debajo de 3:1 contra el fondo, así que hay etiquetas visibles y el gráfico de reparto las lleva.
  - **Meses incompletos** en el gráfico: barras rayadas, con una nota. Reparto por servicio: barras horizontales con importe y porcentaje (no un gráfico circular).
  - **Base de los tests de la app:** `datos.RUTA_BASE`, que los tests reemplazan; la ruta es parte de la clave de la caché (`st.cache_data`, `ttl="5m"`), y la conexión se abre y se cierra dentro de la función cacheada.
- Desvíos respecto de la especificación: ninguno.
- Cómo verificarlo: `.venv\Scripts\python -m pytest -q --tb=short tests\test_dashboard_app.py tests\test_dashboard_datos.py tests\test_dashboard_semantica.py tests\test_codigo.py`; la app, con `scripts\dashboard.ps1`.
- Cambios tras ver la app (la persona usuaria, 2026-10-06), solo de estilo y formato, sin tocar carga, base ni datos:
  - **Servicios:** `st.pills` de selección múltiple (`key="service_filter"`) con el CSS de `bi-hogar/styling.py` adaptado: cada botón activo lleva el color de su servicio, con el fondo al 30 % de opacidad y el borde sólido (el selector es el id del botón, `<widget>-<posición>`, no verificado en un navegador); los colores, el orden (gas, luz, agua, wifi, móvil) y la etiqueta «Wifi» (en `semantica.toml`, `nombre` de fibra) son los de `bi-hogar`. Colores: gas `#d95926`, luz `#c98500`, agua `#3987e5`, fibra `#199e70`, móvil `#d55181`.
  - **Tema oscuro fijo:** `.streamlit/config.toml` copiado de `bi-hogar`. `graficos.py` ya no tiene variantes claras; saca `_oscuro()`.
  - **«Last 12 months»:** los 12 últimos meses con datos, no los que terminan hoy. Ahora son sep 2025–ago 2026.
  - **Meses incompletos:** barras a media opacidad y « (partial)» en el hover, como en `bi-hogar` (el rayado no se veía).
  - **Eliminado** el gráfico «Share by service». En su lugar, la persona usuaria pidió las tres opciones propuestas, una debajo de otra:
    - **Trend:** total de cada mes y su media móvil de 3 meses (`datos.media_movil`, solo con meses seguidos: sin los meses excluidos por incompletos no hay media);
    - **Year over year:** cada mes frente al mismo mes un año antes (`datos.interanual`); el año anterior sale de todo el histórico, aunque quede fuera del período, y los meses sin mes comparable se omiten;
    - **Service mix:** barras al 100 % por servicio y mes, con los incompletos a media opacidad.
  - Tests nuevos en `test_dashboard_datos.py`: `media_movil`, `interanual`, `total_mensual`.
- Pendiente: ninguno de la etapa.

### Dashboard, etapa 3a: Analysis, Water (2026-10-06)
- Estado: aprobado (2026-10-07), junto con la 3b y la 3c, sin cambios
- Qué se hizo:
  - **`paginas/analysis.py`:** `_servicio(categoria, …)` es el patrón común de una pestaña con volumen: composición por grupo, pesos de cada grupo (wᵢ), desglose por concepto, volumen, precio unitario efectivo y cascada entre dos facturas. Una sola lectura cacheada (`@st.cache_data(ttl="5m")`) trae facturas, importes, consumos y los conceptos sin clasificar, que se avisan arriba.
  - **`graficos.py`:** `RANURAS` y `color_ranura`, `apiladas` (barras por factura, en euros o al 100 %), `volumen_por_factura`, `precio_unitario`, `cascada`, `formato_numero`, `formato_periodo`.
  - **`datos.py`:** `importes_por_grupo`, `importes_por_concepto`, `cambios_de_contrato` y `factura_del_anio_anterior` (el pendiente heredado de la etapa 1).
  - **Tests:** `test_dashboard_app.py` pasa de 6 a 17 tests (11 de Water, con los valores de la cascada calculados a mano) y `test_dashboard_datos.py` de 27 a 33. Los helpers que comparten (`variante`, la segunda factura de agua y de gas, la rectificativa del gas) pasaron a `datos_prueba.py` y `base_completa`, a `conftest.py`. El test de las cuatro pestañas leía la base real; ahora usa una de prueba.
  - **Evidencia sobre la base real** (`AppTest` en solo lectura contra SQL directo, sin pasar por `datos.py`):
    - la composición de Water suma, factura a factura, el `importe_total_centimos` de `v_factura_vigente` (10 facturas, JJQ,ZJ €);
    - la cascada por defecto, 11 abr–10 jun de 2025 (QX,XQ €, 17 m³) → 10 abr–8 jun de 2026 (ZX,KK €, 15 m³): volumen −K,QQ €, precio +X,JZ €, ciclo del agua (parte fija) +Z,QZ € y residuos +K,JX €; A más los pasos da B exacto, y el volumen y el precio recalculados desde SQL coinciden.
- Decisiones no previstas en la especificación:
  - **Mismo período del año anterior:** se desplaza el período de la última factura un año atrás y, entre las facturas de la categoría (con cualquier contrato) que lo solapan, se toma la de punto medio más cercano. Sin ninguna, la comparación empieza por «Previous invoice» y la opción del año anterior avisa de que no hay factura.
  - **Selector de comparación:** botones de radio (año anterior, factura anterior, elegir dos); con «Pick two invoices» salen dos listas, con las facturas más recientes primero. Un conmutador amplía la cascada para ver los cambios pequeños frente a los totales: el eje no parte de cero y se dice. Está apagado por defecto.
  - **Cascada:** subir el gasto va en rojo y bajarlo en azul (el par divergente de la paleta), los totales en gris, y cada barra lleva su importe con signo. Un grupo con un concepto variable (el ciclo del agua) aparece como «Water cycle (fixed part)», porque solo cuenta lo que no depende del volumen. Los totales llevan los días de su período.
  - **Colores:** cada grupo toma la ranura de la paleta de `dataviz` (modo oscuro) que corresponde a su posición en `semantica.toml`, y cada concepto, la de su posición dentro del grupo. Los gráficos de una sola serie (volumen y precio) usan el color del servicio. Se validó con `validate_palette.js` sobre el fondo `#0d0d0d`: pasa todo (CVD adyacente 8,4; visión normal 19,3).
  - **Eje x:** una posición por factura con el texto del período («11 Oct–12 Dec» y el año), no una categoría, porque dos facturas pueden tener el mismo texto. Con más de 12 facturas, el mes del fin del período en vertical.
  - **Pesos:** barras al 100 % por factura (cada una suma 100 %) y, debajo, una línea con los pesos de la última factura.
  - **Desglose por concepto:** un gráfico por grupo, en dos columnas. Un grupo con un solo concepto no se repite.
  - **Cambio de contrato o de comercializadora:** una línea vertical «Contract change» en los gráficos por factura y un aviso con los alias y los proveedores. La serie sigue siendo una. En el agua real no hay ninguno.
- Desvíos respecto de la especificación: «Desglose por concepto dentro de cada grupo» no repite un grupo que tiene un solo concepto (sería el mismo gráfico que la composición).
- Observaciones sobre las herramientas: `AppTest.select_index` falla con un `format_func` (vuelve a formatear el texto ya formateado); los tests eligen con `set_value` y la posición de la factura. `AppTest` recorre primero la columna izquierda de un `st.columns`.
- Cómo verificarlo: `.venv\Scripts\python -m pytest -q --tb=short tests\test_dashboard_app.py tests\test_dashboard_datos.py tests\test_dashboard_semantica.py tests\test_codigo.py`; la app, con `scripts\dashboard.ps1`, página Analysis, pestaña Water.
- Pendiente: ninguno de la etapa.

### Dashboard, etapa 3b: Analysis, Electricity y Gas (2026-10-06)
- Estado: aprobado (2026-10-07), junto con la 3a y la 3c, sin cambios
- Qué se hizo:
  - Electricity y Gas usan `_servicio`, sin cambios en el patrón, más lo suyo:
    - **Lecturas estimadas frente a reales** (las tres pestañas con volumen): el volumen se dibuja como dos series, «Real reading» y «Estimated reading» (media opacidad y leyenda); una factura estimada lleva «estimated» en el eje de todos los gráficos por factura, y debajo del volumen se cuentan («1 of 3 invoices are based on estimated readings (344 of 860 kWh)…»). `datos.facturas_estimadas`.
    - **Electricity, consumo por franja:** barras apiladas de kWh por factura en punta, llano y valle («Peak», «Standard», «Off-peak»). `datos.consumo_por_franja`.
  - **Tests:** 6 de Electricity y Gas en `test_dashboard_app.py` (de 17 a 23; con una factura de hace un año de cada servicio, la del gas estimada) y 3 en `test_dashboard_datos.py` (de 33 a 36). Las cascadas de la luz (ZQ,JJ → XJ,ZZ €) y del gas (KJ,ZJ → KQ,KZ €) están calculadas a mano.
  - **Evidencia sobre la base real:**
    - la composición suma, factura a factura, el total de `v_factura_vigente`: luz 22 facturas (JXJ,QJ €) y gas 11 (ZXQ,ZZ €, con la rectificativa sumada a su original);
    - cascada por defecto de la luz: 1–29 jun de 2025 (KK,KX €, 126 kWh) → 27 may–28 jun de 2026 (XJ,ZZ €, 81 kWh): volumen −Z,JJ €, precio +Z,ZX €, potencia +X,QQ €, otros fijos +K,QK € e impuestos −K,ZJ €;
    - cascada por defecto del gas: 25 abr–25 jun de 2025 (XZQ,JQ €, 1.305 kWh) → 30 abr–25 jun de 2026 (QJ,KX €, 138 kWh): volumen −JX,QJ €, precio −Q,KZ €, término fijo +J,ZZ €, otros fijos −ZJ,JJ € e impuestos (parte fija, el IVA) −JX,ZJ €;
    - ambas cuadran exactas, y el volumen y el precio recalculados desde SQL coinciden;
    - marcas: 6 de las 11 facturas de gas son estimadas (la 2.ª, 3.ª, 4.ª, 7.ª, 8.ª y 9.ª; la de abr–jun de 2026, rectificada, cuenta como real); la luz es toda de lectura real; los dos servicios tienen un cambio de contrato, antes de la 4.ª factura (luz 2 → luz 1, desde el 1 de enero de 2025; gas 2 → gas 1, desde el 26 de febrero de 2025).
- Decisiones no previstas en la especificación:
  - **Una factura es estimada** si alguna medición de la magnitud del servicio lo es. Las otras magnitudes (la potencia) no cuentan.
  - **Colores de las franjas:** las ranuras 4 a 6 de la paleta. Las 0 a 3 son de los cuatro grupos de la luz, que están en la misma pestaña; así un color nunca significa dos cosas en una pestaña.
  - **Nombres de las franjas en inglés:** una constante de `analysis.py`, no `semantica.toml` (no son del caso: son las de la tarifa).
  - La luz tiene 22 facturas: el eje usa el mes del fin del período, en vertical.
- Desvíos respecto de la especificación: ninguno.
- Cómo verificarlo: igual que la 3a; pestañas Electricity y Gas.
- Pendiente: ninguno de la etapa.

### Dashboard, etapa 3c: Analysis, DIGI (2026-10-06)
- Estado: aprobado (2026-10-07), junto con la 3a y la 3b, sin cambios
- Qué se hizo:
  - **Pestaña DIGI** (`_digi`), con el patrón sin volumen ni cascada. Cada línea (contrato de fibra o de móvil) es un grupo: composición por línea (con su IVA), pesos de cada línea, desglose de cada línea por grupo del TOML (cuota, consumo adicional y el IVA aparte) y el gráfico de cuotas con los cambios marcados. Un texto lista las líneas con sus meses.
  - Refactor de `analysis.py` para compartir `_grupos`, `_composicion_y_pesos` y `_desgloses` entre `_servicio` y `_digi`.
  - **`datos.py`:** `facturas_enteras` (una fila por factura sumando sus líneas) y `cambios_de_cuota`. **`graficos.cuotas_por_linea`.**
  - **Tests:** 6 de DIGI en `test_dashboard_app.py` (de 23 a 29; tres facturas, con una fibra que desaparece y cuotas que cambian) y 3 en `test_dashboard_datos.py` (de 36 a 39); los valores están calculados a mano.
  - **Evidencia sobre la base real:** la composición suma el total de `v_factura_vigente` en las 20 facturas de DIGI (QXQ,QK €); las líneas son fibra 1, fibra 2, movil 1 y movil 2; hay 8 cambios de cuota.
- Decisiones no previstas en la especificación:
  - **«El IVA aparte»:** el IVA de cada línea va dentro de su importe en la composición y los pesos (así cada factura suma su total) y aparte en el desglose de la línea.
  - **Cambio de cuota:** una cuota distinta de la de la factura anterior de esa línea, sin IVA. La primera factura de una línea no cuenta. Los meses prorrateados (el primero y el último de una línea) salen como cambios, y el texto lo dice: en los datos, movil 1 pasa de Z,QX € a Q,XJ € en su segundo mes y fibra 2 de X,KX € a Z,XK € en el último. Los otros cambios son de la cuota: en oct 2025, fibra 1 baja de QK,KQ € a QX,QJ €, movil 1 de Q,XJ € a J,QX € y movil 2 de Z,XQ € a K,XQ €, y en nov fibra 1 y movil 2 vuelven a su cuota (movil 1 baja a Z,ZX €, su último mes, prorrateado).
  - Los cambios se marcan con un rombo en el gráfico y se listan debajo, con el período, el importe anterior y el nuevo.
  - **Sin marca de cambio de contrato:** en DIGI el proveedor no cambia y las líneas aparecen y desaparecen, así que se listan con sus meses.
  - **Colores:** las líneas toman las ranuras 0 a 3 y los grupos dentro de una línea, desde la 4 (cuota, IVA y consumo adicional, con el mismo color en todas las líneas).
- Desvíos respecto de la especificación: ninguno.
- Cómo verificarlo: igual que la 3a; pestaña DIGI.
- Pendiente: ninguno de la etapa.

### Dashboard, etapa 4: interpretación fuera de la base (2026-10-07)
- Estado: aprobado (2026-10-07), sin cambios.
- Qué se hizo:
  - **Esquema (versión 2):** se quitaron la tabla `tipo_cargo`, `concepto.tipo_cargo_id` con su índice, `v_dim_tipo_cargo`, las columnas `tipo_cargo_*` de `v_dim_concepto`, `v_linea`, `v_hecho_gasto_diario` y `v_hecho_gasto_mensual`, y las vistas `v_hecho_cobertura_contrato_mensual` y `v_hecho_cobertura_categoria_mensual`. La semilla `tipo_cargo.csv` se borró y `concepto.csv` perdió su columna `tipo_cargo`. Huella nueva en `test_conexion.py`.
  - **Consultas de referencia:** C2 devuelve solo el gasto mensual por categoría, C3 se borró, C4 agrupa por concepto y C5 recibe `:conceptos` (arreglo JSON) en lugar de `:tipo_cargo`.
  - **`estado`:** los meses incompletos salen de `dashboard.datos.cobertura_mensual`, por categoría y desde el primer hasta el último mes con gasto.
  - **Diccionario:** `docs/diccionario.md` lista cada concepto con su código.
  - **Tests:** se quitaron los 4 tests de `test_vistas.py` que probaban las vistas de cobertura (la regla se prueba en `test_dashboard_datos.py`, contra los mismos controles del caso) y el de C3; los que usaban la cobertura como observable (abonos, sustitución, línea puntual) la leen con `datos.cobertura_mensual`. Los que comparaban el tipo de cargo con el caso (`test_parsers.py`, `test_diccionario.py`) ahora solo comparan conceptos.
  - **Base real:** reconstruida con `reprocesar --todo` (64 facturas).
- Evidencia: 556 tests pasan y se salta 1 (el del plan B en pausa; antes, 562 y 1: se quitaron 6 de cobertura y C3). Sobre la base real: el total de todos los meses es QZQKZQ céntimos, igual al de `v_factura_vigente`; las 96 filas factura × contrato suman su total; las 40 cascadas consecutivas de agua, luz y gas cuadran; cada servicio suma lo de siempre (agua JJQ,ZJ €, luz JXJ,QJ €, gas ZXQ,ZZ €, DIGI QXQ,QK €); `estado` verifica I1 en las 64 facturas.
- Decisiones no previstas en la especificación (elegidas por la persona usuaria al aprobar la lista de archivos):
  - **`caso_hogar.md`, `requisitos.md` y `tests/caso.py` no se modifican.** Quedan con vocabulario que ya no coincide con la base (tipo de cargo, R26).
  - **C2–C5 se ajustan** (no se borran), para que haya una referencia SQL independiente del dashboard.
  - **`estado` reutiliza la cobertura del dashboard.** Cambia lo que informa: antes, por contrato, hasta el mes en curso y con las fechas de alta y baja.
- Desvíos respecto de la especificación: la base ya no clasifica los conceptos por tipo de cargo, así que ningún test compara esa clasificación con el caso. La clasificación que queda (grupos y conceptos variables) está en `semantica.toml`, y su evidencia es la de la etapa 1 (cuadre de grupos y cascadas).
- Observaciones: la reconstrucción cambió el alias por defecto de fibra y de móvil (excepción conocida D7): `movil 1` y `movil 2` intercambiaron sus contratos, igual que `fibra 1` y `fibra 2`; los del gas y la luz volvieron a los de antes. Los importes no cambian.
- Cómo verificarlo: `.venv\Scripts\python -m pytest -q --tb=line`; `$env:PYTHONPATH = "src"; .venv\Scripts\python -m facturas estado`; `git diff docs/diccionario.md` tras regenerarlo no muestra cambios.
- Pendiente: `contrato.fecha_alta` y `fecha_baja` (y `contrato --alta/--baja`) ya no tienen consumidor; decidir si se quitan (bloque 7 o antes). D7, sin cambios.

### Contrato: quitar fecha_alta y fecha_baja (2026-10-07)
- Estado: hecho a pedido de la persona usuaria (opción A de `prompt_esquemas.md`, parte A); pendiente de su visto bueno.
- Qué se hizo:
  - **Esquema (versión 3):** se quitaron `contrato.fecha_alta`, `contrato.fecha_baja` y sus tres `CHECK`, y las dos columnas de `v_dim_contrato`. El trigger de identidad de `contrato` ahora dice que solo se modifica el alias. Huella nueva en `test_conexion.py`.
  - **Código:** `construir.py` (`leer_ajustes` rechaza cualquier campo que no sea `alias`; `aplicar_ajustes`), `volcado.py`, `operacion/ajustes.py` (`contrato` solo acepta `--alias`; `contratos` lista alias, categoría y proveedor) y `__main__.py` (sin `--alta` ni `--baja`).
  - **Tests:** se ajustaron `test_ajustes.py`, `test_carga.py`, `test_construir.py`, `test_integridad.py`, `test_respaldo.py` y `test_conexion.py`. Se quitaron los tests de fechas inválidas y de «alta posterior a la baja», y el de fechas se reemplazó por uno de dos cambios de alias sobre la misma entrada del archivo.
  - **Docs:** `docs/diseno.md` (§1.4 E7, C13, tabla de `contrato`, `v_dim_contrato`, §14.2, §16.2), `CLAUDE.md` (comandos) y las fichas `04_carga` y `07_cierre`.
  - **Base real:** reconstruida con `reprocesar --todo`; el respaldo previo no se pudo hacer con `respaldar` (el código nuevo rechaza la base v2), así que se copiaron `facturas.db` y `ajustes_manuales.json` a la carpeta temporal de la sesión antes de reconstruir.
- Evidencia: antes y después, 64 facturas, QZQKZQ céntimos (Q.JKQ,KZ €), 9 contratos y 443 líneas; `estado` sale con 0 y sin pendientes; `docs/diccionario.md` no cambia.
- Decisiones no previstas en la especificación: un campo desconocido en `ajustes_manuales.json` (por ejemplo `fecha_alta` de un archivo viejo) se rechaza al leerlo, como cualquier campo de más.
- Desvíos respecto de la especificación: `requisitos.md` (R41), `tarea.md` y `caso_hogar.md` no se modificaron y quedan desfasados en lo de las fechas.
- Cómo verificarlo: `.venv\Scripts\python -m pytest -q --tb=line`; `$env:PYTHONPATH = "src"; .venv\Scripts\python -m facturas estado`; `grep -rn 'fecha_alta\|fecha_baja' src tests` no encuentra nada.
- Pendiente: ninguno de esta parte. Sigue la Parte B de `prompt_esquemas.md` (esquemas resumen).

### Decisiones previas al bloque 7 (2026-10-08)
- D7: los 9 alias actuales se fijaron en `datos/ajustes_manuales.json` con `contrato <alias> --alias <alias>` (`movil 1` = la línea que indicó la persona usuaria), sin código nuevo. Un contrato futuro no queda fijado solo: el README explica el aviso de `reprocesar --todo`.
- Desvío: el README no incluye «registrar una fecha de alta o de baja» (bloque 7, Mantenimiento), porque esas fechas se quitaron en la versión 3 del esquema.

### Bloque 7: Cierre (2026-10-13)
- Estado: aprobado (2026-10-13). El plan B queda pendiente, sin fecha: quizá se haga en un futuro lejano.
- Qué se hizo:
  - **`README.md`** (en español, decisión de la persona usuaria): qué hace, con un diagrama Mermaid del flujo; instalación desde cero (ruta corta, política de ejecución, `.venv`, hook, `datos/entrada` y `config.toml`, la base con el primer `cargar`, el disparador y los tests); operación diaria (dónde termina cada PDF, notificaciones, `estado`, arreglar un pendiente a pedido, el dashboard y qué responde cada página); mantenimiento (copias, restaurar, reconstruir, alias y su aviso de D7, agregar un proveedor, el disparador, `pypdf`); el plan B con git; cómo replicarlo con otros datos; cómo se construyó.
  - **`docs/guia_carga_historica.md`:** dejar los PDFs, qué esperar (las etapas de rechazo y lo que pasó con el histórico real: 39 de 64 en la primera pasada), huecos y solapes con `estado`, totales por año (dashboard o un comando sobre `v_hecho_gasto_mensual`) y las particularidades del caso.
  - **`LICENSE`:** MIT, a pedido de la persona usuaria, con el usuario de git como titular.
  - **Tests sin los PDFs de ejemplo:** `apoyo_carga.ejemplo()` salta el test con un mensaje si falta el PDF, como los tests de parsers desde el bloque 3; `poner()`, `test_carga` y `test_respaldo` lo usan. En un clon sin `ejemplos/` fallaban 45 tests y 38 daban error; ahora 403 pasan y 152 se saltan.
  - **`config.toml` con BOM:** `Set-Content -Encoding utf8` y `Out-File` de PowerShell 5.1 escriben un BOM, y `tomllib` lo rechazaba («Invalid statement»). Se lee con `utf-8-sig`; test nuevo `test_una_configuracion_con_bom_se_acepta`.
  - **Notificación del plan B:** remitía a `scripts\revisar_propuesta.ps1`, que no existe (la parte B del bloque 6 no se hizo). Ahora dice «Rama <rama>: cómo revisarla, en el README (Plan B)»; `test_plan_b` comprueba el texto nuevo.
- Revisión final:
  - **Tests:** 554 pasan y se salta 1 (el del plan B en pausa).
  - **Datos personales:** ningún hallazgo en los 431 archivos de todas las versiones del historial ni en los mensajes de commit (con los patrones del hook, los 27 valores de `datos/datos_privados.txt` y los 12 identificadores de `ejemplos/identificadores_esperados.json`), ni en los 134 archivos que se versionan ahora (con, además, los números de factura con el formato de los nombres de archivo). Los mensajes de commit solo tienen el email `noreply` de los `Co-Authored-By`.
  - **Lógica del caso:** no hay códigos de concepto, NIF de proveedores ni categorías en el código genérico (`src/` sin `parsers/`, `semillas/` ni `dashboard/`, y `scripts/`). Solo aparecen en comentarios de C5–C7 y de `bd/invariantes.py`. El dashboard sí es específico del caso: está fuera del alcance de `tarea.md` y tiene su propia especificación (`task_dashboard.md`). Los tests leen el caso a propósito (`tests/caso.py`).
  - **Reconstrucción con los datos reales**, en una copia: con la base presente, `reprocesar --todo` da un volcado idéntico (68 facturas, ZJQQKX céntimos, los 9 ajustes). Sin la base, todo es igual salvo `carga.nombre_archivo`, que pasa a ser el nombre normalizado de `procesadas/` (el original solo está en la base); el README lo explica y recomienda restaurar.
  - **Restauración con los datos reales:** desde una copia local de la instantánea `20261009_132111` (no se escribió en Google Drive), en una copia del proyecto: volcado idéntico, ajustes idénticos y 68 PDFs repuestos.
- **Prueba de punta a punta** (2026-10-13), en un clon del proyecto en el scratchpad con los cambios de la sesión, `datos/` vacío, su propia carpeta de respaldo y su propio disparador (`f58c4283`; el real, `c1de00ea`, siguió corriendo). Se siguieron los pasos 4 a 7 del README tal cual (el 6 dijo «No había base: se construyó.»).
  1. `agua.pdf` en `datos/entrada/`, sin intervenir: en 25 s, «Lote listo», carga con código 0 y el aviso «Facturas: 1 factura cargada»; el PDF en `procesadas/agua/2026/`; `estado` con ZX,KK € y los meses incompletos abr 21/30 y jun 8/30; `v_hecho_gasto_mensual` con ZZ,JK / ZK,KX / X,KJ € (los del caso); instantánea, ajustes y PDF en la carpeta de respaldo. Después, `luz.pdf`, `gas.pdf` y `fibra_movil.pdf` juntos: un lote, «3 facturas cargadas».
  2. Un PDF de un proveedor desconocido: a `pendientes/` con `Etapa: formato`, el aviso «Facturas: 1 pendiente», y `estado` lo lista. `plan_b.ps1 … -Simular`: rama `propuesta/desconocido-…`, worktree en `..\e2e-propuestas\`, informe «SIMULACIÓN» y aviso con el texto nuevo. Revisión con los comandos del README (`git branch --list`, `git show` del informe, `git diff`) y rechazo con `Quitar-Worktree`: sin rama ni worktree, `main` igual, `git status` limpio, el PDF sigue pendiente, el intento queda registrado, el `.venv` intacto y la base idéntica.
  3. `tests/test_consultas.py` contra la base cargada por el disparador (no la escrita a mano): las 11 comprobaciones de C1, C2 y C4–C7 pasan con los valores del caso. La cobertura de `estado` coincide con el caso (mayo: agua y gas completos, luz 5/31; junio: 8/30, 25/30 y 28/30). El dashboard (AppTest) abre el Overview (KZX,XX €, la suma de los cuatro) y las cuatro pestañas de Analysis sin excepciones.
  4. `reprocesar --todo`: volcado idéntico.
  5. Se borraron la base, los ajustes y `procesadas/`, y se ejecutó `restaurar <última marca>`: volcado idéntico y 4 PDFs repuestos.
  - Al final se desinstaló el disparador de la copia; el real sigue instalado.
- Decisiones no previstas en la especificación:
  - El diagrama del README es propio y sencillo, en español; los esquemas de `docs/esquemas/` (Parte B de `prompt_esquemas.md`) siguen en borrador y se enlazan cuando se aprueben.
  - README: la carpeta del proyecto va en una ruta corta, porque Windows trae las rutas largas desactivadas y `pip` falla con las rutas internas de Streamlit; `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` una vez (y `Unblock-File` si se baja un ZIP).
- Desvíos respecto de la especificación, y por qué:
  - **Plan B (opción A de la persona usuaria):** no existen `listar_propuestas.ps1`, `revisar_propuesta.ps1`, `aprobar_propuesta.ps1` ni `rechazar_propuesta.ps1`, porque el bloque 6 está en pausa y su parte B no se hizo. El README explica cómo revisar, aprobar y rechazar con git y con `Quitar-Worktree` de `scripts/comun_plan_b.ps1` (que quita antes el enlace al `.venv`), y el paso 2 de la prueba se hizo así.
  - El README no tiene «registrar una fecha de alta o de baja» (anotado el 2026-10-08).
  - Excepciones a «lo específico del caso solo en el caso, las semillas y los parsers»: el dashboard y los comentarios citados arriba.
  - En la copia de la prueba, el `.venv` es un enlace al del proyecto: `pip install -r requirements.txt` falló en el scratchpad por la longitud de la ruta (148 caracteres más las rutas internas de Streamlit). **No verificado:** la instalación de dependencias en un clon nuevo. El `.venv` del proyecto se creó con `py -m venv`, y `requirements.txt` es su lista fijada.
  - La notificación en pantalla no la puede ver el agente: se verificó la línea «Aviso: …» que `Notificar` escribe en el log. El toast lo comprobó la persona usuaria en el bloque 5.
- Cómo verificarlo:
  - `.venv\Scripts\python -m pytest -q --tb=line` → 554 pasan y se salta 1.
  - En un clon sin `ejemplos/` (con `.venv`): los tests pasan o se saltan con «falta ejemplos/…»; ninguno falla.
  - Leer `README.md` y `docs/guia_carga_historica.md`, y probar la instalación desde cero en una ruta corta (por ejemplo, `C:\proyectos\facturas-bi-prueba`) siguiendo solo el README.
  - `$env:PYTHONPATH = "src"; .venv\Scripts\python -m facturas estado` → 68 facturas, I1 en todas.
- Pendiente:
  - La persona usuaria: instalar desde cero siguiendo el README en una ruta corta (lo único que la sesión no pudo verificar).
  - Esquemas (Parte B de `prompt_esquemas.md`): al aprobarlos, enlazarlos desde el README.
  - Plan B: sigue en pausa; qué hacer con él sigue abierto.
  - Antes de publicar en GitHub, decisiones de la persona usuaria: los importes y consumos reales que hay en la bitácora, el caso, `docs/` y los tests, y el email de los commits.

### Importes reales fuera de lo versionado (2026-10-13)
- Estado: aprobado (2026-10-13). Lo pidió la persona usuaria al aprobar el bloque 7 («no mostremos importes reales, reemplaza los números por letras»).
- Decisiones de la persona usuaria, entre las opciones propuestas: facturas ficticias en los tests y los valores reales en archivos locales (opción B); se ocultan solo los euros (importes, bases, totales y precios unitarios, porque precio × cantidad da el importe), y quedan los consumos, las lecturas, las fechas y los recuentos; al publicar, un solo commit con el estado final.
- Qué se hizo:
  - **Letras en la documentación:** la bitácora, el caso, el diseño, las revisiones técnicas, las fichas, `docs/estado.md` y los comentarios de `semantica.toml`, `parsers/comun.py` y `paginas/analysis.py`. Cada cifra pasa a una letra de J, K, Q, X y Z (sin vocales ni W: no forman palabras, ni `kW`); el mismo importe lleva las mismas letras en todo el repositorio, y se conservan el signo, los separadores y el `€`. No se tocan los ejemplos genéricos de formato (`1.234,56 €`), los tiempos de las consultas ni el cero.
  - **`caso_hogar.md`** (a pedido; es especificación): «Valores esperados de los ejemplos» y «Controles de prorrateo y cobertura» van en letras, con una nota. Las mismas secciones con los valores reales están en `ejemplos/valores_esperados.md`, fuera de git como los PDFs.
  - **Tests que leen los PDFs:** `tests/caso.py` lee los valores esperados y los controles del archivo local (si falta, el test se salta); `caso.importes(pdf)` lee `ejemplos/importes_esperados.json`, también local, con lo impreso en los PDFs de variantes y de la ampliación; `caso.mas_centimos` altera un importe del PDF sin escribirlo en el test. En el código quedan los textos y los períodos; los importes, en el archivo local. `test_euros_usa_el_formato_espanol` usa importes inventados.
  - **Facturas ficticias** en `tests/datos_prueba.py`: los mismos conceptos, consumos y fechas que los ejemplos, con importes inventados que suman exacto, IVA cercano a la base por el tipo y el IVA de Digi igual a lo repartido. `datos_prueba.CONTROLES` tiene sus controles de prorrateo, calculados a mano como los del caso (importe × días del mes ÷ días del período); los tests de la base y del dashboard comparan contra ellos. El segundo gas tiene un consumo de 13,50 € para que el efecto precio de su cascada no sea cero. Las facturas propias de `test_dashboard_app.py` (la luz anterior y las dos de DIGI) también son ficticias.
  - **Referencias recalculadas a mano** antes de correr los tests: las cascadas del agua (5,35 / 3,53 / 0,37), la luz (2,53 / 0,43) y el gas (−11,44 / 0,63 / −2,27), los precios unitarios, los pesos, los totales por línea y las cuotas de DIGI. El código dio lo mismo.
  - **`docs/diseno.md` §8.2 y §16:** los ejemplos resueltos usan la factura ficticia de Digi; el reparto por línea y mes se calculó a mano y coincide con `v_hecho_gasto_mensual`. §17 (verificación), en letras.
  - **README**, «Cómo replicarlo»: cómo hacer lo mismo con otro caso.
- Verificación:
  - **Búsqueda de importes reales** en todos los archivos que se versionan, tests incluidos: los 471 importes distintos de la base real (líneas, totales, sumas por mes y por categoría; abierta en solo lectura) y de los dos archivos locales, en euros y en céntimos. Quedan solo coincidencias de números ficticios con algún importe real, tiempos, recuentos, colores y lecturas de contador.
  - **Tests:** 554 pasan y se salta 1, como antes. En una copia sin `ejemplos/` (como quedará en GitHub): 403 pasan y 152 se saltan, ninguno falla.
- Desvíos respecto de la especificación, y por qué:
  - `caso_hogar.md` y `docs/diseno.md` se modificaron a pedido. `tarea.md` dice que los valores esperados del caso salen de facturas reales: siguen saliendo de ahí, pero los reales están en un archivo local, como ya pasaba con los identificadores.
  - Los tests de la base comparan contra facturas ficticias y no contra el caso: la referencia independiente con los importes reales queda en los tests de los PDFs.
  - `ejemplos/valores_esperados.md` repite dos secciones del caso: si el caso cambia, hay que cambiar las dos.
- Cómo verificarlo:
  - `.venv\Scripts\python -m pytest -q --tb=line` → 554 pasan y se salta 1.
  - `git grep -nE '[0-9]+,[0-9]{2} ?€'`: solo ejemplos genéricos y los importes ficticios de los tests y del diseño.
- Pendiente: el historial de git sigue teniendo los importes reales; al publicar, un solo commit con el estado final y el email privado de GitHub (decidido).
