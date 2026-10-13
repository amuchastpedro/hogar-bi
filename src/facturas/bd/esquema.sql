-- Esquema de la base de facturas: tablas, índices, triggers y vistas.
-- Cada elemento está documentado en docs/diseno.md (secciones 2 a 9).
-- La versión del esquema (R40) es la de esta línea; conexion.py la lee de acá.
PRAGMA user_version = 3;

-- Los CHECK de fecha usan `col IS date(col)`: date() devuelve NULL para un texto que no
-- es una fecha, y con `=` el CHECK daría NULL, que SQLite toma como cumplido. Con `IS`,
-- NULL solo pasa si la columna es nula (y NOT NULL lo impide donde corresponde).

-- =====================================================================
-- Diccionario y dimensiones: se cargan desde las semillas.
-- =====================================================================

CREATE TABLE moneda (
    moneda_id INTEGER PRIMARY KEY,
    codigo    TEXT    NOT NULL,
    CONSTRAINT uq_moneda_codigo UNIQUE (codigo),
    CONSTRAINT ck_moneda_codigo CHECK (length(codigo) = 3 AND codigo NOT GLOB '*[^A-Z]*')
) STRICT;

CREATE TABLE categoria (
    categoria_id INTEGER PRIMARY KEY,
    codigo       TEXT    NOT NULL,
    nombre       TEXT    NOT NULL,
    CONSTRAINT uq_categoria_codigo UNIQUE (codigo),
    CONSTRAINT ck_categoria_codigo CHECK (codigo <> '' AND codigo NOT GLOB '*[^a-z0-9_]*'),
    CONSTRAINT ck_categoria_nombre CHECK (nombre <> '')
) STRICT;

CREATE TABLE concepto (
    concepto_id        INTEGER PRIMARY KEY,
    categoria_id       INTEGER NOT NULL REFERENCES categoria (categoria_id),
    codigo             TEXT    NOT NULL,
    nombre             TEXT    NOT NULL,
    imputacion_defecto TEXT    NOT NULL,
    CONSTRAINT uq_concepto_categoria_codigo UNIQUE (categoria_id, codigo),
    CONSTRAINT uq_concepto_concepto_categoria UNIQUE (concepto_id, categoria_id),
    CONSTRAINT ck_concepto_codigo CHECK (codigo <> '' AND codigo NOT GLOB '*[^a-z0-9_]*'),
    CONSTRAINT ck_concepto_nombre CHECK (nombre <> ''),
    CONSTRAINT ck_concepto_imputacion_defecto CHECK (imputacion_defecto IN ('periodo', 'puntual'))
) STRICT;

-- Patrones GLOB sobre la sección y el texto normalizados de una línea (R29-R31).
CREATE TABLE alias_concepto (
    alias_concepto_id INTEGER PRIMARY KEY,
    categoria_id      INTEGER NOT NULL,
    concepto_id       INTEGER NOT NULL,
    patron_seccion    TEXT    NOT NULL,
    patron_texto      TEXT    NOT NULL,
    CONSTRAINT uq_alias_concepto_categoria_patrones UNIQUE (categoria_id, patron_seccion, patron_texto),
    CONSTRAINT fk_alias_concepto_concepto FOREIGN KEY (concepto_id, categoria_id)
        REFERENCES concepto (concepto_id, categoria_id),
    -- Normalizados (R30): minúsculas, ASCII imprimible, sin espacios repetidos ni en los extremos.
    CONSTRAINT ck_alias_concepto_patron_seccion CHECK (
        patron_seccion = lower(patron_seccion) AND patron_seccion = trim(patron_seccion)
        AND patron_seccion NOT GLOB '*[^ -~]*' AND instr(patron_seccion, '  ') = 0),
    CONSTRAINT ck_alias_concepto_patron_texto CHECK (
        patron_texto <> '' AND patron_texto = lower(patron_texto) AND patron_texto = trim(patron_texto)
        AND patron_texto NOT GLOB '*[^ -~]*' AND instr(patron_texto, '  ') = 0)
) STRICT;

CREATE TABLE unidad (
    unidad_id INTEGER PRIMARY KEY,
    codigo    TEXT    NOT NULL,
    simbolo   TEXT    NOT NULL,
    CONSTRAINT uq_unidad_codigo UNIQUE (codigo),
    CONSTRAINT ck_unidad_codigo CHECK (codigo <> '' AND codigo NOT GLOB '*[^a-z0-9_]*'),
    CONSTRAINT ck_unidad_simbolo CHECK (simbolo <> '')
) STRICT;

CREATE TABLE magnitud (
    magnitud_id INTEGER PRIMARY KEY,
    codigo      TEXT    NOT NULL,
    nombre      TEXT    NOT NULL,
    CONSTRAINT uq_magnitud_codigo UNIQUE (codigo),
    CONSTRAINT ck_magnitud_codigo CHECK (codigo <> '' AND codigo NOT GLOB '*[^a-z0-9_]*'),
    CONSTRAINT ck_magnitud_nombre CHECK (nombre <> '')
) STRICT;

