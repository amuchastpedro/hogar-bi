"""Datos del dashboard: gasto mensual, cobertura, grano por factura y cascada.

Las referencias son independientes de `datos.py`: los totales de `v_factura_vigente`,
los controles de `datos_prueba.CONTROLES` y los importes (ficticios) escritos a mano en `datos_prueba.py` y acá.
"""

import copy
from datetime import date
import re
from pathlib import Path

import pytest

import datos_prueba
from datos_prueba import (
    FACTURA_AGUA, FACTURA_AGUA_2, FACTURA_GAS, FACTURA_GAS_2, RECTIFICATIVA_GAS, linea, medicion,
)
from facturas.dashboard import datos, semantica
from facturas.dashboard.semantica import SIN_CLASIFICAR

SEM = semantica.cargar()


def _factura(filas, numero_original, conexion):
    (factura_id,) = conexion.execute("SELECT factura_id FROM factura WHERE numero = ?", (numero_original,)).fetchone()
    (fila,) = [f for f in filas if f.factura_id == factura_id]
    return fila


# --- Por mes -----------------------------------------------------------------


def test_la_suma_mensual_es_la_suma_de_las_facturas(base_completa):
    mensual = datos.gasto_mensual(base_completa)
    (total,) = base_completa.execute("SELECT sum(importe_total_centimos) FROM v_factura_vigente").fetchone()
    assert sum(g.importe_centimos for g in mensual) == total == 6718 + 4271 + 4279 + 2979 + 7643 + 2963 - 1104
    for categoria in SEM:
        por_factura = sum(f.importe_centimos for f in datos.facturas(base_completa, SEM) if f.categoria == categoria)
        assert sum(g.importe_centimos for g in mensual if g.categoria == categoria) == por_factura, categoria


def test_el_gasto_mensual_coincide_con_los_controles_del_caso(base_ejemplos):
    _, controles = datos_prueba.CONTROLES
    mensual = {(g.categoria, g.anio_mes): g.importe_centimos for g in datos.gasto_mensual(base_ejemplos)}
    assert mensual.keys() == controles.keys()
    for clave, esperado in controles.items():
        assert abs(mensual[clave] - esperado) <= 1, (clave, mensual[clave], esperado)


def test_cobertura_coincide_con_los_controles_del_caso(base_ejemplos):
    cobertura = {
        (c.categoria, c.anio_mes): (c.dias_cubiertos, c.dias_mes)
        for c in datos.cobertura_mensual(base_ejemplos, ["agua", "gas", "luz"], "2026-05", "2026-06")
    }
    assert cobertura == datos_prueba.COBERTURA_CASO


def test_mes_completo_e_incompleto_con_cualquier_contrato(base_ejemplos):
    def completos(conexion):
        return {c.anio_mes: c.completo for c in datos.cobertura_mensual(conexion, ["agua"], "2026-03", "2026-08")}

    # Solo el ejemplo (del 10 de abril al 8 de junio): mayo completo; abril y junio, no.
    # Marzo y agosto no tienen facturas, pero están: incompletos, con 0 días.
    assert completos(base_ejemplos) == {"2026-03": False, "2026-04": False, "2026-05": True,
                                        "2026-06": False, "2026-07": False, "2026-08": False}
    # El período siguiente, con otro contrato, completa junio y julio.
    datos_prueba.insertar(base_ejemplos, FACTURA_AGUA_2)
    assert completos(base_ejemplos) == {"2026-03": False, "2026-04": False, "2026-05": True,
                                        "2026-06": True, "2026-07": True, "2026-08": False}


