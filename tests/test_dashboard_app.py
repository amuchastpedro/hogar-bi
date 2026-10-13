"""La app del dashboard con AppTest, sobre una base de prueba (nunca datos/facturas.db)."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import datos_prueba
from facturas.dashboard import datos, graficos

APP = Path(__file__).resolve().parents[1] / "src" / "facturas" / "dashboard" / "app.py"


@pytest.fixture
def app(base_ejemplos, ruta_base, monkeypatch):
    monkeypatch.setattr(datos, "RUTA_BASE", ruta_base)
    return AppTest.from_file(str(APP), default_timeout=30).run()


def _metricas(at):
    return {m.label: m.value for m in at.metric}


def test_la_app_arranca_sin_errores(app):
    assert not app.exception
    assert app.title[0].value == "Overview"


def test_el_total_del_historico_es_el_de_las_facturas(app, base_ejemplos):
    (total,) = base_ejemplos.execute("SELECT sum(importe_total_centimos) FROM v_factura_vigente").fetchone()
    assert total == 6718 + 4271 + 4279 + 2979
    metricas = _metricas(app)
    assert metricas["Total spend"] == graficos.formato_importe(total)
    # Los servicios van en el orden de bi-hogar: gas, luz, agua, wifi, móvil.
    assert list(metricas) == ["Total spend", "Average per month", "Gas", "Electricity", "Water", "Wifi", "Mobile"]


def test_los_filtros_cambian_el_resultado(app):
    todo = _metricas(app)["Total spend"]
    app.pills(key="service_filter").set_value(["agua"]).run()
    assert not app.exception
    assert _metricas(app)["Total spend"] == graficos.formato_importe(6718)
    assert set(_metricas(app)) == {"Total spend", "Average per month", "Water"}
    app.pills(key="service_filter").set_value(["agua", "gas", "luz", "fibra", "movil"]).run()
    assert _metricas(app)["Total spend"] == todo
    for periodo in ("month", "year", "ytd", "last12", "range"):
        app.selectbox[0].set_value(periodo).run()
        assert not app.exception, periodo
    app.checkbox[0].check().run()
    assert not app.exception


def _pagina_analysis():
    from facturas.dashboard.paginas import analysis

    analysis.mostrar()


def _analysis(base, ruta_base, monkeypatch):
    monkeypatch.setattr(datos, "RUTA_BASE", ruta_base)
    return AppTest.from_function(_pagina_analysis, default_timeout=30).run()


def test_la_pagina_analysis_tiene_sus_cuatro_pestanas(base_ejemplos, ruta_base, monkeypatch):
    at = _analysis(base_ejemplos, ruta_base, monkeypatch)
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Water", "Electricity", "Gas", "DIGI"]


def test_formato_de_importes():
    assert graficos.formato_importe(123456) == "1.234,56 €"
    assert graficos.formato_importe(5) == "0,05 €"
    assert graficos.formato_importe(-1104) == "-11,04 €"
    assert graficos.formato_mes("2026-08") == "Aug 2026"


def test_cada_boton_de_servicio_toma_el_color_de_su_servicio():
    for i, categoria in enumerate(graficos.ORDEN_SERVICIOS):
        regla = f'button[id$="-{i}"][aria-checked="true"]'
        assert regla in graficos.CSS
        assert f"border-color: {graficos.COLORES[categoria]}" in graficos.CSS


# --- Analysis: Water, Electricity y Gas ------------------------------------------
#
# La base de prueba (los ejemplos, un segundo período de agua y de gas, y la rectificativa del gas)
# más una factura de hace un año por servicio, para que haya mismo período del año anterior:
#
# - agua: AGUA-PRUEBA-0 (9 jun–7 ago de 2025, copia exacta del ejemplo, contrato «agua 1»),
#   AGUA-PRUEBA-1 (el ejemplo, 10 abr–8 jun de 2026) y AGUA-PRUEBA-2 (9 jun–7 ago de 2026,
#   otro contrato, «agua 2»);
# - gas: GAS-PRUEBA-0 (26 jun–25 ago de 2025, copia del ejemplo: 344 kWh con lectura estimada),
#   GAS-PRUEBA-1 (el ejemplo, con su rectificativa) y GAS-PRUEBA-2 (26 jun–25 ago de 2026);
# - luz: LUZ-PRUEBA-0 (27 may–28 jun de 2025, como el ejemplo salvo el consumo, 10,00 €, y el IVA,
#   7,00 €) y LUZ-PRUEBA-1 (el ejemplo, 27 may–28 jun de 2026).
# Los importes son los ficticios de `datos_prueba.py`.

AGUA_ANTERIOR = datos_prueba.variante(
    datos_prueba.FACTURA_AGUA, "AGUA-PRUEBA-0", "2025-08-20", "2025-06-09", "2025-08-07"
)
GAS_ANTERIOR = datos_prueba.variante(
    datos_prueba.FACTURA_GAS, "GAS-PRUEBA-0", "2025-08-30", "2025-06-26", "2025-08-25"
)
_LUZ = "CUPS-LUZ-PRUEBA"
LUZ_ANTERIOR = datos_prueba.variante(
    datos_prueba.FACTURA_LUZ, "LUZ-PRUEBA-0", "2025-07-03", "2025-05-27", "2025-06-28",
    lineas=[
        datos_prueba.linea(_LUZ, "consumo_electricidad", "Consumo electricidad", 1000),
        datos_prueba.linea(_LUZ, "potencia_p1", "Término potencia P1", 1388),
        datos_prueba.linea(_LUZ, "potencia_p2", "Término potencia P2", 562),
        datos_prueba.linea(_LUZ, "bono_social", "Financiación de Bono Social", 71),
        datos_prueba.linea(_LUZ, "impuesto_electricidad", "Impuesto electricidad", 167),
        datos_prueba.linea(_LUZ, "alquiler_contador", "Alquiler de contador", 95),
        datos_prueba.linea(_LUZ, "iva", "IVA (21%)", 700),
    ],
)  # total 3983


@pytest.fixture
def servicios(base_completa, ruta_base, monkeypatch):
    for factura in (AGUA_ANTERIOR, GAS_ANTERIOR, LUZ_ANTERIOR):
        datos_prueba.insertar(base_completa, factura)
    return _analysis(base_completa, ruta_base, monkeypatch)


PESTANAS = {"Water": 0, "Electricity": 1, "Gas": 2, "DIGI": 3}


def _pestana(at, nombre):
    return at.tabs[PESTANAS[nombre]]


def _figuras(at, nombre):
    """Las figuras Plotly de una pestaña, en orden, como diccionarios."""
    return [json.loads(e.proto.spec) for e in _pestana(at, nombre).get("plotly_chart")]


def _y_por_serie(figura):
    """Nombre de cada serie → sus valores (uno por factura)."""
    return {t["name"]: t["y"] for t in figura["data"]}


def _centimos(valores):
    return [round(100 * v) for v in valores]


def _textos(elementos):
    return [e.value for e in elementos]


def _totales(conexion, *numeros_por_factura):
    """El total de cada factura de la vista `v_factura_vigente` (varios números se suman)."""
    return [
        sum(conexion.execute("SELECT importe_total_centimos FROM v_factura_vigente WHERE numero = ?", (n,)).fetchone()[0]
            for n in numeros)
        for numeros in numeros_por_factura
    ]


# --- Water


def test_la_pestana_water_dibuja_todo_el_patron_comun(servicios):
    assert not servicios.exception
    agua = _pestana(servicios, "Water")
    assert _textos(agua.subheader) == [
        "Composition by group", "Weight of each group", "Breakdown by charge",
        "Volume (m³)", "Effective unit price", "What changed between two invoices",
    ]
    # Composición, pesos, el desglose del ciclo del agua y el de los residuos, volumen, precio y cascada.
    assert [f["data"][0]["type"] for f in _figuras(servicios, "Water")] == ["bar"] * 5 + ["scatter", "waterfall"]


def test_en_water_cada_factura_suma_su_total(servicios, base_completa):
    """Referencia independiente: el total que guarda `v_factura_vigente` (6718, 6718 y 7643)."""
    totales = [t for (t,) in base_completa.execute(
        "SELECT importe_total_centimos FROM v_factura_vigente WHERE numero LIKE 'AGUA-PRUEBA-%' ORDER BY fecha_inicio"
    )]
    assert totales == [6718, 6718, 7643]
    composicion, pesos, ciclo, residuos, *_ = _figuras(servicios, "Water")
    por_grupo = _y_por_serie(composicion)
    assert set(por_grupo) == {"Water cycle", "Waste"}
    assert _centimos(map(sum, zip(*por_grupo.values()))) == totales
    # Los pesos de cada factura suman 100 %, y son los de cada grupo sobre su total.
    for i, total in enumerate(totales):
        pesos_i = {nombre: y[i] for nombre, y in _y_por_serie(pesos).items()}
        assert sum(pesos_i.values()) == pytest.approx(100)
        assert pesos_i["Waste"] == pytest.approx(100 * (por_grupo["Waste"][i] * 100) / total)
    # Los pesos de la última factura (7643: residuos 22,18 €) también están escritos.
    assert "Latest invoice: Water cycle 71,0 % · Waste 29,0 %." in _textos(_pestana(servicios, "Water").caption)
    # El desglose por concepto suma lo mismo que su grupo, factura a factura.
    por_concepto = _y_por_serie(ciclo)
    assert list(por_concepto) == ["Service fee", "Water consumption", "Water levy", "Sewerage fee", "VAT"]
    assert _centimos(map(sum, zip(*por_concepto.values()))) == _centimos(por_grupo["Water cycle"])
    assert _centimos(map(sum, zip(*_y_por_serie(residuos).values()))) == _centimos(por_grupo["Waste"])


def test_los_colores_de_cada_grupo_son_los_de_su_posicion(servicios):
    composicion, pesos, ciclo, *_ = _figuras(servicios, "Water")
    esperado = {"Water cycle": graficos.RANURAS[0], "Waste": graficos.RANURAS[1]}
    for figura in (composicion, pesos):
        assert {t["name"]: t["marker"]["color"] for t in figura["data"]} == esperado
    # Los conceptos toman la ranura de su posición dentro del grupo.
    assert [t["marker"]["color"] for t in ciclo["data"]] == list(graficos.RANURAS[:5])


def test_el_volumen_y_el_precio_unitario_son_los_de_las_facturas(servicios):
    *_, volumen, precio, _ = _figuras(servicios, "Water")
    assert volumen["data"][0]["y"] == [15, 15, 18]  # m³
    assert volumen["data"][0]["marker"]["color"] == graficos.COLORES["agua"]
    # Importe variable / volumen: 26,77/15 = 1,7847 y 35,65/18 = 1,9806 (€/m³, sin IVA).
    assert precio["data"][0]["y"] == pytest.approx([1.7847, 1.7847, 1.9806], abs=1e-4)
    assert "All the invoices are based on real readings." in _textos(_pestana(servicios, "Water").caption)


def test_el_cambio_de_contrato_queda_marcado_en_el_eje(servicios):
    composicion, *_ = _figuras(servicios, "Water")
    # Entre la 2.ª y la 3.ª factura (posiciones 1 y 2) cambia el alias: «agua 1» → «agua 2».
    (linea,) = composicion["layout"]["shapes"]
    assert linea["x0"] == 1.5
    assert composicion["layout"]["annotations"][0]["text"] == "Contract change"
    assert any("agua 1" in c and "agua 2" in c for c in _textos(_pestana(servicios, "Water").caption))
    # La luz y el gas no cambian de contrato en la base de prueba.
    for pestana in ("Electricity", "Gas"):
        assert not _figuras(servicios, pestana)[0]["layout"].get("shapes")


def test_la_cascada_por_defecto_compara_con_el_mismo_periodo_del_anio_anterior(servicios):
    assert servicios.radio(key="agua_comparison").value == "Same period last year"
    assert {m.label: m.value for m in _pestana(servicios, "Water").metric} == {
        "Invoice A: 9 Jun 2025 – 7 Aug 2025": graficos.formato_importe(6718),
        "Invoice B: 9 Jun 2026 – 7 Aug 2026": graficos.formato_importe(7643),
    }
    cascada = _figuras(servicios, "Water")[-1]["data"][0]
    assert cascada["measure"] == ["absolute"] + ["relative"] * 4 + ["total"]
    assert cascada["x"] == [
        "Invoice A<br>60 days", "Volume effect", "Price effect", "Water cycle<br>(fixed part)", "Waste",
        "Invoice B<br>60 days",
    ]
    # Calculada a mano (tests de datos): volumen 5,35, precio 3,53, ciclo del agua 0,37 y residuos 0.
    assert cascada["y"] == [67.18, 5.35, 3.53, 0.37, 0.0, 76.43]
    # A más los cambios da B, exacto en céntimos.
    assert sum(_centimos(cascada["y"][:5])) == _centimos(cascada["y"])[5]


def test_la_cascada_se_puede_hacer_con_la_factura_anterior_o_con_dos_elegidas(servicios):
    metricas = lambda: _pestana(servicios, "Water").metric
    servicios.radio(key="agua_comparison").set_value("Previous invoice").run()
    assert not servicios.exception
    assert [m.value for m in metricas()] == [graficos.formato_importe(6718), graficos.formato_importe(7643)]
    assert metricas()[0].label.startswith("Invoice A: 10 Apr 2026")

    servicios.radio(key="agua_comparison").set_value("Pick two invoices").run()
    assert not servicios.exception
    # Por defecto, A es la penúltima y B la última. Las opciones de los selectores son las posiciones
    # de la serie (0 es la más antigua; `select_index` de AppTest no sirve con un `format_func`).
    assert metricas()[0].label.startswith("Invoice A: 10 Apr 2026")
    servicios.selectbox(key="agua_a").set_value(0).run()
    assert metricas()[0].label.startswith("Invoice A: 9 Jun 2025")
    servicios.selectbox(key="agua_b").set_value(1).run()
    assert metricas()[1].label.startswith("Invoice B: 10 Apr 2026")
    assert not servicios.exception
    # Dos veces la misma factura no compara nada.
    servicios.selectbox(key="agua_b").set_value(0).run()
    assert "Pick two different invoices." in _textos(_pestana(servicios, "Water").info)


def test_el_zoom_de_la_cascada_cambia_solo_el_eje(servicios):
    sin_zoom = _figuras(servicios, "Water")[-1]
    servicios.toggle(key="agua_zoom").set_value(True).run()
    con_zoom = _figuras(servicios, "Water")[-1]
    assert con_zoom["data"] == sin_zoom["data"]
    assert "range" not in sin_zoom["layout"]["yaxis"]
    assert con_zoom["layout"]["yaxis"]["range"][0] > 0


def test_sin_facturas_de_agua_la_pestana_lo_dice(base, ruta_base, monkeypatch):
    at = _analysis(base, ruta_base, monkeypatch)
    assert not at.exception
    assert "There are no water invoices loaded yet." in _textos(_pestana(at, "Water").info)


def test_con_una_sola_factura_la_cascada_pide_otra(base_ejemplos, ruta_base, monkeypatch):
    at = _analysis(base_ejemplos, ruta_base, monkeypatch)
    assert not at.exception
    for pestana in ("Water", "Electricity"):
        assert "A comparison needs at least two invoices." in _textos(_pestana(at, pestana).info)


def test_sin_factura_un_anio_atras_la_cascada_empieza_por_la_anterior(base_completa, ruta_base, monkeypatch):
    at = _analysis(base_completa, ruta_base, monkeypatch)  # solo 2026: nada un año atrás
    assert not at.exception
    assert at.radio(key="agua_comparison").value == "Previous invoice"
    at.radio(key="agua_comparison").set_value("Same period last year").run()
    assert "No invoice covers the same period a year before the latest one." in _textos(_pestana(at, "Water").info)


# --- Electricity


def test_la_pestana_electricity_tiene_el_patron_comun_y_el_consumo_por_franja(servicios):
    luz = _pestana(servicios, "Electricity")
    assert _textos(luz.subheader) == [
        "Composition by group", "Weight of each group", "Breakdown by charge", "Volume (kWh)",
        "Consumption by time band", "Effective unit price", "What changed between two invoices",
    ]
    # Composición, pesos, desglose de Power, Other fixed y Taxes (Energy tiene un solo concepto),
    # volumen, franjas, precio y cascada.
    assert [f["data"][0]["type"] for f in _figuras(servicios, "Electricity")] == ["bar"] * 7 + ["scatter", "waterfall"]


def test_en_electricity_cada_factura_suma_su_total_y_las_franjas_su_volumen(servicios, base_completa):
    totales = _totales(base_completa, ["LUZ-PRUEBA-0"], ["LUZ-PRUEBA-1"])
    assert totales == [3983, 4279]
    composicion, _, *desglose, volumen, franjas, precio, _cascada = _figuras(servicios, "Electricity")
    por_grupo = _y_por_serie(composicion)
    assert list(por_grupo) == ["Energy", "Power", "Other fixed", "Taxes"]
    assert [t["marker"]["color"] for t in composicion["data"]] == list(graficos.RANURAS[:4])
    assert _centimos(map(sum, zip(*por_grupo.values()))) == totales
    # Los desgloses suman lo de su grupo. En pantalla van en dos columnas (Power | Other fixed, y debajo
    # Taxes), pero AppTest recorre primero la columna izquierda entera.
    for figura, grupo in zip(desglose, ("Power", "Taxes", "Other fixed")):
        assert _centimos(map(sum, zip(*_y_por_serie(figura).values()))) == _centimos(por_grupo[grupo])
    # Las franjas, en kWh y en orden, suman el volumen de la factura (20 + 21 + 40 = 81).
    por_franja = _y_por_serie(franjas)
    assert por_franja == {"Peak": [20, 20], "Standard": [21, 21], "Off-peak": [40, 40]}
    assert [sum(v) for v in zip(*por_franja.values())] == volumen["data"][0]["y"] == [81, 81]
    # Precio unitario de la energía: 12,53 € / 81 kWh = 0,1547 (y 10,00 / 81 = 0,1235 en la anterior).
    assert precio["data"][0]["y"] == pytest.approx([0.1235, 0.1547], abs=1e-4)
    # Todas las lecturas son reales: no hay serie de estimadas.
    assert [t["name"] for t in volumen["data"]] == ["Real reading"]
    assert "All the invoices are based on real readings." in _textos(_pestana(servicios, "Electricity").caption)


def test_la_cascada_de_electricity_calculada_a_mano(servicios):
    metricas = {m.label: m.value for m in _pestana(servicios, "Electricity").metric}
    assert list(metricas.values()) == [graficos.formato_importe(3983), graficos.formato_importe(4279)]
    cascada = _figuras(servicios, "Electricity")[-1]["data"][0]
    # El mismo volumen (81 kWh): sin efecto volumen. La energía sube de 10,00 a 12,53 (efecto precio,
    # 2,53) y el IVA de 7,00 a 7,43 (impuestos, 0,43). La energía no tiene parte fija, así que no
    # tiene paso propio; potencia y otros fijos no cambian.
    assert cascada["x"] == [
        "Invoice A<br>33 days", "Volume effect", "Price effect", "Power", "Other fixed", "Taxes",
        "Invoice B<br>33 days",
    ]
    assert cascada["y"] == [39.83, 0.0, 2.53, 0.0, 0.0, 0.43, 42.79]


# --- Gas


def test_la_pestana_gas_marca_las_facturas_estimadas(servicios):
    gas = _pestana(servicios, "Gas")
    assert _textos(gas.subheader) == [
        "Composition by group", "Weight of each group", "Breakdown by charge", "Volume (kWh)",
        "Effective unit price", "What changed between two invoices",
    ]
    composicion, _, impuestos, volumen, precio, _cascada = _figuras(servicios, "Gas")
    # Solo GAS-PRUEBA-0 (344 kWh estimados) es estimada; GAS-PRUEBA-1 la corrige con una lectura real.
    por_lectura = {t["name"]: (t["x"], t["y"]) for t in volumen["data"]}
    assert por_lectura == {"Real reading": ([1, 2], [332.53, 183.52]), "Estimated reading": ([0], [344])}
    (estimada,) = [t for t in volumen["data"] if t["name"] == "Estimated reading"]
    assert estimada["marker"]["opacity"] == 0.45 and estimada["marker"]["color"] == graficos.COLORES["gas"]
    assert volumen["layout"]["showlegend"] is True
    # Las facturas estimadas también se marcan en el eje, en todos los gráficos por factura.
    for figura in (composicion, volumen, precio):
        textos = figura["layout"]["xaxis"]["ticktext"]
        assert textos[0].endswith("<br>estimated") and not textos[1].endswith("estimated")
    assert "1 of 3 invoices are based on estimated readings (344 of 860 kWh): the faded bars, " \
        "marked «estimated» on the axis." in _textos(gas.caption)
    # Los impuestos son el único grupo con dos conceptos, y el volumen es el de las facturas.
    assert list(_y_por_serie(impuestos)) == ["Hydrocarbons tax", "VAT"]


def test_en_gas_cada_factura_suma_su_total(servicios, base_completa):
    """Referencia independiente: la factura y su rectificativa en `v_factura_vigente` (4271 − 1104)."""
    totales = _totales(base_completa, ["GAS-PRUEBA-0"], ["GAS-PRUEBA-1", "GAS-PRUEBA-1R"], ["GAS-PRUEBA-2"])
    assert totales == [4271, 4271 - 1104, 2963]
    composicion = _figuras(servicios, "Gas")[0]
    por_grupo = _y_por_serie(composicion)
    assert list(por_grupo) == ["Energy", "Fixed", "Taxes"]  # «Other fixed» no tiene importes
    # Los colores son los de la posición en `semantica.toml` (el grupo ausente conserva su ranura).
    assert [t["marker"]["color"] for t in composicion["data"]] == [
        graficos.RANURAS[0], graficos.RANURAS[1], graficos.RANURAS[3]]
    assert _centimos(map(sum, zip(*por_grupo.values()))) == totales


def test_la_cascada_de_gas_calculada_a_mano(servicios):
    cascada = _figuras(servicios, "Gas")[-1]["data"][0]
    # A = GAS-PRUEBA-0: 344 kWh y 24,53 € variables (consumo 24,12 + hidrocarburos 0,41).
    # B = GAS-PRUEBA-2: 183,52 kWh y 13,72 € (13,50 + 0,22).
    # Volumen: (183,52 − 344) × 24,53/344 = −11,44. Precio: 13,72 − 24,53 + 11,44 = 0,63.
    # Término fijo igual; IVA 7,41 → 5,14 (−2,27). 42,71 − 11,44 + 0,63 − 2,27 = 29,63.
    assert cascada["x"] == [
        "Invoice A<br>61 days", "Volume effect", "Price effect", "Fixed", "Other fixed", "Taxes<br>(fixed part)",
        "Invoice B<br>61 days",
    ]
    assert cascada["y"] == [42.71, -11.44, 0.63, 0.0, 0.0, -2.27, 29.63]
    assert round(100 * sum(cascada["y"][:6])) == round(100 * cascada["y"][6])


# --- DIGI

# Tres facturas mensuales (con la del ejemplo, la última), cuatro líneas en total:
# - DIGI-PRUEBA-M2 (15 may–14 jun de 2026): fibra 1 a 17,50 € (más IVA, 3,68), movil 1 a 5,60 € (IVA 1,18)
#   y una segunda fibra («fibra 2»), de 0,95 € (IVA 0,20), que solo está en esta factura. Total 29,11 €.
# - DIGI-PRUEBA-M1 (15 jun–14 jul de 2026): fibra 1 a 18,40 € (IVA 3,86) y movil 1 a 6,15 € (IVA 1,29). 29,70 €.
# - DIGI-PRUEBA-1 (el ejemplo, 15 jul–14 ago): las mismas cuotas, y 0,07 € de consumo adicional. 29,79 €.
# Los importes son ficticios, como los de `datos_prueba.py`.
_MOVIL, _FIBRA, _FIBRA_2 = "LINEA-MOVIL-PRUEBA", "FIBRA-PRUEBA", "FIBRA-PRUEBA-2"
_CONTRATOS_DIGI = {_MOVIL: "movil", _FIBRA: "fibra", _FIBRA_2: "fibra"}


def _linea_digi(contrato, concepto, importe):
    texto = datos_prueba.IVA_DIGI if concepto == "iva" else concepto
    return datos_prueba.linea(contrato, concepto, texto, importe, derivada=concepto == "iva")


DIGI_M2 = datos_prueba.variante(
    datos_prueba.FACTURA_DIGI, "DIGI-PRUEBA-M2", "2026-06-21", "2026-05-15", "2026-06-14",
    contratos=_CONTRATOS_DIGI,
    lineas=[
        _linea_digi(_MOVIL, "cuota_plan", 560), _linea_digi(_MOVIL, "consumo_incluido", 0),
        _linea_digi(_MOVIL, "iva", 118),
        _linea_digi(_FIBRA, "cuota_fibra", 1750), _linea_digi(_FIBRA, "iva", 368),
        _linea_digi(_FIBRA_2, "cuota_fibra", 95), _linea_digi(_FIBRA_2, "iva", 20),
    ],
)  # total 2911
DIGI_M1 = datos_prueba.variante(
    datos_prueba.FACTURA_DIGI, "DIGI-PRUEBA-M1", "2026-07-21", "2026-06-15", "2026-07-14",
    lineas=[
        _linea_digi(_MOVIL, "cuota_plan", 615), _linea_digi(_MOVIL, "consumo_incluido", 0),
        _linea_digi(_MOVIL, "iva", 129),
        _linea_digi(_FIBRA, "cuota_fibra", 1840), _linea_digi(_FIBRA, "iva", 386),
    ],
)  # total 2970


@pytest.fixture
def digi(base_completa, ruta_base, monkeypatch):
    """Los ejemplos más las dos facturas anteriores de DIGI, ya con la app corriendo."""
    for factura in (DIGI_M2, DIGI_M1):
        datos_prueba.insertar(base_completa, factura)
    return _analysis(base_completa, ruta_base, monkeypatch)


def test_la_pestana_digi_tiene_el_patron_comun_sin_volumen_ni_cascada(digi):
    assert not digi.exception
    assert _textos(_pestana(digi, "DIGI").subheader) == [
        "Composition by line", "Weight of each line", "Breakdown by charge", "Fee by line",
    ]
    # Composición, pesos, el desglose de cada línea (fibra 1, movil 1 y fibra 2: dos columnas) y las cuotas.
    assert [f["data"][0]["type"] for f in _figuras(digi, "DIGI")] == ["bar"] * 5 + ["scatter"]
    assert not _pestana(digi, "DIGI").metric and not _pestana(digi, "DIGI").radio
    assert "Lines: fibra 1 (Wifi, Jun 2026 to Aug 2026) · fibra 2 (Wifi, Jun 2026 to Jun 2026) · " \
        "movil 1 (Mobile, Jun 2026 to Aug 2026)." in _textos(_pestana(digi, "DIGI").caption)


def test_en_digi_cada_factura_suma_su_total(digi, base_completa):
    """Referencia independiente: el total de cada factura en `v_factura_vigente` (29,11, 29,70 y 29,79 €)."""
    totales = _totales(base_completa, ["DIGI-PRUEBA-M2"], ["DIGI-PRUEBA-M1"], ["DIGI-PRUEBA-1"])
    assert totales == [2911, 2970, 2979]
    composicion, pesos, *desgloses, _cuotas = _figuras(digi, "DIGI")
    por_linea = _y_por_serie(composicion)
    assert por_linea == {
        "fibra 1": [21.18, 22.26, 22.26], "fibra 2": [1.15, 0.0, 0.0], "movil 1": [6.78, 7.44, 7.53],
    }
    assert [t["marker"]["color"] for t in composicion["data"]] == list(graficos.RANURAS[:3])
    assert _centimos(map(sum, zip(*por_linea.values()))) == totales
    assert [round(sum(v)) for v in zip(*_y_por_serie(pesos).values())] == [100, 100, 100]
    # El desglose de cada línea suma lo de su línea. AppTest recorre la columna izquierda entera (fibra 1 y
    # movil 1) y luego la derecha (fibra 2); en pantalla van fibra 1 | fibra 2, y debajo movil 1.
    for figura, linea in zip(desgloses, ("fibra 1", "movil 1", "fibra 2")):
        assert _centimos(map(sum, zip(*_y_por_serie(figura).values()))) == _centimos(por_linea[linea]), linea


def test_el_desglose_de_cada_linea_separa_cuota_consumo_adicional_e_iva(digi):
    _, _, fibra_1, movil_1, fibra_2, _ = _figuras(digi, "DIGI")
    assert _y_por_serie(fibra_1) == {"Fee": [17.5, 18.4, 18.4], "VAT": [3.68, 3.86, 3.86]}
    assert _y_por_serie(fibra_2) == {"Fee": [0.95, 0.0, 0.0], "VAT": [0.2, 0.0, 0.0]}
    # El consumo adicional (0,07 €) solo está en la última factura; el IVA va aparte.
    assert _y_por_serie(movil_1) == {
        "Fee": [5.6, 6.15, 6.15], "Extra usage": [0.0, 0.0, 0.07], "VAT": [1.18, 1.29, 1.31],
    }
    # Cada grupo tiene el mismo color en todas las líneas (ranuras 4 en adelante: las 0 a 2 son de las líneas).
    colores = {t["name"]: t["marker"]["color"] for f in (fibra_1, fibra_2, movil_1) for t in f["data"]}
    assert colores == {"Fee": graficos.RANURAS[4], "VAT": graficos.RANURAS[5], "Extra usage": graficos.RANURAS[6]}


def test_los_cambios_de_cuota_quedan_marcados(digi):
    cuotas = _figuras(digi, "DIGI")[-1]
    por_linea = {t["name"]: t for t in cuotas["data"]}
    assert por_linea["fibra 1"]["y"] == [17.5, 18.4, 18.4]
    assert por_linea["fibra 2"]["y"] == [0.95, None, None]  # la línea ya no está
    assert por_linea["movil 1"]["y"] == [5.6, 6.15, 6.15]
    # Un rombo grande en la factura donde la cuota cambia (la segunda); nada en la primera de cada línea
    # ni donde la línea desaparece.
    for nombre in ("fibra 1", "movil 1"):
        assert por_linea[nombre]["marker"]["symbol"] == ["circle", "diamond", "circle"]
        assert por_linea[nombre]["marker"]["size"] == [8, 13, 8]
    assert por_linea["fibra 2"]["marker"]["symbol"] == ["circle"] * 3
    assert "(changed from 17,50 €)" in por_linea["fibra 1"]["customdata"][1][2]
    lista = [m.value for m in _pestana(digi, "DIGI").markdown if m.value.startswith("- ")]
    assert lista == [
        "- **fibra 1**, 15 Jun 2026 – 14 Jul 2026: 17,50 € → 18,40 € (+0,90 €)",
        "- **movil 1**, 15 Jun 2026 – 14 Jul 2026: 5,60 € → 6,15 € (+0,55 €)",
    ]


def test_digi_con_una_sola_factura_no_tiene_cambios_de_cuota(base_ejemplos, ruta_base, monkeypatch):
    at = _analysis(base_ejemplos, ruta_base, monkeypatch)
    assert not at.exception
    assert "No line changed its fee." in _textos(_pestana(at, "DIGI").caption)
    composicion = _figuras(at, "DIGI")[0]
    assert _y_por_serie(composicion) == {"fibra 1": [22.26], "movil 1": [7.53]}


def test_sin_facturas_de_digi_la_pestana_lo_dice(base, ruta_base, monkeypatch):
    at = _analysis(base, ruta_base, monkeypatch)
    assert not at.exception
    assert "There are no DIGI invoices loaded yet." in _textos(_pestana(at, "DIGI").info)