-- Qué magnitudes se miden en cada categoría, en qué unidad canónica (R13)
-- y en qué unidad están las lecturas del contador.
CREATE TABLE magnitud_categoria (
    magnitud_categoria_id INTEGER PRIMARY KEY,
    categoria_id          INTEGER NOT NULL REFERENCES categoria (categoria_id),
    magnitud_id           INTEGER NOT NULL REFERENCES magnitud (magnitud_id),
    unidad_canonica_id    INTEGER NOT NULL REFERENCES unidad (unidad_id),
    unidad_contador_id    INTEGER NOT NULL REFERENCES unidad (unidad_id),
    CONSTRAINT uq_magnitud_categoria_categoria_magnitud UNIQUE (categoria_id, magnitud_id),
    CONSTRAINT uq_magnitud_categoria_magnitud_categoria_categoria UNIQUE (magnitud_categoria_id, categoria_id)
) STRICT;

CREATE TABLE franja (
    franja_id INTEGER PRIMARY KEY,
    codigo    TEXT    NOT NULL,
    nombre    TEXT    NOT NULL,
    CONSTRAINT uq_franja_codigo UNIQUE (codigo),
    CONSTRAINT ck_franja_codigo CHECK (codigo <> '' AND codigo NOT GLOB '*[^a-z0-9_]*'),
    CONSTRAINT ck_franja_nombre CHECK (nombre <> '')
) STRICT;

-- Atributos de contrato que determinan el coste (R22), por categoría.
CREATE TABLE atributo_contrato (
    atributo_contrato_id INTEGER PRIMARY KEY,
    categoria_id         INTEGER NOT NULL REFERENCES categoria (categoria_id),
    unidad_id            INTEGER NOT NULL REFERENCES unidad (unidad_id),
    codigo               TEXT    NOT NULL,
    nombre               TEXT    NOT NULL,
    CONSTRAINT uq_atributo_contrato_categoria_codigo UNIQUE (categoria_id, codigo),
    CONSTRAINT uq_atributo_contrato_atributo_contrato_categoria UNIQUE (atributo_contrato_id, categoria_id),
    CONSTRAINT ck_atributo_contrato_codigo CHECK (codigo <> '' AND codigo NOT GLOB '*[^a-z0-9_]*'),
    CONSTRAINT ck_atributo_contrato_nombre CHECK (nombre <> '')
) STRICT;

CREATE TABLE proveedor (
    proveedor_id         INTEGER PRIMARY KEY,
    identificador_fiscal TEXT    NOT NULL,
    nombre               TEXT    NOT NULL,
    CONSTRAINT uq_proveedor_identificador_fiscal UNIQUE (identificador_fiscal),
    CONSTRAINT ck_proveedor_identificador_fiscal CHECK (
        identificador_fiscal <> '' AND identificador_fiscal NOT GLOB '*[^A-Z0-9]*'),
    CONSTRAINT ck_proveedor_nombre CHECK (nombre <> '')
) STRICT;

-- Un registro por día (R24). La clave es la fecha como entero AAAAMMDD.
CREATE TABLE calendario (
    calendario_id INTEGER PRIMARY KEY,
    fecha         TEXT    NOT NULL,
    anio          INTEGER NOT NULL,
    mes           INTEGER NOT NULL,
    dia           INTEGER NOT NULL,
    anio_mes      TEXT    NOT NULL,
    dias_mes      INTEGER NOT NULL,
    CONSTRAINT uq_calendario_fecha UNIQUE (fecha),
    CONSTRAINT ck_calendario_fecha CHECK (fecha IS date(fecha)),
    CONSTRAINT ck_calendario_calendario_id CHECK (calendario_id = CAST(strftime('%Y%m%d', fecha) AS INTEGER)),
    CONSTRAINT ck_calendario_partes CHECK (
        anio = CAST(strftime('%Y', fecha) AS INTEGER) AND mes = CAST(strftime('%m', fecha) AS INTEGER)
        AND dia = CAST(strftime('%d', fecha) AS INTEGER) AND anio_mes = strftime('%Y-%m', fecha)
        AND dias_mes = CAST(strftime('%d', fecha, 'start of month', '+1 month', '-1 day') AS INTEGER))
) STRICT;

-- Una sola fila: con qué semillas se construyó la base (R29, R40).
CREATE TABLE construccion (
    construccion_id INTEGER PRIMARY KEY,
    huella_semillas TEXT    NOT NULL,
    CONSTRAINT ck_construccion_unica CHECK (construccion_id = 1),
    CONSTRAINT ck_construccion_huella_semillas CHECK (
        length(huella_semillas) = 64 AND huella_semillas NOT GLOB '*[^0-9a-f]*')
) STRICT;

-- =====================================================================
-- Capa cruda: lo que dicen los PDFs.
-- =====================================================================

