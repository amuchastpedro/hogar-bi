"""La base rechaza los datos inválidos, vengan de donde vengan (R6, R7, R9, R16, R27, R28, R42)."""

import copy
import sqlite3

import pytest

import datos_prueba
from datos_prueba import FACTURA_AGUA, FACTURA_GAS, FACTURA_LUZ, abono_de, insertar


def variante(factura, **cambios):
    nueva = copy.deepcopy(factura)
    nueva.update(cambios)
    return nueva


def _id(conexion, sql, *parametros):
    return conexion.execute(sql, parametros).fetchone()[0]


# Fechas, períodos, tipos y nulos ------------------------------------------------

@pytest.mark.parametrize("fecha", ["2026-02-30", "23/06/2026", "2026-6-23", "2026-06-23 10:00:00"])
def test_rechaza_fecha_invalida_o_en_otro_formato(base, fecha):
    with pytest.raises(sqlite3.IntegrityError, match="ck_factura_fecha_emision"):
        insertar(base, variante(FACTURA_AGUA, emision=fecha))


@pytest.mark.parametrize("fecha", ["31/12/2026", "no es una fecha"])
def test_rechaza_fecha_invalida_en_columnas_nulables(base_ejemplos, fecha):
    with pytest.raises(sqlite3.IntegrityError, match="ck_factura_fecha_vencimiento"):
        insertar(base_ejemplos, variante(FACTURA_AGUA, numero="AGUA-PRUEBA-2", vencimiento=fecha))
    with pytest.raises(sqlite3.IntegrityError, match="ck_carga_fecha_hora"):
        base_ejemplos.execute(
            """INSERT INTO carga (sha256, nombre_archivo, fecha_hora, estado, etapa_rechazo, motivo_rechazo)
               VALUES (?, 'x.pdf', ?, 'rechazada', 'formato', 'motivo')""", ("c" * 64, fecha))


def test_rechaza_periodo_invertido(base):
    with pytest.raises(sqlite3.IntegrityError, match="ck_factura_periodo"):
        insertar(base, variante(FACTURA_AGUA, inicio="2026-06-09", fin="2026-06-08"))
    factura = copy.deepcopy(FACTURA_AGUA)
    factura["lineas"][0]["periodo"] = ("2026-05-02", "2026-05-01")
    with pytest.raises(sqlite3.IntegrityError, match="ck_linea_periodo"):
        insertar(base, factura)


@pytest.mark.parametrize("importe", [12.34, "12,34", "doce"])
def test_rechaza_importe_con_decimales_o_en_texto(base, importe):
    factura = copy.deepcopy(FACTURA_AGUA)
    factura["lineas"][0]["importe"] = importe
    with pytest.raises(sqlite3.IntegrityError, match="cannot store .* value in INTEGER column linea.importe_centimos"):
        insertar(base, factura)
    with pytest.raises(sqlite3.IntegrityError, match="factura.importe_total_centimos"):
        insertar(base, variante(FACTURA_AGUA, total=importe))


def test_rechaza_nulo_en_campo_obligatorio(base):
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed: factura.fecha_emision"):
        insertar(base, variante(FACTURA_AGUA, emision=None))
    factura = copy.deepcopy(FACTURA_AGUA)
    factura["mediciones"][0]["tipo_lectura"] = None
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed: medicion.tipo_lectura"):
        insertar(base, factura)


def test_rechaza_valor_no_permitido(base):
    with pytest.raises(sqlite3.IntegrityError, match="ck_factura_tipo"):
        insertar(base, variante(FACTURA_AGUA, tipo="nota_de_credito", corregida="X"))
    factura = copy.deepcopy(FACTURA_GAS)
    factura["mediciones"][0]["tipo_lectura"] = "calculada"
    with pytest.raises(sqlite3.IntegrityError, match="ck_medicion_tipo_lectura"):
        insertar(base, factura)