def test_una_rectificativa_por_diferencias_no_cubre_dias(base_ejemplos):
    gas_mayo = lambda: datos.cobertura_mensual(base_ejemplos, ["gas"], "2026-04", "2026-04")[0].dias_cubiertos
    antes = gas_mayo()
    rectificativa = copy.deepcopy(RECTIFICATIVA_GAS)
    rectificativa.update(inicio="2026-04-01", corregida="GAS-INEXISTENTE")  # no corrige nada cargado
    for l in rectificativa["lineas"]:
        l["periodo"] = ("2026-04-01", FACTURA_GAS["fin"])
    datos_prueba.insertar(base_ejemplos, rectificativa)
    assert gas_mayo() == antes == 1  # abril: solo el 30, de la factura ordinaria


# --- Por factura -------------------------------------------------------------


def test_los_grupos_de_cada_factura_suman_su_total(base_completa):
    """I1 en el grano del dashboard: la suma de los grupos es el total de la factura (más sus rectificativas)."""
    esperado = dict(base_completa.execute(
        """SELECT coalesce(o.factura_id, f.factura_id), sum(f.importe_total_centimos)
           FROM v_factura_vigente AS f
           LEFT JOIN v_factura_vigente AS o ON o.numero = f.numero_factura_corregida
           GROUP BY 1"""))
    por_factura = {}
    for fila in datos.importes_por_factura(base_completa, SEM):
        por_factura[fila.factura_id] = por_factura.get(fila.factura_id, 0) + fila.importe_centimos
        assert fila.grupo != SIN_CLASIFICAR, fila
    assert por_factura == esperado
    assert len(esperado) == 6  # la rectificativa no es una factura aparte


def test_una_rectificativa_por_diferencias_se_suma_a_la_factura_que_corrige(base_completa):
    gas = _factura(datos.facturas(base_completa, SEM), "GAS-PRUEBA-1", base_completa)
    assert (gas.fecha_inicio, gas.fecha_fin, gas.dias) == ("2026-04-30", "2026-06-25", 57)
    assert gas.importe_centimos == 4271 - 1104
    assert gas.importe_variable_centimos == 2412 + 41 - 912
    assert (gas.volumen_milesimas, gas.unidad) == (344000 - 11470, "kWh")
    consumo = {
        (c.franja, c.tipo_lectura): c.cantidad_milesimas
        for c in datos.consumo_por_factura(base_completa) if c.factura_id == gas.factura_id
    }
    # La lectura real de la rectificativa manda: una sola fila, con el consumo neto.
    assert consumo == {("sin_franja", "real"): 344000 - 11470}


def test_factura_volumen_precio_dias_y_contrato(base_completa):
    filas = datos.facturas(base_completa, SEM)
    agua = _factura(filas, "AGUA-PRUEBA-1", base_completa)
    assert (agua.contrato, agua.dias, agua.importe_centimos) == ("agua 1", 60, 6718)
    # Variables del agua: consumo (11,04 + 3,72), canon (8,12) y alcantarillado (3,89).
    assert agua.importe_variable_centimos == 1104 + 372 + 812 + 389
    assert (agua.volumen_milesimas, agua.unidad) == (15000, "m³")
    assert agua.precio_unitario == pytest.approx(26.77 / 15)
    assert _factura(filas, "AGUA-PRUEBA-2", base_completa).contrato == "agua 2"

    luz = _factura(filas, "LUZ-PRUEBA-1", base_completa)
    assert (luz.volumen_milesimas, luz.importe_variable_centimos) == (81000, 1253)  # punta + llano + valle

    digi = [f for f in filas if f.proveedor.startswith("DIGI")]
    assert {(f.categoria, f.contrato, f.importe_centimos) for f in digi} == {
        ("movil", "movil 1", 615 + 0 + 7 + 131), ("fibra", "fibra 1", 1840 + 386)}
    assert all(f.volumen_milesimas is None and f.precio_unitario is None for f in digi)


def test_importes_por_concepto_con_su_grupo(base_ejemplos):
    agua = [f for f in datos.importes_por_factura(base_ejemplos, SEM) if f.categoria == "agua"]
    assert [(f.concepto, f.grupo, f.variable, f.importe_centimos) for f in agua] == [
        ("cuota_servicio", "ciclo_agua", False, 1523),
        ("consumo_agua", "ciclo_agua", True, 1104 + 372),
        ("canon_agua", "ciclo_agua", True, 812),
        ("iva", "ciclo_agua", False, 300),
        ("alcantarillado", "ciclo_agua", True, 389),
        ("residuos_municipales", "residuos", False, 1250),
        ("tmtr", "residuos", False, 968),
    ]