-- Un registro por PDF procesado (R14), identificado por su hash.
CREATE TABLE carga (
    carga_id        INTEGER PRIMARY KEY,
    sha256          TEXT    NOT NULL,
    nombre_archivo  TEXT    NOT NULL,
    formato         TEXT,
    version_parser  TEXT,
    fecha_hora      TEXT    NOT NULL,
    estado          TEXT    NOT NULL,
    etapa_rechazo   TEXT,
    motivo_rechazo  TEXT,
    extraccion_json TEXT,
    CONSTRAINT uq_carga_sha256 UNIQUE (sha256),
    CONSTRAINT ck_carga_sha256 CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
    CONSTRAINT ck_carga_nombre_archivo CHECK (nombre_archivo <> ''),
    CONSTRAINT ck_carga_fecha_hora CHECK (fecha_hora IS datetime(fecha_hora)),
    CONSTRAINT ck_carga_estado CHECK (
        (estado = 'cargada' AND etapa_rechazo IS NULL AND motivo_rechazo IS NULL
            AND extraccion_json IS NOT NULL)
        OR (estado = 'rechazada'
            AND etapa_rechazo IS NOT NULL
            AND etapa_rechazo IN ('formato', 'extraccion', 'traduccion', 'duplicado', 'insercion', 'invariantes')
            AND motivo_rechazo IS NOT NULL AND motivo_rechazo <> '')),
    CONSTRAINT ck_carga_formato CHECK (
        (formato IS NULL) = (version_parser IS NULL)
        AND (coalesce(etapa_rechazo, '') = 'formato') = (formato IS NULL)),
    CONSTRAINT ck_carga_extraccion_json CHECK (
        (coalesce(etapa_rechazo, '') IN ('formato', 'extraccion')) = (extraccion_json IS NULL)
        AND (extraccion_json IS NULL OR json_valid(extraccion_json)))
) STRICT;

CREATE TABLE contrato (
    contrato_id           INTEGER PRIMARY KEY,
    proveedor_id          INTEGER NOT NULL REFERENCES proveedor (proveedor_id),
    categoria_id          INTEGER NOT NULL REFERENCES categoria (categoria_id),
    identificador_externo TEXT    NOT NULL,
    alias                 TEXT    NOT NULL,
    CONSTRAINT uq_contrato_proveedor_identificador_externo UNIQUE (proveedor_id, identificador_externo),
    CONSTRAINT uq_contrato_alias UNIQUE (alias),
    CONSTRAINT uq_contrato_contrato_categoria UNIQUE (contrato_id, categoria_id),
    CONSTRAINT ck_contrato_identificador_externo CHECK (
        identificador_externo <> '' AND identificador_externo = trim(identificador_externo)),
    CONSTRAINT ck_contrato_alias CHECK (alias <> '' AND alias = trim(alias))
) STRICT;

CREATE TABLE factura (
    factura_id               INTEGER PRIMARY KEY,
    carga_id                 INTEGER NOT NULL REFERENCES carga (carga_id),
    proveedor_id             INTEGER NOT NULL REFERENCES proveedor (proveedor_id),
    moneda_id                INTEGER NOT NULL REFERENCES moneda (moneda_id),
    numero                   TEXT    NOT NULL,
    tipo                     TEXT    NOT NULL,
    numero_factura_corregida TEXT,
    fecha_emision            TEXT    NOT NULL,
    fecha_vencimiento        TEXT,
    fecha_inicio             TEXT    NOT NULL,
    fecha_fin                TEXT    NOT NULL,
    importe_total_centimos   INTEGER NOT NULL,
    CONSTRAINT uq_factura_carga UNIQUE (carga_id),
    CONSTRAINT uq_factura_proveedor_numero UNIQUE (proveedor_id, numero),
    CONSTRAINT ck_factura_numero CHECK (numero <> '' AND numero = trim(numero)),
    CONSTRAINT ck_factura_tipo CHECK (
        tipo IN ('ordinaria', 'rectificativa_sustitucion', 'rectificativa_diferencias', 'abono')),
    CONSTRAINT ck_factura_numero_factura_corregida CHECK (
        (tipo = 'ordinaria') = (numero_factura_corregida IS NULL)
        AND (numero_factura_corregida IS NULL
             OR (numero_factura_corregida <> '' AND numero_factura_corregida = trim(numero_factura_corregida)
                 AND numero_factura_corregida <> numero))),
    CONSTRAINT ck_factura_fecha_emision CHECK (fecha_emision IS date(fecha_emision)),
    CONSTRAINT ck_factura_fecha_vencimiento CHECK (fecha_vencimiento IS date(fecha_vencimiento)),
    CONSTRAINT ck_factura_periodo CHECK (
        fecha_inicio IS date(fecha_inicio) AND fecha_fin IS date(fecha_fin) AND fecha_inicio <= fecha_fin)
) STRICT;