def test_tras_un_rechazo_no_queda_nada_parcial(base):
    factura = copy.deepcopy(FACTURA_AGUA)
    factura["lineas"][-1]["importe"] = 11.77
    with pytest.raises(sqlite3.IntegrityError):
        insertar(base, factura)
    for tabla in ("carga", "contrato", "factura", "linea", "medicion"):
        assert base.execute(f"SELECT count(*) FROM {tabla}").fetchone() == (0,), tabla


# Moneda (R42) -------------------------------------------------------------------

def test_rechaza_moneda_no_admitida(base_ejemplos):
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed: factura.moneda_id"):
        insertar(base_ejemplos, variante(FACTURA_AGUA, numero="AGUA-PRUEBA-USD", moneda="USD"))
    # Con un id que no está en `moneda`, la clave foránea la rechaza.
    carga_id = _id(base_ejemplos, """
        INSERT INTO carga (sha256, nombre_archivo, formato, version_parser, fecha_hora, estado, extraccion_json)
        VALUES (?, 'usd.pdf', 'prueba', 'prueba', '2026-10-02 12:00:00', 'cargada', '{}')
        RETURNING carga_id""", "b" * 64)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        base_ejemplos.execute(
            """INSERT INTO factura (carga_id, proveedor_id, moneda_id, numero, tipo, fecha_emision,
                                    fecha_inicio, fecha_fin, importe_total_centimos)
               VALUES (?, 1, 99, 'OTRA', 'ordinaria', '2026-06-23', '2026-04-10', '2026-06-08', 0)""",
            (carga_id,))


# Concepto de otra categoría (R9) ------------------------------------------------

def _insertar_linea(conexion, contrato_externo, categoria_linea, categoria_concepto, concepto):
    contrato_id = _id(conexion, "SELECT contrato_id FROM contrato WHERE identificador_externo = ?",
                      contrato_externo)
    conexion.execute(
        """INSERT INTO linea (factura_id, posicion, contrato_id, categoria_id, concepto_id, texto,
                              importe_centimos, imputacion, fecha_inicio, fecha_fin, es_derivada)
           SELECT f.factura_id, 99, ?, (SELECT categoria_id FROM categoria WHERE codigo = ?),
                  (SELECT co.concepto_id FROM concepto AS co JOIN categoria AS ca USING (categoria_id)
                   WHERE ca.codigo = ? AND co.codigo = ?),
                  'texto', 100, 'periodo', f.fecha_inicio, f.fecha_fin, 0
           FROM factura AS f WHERE f.numero = 'DIGI-PRUEBA-1'""",
        (contrato_id, categoria_linea, categoria_concepto, concepto))


def test_rechaza_linea_con_concepto_de_otra_categoria(base_ejemplos):
    # Una línea del móvil con el IVA de la fibra: falla (concepto_id, categoria_id) → concepto.
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        _insertar_linea(base_ejemplos, "LINEA-MOVIL-PRUEBA", "movil", "fibra", "iva")
    # Y si la línea declara la categoría del concepto: falla (contrato_id, categoria_id) → contrato.
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        _insertar_linea(base_ejemplos, "LINEA-MOVIL-PRUEBA", "fibra", "fibra", "iva")
    # La misma línea con el IVA del móvil se acepta.
    _insertar_linea(base_ejemplos, "LINEA-MOVIL-PRUEBA", "movil", "movil", "iva")


# Duplicados (R16) y rectificativas (R27) ------------------------------------------

def test_rechaza_factura_duplicada(base_ejemplos):
    # Otro PDF (otro contenido) con el mismo proveedor y número.
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed: factura.proveedor_id, factura.numero"):
        insertar(base_ejemplos, variante(FACTURA_GAS, total=4524))