def test_un_concepto_sin_clasificar_va_a_unclassified_y_no_se_pierde(tmp_path, base_completa):
    texto = semantica.RUTA_SEMANTICA.read_text(encoding="utf-8")
    ruta = tmp_path / "semantica.toml"
    ruta.write_text(texto.replace('tmtr = "Metropolitan waste treatment fee"\n', ""), encoding="utf-8")
    sem = semantica.cargar(ruta)
    assert [(f.categoria, f.concepto) for f in semantica.validar(sem, base_completa)] == [("agua", "tmtr")]

    importes = datos.importes_por_factura(base_completa, sem)
    tmtr = [f for f in importes if f.concepto == "tmtr"]
    assert {(f.grupo, f.importe_centimos) for f in tmtr} == {(SIN_CLASIFICAR, 968)}
    filas = datos.facturas(base_completa, sem)
    a, b = (_factura(filas, n, base_completa) for n in ("AGUA-PRUEBA-1", "AGUA-PRUEBA-2"))
    assert (a.importe_centimos, b.importe_centimos) == (6718, 7643)
    pasos = datos.cascada(a, b, importes, sem)
    assert [p.paso for p in pasos] == ["total_a", "volumen", "precio", "ciclo_agua", "residuos", SIN_CLASIFICAR,
                                       "total_b"]


# --- Cascada -----------------------------------------------------------------


def test_cascada_del_agua_calculada_a_mano(base_completa):
    filas = datos.facturas(base_completa, SEM)
    a, b = (_factura(filas, n, base_completa) for n in ("AGUA-PRUEBA-1", "AGUA-PRUEBA-2"))
    pasos = datos.cascada(a, b, datos.importes_por_factura(base_completa, SEM), SEM)
    # V_A = 26,77 € con 15 m³; V_B = 35,65 € con 18 m³.
    # Volumen: 3 m³ × 26,77/15 = 5,354 → 5,35. Precio: (35,65/18 − 26,77/15) × 18 = 3,526 → 3,53.
    # Ciclo del agua sin la parte variable (cuota e IVA): 18,23 → 18,60. Residuos: igual.
    assert [(p.paso, p.importe_centimos) for p in pasos] == [
        ("total_a", 6718), ("volumen", 535), ("precio", 353), ("ciclo_agua", 37), ("residuos", 0),
        ("total_b", 7643),
    ]


@pytest.mark.parametrize("categoria, numeros", [
    ("agua", ("AGUA-PRUEBA-1", "AGUA-PRUEBA-2")),
    ("agua", ("AGUA-PRUEBA-2", "AGUA-PRUEBA-1")),
    ("gas", ("GAS-PRUEBA-1", "GAS-PRUEBA-2")),
    ("gas", ("GAS-PRUEBA-2", "GAS-PRUEBA-1")),
])
def test_la_cascada_cuadra_exacta(base_completa, categoria, numeros):
    filas = datos.facturas(base_completa, SEM)
    importes = datos.importes_por_factura(base_completa, SEM)
    a, b = (_factura(filas, n, base_completa) for n in numeros)
    pasos = datos.cascada(a, b, importes, SEM)
    assert pasos[0].importe_centimos + sum(p.importe_centimos for p in pasos[1:-1]) == pasos[-1].importe_centimos
    # Cada efecto, a menos de medio céntimo de su fórmula.
    p_a = a.importe_variable_centimos / a.volumen_milesimas
    p_b = b.importe_variable_centimos / b.volumen_milesimas
    efectos = {p.paso: p.importe_centimos for p in pasos}
    assert abs(efectos["volumen"] - (b.volumen_milesimas - a.volumen_milesimas) * p_a) <= 0.5
    assert abs(efectos["precio"] - (p_b - p_a) * b.volumen_milesimas) <= 0.5 + 1e-9


