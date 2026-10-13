"""Invariantes de una factura (R33): cada uno detecta su violación; los ejemplos no tienen ninguna."""

import copy

import pytest

import datos_prueba
from datos_prueba import FACTURA_DIGI, FACTURA_GAS, abono_de, insertar, insertar_filas
from facturas.bd.invariantes import verificar


def _en_transaccion(conexion, factura, preparar=None):
    """Inserta la factura sin confirmar, devuelve sus violaciones y revierte todo."""
    conexion.execute("BEGIN IMMEDIATE")
    try:
        conexion.execute("PRAGMA defer_foreign_keys = ON")  # como la carga (diseño, sección 13.2)
        if preparar:
            preparar(conexion)
        return verificar(conexion, insertar_filas(conexion, factura))
    finally:
        conexion.execute("ROLLBACK")


def test_los_ejemplos_cumplen_todos_los_invariantes(base_ejemplos):
    for (factura_id,) in base_ejemplos.execute("SELECT factura_id FROM factura").fetchall():
        assert verificar(base_ejemplos, factura_id) == []


def test_i1_detecta_lineas_que_no_suman_el_total(base_ejemplos):
    factura = copy.deepcopy(FACTURA_GAS)
    factura.update(numero="GAS-PRUEBA-2", inicio="2026-06-26", fin="2026-08-24", total=4272)
    violaciones = verificar(base_ejemplos, insertar(base_ejemplos, factura))
    assert violaciones == ["I1: las líneas suman 4271 céntimos y el total de la factura es 4272"]


def test_i4_detecta_un_prorrateo_que_no_suma(base):
    # Un período fuera del calendario (2000-2099) no reparte ningún día.
    factura = copy.deepcopy(FACTURA_GAS)
    factura.update(inicio="2100-01-01", fin="2100-01-31", emision="2100-02-05")
    violaciones = _en_transaccion(base, factura)
    assert "I4: el prorrateo de la línea 1 suma 0 céntimos y su importe es 2412" in violaciones
    assert any(v.startswith("I4: el prorrateo de la medición") for v in violaciones)


def test_i5_e_i7_detectan_un_concepto_de_otra_categoria(base):
    # Con las claves foráneas diferidas, una línea del móvil con el IVA de la fibra llega
    # hasta los invariantes. Importe 0, para no romper también I1.
    base.execute("BEGIN IMMEDIATE")
    try:
        base.execute("PRAGMA defer_foreign_keys = ON")
        factura_id = insertar_filas(base, FACTURA_DIGI)
        base.execute(
            """INSERT INTO linea (factura_id, posicion, contrato_id, categoria_id, concepto_id, texto,
                                  importe_centimos, imputacion, fecha_inicio, fecha_fin, es_derivada)
               SELECT ?, 7, c.contrato_id, co.categoria_id, co.concepto_id, 'IVA', 0, 'periodo',
                      '2026-07-15', '2026-08-14', 0
               FROM contrato AS c, concepto AS co
               WHERE c.identificador_externo = 'LINEA-MOVIL-PRUEBA' AND co.codigo = 'iva'
                 AND co.categoria_id = (SELECT categoria_id FROM categoria WHERE codigo = 'fibra')""",
            (factura_id,))
        violaciones = verificar(base, factura_id)
    finally:
        base.execute("ROLLBACK")
    assert violaciones[0] == "I5: el concepto de la línea 7 no es de la categoría de su contrato"
    assert violaciones[1].startswith("I7: linea → contrato (contrato_id, categoria_id), fila ")
    assert len(violaciones) == 2


def test_i6_detecta_un_solape_si_el_trigger_no_estuviera(base_ejemplos):
    solapada = copy.deepcopy(FACTURA_GAS)
    solapada.update(numero="GAS-PRUEBA-2", inicio="2026-06-20", fin="2026-08-20")
    violaciones = _en_transaccion(base_ejemplos, solapada, lambda c: c.execute("DROP TRIGGER tg_linea_bi_solape"))
    assert violaciones == [
        "I6: en el contrato 'gas 1', el período se superpone con la factura GAS-PRUEBA-1 (2026-04-30 a 2026-06-25)"]
    # El DROP TRIGGER se revirtió con la transacción.
    with pytest.raises(Exception, match="solape"):
        insertar(base_ejemplos, solapada)