def test_rechaza_dos_sustituciones_de_la_misma_factura(base_ejemplos):
    sustitucion = variante(FACTURA_GAS, numero="GAS-PRUEBA-R1", tipo="rectificativa_sustitucion",
                           corregida="GAS-PRUEBA-1")
    insertar(base_ejemplos, sustitucion)
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed: factura.proveedor_id, factura.numero_factura_corregida"):
        insertar(base_ejemplos, variante(sustitucion, numero="GAS-PRUEBA-R2"))


def test_ordinaria_sin_referencia_y_rectificativa_con_referencia(base):
    with pytest.raises(sqlite3.IntegrityError, match="ck_factura_numero_factura_corregida"):
        insertar(base, variante(FACTURA_GAS, corregida="GAS-PRUEBA-0"))
    with pytest.raises(sqlite3.IntegrityError, match="ck_factura_numero_factura_corregida"):
        insertar(base, variante(FACTURA_GAS, tipo="abono"))


# Solapes (R28) ------------------------------------------------------------------

def test_rechaza_solape_entre_ordinarias_del_mismo_contrato(base_ejemplos):
    solapada = variante(FACTURA_GAS, numero="GAS-PRUEBA-2", inicio="2026-06-25", fin="2026-08-24")
    with pytest.raises(sqlite3.IntegrityError, match="solape"):
        insertar(base_ejemplos, solapada)


def test_acepta_facturas_contiguas(base_ejemplos):
    insertar(base_ejemplos, variante(FACTURA_GAS, numero="GAS-PRUEBA-2", inicio="2026-06-26", fin="2026-08-24"))
    insertar(base_ejemplos, variante(FACTURA_GAS, numero="GAS-PRUEBA-0", inicio="2026-03-01", fin="2026-04-29"))


def test_solape_de_otro_contrato_no_cuenta(base_ejemplos):
    otro_contrato = variante(FACTURA_GAS, numero="GAS-PRUEBA-OTRO", contratos={"CUPS-GAS-OTRO": "gas"})
    for linea in otro_contrato["lineas"] + otro_contrato["mediciones"]:
        linea["contrato"] = "CUPS-GAS-OTRO"
    insertar(base_ejemplos, otro_contrato)


def test_abono_y_refacturacion_del_mismo_periodo(base_ejemplos):
    # Revisión del bloque 1, H4: el abono anula la factura y la refacturación no choca con ella.
    # El gasto y el consumo resultantes se prueban en test_vistas.py.
    insertar(base_ejemplos, abono_de(FACTURA_GAS, "GAS-PRUEBA-A1"))
    insertar(base_ejemplos, variante(FACTURA_GAS, numero="GAS-PRUEBA-2"))


# Consumo negativo (R3; revisión del bloque 2, H9) -------------------------------------

def test_una_ordinaria_puede_regularizar_un_consumo_negativo(base_ejemplos):
    # La lectura real quedó 2 m³ por debajo de la estimada de la factura anterior.
    gas = variante(FACTURA_GAS, numero="GAS-PRUEBA-2", inicio="2026-06-26", fin="2026-08-24", total=1077)
    gas["lineas"] = [datos_prueba.linea("CUPS-GAS-PRUEBA", "termino_fijo", "Término fijo", 1077)]
    gas["mediciones"][0].update(cantidad=-23000, cantidad_contador=-2000, lectura=15575000, tipo_lectura="real")
    insertar(base_ejemplos, gas)
    # En la luz, la regularización puede venir en una sola franja.
    luz = variante(FACTURA_LUZ, numero="LUZ-PRUEBA-2", inicio="2026-06-29", fin="2026-07-28", atributos=[])
    luz["mediciones"][0]["cantidad"] = -5000
    insertar(base_ejemplos, luz)


def test_una_rectificativa_por_diferencias_informa_la_diferencia_con_cualquier_signo(base_ejemplos):
    diferencia = variante(FACTURA_GAS, numero="GAS-PRUEBA-D1", tipo="rectificativa_diferencias",
                          corregida="GAS-PRUEBA-1", total=-100)
    diferencia["lineas"] = [datos_prueba.linea("CUPS-GAS-PRUEBA", "consumo_gas", "Consumo gas", -100)]
    diferencia["mediciones"][0].update(cantidad=-12000, cantidad_contador=-1000)
    insertar(base_ejemplos, diferencia)