CREATE TABLE linea (
    linea_id         INTEGER PRIMARY KEY,
    factura_id       INTEGER NOT NULL REFERENCES factura (factura_id) ON DELETE CASCADE,
    posicion         INTEGER NOT NULL,
    contrato_id      INTEGER NOT NULL,
    categoria_id     INTEGER NOT NULL,
    concepto_id      INTEGER NOT NULL,
    texto            TEXT    NOT NULL,
    importe_centimos INTEGER NOT NULL,
    imputacion       TEXT    NOT NULL,
    fecha_inicio     TEXT    NOT NULL,
    fecha_fin        TEXT    NOT NULL,
    es_derivada      INTEGER NOT NULL,
    CONSTRAINT uq_linea_factura_posicion UNIQUE (factura_id, posicion),
    -- R9: la categoría de la línea es a la vez la de su contrato y la de su concepto.
    CONSTRAINT fk_linea_contrato FOREIGN KEY (contrato_id, categoria_id)
        REFERENCES contrato (contrato_id, categoria_id),
    CONSTRAINT fk_linea_concepto FOREIGN KEY (concepto_id, categoria_id)
        REFERENCES concepto (concepto_id, categoria_id),
    CONSTRAINT ck_linea_posicion CHECK (posicion >= 1),
    CONSTRAINT ck_linea_texto CHECK (texto <> ''),
    CONSTRAINT ck_linea_imputacion CHECK (imputacion IN ('periodo', 'puntual')),
    CONSTRAINT ck_linea_periodo CHECK (
        fecha_inicio IS date(fecha_inicio) AND fecha_fin IS date(fecha_fin) AND fecha_inicio <= fecha_fin),
    CONSTRAINT ck_linea_es_derivada CHECK (es_derivada IN (0, 1))
) STRICT;

CREATE TABLE medicion (
    medicion_id                 INTEGER PRIMARY KEY,
    factura_id                  INTEGER NOT NULL REFERENCES factura (factura_id) ON DELETE CASCADE,
    contrato_id                 INTEGER NOT NULL,
    categoria_id                INTEGER NOT NULL,
    magnitud_categoria_id       INTEGER NOT NULL,
    franja_id                   INTEGER REFERENCES franja (franja_id),
    cantidad_milesimas          INTEGER NOT NULL,
    cantidad_contador_milesimas INTEGER,
    factor_conversion           TEXT,
    fecha_lectura               TEXT    NOT NULL,
    lectura_milesimas           INTEGER NOT NULL,
    tipo_lectura                TEXT    NOT NULL,
    CONSTRAINT fk_medicion_contrato FOREIGN KEY (contrato_id, categoria_id)
        REFERENCES contrato (contrato_id, categoria_id),
    CONSTRAINT fk_medicion_magnitud_categoria FOREIGN KEY (magnitud_categoria_id, categoria_id)
        REFERENCES magnitud_categoria (magnitud_categoria_id, categoria_id),
    CONSTRAINT ck_medicion_conversion CHECK ((cantidad_contador_milesimas IS NULL) = (factor_conversion IS NULL)),
    CONSTRAINT ck_medicion_factor_conversion CHECK (
        factor_conversion IS NULL
        OR (factor_conversion GLOB '[0-9]*' AND factor_conversion NOT GLOB '*[^0-9.]*'
            AND factor_conversion NOT GLOB '*.*.*' AND factor_conversion NOT GLOB '*.'
            AND CAST(factor_conversion AS REAL) > 0)),
    CONSTRAINT ck_medicion_fecha_lectura CHECK (fecha_lectura IS date(fecha_lectura)),
    CONSTRAINT ck_medicion_tipo_lectura CHECK (tipo_lectura IN ('real', 'estimada'))
) STRICT;

-- Valor de un atributo de contrato según una factura: rige durante su período (R22).
CREATE TABLE valor_atributo (
    valor_atributo_id    INTEGER PRIMARY KEY,
    factura_id           INTEGER NOT NULL REFERENCES factura (factura_id) ON DELETE CASCADE,
    contrato_id          INTEGER NOT NULL,
    categoria_id         INTEGER NOT NULL,
    atributo_contrato_id INTEGER NOT NULL,
    valor_milesimas      INTEGER NOT NULL,
    CONSTRAINT uq_valor_atributo_factura_contrato_atributo UNIQUE (factura_id, contrato_id, atributo_contrato_id),
    CONSTRAINT fk_valor_atributo_contrato FOREIGN KEY (contrato_id, categoria_id)
        REFERENCES contrato (contrato_id, categoria_id),
    CONSTRAINT fk_valor_atributo_atributo_contrato FOREIGN KEY (atributo_contrato_id, categoria_id)
        REFERENCES atributo_contrato (atributo_contrato_id, categoria_id)
) STRICT;

-- =====================================================================
-- Índices (R38)
-- =====================================================================

