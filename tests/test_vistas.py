"""Vistas con las facturas de ejemplo: totales, prorrateo y vigencia (R22, R25-R27, R32)."""

import copy

import pytest

import datos_prueba
from datos_prueba import FACTURA_GAS, FACTURA_LUZ, abono_de, insertar
from facturas.dashboard import datos


def _por_categoria(conexion):
    return dict(conexion.execute(
        "SELECT categoria_codigo, sum(importe_centimos) FROM v_hecho_gasto_mensual GROUP BY categoria_codigo"))


def test_totales_por_categoria_coinciden_con_el_caso(base_ejemplos):
    totales, _ = datos_prueba.CONTROLES
    assert _por_categoria(base_ejemplos) == totales


def test_prorrateo_de_cada_linea_y_factura_suma_exactamente_su_importe(base_ejemplos):
    lineas = base_ejemplos.execute(
        """SELECT l.linea_id, l.importe_centimos, coalesce(sum(p.importe_centimos), 0), count(p.fecha),
                  CAST(julianday(l.fecha_fin) - julianday(l.fecha_inicio) AS INTEGER) + 1,
                  coalesce(min(p.importe_centimos), 0)
           FROM linea AS l LEFT JOIN v_prorrateo_linea AS p USING (linea_id)
           GROUP BY l.linea_id""").fetchall()
    assert len(lineas) == 25
    for linea_id, importe, prorrateado, dias, dias_periodo, minimo in lineas:
        assert (prorrateado, dias) == (importe, dias_periodo), linea_id
        assert minimo >= 0, linea_id  # ningún día negativo con los importes del caso

    facturas = base_ejemplos.execute(
        """SELECT f.numero, f.importe_total_centimos, sum(p.importe_centimos)
           FROM factura AS f JOIN v_prorrateo_linea AS p USING (factura_id) GROUP BY f.factura_id""")
    for numero, total, prorrateado in facturas:
        assert prorrateado == total, numero


def test_reparto_mensual_coincide_con_los_controles_del_caso(base_ejemplos):
    _, controles = datos_prueba.CONTROLES
    reparto = {
        (categoria, mes): importe
        for categoria, mes, importe in base_ejemplos.execute(
            """SELECT categoria_codigo, anio_mes, sum(importe_centimos)
               FROM v_hecho_gasto_mensual GROUP BY categoria_codigo, anio_mes""")
    }
    assert reparto.keys() == controles.keys()
    for clave, esperado in controles.items():
        assert abs(reparto[clave] - esperado) <= 1, (clave, reparto[clave], esperado)


def test_mediciones_prorrateadas_suman_su_cantidad(base_ejemplos):
    filas = base_ejemplos.execute(
        """SELECT m.medicion_id, m.cantidad_milesimas, sum(p.cantidad_milesimas)
           FROM medicion AS m JOIN v_prorrateo_medicion AS p USING (medicion_id)
           GROUP BY m.medicion_id""").fetchall()
    assert len(filas) == 5
    for medicion_id, cantidad, prorrateada in filas:
        assert prorrateada == cantidad, medicion_id
    consumo = dict(base_ejemplos.execute(
        """SELECT categoria_codigo || ' ' || franja_codigo || ' ' || tipo_lectura, sum(cantidad_milesimas)
           FROM v_hecho_consumo_mensual GROUP BY 1"""))
    assert consumo == {
        "agua sin_franja real": 15000, "gas sin_franja estimada": 344000,
        "luz punta real": 20000, "luz llano real": 21000, "luz valle real": 40000,
    }


def _cobertura(conexion):
    """Días cubiertos y días del mes por categoría y mes, con la regla del dashboard."""
    return {
        (c.categoria, c.anio_mes): (c.dias_cubiertos, c.dias_mes)
        for c in datos.cobertura_mensual(conexion, ["agua", "gas", "luz"], "2026-04", "2026-08")
    }