def test_cascada_del_gas_con_un_impuesto_variable(base_completa):
    filas = datos.facturas(base_completa, SEM)
    a, b = (_factura(filas, n, base_completa) for n in ("GAS-PRUEBA-1", "GAS-PRUEBA-2"))
    pasos = {p.paso: p.importe_centimos for p in datos.cascada(a, b, datos.importes_por_factura(base_completa, SEM), SEM)}
    # La energía es toda variable: no tiene paso. De los impuestos solo cuenta el IVA
    # (7,41 − 1,92 de la rectificativa → 5,14); el de hidrocarburos va en volumen y precio.
    assert list(pasos) == ["total_a", "volumen", "precio", "fijo", "otros_fijos", "impuestos", "total_b"]
    assert pasos["impuestos"] == 514 - (741 - 192)


def test_cascada_sin_volumen_o_entre_servicios_distintos(base_completa):
    filas = datos.facturas(base_completa, SEM)
    importes = datos.importes_por_factura(base_completa, SEM)
    agua = _factura(filas, "AGUA-PRUEBA-1", base_completa)
    gas = _factura(filas, "GAS-PRUEBA-1", base_completa)
    (fibra,) = [f for f in filas if f.categoria == "fibra"]
    with pytest.raises(datos.ErrorCascada, match="categorías distintas"):
        datos.cascada(agua, gas, importes, SEM)
    with pytest.raises(datos.ErrorCascada, match="no tiene volumen"):
        datos.cascada(fibra, fibra, importes, SEM)


# --- Reglas ------------------------------------------------------------------


@pytest.mark.parametrize("modulo", [datos, semantica], ids=lambda m: m.__name__)
def test_solo_lee_vistas(modulo):
    """R32: las consultas de `datos` y de `semantica` leen solo vistas (o sus propias CTE)."""
    codigo = Path(modulo.__file__).read_text(encoding="utf-8")
    leidas = set(re.findall(r"\b(?:FROM|JOIN)\s+(\w+)", codigo))
    cte = set(re.findall(r"(\w+) AS \(", codigo))
    assert leidas, modulo.__name__
    assert {n for n in leidas - cte if not n.startswith("v_")} == set()


# --- Períodos del Overview ---------------------------------------------------

HOY = date(2026, 10, 6)
HISTORICO = datos.meses_entre("2024-08", "2026-08")  # 25 meses


def _meses(periodo, con_gasto=HISTORICO, **opciones):
    return datos.meses_del_periodo(periodo, con_gasto, HOY, **opciones)


def test_meses_entre_cruza_los_anios():
    assert datos.meses_entre("2025-11", "2026-02") == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert datos.meses_entre("2026-03", "2026-03") == ["2026-03"]


def test_cada_periodo_toma_los_meses_correctos():
    assert _meses("all") == HISTORICO and len(HISTORICO) == 25
    assert _meses("month", mes="2026-03") == ["2026-03"]
    assert _meses("year", anio=2025) == datos.meses_entre("2025-01", "2025-12")
    assert _meses("year", anio=2024) == datos.meses_entre("2024-08", "2024-12")  # solo desde la primera factura
    # El año en curso llega hasta el último mes con gasto, no hasta hoy (octubre).
    assert _meses("ytd") == datos.meses_entre("2026-01", "2026-08")
    # Los 12 últimos meses con datos, no los que terminan hoy (octubre de 2026).
    assert _meses("last12") == datos.meses_entre("2025-09", "2026-08")
    assert _meses("last12", con_gasto=["2026-01", "2026-04"]) == datos.meses_entre("2026-01", "2026-04")
    assert _meses("range", desde="2025-12", hasta="2026-02") == ["2025-12", "2026-01", "2026-02"]