-- Claves foráneas que no quedan cubiertas por un UNIQUE que empiece por ellas.
CREATE INDEX ix_alias_concepto_concepto_id_categoria_id ON alias_concepto (concepto_id, categoria_id);
CREATE INDEX ix_magnitud_categoria_magnitud_id ON magnitud_categoria (magnitud_id);
CREATE INDEX ix_magnitud_categoria_unidad_canonica_id ON magnitud_categoria (unidad_canonica_id);
CREATE INDEX ix_magnitud_categoria_unidad_contador_id ON magnitud_categoria (unidad_contador_id);
CREATE INDEX ix_atributo_contrato_unidad_id ON atributo_contrato (unidad_id);
CREATE INDEX ix_contrato_categoria_id ON contrato (categoria_id);
CREATE INDEX ix_factura_moneda_id ON factura (moneda_id);
CREATE INDEX ix_linea_contrato_id_categoria_id ON linea (contrato_id, categoria_id);
CREATE INDEX ix_linea_concepto_id_categoria_id ON linea (concepto_id, categoria_id);
CREATE INDEX ix_medicion_contrato_id_categoria_id ON medicion (contrato_id, categoria_id);
CREATE INDEX ix_medicion_magnitud_categoria_id_categoria_id ON medicion (magnitud_categoria_id, categoria_id);
CREATE INDEX ix_medicion_franja_id ON medicion (franja_id);
CREATE INDEX ix_valor_atributo_contrato_id_categoria_id ON valor_atributo (contrato_id, categoria_id);
CREATE INDEX ix_valor_atributo_atributo_contrato_id_categoria_id ON valor_atributo (atributo_contrato_id, categoria_id);

-- Consultas y reglas.
CREATE INDEX ix_factura_proveedor_id_numero_factura_corregida ON factura (proveedor_id, numero_factura_corregida);
-- Una factura se sustituye como mucho una vez (R27): la sustituta de la sustituta encadena.
CREATE UNIQUE INDEX ux_factura_proveedor_id_numero_factura_corregida_sustitucion
    ON factura (proveedor_id, numero_factura_corregida) WHERE tipo = 'rectificativa_sustitucion';
CREATE UNIQUE INDEX ux_medicion_factura_contrato_magnitud_franja
    ON medicion (factura_id, contrato_id, magnitud_categoria_id, ifnull(franja_id, 0));

-- =====================================================================
-- Triggers
-- =====================================================================

-- R28: dos facturas del mismo contrato no pueden solaparse. Se controlan las ordinarias
-- y las rectificativas por sustitución; no cuentan las que una sustitución o un abono
-- del mismo proveedor corrige (entre ellas, la sustituida frente a su sustituta).
CREATE TRIGGER tg_linea_bi_solape
BEFORE INSERT ON linea
WHEN NEW.imputacion = 'periodo'
BEGIN
    SELECT RAISE(ABORT, 'solape: el periodo se superpone con otra factura del mismo contrato')
    FROM factura AS nueva
    WHERE nueva.factura_id = NEW.factura_id
      AND nueva.tipo IN ('ordinaria', 'rectificativa_sustitucion')
      AND NOT EXISTS (
          SELECT 1 FROM factura AS c
          WHERE c.proveedor_id = nueva.proveedor_id AND c.numero_factura_corregida = nueva.numero
            AND c.tipo IN ('rectificativa_sustitucion', 'abono'))
      AND EXISTS (
          SELECT 1
          FROM linea AS l
          JOIN factura AS otra ON otra.factura_id = l.factura_id
          WHERE l.contrato_id = NEW.contrato_id
            AND l.factura_id <> NEW.factura_id
            AND l.imputacion = 'periodo'
            AND otra.tipo IN ('ordinaria', 'rectificativa_sustitucion')
            AND otra.fecha_inicio <= nueva.fecha_fin
            AND nueva.fecha_inicio <= otra.fecha_fin
            AND NOT EXISTS (
                SELECT 1 FROM factura AS c
                WHERE c.proveedor_id = otra.proveedor_id AND c.numero_factura_corregida = otra.numero
                  AND c.tipo IN ('rectificativa_sustitucion', 'abono')));
END;

-- R3, R13: una medición no mezcla el total sin franja con su desglose por franja.
CREATE TRIGGER tg_medicion_bi_franja
BEFORE INSERT ON medicion
BEGIN
    SELECT RAISE(ABORT, 'medicion: no se mezcla una medicion sin franja con mediciones por franja')
    WHERE EXISTS (
        SELECT 1 FROM medicion AS m
        WHERE m.factura_id = NEW.factura_id AND m.contrato_id = NEW.contrato_id
          AND m.magnitud_categoria_id = NEW.magnitud_categoria_id
          AND (m.franja_id IS NULL) <> (NEW.franja_id IS NULL));
END;

-- R10, R13: si el contador mide en otra unidad, la conversión es obligatoria.
CREATE TRIGGER tg_medicion_bi_conversion
BEFORE INSERT ON medicion
WHEN NEW.cantidad_contador_milesimas IS NULL
BEGIN
    SELECT RAISE(ABORT, 'medicion: falta la cantidad en la unidad del contador y su factor de conversion')
    FROM magnitud_categoria AS mc
    WHERE mc.magnitud_categoria_id = NEW.magnitud_categoria_id
      AND mc.unidad_contador_id <> mc.unidad_canonica_id;
END;

-- R15: una factura sale de una carga exitosa, y una carga que produjo una factura
-- no cambia (ni pasa a rechazada).
CREATE TRIGGER tg_factura_bi_carga
BEFORE INSERT ON factura
BEGIN
    SELECT RAISE(ABORT, 'factura: su carga tiene que estar cargada')
    FROM carga
    WHERE carga.carga_id = NEW.carga_id AND carga.estado <> 'cargada';
END;

