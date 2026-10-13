"""Consultas de referencia C1, C2 y C4-C7 con las facturas de ejemplo: responden las preguntas del dashboard.

Las facturas son las de `datos_prueba.py`: los ejemplos del caso con importes ficticios.
Los valores esperados son sus controles (`datos_prueba.CONTROLES`, calculados a mano
como los del caso) y sus líneas y mediciones.
"""

import json
from pathlib import Path

import pytest

import datos_prueba

DIR_CONSULTAS = Path(__file__).resolve().parents[1] / "src" / "facturas" / "bd" / "consultas"
TODO_EL_HISTORICO = {"mes_desde": "0000-01", "mes_hasta": "9999-12"}


def consulta(conexion, nombre, **parametros):
    """Ejecuta src/facturas/bd/consultas/<nombre>*.sql y devuelve las filas como diccionarios."""
    (archivo,) = DIR_CONSULTAS.glob(f"{nombre}_*.sql")
    if "categorias" in parametros:
        parametros["categorias"] = json.dumps(parametros["categorias"])
    cursor = conexion.execute(archivo.read_text(encoding="utf-8"), parametros)
    columnas = [d[0] for d in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor]


def test_c1_gasto_por_categoria_y_total(base_ejemplos):
    totales, reparto = datos_prueba.CONTROLES
    filas = consulta(base_ejemplos, "c1", categorias=list(totales), **TODO_EL_HISTORICO)
    assert {f["categoria_codigo"]: f["importe_centimos"] for f in filas} == {**totales, "total": sum(totales.values())}

    # Selección múltiple y un solo mes: fibra y móvil en julio.
    filas = consulta(base_ejemplos, "c1", categorias=["fibra", "movil"], mes_desde="2026-07", mes_hasta="2026-07")
    resultado = {f["categoria_codigo"]: f["importe_centimos"] for f in filas}
    assert resultado["fibra"] == pytest.approx(reparto[("fibra", "2026-07")], abs=1)
    assert resultado["movil"] == pytest.approx(reparto[("movil", "2026-07")], abs=1)
    assert resultado["total"] == resultado["fibra"] + resultado["movil"]


def test_c1_sin_datos_devuelve_total_cero(base_ejemplos):
    assert consulta(base_ejemplos, "c1", categorias=["agua"], mes_desde="2025-01", mes_hasta="2025-12") == [
        {"categoria_codigo": "total", "importe_centimos": 0}]


def test_c2_evolucion_mensual_por_categoria(base_ejemplos):
    _, reparto = datos_prueba.CONTROLES
    filas = consulta(base_ejemplos, "c2", categorias=["agua", "gas", "luz"], mes_desde="2026-04", mes_hasta="2026-06")
    por_clave = {(f["anio_mes"], f["categoria_codigo"]): f for f in filas}
    assert len(por_clave) == len(filas)
    for (categoria, mes), importe in reparto.items():
        if categoria in ("agua", "gas", "luz"):
            assert por_clave[(mes, categoria)]["importe_centimos"] == pytest.approx(importe, abs=1)

    # Sin la luz y con un solo mes, devuelve solo las categorías elegidas.
    filas = consulta(base_ejemplos, "c2", categorias=["agua", "gas"], mes_desde="2026-05", mes_hasta="2026-05")
    assert [(f["anio_mes"], f["categoria_codigo"]) for f in filas] == [("2026-05", "agua"), ("2026-05", "gas")]


def test_c4_fibra_y_movil_por_separado(base_ejemplos):
    totales, _ = datos_prueba.CONTROLES
    c4 = consulta(base_ejemplos, "c4", categorias=["fibra", "movil"], **TODO_EL_HISTORICO)
    por_categoria = {}
    for f in c4:
        por_categoria[f["categoria_codigo"]] = por_categoria.get(f["categoria_codigo"], 0) + f["importe_centimos"]
    assert por_categoria == {"fibra": totales["fibra"], "movil": totales["movil"]}
    # El consumo adicional del móvil (SMS, 0,07) aparece en el desglose por concepto.
    adicional = sum(f["importe_centimos"] for f in c4 if f["concepto_codigo"] == "consumo_adicional")
    assert adicional == 7


def test_c4_desglose_por_concepto(base_ejemplos):
    filas = consulta(base_ejemplos, "c4", categorias=["luz"], **TODO_EL_HISTORICO)
    por_concepto = {}
    for f in filas:
        por_concepto[f["concepto_codigo"]] = por_concepto.get(f["concepto_codigo"], 0) + f["importe_centimos"]
    assert por_concepto == {
        "consumo_electricidad": 1253, "potencia_p1": 1388, "potencia_p2": 562,
        "bono_social": 71, "alquiler_contador": 95, "impuesto_electricidad": 167, "iva": 743,
    }


@pytest.mark.parametrize("categoria, concepto, unidad, cantidad, importe_consumo", [
    ("agua", "consumo_agua", "m³", 15000, 1104 + 372),  # 15 m³; tramos de consumo 11,04 + 3,72
    ("gas", "consumo_gas", "kWh", 344000, 2412),        # 344 kWh; consumo gas 24,12
    ("luz", "consumo_electricidad", "kWh", 81000, 1253),  # 81 kWh; consumo electricidad 12,53
])
def test_c5_volumen_o_energia_y_precio_efectivo(base_ejemplos, categoria, concepto, unidad, cantidad, importe_consumo):
    filas = consulta(base_ejemplos, "c5", categoria=categoria, conceptos=json.dumps([concepto]), **TODO_EL_HISTORICO)
    assert {f["unidad"] for f in filas} == {unidad}
    assert sum(f["cantidad_milesimas"] for f in filas) == cantidad
    assert sum(f["importe_consumo_centimos"] for f in filas) == importe_consumo
    precio = (importe_consumo / 100) / (cantidad / 1000)  # agua ≈ 0,984 €/m³
    for f in filas:
        assert f["precio_efectivo"] == pytest.approx(precio, rel=0.01), f["anio_mes"]


@pytest.mark.parametrize("categoria, tipo_lectura, cantidad", [("gas", "estimada", 344000), ("luz", "real", 81000)])
def test_c6_consumo_segun_lecturas_reales_o_estimadas(base_ejemplos, categoria, tipo_lectura, cantidad):
    filas = consulta(base_ejemplos, "c6", categoria=categoria, **TODO_EL_HISTORICO)
    assert {f["tipo_lectura"] for f in filas} == {tipo_lectura}
    assert sum(f["cantidad_milesimas"] for f in filas) == cantidad


def test_c7_consumo_de_luz_por_franja(base_ejemplos):
    por_franja = {}
    for f in consulta(base_ejemplos, "c7", categoria="luz", **TODO_EL_HISTORICO):
        por_franja[f["franja_codigo"]] = por_franja.get(f["franja_codigo"], 0) + f["cantidad_milesimas"]
    assert por_franja == {"punta": 20000, "llano": 21000, "valle": 40000}