def test_periodos_vacios_o_con_huecos():
    assert _meses("all", con_gasto=[]) == []
    assert _meses("month", mes="2030-01") == []
    assert _meses("range", desde="2026-05", hasta="2026-02") == []
    # Un mes sin facturas entre dos con gasto sigue siendo un mes del histórico.
    assert _meses("all", con_gasto=["2026-01", "2026-04"]) == ["2026-01", "2026-02", "2026-03", "2026-04"]
    with pytest.raises(ValueError):
        _meses("semana")


def test_la_casilla_excluye_los_meses_incompletos_del_total(base_ejemplos):
    _, controles = datos_prueba.CONTROLES
    categorias = ["agua", "gas"]
    gastos = datos.gasto_mensual(base_ejemplos)
    cobertura = datos.cobertura_mensual(base_ejemplos, categorias, "2026-04", "2026-08")
    completos = semantica.meses_completos(cobertura, categorias)
    meses = datos.meses_del_periodo("all", sorted({g.anio_mes for g in gastos}), HOY)

    # Con agua y gas (ejemplo de abr-jun), solo mayo está completo para los dos.
    assert datos.quitar_incompletos(meses, completos) == ["2026-05"]
    con = datos.total_por_categoria(gastos, datos.quitar_incompletos(meses, completos), categorias)
    for categoria in categorias:
        assert abs(con[categoria] - controles[(categoria, "2026-05")]) <= 1
    # Sin la casilla entran también abril, junio y los meses sin cobertura completa.
    sin = datos.total_por_categoria(gastos, meses, categorias)
    assert sum(sin.values()) > sum(con.values())
    # El total de todos los meses es el de la base (referencia: v_factura_vigente).
    todas = list(SEM)
    (total_base,) = base_ejemplos.execute("SELECT sum(importe_total_centimos) FROM v_factura_vigente").fetchone()
    assert sum(datos.total_por_categoria(gastos, meses, todas).values()) == total_base


def test_serie_mensual_rellena_con_cero_y_el_gasto_medio_redondea():
    gastos = [datos.GastoMes("2026-01", "agua", 1000), datos.GastoMes("2026-03", "agua", 500)]
    serie = datos.serie_mensual(gastos, ["2026-01", "2026-02", "2026-03"], ["agua", "gas"])
    assert [(g.anio_mes, g.categoria, g.importe_centimos) for g in serie] == [
        ("2026-01", "agua", 1000), ("2026-01", "gas", 0),
        ("2026-02", "agua", 0), ("2026-02", "gas", 0),
        ("2026-03", "agua", 500), ("2026-03", "gas", 0),
    ]
    assert datos.gasto_medio(1000, 3) == 333 and datos.gasto_medio(1001, 2) == 501 and datos.gasto_medio(5, 0) == 0


# --- Gráficos complementarios del Overview ------------------------------------


def test_media_movil_solo_con_meses_seguidos():
    totales = {"2026-01": 300, "2026-02": 600, "2026-03": 900, "2026-04": 1200}
    assert datos.media_movil(totales) == {"2026-03": 600, "2026-04": 900}
    # Sin febrero (excluido por incompleto) no hay ventana de 3 meses seguidos.
    assert datos.media_movil({"2026-01": 300, "2026-03": 900, "2026-04": 1200}) == {}
    assert datos.media_movil({"2026-01": 1, "2026-02": 2}) == {}


def test_interanual_compara_con_el_mismo_mes_del_anio_anterior():
    gastos = [
        datos.GastoMes("2025-08", "agua", 1000), datos.GastoMes("2025-08", "gas", 500),
        datos.GastoMes("2025-09", "agua", 2000),
        datos.GastoMes("2026-08", "agua", 1500), datos.GastoMes("2026-08", "gas", 700),
        datos.GastoMes("2026-09", "agua", 2500),
    ]
    con_gasto = datos.meses_entre("2025-08", "2026-09")
    assert datos.hace_un_anio("2026-03") == "2025-03"
    meses = ["2025-08", "2026-08", "2026-09"]
    # 2025-08 no tiene un mes un año antes dentro del histórico: queda fuera.
    assert datos.interanual(gastos, meses, ["agua", "gas"], con_gasto) == [
        ("2026-08", 2200, 1500), ("2026-09", 2500, 2000)]
    assert datos.interanual(gastos, meses, ["agua"], con_gasto) == [
        ("2026-08", 1500, 1000), ("2026-09", 2500, 2000)]