CREATE TRIGGER tg_carga_bu_cargada
BEFORE UPDATE ON carga
WHEN EXISTS (SELECT 1 FROM factura WHERE factura.carga_id = OLD.carga_id)
BEGIN
    SELECT RAISE(ABORT, 'carga: una carga con factura no se modifica');
END;

-- R17: los hechos no se editan ni se borran sueltos; una factura se reemplaza entera.
-- Borrar la factura borra sus filas (ON DELETE CASCADE): cuando la cascada llega a
-- ellas, la factura ya no existe y los triggers *_bd_suelta las dejan pasar.
CREATE TRIGGER tg_factura_bu_inmutable BEFORE UPDATE ON factura
BEGIN SELECT RAISE(ABORT, 'inmutable: una factura se reemplaza entera, no se modifica'); END;
CREATE TRIGGER tg_linea_bu_inmutable BEFORE UPDATE ON linea
BEGIN SELECT RAISE(ABORT, 'inmutable: una factura se reemplaza entera, no se modifica'); END;
CREATE TRIGGER tg_medicion_bu_inmutable BEFORE UPDATE ON medicion
BEGIN SELECT RAISE(ABORT, 'inmutable: una factura se reemplaza entera, no se modifica'); END;
CREATE TRIGGER tg_valor_atributo_bu_inmutable BEFORE UPDATE ON valor_atributo
BEGIN SELECT RAISE(ABORT, 'inmutable: una factura se reemplaza entera, no se modifica'); END;

CREATE TRIGGER tg_linea_bd_suelta BEFORE DELETE ON linea
WHEN EXISTS (SELECT 1 FROM factura WHERE factura.factura_id = OLD.factura_id)
BEGIN SELECT RAISE(ABORT, 'inmutable: una linea se borra solo con su factura'); END;
CREATE TRIGGER tg_medicion_bd_suelta BEFORE DELETE ON medicion
WHEN EXISTS (SELECT 1 FROM factura WHERE factura.factura_id = OLD.factura_id)
BEGIN SELECT RAISE(ABORT, 'inmutable: una medicion se borra solo con su factura'); END;
CREATE TRIGGER tg_valor_atributo_bd_suelta BEFORE DELETE ON valor_atributo
WHEN EXISTS (SELECT 1 FROM factura WHERE factura.factura_id = OLD.factura_id)
BEGIN SELECT RAISE(ABORT, 'inmutable: un valor de atributo se borra solo con su factura'); END;

-- R21, R41: de un contrato solo cambian los datos manuales (el alias).
CREATE TRIGGER tg_contrato_bu_identidad
BEFORE UPDATE OF proveedor_id, categoria_id, identificador_externo ON contrato
BEGIN SELECT RAISE(ABORT, 'contrato: solo se modifica el alias'); END;

-- =====================================================================
-- Vistas (capa de lectura, R32 y R36)
-- =====================================================================

-- Dimensiones -----------------------------------------------------------

CREATE VIEW v_dim_fecha AS
SELECT calendario_id, fecha, anio, mes, dia, anio_mes, dias_mes
FROM calendario;

CREATE VIEW v_dim_categoria AS
SELECT categoria_id, codigo AS categoria_codigo, nombre AS categoria_nombre
FROM categoria;

CREATE VIEW v_dim_concepto AS
SELECT co.concepto_id, co.codigo AS concepto_codigo, co.nombre AS concepto_nombre,
       co.categoria_id, ca.codigo AS categoria_codigo,
       co.imputacion_defecto
FROM concepto AS co
JOIN categoria AS ca ON ca.categoria_id = co.categoria_id;

CREATE VIEW v_dim_proveedor AS
SELECT proveedor_id, identificador_fiscal, nombre AS proveedor_nombre
FROM proveedor;

-- Sin el identificador externo: el dashboard muestra el alias (R21).
CREATE VIEW v_dim_contrato AS
SELECT c.contrato_id, c.alias, c.categoria_id, ca.codigo AS categoria_codigo,
       c.proveedor_id, p.nombre AS proveedor_nombre
FROM contrato AS c
JOIN categoria AS ca ON ca.categoria_id = c.categoria_id
JOIN proveedor AS p ON p.proveedor_id = c.proveedor_id;

-- Auxiliares --------------------------------------------------------------

-- Facturas que cuentan (R27). No cuentan una factura sustituida, una factura anulada
-- por un abono ni el abono: un abono anula entera la factura que corrige (I9), así que
-- el par no aporta gasto, consumo ni atributos, y la factura que lo reemplaza es otra.
-- Una rectificativa por diferencias cuenta junto con la factura que corrige: se suman.
CREATE VIEW v_factura_vigente AS
SELECT f.factura_id, f.carga_id, f.proveedor_id, f.numero, f.tipo, f.numero_factura_corregida,
       m.codigo AS moneda, f.fecha_emision, f.fecha_vencimiento, f.fecha_inicio, f.fecha_fin,
       f.importe_total_centimos