# Mediciones (R3, R13) ------------------------------------------------------------

def test_rechaza_total_sin_franja_junto_con_su_desglose(base):
    luz = copy.deepcopy(FACTURA_LUZ)
    luz["mediciones"].append(datos_prueba.medicion("CUPS-LUZ-PRUEBA", "energia", 81000, "2026-06-28", 0, "real"))
    with pytest.raises(sqlite3.IntegrityError, match="no se mezcla"):
        insertar(base, luz)


def test_rechaza_medicion_de_gas_sin_conversion(base):
    gas = copy.deepcopy(FACTURA_GAS)
    gas["mediciones"][0].update(cantidad_contador=None, factor=None)
    with pytest.raises(sqlite3.IntegrityError, match="falta la cantidad en la unidad del contador"):
        insertar(base, gas)


@pytest.mark.parametrize("factor", ["11,470", "0", "0.000", ".5", "1."])
def test_rechaza_factor_de_conversion_mal_escrito_o_cero(base, factor):
    gas = copy.deepcopy(FACTURA_GAS)
    gas["mediciones"][0]["factor"] = factor
    with pytest.raises(sqlite3.IntegrityError, match="ck_medicion_factor_conversion"):
        insertar(base, gas)


# Borrado e inmutabilidad (R7, R17) ------------------------------------------------

def test_borrar_una_factura_borra_sus_lineas_mediciones_y_atributos(base_ejemplos):
    factura_id = _id(base_ejemplos, "SELECT factura_id FROM factura WHERE numero = 'LUZ-PRUEBA-1'")
    base_ejemplos.execute("DELETE FROM factura WHERE factura_id = ?", (factura_id,))
    for tabla in ("linea", "medicion", "valor_atributo"):
        assert _id(base_ejemplos, f"SELECT count(*) FROM {tabla} WHERE factura_id = ?", factura_id) == 0
    # Las de las demás facturas siguen.
    assert _id(base_ejemplos, "SELECT count(*) FROM linea") == 25 - 7


@pytest.mark.parametrize("sentencia", [
    "UPDATE factura SET importe_total_centimos = 1",
    "UPDATE linea SET importe_centimos = 1",
    "UPDATE medicion SET cantidad_milesimas = 1",
    "UPDATE valor_atributo SET valor_milesimas = 1",
])
def test_los_hechos_no_se_modifican(base_ejemplos, sentencia):
    with pytest.raises(sqlite3.IntegrityError, match="inmutable"):
        base_ejemplos.execute(sentencia)


@pytest.mark.parametrize("tabla", ["linea", "medicion", "valor_atributo"])
def test_las_filas_de_una_factura_no_se_borran_sueltas(base_ejemplos, tabla):
    # Revisión del bloque 2, H4: una corrección manual descuadraría la factura.
    with pytest.raises(sqlite3.IntegrityError, match="se borra solo con su factura"):
        base_ejemplos.execute(f"DELETE FROM {tabla} WHERE factura_id = (SELECT factura_id FROM factura WHERE numero = 'LUZ-PRUEBA-1')")


def test_de_un_contrato_solo_cambian_los_datos_manuales(base_ejemplos):
    base_ejemplos.execute("UPDATE contrato SET alias = 'luz de casa' WHERE identificador_externo = 'CUPS-LUZ-PRUEBA'")
    with pytest.raises(sqlite3.IntegrityError, match="solo se modifica el alias"):
        base_ejemplos.execute("UPDATE contrato SET identificador_externo = 'OTRO' WHERE identificador_externo = 'CUPS-LUZ-PRUEBA'")