def test_total_mensual_suma_las_categorias_elegidas():
    gastos = [datos.GastoMes("2026-01", "agua", 100), datos.GastoMes("2026-01", "gas", 50)]
    assert datos.total_mensual(gastos, ["2026-01", "2026-02"], ["agua", "gas"]) == {"2026-01": 150, "2026-02": 0}
    assert datos.total_mensual(gastos, ["2026-01"], ["gas"]) == {"2026-01": 50}


# --- Analysis: grupos, conceptos, contratos y año anterior ---------------------


def _fila(factura_id, inicio, fin, categoria="agua", contrato="agua 1", proveedor="Aigües"):
    """Una `Factura` armada a mano, para probar las reglas de la serie sin base."""
    return datos.Factura(
        factura_id, 1, categoria, contrato, proveedor, fin, inicio, fin, 60, 1000, 500, 10000, "m³"
    )


def test_los_grupos_de_cada_factura_suman_el_total_de_la_vista(base_completa):
    """Referencia independiente: el total que guarda `v_factura_vigente`, no la suma de líneas."""
    totales = dict(base_completa.execute(
        "SELECT numero, importe_total_centimos FROM v_factura_vigente"
    ))
    filas = {f.factura_id: f for f in datos.facturas(base_completa, SEM)}
    importes = datos.importes_por_factura(base_completa, SEM)
    for categoria, numero in (("agua", "AGUA-PRUEBA-1"), ("agua", "AGUA-PRUEBA-2"), ("luz", "LUZ-PRUEBA-1")):
        por_grupo = datos.importes_por_grupo(importes, categoria)
        (factura_id,) = base_completa.execute("SELECT factura_id FROM factura WHERE numero = ?", (numero,)).fetchone()
        (clave,) = [k for k in por_grupo if k[0] == factura_id]
        assert sum(por_grupo[clave].values()) == totales[numero] == filas[factura_id].importe_centimos, numero
    # El agua de ejemplo: ciclo del agua 1523+1476+812+300+389 y residuos 1250+968.
    (clave,) = [k for k in datos.importes_por_grupo(importes, "agua") if k[0] == _id(base_completa, "AGUA-PRUEBA-1")]
    assert datos.importes_por_grupo(importes, "agua")[clave] == {"ciclo_agua": 4500, "residuos": 2218}


def _id(conexion, numero):
    (factura_id,) = conexion.execute("SELECT factura_id FROM factura WHERE numero = ?", (numero,)).fetchone()
    return factura_id


def test_importes_por_concepto_de_un_grupo(base_ejemplos):
    importes = datos.importes_por_factura(base_ejemplos, SEM)
    (por_concepto,) = datos.importes_por_concepto(importes, "agua", "ciclo_agua").values()
    assert por_concepto == {
        "cuota_servicio": 1523, "consumo_agua": 1104 + 372, "canon_agua": 812, "iva": 300, "alcantarillado": 389,
    }
    assert datos.importes_por_concepto(importes, "agua", "inexistente") == {}
    assert datos.importes_por_concepto(importes, "gas", "ciclo_agua") == {}