def _consumo_gas(conexion):
    return dict(conexion.execute(
        """SELECT tipo_lectura, sum(cantidad_milesimas) FROM v_hecho_consumo_mensual
           WHERE categoria_codigo = 'gas' GROUP BY tipo_lectura"""))


def _meses_completos_gas(conexion):
    return sorted(mes for (categoria, mes), (cubiertos, dias) in _cobertura(conexion).items()
                  if categoria == "gas" and cubiertos == dias)


@pytest.mark.parametrize("con_mediciones", [True, False], ids=["abono_con_consumo", "abono_sin_consumo"])
def test_abono_y_refacturacion_no_duplican_gasto_ni_consumo(base_ejemplos, con_mediciones):
    # Revisión del bloque 2, H1 y H7: se anula la factura de gas, con su lectura estimada,
    # y se refactura el mismo período con una lectura real. La factura anulada y su abono
    # no cuentan, traiga o no el abono su consumo.
    assert _meses_completos_gas(base_ejemplos) == ["2026-05"]
    abono = abono_de(FACTURA_GAS, "GAS-PRUEBA-A1")
    if not con_mediciones:
        abono["mediciones"] = []
    insertar(base_ejemplos, abono)
    assert "gas" not in _por_categoria(base_ejemplos)
    assert _consumo_gas(base_ejemplos) == {}
    # Hasta que llega la refacturación, la cobertura avisa que falta una factura, y los
    # meses de la factura anulada siguen contando (H8).
    assert _meses_completos_gas(base_ejemplos) == []
    assert _cobertura(base_ejemplos)[("gas", "2026-05")] == (0, 31)

    refacturacion = copy.deepcopy(FACTURA_GAS)
    refacturacion["numero"] = "GAS-PRUEBA-2"
    refacturacion["mediciones"][0]["tipo_lectura"] = "real"
    insertar(base_ejemplos, refacturacion)
    assert _por_categoria(base_ejemplos)["gas"] == 4271
    assert _consumo_gas(base_ejemplos) == {"real": 344000}
    assert _meses_completos_gas(base_ejemplos) == ["2026-05"]


def test_los_atributos_de_una_factura_anulada_no_cuentan(base_ejemplos):
    # Revisión del bloque 2, H7: se anula la luz y se refactura con otra potencia.
    insertar(base_ejemplos, abono_de(FACTURA_LUZ, "LUZ-PRUEBA-A1"))
    refacturacion = copy.deepcopy(FACTURA_LUZ)
    refacturacion.update(numero="LUZ-PRUEBA-2",
                         atributos=[("CUPS-LUZ-PRUEBA", "potencia_p1", 3450), ("CUPS-LUZ-PRUEBA", "potencia_p2", 3450)])
    insertar(base_ejemplos, refacturacion)
    assert base_ejemplos.execute(
        "SELECT atributo_codigo, valor_milesimas, vigente_desde, vigente_hasta FROM v_dim_contrato_atributo ORDER BY 1"
    ).fetchall() == [("potencia_p1", 3450, "2026-05-27", "2026-06-28"), ("potencia_p2", 3450, "2026-05-27", "2026-06-28")]


def test_un_abono_que_llega_antes_que_su_original_tampoco_cuenta(base):
    insertar(base, abono_de(FACTURA_GAS, "GAS-PRUEBA-A1"))
    assert _por_categoria(base) == {}
    insertar(base, FACTURA_GAS)
    assert _por_categoria(base) == {}
    assert _cobertura(base)[("gas", "2026-05")] == (0, 31)