def test_i8_detecta_derivadas_que_no_suman_el_total_impreso(base):
    # I8 admite 10 céntimos de diferencia (redondeo de Digi): 11 ya no.
    factura = copy.deepcopy(FACTURA_DIGI)
    factura["lineas"][5]["importe"] = 375
    factura["total"] = 2968
    assert _en_transaccion(base, factura) == [
        "I8: las líneas derivadas de 'IMPUESTOS (21.00% IVA)' suman 506 céntimos y el total impreso es 517"]


def test_i8_acepta_derivadas_que_difieren_del_total_hasta_10_centimos(base):
    factura = copy.deepcopy(FACTURA_DIGI)
    factura["lineas"][5]["importe"] = 376
    factura["total"] = 2969
    assert _en_transaccion(base, factura) == []


def test_i8_detecta_una_derivada_sin_total_repartido(base):
    factura = copy.deepcopy(FACTURA_DIGI)
    factura["lineas"][5]["texto"] = "OTRO IMPUESTO"
    violaciones = _en_transaccion(base, factura)
    assert "I8: la línea derivada 6 no corresponde a ningún total repartido" in violaciones


def test_verificar_una_factura_que_no_existe(base):
    with pytest.raises(ValueError, match="No existe la factura"):
        verificar(base, 999)


def test_la_original_que_llega_despues_de_su_sustitucion_cumple_los_invariantes(base):
    # Revisión del bloque 1, H3: la original se verifica aunque ya no esté vigente.
    sustitucion = copy.deepcopy(FACTURA_GAS)
    sustitucion.update(numero="GAS-PRUEBA-R1", tipo="rectificativa_sustitucion", corregida="GAS-PRUEBA-1")
    insertar(base, sustitucion)
    original_id = insertar(base, datos_prueba.FACTURA_GAS)
    assert verificar(base, original_id) == []


def test_i9_un_abono_anula_entera_la_factura_que_corrige(base_ejemplos):
    abono = abono_de(FACTURA_GAS, "GAS-PRUEBA-A1")
    assert verificar(base_ejemplos, insertar(base_ejemplos, abono)) == []


def test_i9_detecta_un_abono_parcial(base_ejemplos):
    # Revisión del bloque 2, H7: Digi abona 2,00 € de la cuota del móvil. Eso es una
    # rectificativa por diferencias; como abono anularía la factura entera, fibra incluida.
    abono = copy.deepcopy(FACTURA_DIGI)
    abono.update(numero="DIGI-PRUEBA-A1", tipo="abono", corregida="DIGI-PRUEBA-1", total=-200,
                 totales_repartidos=[], vencimiento=None)
    abono["lineas"] = [datos_prueba.linea("LINEA-MOVIL-PRUEBA", "cuota_plan", "Abono cuota (15 Jul - 14 Ago)", -200)]
    assert verificar(base_ejemplos, insertar(base_ejemplos, abono)) == [
        "I9: el abono DIGI-PRUEBA-A1 no anula entera la factura DIGI-PRUEBA-1: en el contrato 'fibra 1' suman 2226 céntimos",
        "I9: el abono DIGI-PRUEBA-A1 no anula entera la factura DIGI-PRUEBA-1: en el contrato 'movil 1' suman 553 céntimos",
    ]


def test_i9_se_verifica_tambien_si_el_abono_llega_primero(base):
    abono = abono_de(FACTURA_GAS, "GAS-PRUEBA-A1")
    abono["lineas"][0]["importe"] += 1
    abono["total"] += 1
    insertar(base, abono)
    assert verificar(base, insertar(base, FACTURA_GAS)) == [
        "I9: el abono GAS-PRUEBA-A1 no anula entera la factura GAS-PRUEBA-1: en el contrato 'gas 1' suman 1 céntimos"]