def test_los_cambios_de_contrato_o_de_comercializadora(base_completa):
    agua = [f for f in datos.facturas(base_completa, SEM) if f.categoria == "agua"]
    assert [f.contrato for f in agua] == ["agua 1", "agua 2"]
    assert datos.cambios_de_contrato(agua) == [1]
    assert datos.cambios_de_contrato(agua[:1]) == [] == datos.cambios_de_contrato([])
    # Mismo contrato y otra comercializadora también es un cambio; mismo contrato y proveedor, no.
    serie = [_fila(1, "2025-01-01", "2025-02-28"), _fila(2, "2025-03-01", "2025-04-30"),
             _fila(3, "2025-05-01", "2025-06-30", proveedor="Otra")]
    assert datos.cambios_de_contrato(serie) == [2]


def test_el_mismo_periodo_del_anio_anterior_es_el_de_punto_medio_mas_cercano():
    # Facturas bimestrales de 2025 (ids 1 a 6) y la última, del 10 de abril al 8 de junio de 2026.
    serie = [
        _fila(1, "2025-02-11", "2025-04-10"), _fila(2, "2025-04-11", "2025-06-10"),
        _fila(3, "2025-06-11", "2025-08-08"), _fila(4, "2025-08-09", "2025-10-08"),
        _fila(5, "2026-02-06", "2026-04-09"), _fila(6, "2026-04-10", "2026-06-08"),
    ]
    assert datos.factura_del_anio_anterior(serie, serie[5]).factura_id == 2
    # Un período desfasado: el de hace un año (6 feb–9 abr de 2025) solo solapa con la 1.
    assert datos.factura_del_anio_anterior(serie, serie[4]).factura_id == 1
    # Una factura nunca es su propia comparación, y sin año anterior en el histórico no hay nada.
    assert datos.factura_del_anio_anterior(serie, serie[0]) is None
    assert datos.factura_del_anio_anterior(serie[3:], serie[5]) is None


def test_el_anio_anterior_cruza_contratos_pero_no_categorias():
    ultima = _fila(9, "2026-04-10", "2026-06-08", contrato="agua 2")
    vieja_otro_contrato = _fila(1, "2025-04-11", "2025-06-10", contrato="agua 1")
    de_otra_categoria = _fila(2, "2025-04-11", "2025-06-10", categoria="gas", contrato="gas 1")
    assert datos.factura_del_anio_anterior([de_otra_categoria, vieja_otro_contrato, ultima], ultima).factura_id == 1
    assert datos.factura_del_anio_anterior([de_otra_categoria, ultima], ultima) is None


def test_el_29_de_febrero_se_desplaza_al_28():
    ultima = _fila(9, "2024-02-20", "2024-02-29")
    anterior = _fila(1, "2023-02-15", "2023-02-28")
    assert datos.factura_del_anio_anterior([anterior, ultima], ultima).factura_id == 1


def test_el_consumo_por_franja_suma_el_volumen_de_la_factura(base_completa):
    filas = datos.facturas(base_completa, SEM)
    luz = _factura(filas, "LUZ-PRUEBA-1", base_completa)
    consumo = datos.consumo_por_factura(base_completa)
    por_franja = datos.consumo_por_franja(consumo, "luz", SEM["luz"].magnitud)
    # Las tres franjas del ejemplo, en kWh: 20 + 21 + 40 = 81 (el volumen de la factura).
    assert por_franja[(luz.factura_id, luz.contrato_id)] == {"punta": 20000, "llano": 21000, "valle": 40000}
    assert sum(por_franja[(luz.factura_id, luz.contrato_id)].values()) == luz.volumen_milesimas
    # El gas no tiene franjas; una magnitud o una categoría ajenas no dan nada.
    gas = _factura(filas, "GAS-PRUEBA-1", base_completa)
    assert datos.consumo_por_franja(consumo, "gas", "energia")[(gas.factura_id, gas.contrato_id)] == {
        "sin_franja": 344000 - 11470}
    assert datos.consumo_por_franja(consumo, "luz", "volumen") == {}