def test_una_factura_sale_de_una_carga_cargada(base):
    carga_id = _id(base, """
        INSERT INTO carga (sha256, nombre_archivo, formato, version_parser, fecha_hora, estado,
                           etapa_rechazo, motivo_rechazo, extraccion_json)
        VALUES (?, 'x.pdf', 'prueba', 'prueba', '2026-10-02 12:00:00', 'rechazada', 'invariantes', 'motivo', '{}')
        RETURNING carga_id""", "d" * 64)
    with pytest.raises(sqlite3.IntegrityError, match="su carga tiene que estar cargada"):
        base.execute(
            """INSERT INTO factura (carga_id, proveedor_id, moneda_id, numero, tipo, fecha_emision,
                                    fecha_inicio, fecha_fin, importe_total_centimos)
               VALUES (?, 1, 1, 'X', 'ordinaria', '2026-06-23', '2026-04-10', '2026-06-08', 0)""", (carga_id,))


@pytest.mark.parametrize("corregida", ["", " GAS-PRUEBA-1", "GAS-PRUEBA-1 "])
def test_rechaza_numero_de_factura_corregida_vacio_o_con_espacios(base_ejemplos, corregida):
    with pytest.raises(sqlite3.IntegrityError, match="ck_factura_numero_factura_corregida"):
        insertar(base_ejemplos, abono_de(variante(FACTURA_GAS, numero=corregida), "GAS-PRUEBA-A1"))


def test_una_carga_con_factura_no_se_modifica(base_ejemplos):
    with pytest.raises(sqlite3.IntegrityError, match="una carga con factura no se modifica"):
        base_ejemplos.execute(
            "UPDATE carga SET estado = 'rechazada', etapa_rechazo = 'insercion', motivo_rechazo = 'x'")


# Carga rechazada y construcción ----------------------------------------------------

@pytest.mark.parametrize("formato, etapa, extraccion, valida", [
    (None, "formato", None, True),
    ("f", "extraccion", None, True),
    ("f", "traduccion", "{}", True),
    ("f", "invariantes", "{}", True),
    (None, "traduccion", "{}", False),     # sin formato solo si falló el reconocimiento
    ("f", "formato", None, False),         # con formato, no puede haber fallado el reconocimiento
    ("f", "extraccion", "{}", False),      # sin extracción si falló la extracción
    ("f", "traduccion", None, False),      # con extracción después de extraer
    ("f", "traduccion", "no es json", False),
    ("f", None, "{}", False),              # una rechazada siempre dice en qué etapa
    ("f", "otra", "{}", False),
])
def test_coherencia_de_una_carga_rechazada(base, formato, etapa, extraccion, valida):
    sentencia = """INSERT INTO carga (sha256, nombre_archivo, formato, version_parser, fecha_hora, estado,
                                      etapa_rechazo, motivo_rechazo, extraccion_json)
                   VALUES (?, 'x.pdf', ?, ?, '2026-10-02 12:00:00', 'rechazada', ?, 'motivo', ?)"""
    parametros = ("a" * 64, formato, formato and "1.0.0", etapa, extraccion)
    if valida:
        base.execute(sentencia, parametros)
    else:
        with pytest.raises(sqlite3.IntegrityError, match="ck_carga"):
            base.execute(sentencia, parametros)


def test_carga_rechazada_sin_motivo(base):
    with pytest.raises(sqlite3.IntegrityError, match="ck_carga_estado"):
        base.execute(
            """INSERT INTO carga (sha256, nombre_archivo, fecha_hora, estado, etapa_rechazo)
               VALUES (?, 'x.pdf', '2026-10-02 12:00:00', 'rechazada', 'formato')""", ("a" * 64,))


def test_construccion_tiene_una_sola_fila(base):
    with pytest.raises(sqlite3.IntegrityError, match="ck_construccion_unica"):
        base.execute("INSERT INTO construccion VALUES (2, ?)", ("0" * 64,))