FROM factura AS f
JOIN moneda AS m ON m.moneda_id = f.moneda_id
WHERE f.tipo <> 'abono'
  AND NOT EXISTS (
    SELECT 1 FROM factura AS c
    WHERE c.proveedor_id = f.proveedor_id
      AND c.numero_factura_corregida = f.numero
      AND c.tipo IN ('rectificativa_sustitucion', 'abono'));

-- Tramos de vigencia de cada atributo de contrato (R22): facturas vigentes
-- consecutivas con el mismo valor forman un tramo.
CREATE VIEW v_dim_contrato_atributo AS
WITH observacion AS (
    SELECT va.contrato_id, va.atributo_contrato_id, va.valor_milesimas, f.fecha_inicio, f.fecha_fin,
           row_number() OVER (PARTITION BY va.contrato_id, va.atributo_contrato_id ORDER BY f.fecha_inicio)
         - row_number() OVER (PARTITION BY va.contrato_id, va.atributo_contrato_id, va.valor_milesimas
                              ORDER BY f.fecha_inicio) AS tramo
    FROM valor_atributo AS va
    JOIN v_factura_vigente AS f ON f.factura_id = va.factura_id
)
SELECT o.contrato_id, ac.codigo AS atributo_codigo, ac.nombre AS atributo_nombre, u.simbolo AS unidad,
       o.valor_milesimas, min(o.fecha_inicio) AS vigente_desde, max(o.fecha_fin) AS vigente_hasta
FROM observacion AS o
JOIN atributo_contrato AS ac ON ac.atributo_contrato_id = o.atributo_contrato_id
JOIN unidad AS u ON u.unidad_id = ac.unidad_id
GROUP BY o.contrato_id, o.atributo_contrato_id, o.valor_milesimas, o.tramo;

-- Líneas de facturas vigentes, con su categoría y concepto.
CREATE VIEW v_linea AS
SELECT l.linea_id, l.factura_id, l.posicion, f.proveedor_id, f.fecha_emision,
       l.contrato_id, l.categoria_id, ca.codigo AS categoria_codigo,
       l.concepto_id, co.codigo AS concepto_codigo, co.nombre AS concepto_nombre,
       l.texto, l.importe_centimos, l.imputacion, l.fecha_inicio, l.fecha_fin,
       CAST(julianday(l.fecha_fin) - julianday(l.fecha_inicio) AS INTEGER) + 1 AS dias,
       l.es_derivada
FROM linea AS l
JOIN v_factura_vigente AS f ON f.factura_id = l.factura_id
JOIN concepto AS co ON co.concepto_id = l.concepto_id
JOIN categoria AS ca ON ca.categoria_id = l.categoria_id;

-- Prorrateo de todas las líneas, vigentes o no (R25). Grano: línea × día.
-- Lo usan v_hecho_gasto_diario (que filtra las vigentes) y el invariante I4.
CREATE VIEW v_prorrateo_linea AS
WITH linea_periodo AS (
    SELECT l.linea_id, l.factura_id, l.fecha_inicio,
           CAST(julianday(l.fecha_fin) - julianday(l.fecha_inicio) AS INTEGER) + 1 AS dias,
           l.fecha_fin,
           sum(l.importe_centimos) OVER grupo AS acumulado_hasta,
           sum(l.importe_centimos) OVER grupo - l.importe_centimos AS acumulado_previo
    FROM linea AS l
    WHERE l.imputacion = 'periodo'
    WINDOW grupo AS (PARTITION BY l.factura_id, l.contrato_id, l.fecha_inicio, l.fecha_fin
                     ORDER BY l.posicion)
),
linea_dia AS (
    SELECT lp.*, c.calendario_id, c.fecha, c.anio_mes,
           CAST(julianday(c.fecha) - julianday(lp.fecha_inicio) AS INTEGER) + 1 AS k
    FROM linea_periodo AS lp
    JOIN calendario AS c ON c.fecha BETWEEN lp.fecha_inicio AND lp.fecha_fin
),
linea_dia_acumulado AS (
    -- Lo asignado a la línea desde el inicio hasta el día k:
    -- redondeo(acumulado_hasta·k/dias) − redondeo(acumulado_previo·k/dias),
    -- con redondeo al entero más cercano (mitades hacia afuera).
    SELECT ld.*,
           (CASE WHEN acumulado_hasta * k >= 0
                 THEN (2 * acumulado_hasta * k + dias) / (2 * dias)
                 ELSE -((-2 * acumulado_hasta * k + dias) / (2 * dias)) END)
         - (CASE WHEN acumulado_previo * k >= 0
                 THEN (2 * acumulado_previo * k + dias) / (2 * dias)
                 ELSE -((-2 * acumulado_previo * k + dias) / (2 * dias)) END) AS asignado_hasta_dia
    FROM linea_dia AS ld
)
SELECT linea_id, factura_id, calendario_id, fecha, anio_mes,
       asignado_hasta_dia
         - coalesce(lag(asignado_hasta_dia) OVER (PARTITION BY linea_id ORDER BY fecha), 0) AS importe_centimos