def test_una_factura_estimada_se_marca_salvo_que_la_rectificativa_la_corrija_con_lectura_real(base_completa):
    estimada = datos_prueba.variante(
        datos_prueba.FACTURA_GAS, "GAS-PRUEBA-0", "2025-08-30", "2025-06-26", "2025-08-25")  # 344 kWh estimados
    datos_prueba.insertar(base_completa, estimada)
    filas = datos.facturas(base_completa, SEM)
    consumo = datos.consumo_por_factura(base_completa)
    marcadas = datos.facturas_estimadas(consumo, SEM)
    cero = _factura(filas, "GAS-PRUEBA-0", base_completa)
    assert marcadas == {(cero.factura_id, cero.contrato_id)}
    # GAS-PRUEBA-1 era estimada, pero su rectificativa trae una lectura real: cuenta como real.
    uno = _factura(filas, "GAS-PRUEBA-1", base_completa)
    assert (uno.factura_id, uno.contrato_id) not in marcadas


def test_una_estimacion_de_otra_magnitud_no_marca_la_factura():
    consumo = [
        datos.ConsumoFactura(1, 1, "luz", "energia", "kWh", "punta", "estimada", 10000),
        datos.ConsumoFactura(2, 1, "luz", "potencia", "kW", "sin_franja", "estimada", 4400),
        datos.ConsumoFactura(3, 1, "luz", "energia", "kWh", "valle", "real", 5000),
    ]
    assert datos.facturas_estimadas(consumo, SEM) == {(1, 1)}


def test_una_factura_entera_suma_las_lineas_de_cada_factura(base_ejemplos):
    filas = [f for f in datos.facturas(base_ejemplos, SEM) if f.categoria in ("fibra", "movil")]
    assert len(filas) == 2  # una fila por línea (fibra 1 y movil 1)
    (entera,) = datos.facturas_enteras(filas)
    (total,) = base_ejemplos.execute(
        "SELECT importe_total_centimos FROM v_factura_vigente WHERE numero = 'DIGI-PRUEBA-1'"
    ).fetchone()
    # Referencia independiente: el total que guarda la vista (1840 + 386 de la fibra y 615 + 7 + 131 del móvil).
    assert entera.importe_centimos == total == 2979
    assert entera.contrato == "fibra 1, movil 1" and entera.contrato_id == 0
    assert (entera.fecha_inicio, entera.fecha_fin, entera.dias) == ("2026-07-15", "2026-08-14", 31)
    assert entera.volumen_milesimas is None and entera.precio_unitario is None


def test_las_facturas_enteras_van_por_fecha_aunque_las_filas_no():
    def fila(factura_id, contrato_id, alias, inicio, fin, importe):
        return datos.Factura(factura_id, contrato_id, "movil", alias, "DIGI", fin, inicio, fin, 30, importe, 0, None, None)

    filas = [
        fila(2, 1, "movil 1", "2026-02-01", "2026-02-28", 500), fila(1, 1, "movil 1", "2026-01-01", "2026-01-31", 400),
        fila(1, 2, "movil 2", "2026-01-01", "2026-01-31", 300), fila(2, 2, "movil 2", "2026-02-01", "2026-02-28", 350),
    ]
    assert [(f.factura_id, f.importe_centimos, f.contrato) for f in datos.facturas_enteras(filas)] == [
        (1, 700, "movil 1, movil 2"), (2, 850, "movil 1, movil 2")]
    assert datos.facturas_enteras([]) == []


def test_un_cambio_de_cuota_es_una_cuota_distinta_de_la_factura_anterior_de_la_linea():
    assert datos.cambios_de_cuota([1840, 1840, 1999, 1840]) == [2, 3]
    # La primera factura de una línea no es un cambio (aunque venga a medias), y una línea
    # ausente en una factura no rompe la comparación con la última en que estuvo.
    assert datos.cambios_de_cuota([None, 310, 420, 420, None]) == [2]
    assert datos.cambios_de_cuota([100, None, 100, None, 90]) == [4]
    assert datos.cambios_de_cuota([]) == datos.cambios_de_cuota([None, None]) == datos.cambios_de_cuota([5]) == []