def test_una_sustitucion_reemplaza_a_la_original_sin_duplicar_el_gasto(base_ejemplos):
    sustitucion = copy.deepcopy(FACTURA_GAS)
    sustitucion.update(numero="GAS-PRUEBA-R1", tipo="rectificativa_sustitucion", corregida="GAS-PRUEBA-1", total=4000)
    sustitucion["lineas"][0]["importe"] = 2141  # consumo corregido: 2141 + 41 + 1077 + 741 = 4000
    cobertura_antes = _cobertura(base_ejemplos)
    insertar(base_ejemplos, sustitucion)

    vigentes = [numero for (numero,) in base_ejemplos.execute("SELECT numero FROM v_factura_vigente")]
    assert "GAS-PRUEBA-1" not in vigentes and "GAS-PRUEBA-R1" in vigentes
    assert _por_categoria(base_ejemplos)["gas"] == 4000
    assert base_ejemplos.execute(
        "SELECT sum(cantidad_milesimas) FROM v_hecho_consumo_mensual WHERE categoria_codigo = 'gas'").fetchone() == (344000,)
    assert _cobertura(base_ejemplos) == cobertura_antes


def test_una_linea_puntual_cae_entera_en_el_mes_de_emision_y_no_cubre_dias(base_ejemplos):
    # Factura de luz del período siguiente, emitida en agosto, con un único cargo puntual.
    puntual = copy.deepcopy(FACTURA_LUZ)
    puntual.update(numero="LUZ-PRUEBA-2", emision="2026-08-05", inicio="2026-06-29", fin="2026-07-28",
                   total=1500, mediciones=[], atributos=[])
    puntual["lineas"] = [datos_prueba.linea("CUPS-LUZ-PRUEBA", "alquiler_contador", "Cargo puntual", 1500,
                                            imputacion="puntual")]
    insertar(base_ejemplos, puntual)

    luz = dict(base_ejemplos.execute(
        """SELECT anio_mes, sum(importe_centimos) FROM v_hecho_gasto_mensual
           WHERE categoria_codigo = 'luz' AND concepto_codigo = 'alquiler_contador' GROUP BY anio_mes"""))
    assert luz["2026-08"] == 1500
    assert "2026-07" not in luz
    assert _cobertura(base_ejemplos)[("luz", "2026-07")] == (0, 31)


def test_dimension_contrato_sin_identificador_externo(base_ejemplos):
    columnas = [fila[1] for fila in base_ejemplos.execute("PRAGMA table_info(v_dim_contrato)")]
    assert "identificador_externo" not in columnas
    assert sorted(alias for (alias,) in base_ejemplos.execute("SELECT alias FROM v_dim_contrato")) == [
        "agua 1", "fibra 1", "gas 1", "luz 1", "movil 1"]


def test_atributos_con_vigencia(base_ejemplos):
    siguiente = copy.deepcopy(FACTURA_LUZ)
    siguiente.update(numero="LUZ-PRUEBA-2", emision="2026-08-03", inicio="2026-06-29", fin="2026-07-28",
                     atributos=[("CUPS-LUZ-PRUEBA", "potencia_p1", 4400), ("CUPS-LUZ-PRUEBA", "potencia_p2", 5750)])
    insertar(base_ejemplos, siguiente)
    tramos = base_ejemplos.execute(
        """SELECT atributo_codigo, unidad, valor_milesimas, vigente_desde, vigente_hasta
           FROM v_dim_contrato_atributo ORDER BY atributo_codigo, vigente_desde""").fetchall()
    assert tramos == [
        ("potencia_p1", "kW", 4400, "2026-05-27", "2026-07-28"),
        ("potencia_p2", "kW", 4400, "2026-05-27", "2026-06-28"),
        ("potencia_p2", "kW", 5750, "2026-06-29", "2026-07-28"),
    ]


@pytest.mark.parametrize("vista", ["v_hecho_gasto_diario", "v_hecho_gasto_mensual", "v_linea"])
def test_importe_con_la_misma_semantica_en_todas_las_vistas(base_ejemplos, vista):
    # Sumar todas las líneas da el total pagado en todas las categorías (R32).
    total = sum(f["total"] for f in datos_prueba.EJEMPLOS)
    assert base_ejemplos.execute(f"SELECT sum(importe_centimos) FROM {vista}").fetchone() == (total,)