FROM linea_dia_acumulado
UNION ALL
SELECT l.linea_id, l.factura_id, c.calendario_id, c.fecha, c.anio_mes, l.importe_centimos
FROM linea AS l
JOIN factura AS f ON f.factura_id = l.factura_id
JOIN calendario AS c ON c.fecha = f.fecha_emision
WHERE l.imputacion = 'puntual';

-- Prorrateo de todas las mediciones (R25). Grano: medición × día.
CREATE VIEW v_prorrateo_medicion AS
WITH medicion_periodo AS (
    SELECT m.medicion_id, m.factura_id, f.fecha_inicio, f.fecha_fin,
           CAST(julianday(f.fecha_fin) - julianday(f.fecha_inicio) AS INTEGER) + 1 AS dias,
           sum(m.cantidad_milesimas) OVER grupo AS acumulado_hasta,
           sum(m.cantidad_milesimas) OVER grupo - m.cantidad_milesimas AS acumulado_previo
    FROM medicion AS m
    JOIN factura AS f ON f.factura_id = m.factura_id
    WINDOW grupo AS (PARTITION BY m.factura_id, m.contrato_id, m.magnitud_categoria_id ORDER BY m.franja_id)
),
medicion_dia AS (
    SELECT mp.*, c.calendario_id, c.fecha, c.anio_mes,
           CAST(julianday(c.fecha) - julianday(mp.fecha_inicio) AS INTEGER) + 1 AS k
    FROM medicion_periodo AS mp
    JOIN calendario AS c ON c.fecha BETWEEN mp.fecha_inicio AND mp.fecha_fin
),
medicion_dia_acumulado AS (
    SELECT md.*,
           (CASE WHEN acumulado_hasta * k >= 0
                 THEN (2 * acumulado_hasta * k + dias) / (2 * dias)
                 ELSE -((-2 * acumulado_hasta * k + dias) / (2 * dias)) END)
         - (CASE WHEN acumulado_previo * k >= 0
                 THEN (2 * acumulado_previo * k + dias) / (2 * dias)
                 ELSE -((-2 * acumulado_previo * k + dias) / (2 * dias)) END) AS asignado_hasta_dia
    FROM medicion_dia AS md
)
SELECT medicion_id, factura_id, calendario_id, fecha, anio_mes,
       asignado_hasta_dia
         - coalesce(lag(asignado_hasta_dia) OVER (PARTITION BY medicion_id ORDER BY fecha), 0) AS cantidad_milesimas
FROM medicion_dia_acumulado;

-- Hechos ------------------------------------------------------------------

-- Grano: línea × día, solo facturas vigentes.
CREATE VIEW v_hecho_gasto_diario AS
SELECT p.calendario_id, p.fecha, p.anio_mes, v.linea_id, v.factura_id, v.contrato_id,
       v.categoria_id, v.categoria_codigo,
       v.concepto_id, v.concepto_codigo, v.concepto_nombre,
       p.importe_centimos
FROM v_prorrateo_linea AS p
JOIN v_linea AS v ON v.linea_id = p.linea_id;

-- Grano: mes × contrato × concepto.
CREATE VIEW v_hecho_gasto_mensual AS
SELECT anio_mes, contrato_id, categoria_id, categoria_codigo,
       concepto_id, concepto_codigo, concepto_nombre,
       sum(importe_centimos) AS importe_centimos
FROM v_hecho_gasto_diario
GROUP BY anio_mes, contrato_id, categoria_id, categoria_codigo,
         concepto_id, concepto_codigo, concepto_nombre;

-- Grano: medición × día, solo facturas vigentes; en milésimas de la unidad canónica.
CREATE VIEW v_hecho_consumo_diario AS
SELECT p.calendario_id, p.fecha, p.anio_mes, m.medicion_id, m.factura_id, m.contrato_id,
       m.categoria_id, ca.codigo AS categoria_codigo, mg.codigo AS magnitud_codigo, u.simbolo AS unidad,
       coalesce(fr.codigo, 'sin_franja') AS franja_codigo, m.tipo_lectura,
       p.cantidad_milesimas
FROM v_prorrateo_medicion AS p
JOIN medicion AS m ON m.medicion_id = p.medicion_id
JOIN v_factura_vigente AS f ON f.factura_id = m.factura_id
JOIN magnitud_categoria AS mc ON mc.magnitud_categoria_id = m.magnitud_categoria_id
JOIN magnitud AS mg ON mg.magnitud_id = mc.magnitud_id
JOIN unidad AS u ON u.unidad_id = mc.unidad_canonica_id
JOIN categoria AS ca ON ca.categoria_id = m.categoria_id
LEFT JOIN franja AS fr ON fr.franja_id = m.franja_id;

-- Grano: mes × contrato × magnitud × franja × tipo de lectura.
CREATE VIEW v_hecho_consumo_mensual AS
SELECT anio_mes, contrato_id, categoria_id, categoria_codigo, magnitud_codigo, unidad, franja_codigo,
       tipo_lectura, sum(cantidad_milesimas) AS cantidad_milesimas
FROM v_hecho_consumo_diario
GROUP BY anio_mes, contrato_id, categoria_id, categoria_codigo, magnitud_codigo, unidad, franja_codigo,
         tipo_lectura;
