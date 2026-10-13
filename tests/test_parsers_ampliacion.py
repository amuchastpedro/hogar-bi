"""Ampliación del bloque 3: Digi con el NIF anterior y dos líneas móviles, y el ajuste parcial del gas.

Usa dos PDFs más de `ejemplos/` (fuera de git; si faltan, los tests se saltan):
- `digi_2025_dos_moviles.pdf`: una factura de Digi de 2025, con el NIF de la razón social anterior;
- `gas_ajuste.pdf`: el ajuste (la rectificativa por diferencias) de la factura de `gas.pdf`.

Los identificadores exactos se leen de `ejemplos/identificadores_esperados.json`, y los importes, de
`ejemplos/importes_esperados.json` (`caso.importes`); ninguno de los dos se versiona.
"""

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

import caso
import datos_prueba
from facturas import parsers
from facturas.bd.invariantes import verificar
from facturas.carga.traduccion import traducir
from facturas.extraccion import ErrorExtraccion, FacturaExtraida
from facturas.parsers import comun, digi_convergente, naturgy_gas
from facturas.parsers.pdf import Documento, leer

DIR_EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos"
ARCHIVO_IDENTIFICADORES = DIR_EJEMPLOS / "identificadores_esperados.json"


def _leer(nombre: str) -> Documento:
    ruta = DIR_EJEMPLOS / f"{nombre}.pdf"
    if not ruta.exists():
        pytest.skip(f"falta ejemplos/{nombre}.pdf: los PDFs de ejemplo no se versionan")
    return leer(ruta)


def _esperado(clave: str) -> dict:
    if not ARCHIVO_IDENTIFICADORES.exists():
        pytest.skip("falta ejemplos/identificadores_esperados.json (archivo local, fuera de git)")
    datos = json.loads(ARCHIVO_IDENTIFICADORES.read_text(encoding="utf-8"))
    if clave not in datos:
        pytest.skip(f"falta la clave {clave!r} en identificadores_esperados.json")
    return datos[clave]


def _extraer(nombre: str) -> FacturaExtraida:
    documento = _leer(nombre)
    return parsers.reconocer(documento).extraer(documento)


def _modificada(doc: Documento, anterior: str, nuevo: str) -> Documento:
    assert anterior in doc.texto or anterior in doc.diseno, f"{anterior!r} no está en el documento"
    return Documento(doc.texto.replace(anterior, nuevo), doc.diseno.replace(anterior, nuevo))


def _a_factura_de_prueba(base, factura: FacturaExtraida) -> dict:
    """La factura extraída como la espera `datos_prueba.insertar` (concepto por la traducción de las semillas)."""
    categorias = {c.identificador_externo: c.categoria for c in factura.contratos}

    def concepto(linea):
        concepto_id = traducir(base, categorias[linea.contrato], linea.seccion, linea.texto)
        return base.execute("SELECT codigo FROM concepto WHERE concepto_id = ?", (concepto_id,)).fetchone()[0]

    milesimas = lambda texto: int(Decimal(texto) * 1000)  # noqa: E731
    return datos_prueba.factura(
        factura.identificador_fiscal, factura.numero, factura.fecha_emision, factura.periodo.inicio,
        factura.periodo.fin, factura.importe_total_centimos, categorias,
        [
            datos_prueba.linea(l.contrato, concepto(l), l.texto, l.importe_centimos, l.seccion, l.derivada_de is not None)
            for l in factura.lineas
        ],
        mediciones=[
            datos_prueba.medicion(
                m.contrato, m.magnitud, milesimas(m.cantidad), m.lectura.fecha, milesimas(m.lectura.valor),
                m.lectura.tipo, m.franja,
                None if m.cantidad_contador is None else milesimas(m.cantidad_contador), m.factor_conversion,
            )
            for m in factura.mediciones
        ],
        totales_repartidos=[(t.texto, t.importe_centimos) for t in factura.totales_repartidos],
        tipo=factura.tipo, corregida=factura.numero_factura_corregida,
    )


# --- Digi: NIF de la razón social anterior ----------------------------------------------


def test_digi_con_el_nif_anterior_se_reconoce_y_se_emite_con_el_vigente():
    doc = _modificada(_leer("fibra_movil"), "NIF A-84919760", "NIF B-84919760")
    assert digi_convergente.reconoce(doc)
    assert digi_convergente.extraer(doc).identificador_fiscal == digi_convergente.IDENTIFICADOR_FISCAL


def test_digi_sin_ningun_nif_de_digi_no_se_reconoce():
    doc = _modificada(_leer("fibra_movil"), "NIF A-84919760", "NIF C-84919760")
    assert not digi_convergente.reconoce(doc)


# --- Digi: dos líneas móviles (ejemplo de 2025) ------------------------------------------


def test_digi_2025_dos_moviles_y_una_fibra():
    factura = _extraer("digi_2025_dos_moviles")
    assert factura.formato == digi_convergente.FORMATO and factura.tipo == "ordinaria"
    assert factura.identificador_fiscal == "A84919760"
    assert sorted(c.categoria for c in factura.contratos) == ["fibra", "movil", "movil"]
    assert (factura.periodo.inicio, factura.periodo.fin) == ("2025-08-16", "2025-09-15")
    assert factura.fecha_emision == "2025-09-23" and factura.fecha_vencimiento == "2025-09-29"
    assert factura.importe_total_centimos == caso.importes("digi_2025_dos_moviles")["total"]


def test_digi_2025_el_iva_por_servicio_suma_el_impreso_h12():
    """H12: con el desglose por servicio de otro mes, el IVA repartido también suma lo impreso."""
    importes = caso.importes("digi_2025_dos_moviles")
    factura = _extraer("digi_2025_dos_moviles")
    derivadas = [l.importe_centimos for l in factura.lineas if l.derivada_de is not None]
    assert len(derivadas) == 3 and sum(derivadas) == importes["iva"]
    assert [t.importe_centimos for t in factura.totales_repartidos] == [importes["iva"]]
    base_imponible = sum(l.importe_centimos for l in factura.lineas if l.derivada_de is None)
    assert base_imponible == importes["base"]


def test_digi_2025_identificadores_exactos():
    esperado = _esperado("digi_2025_dos_moviles")
    factura = _extraer("digi_2025_dos_moviles")
    assert factura.numero == esperado["numero"]
    assert sorted(c.identificador_externo for c in factura.contratos) == sorted(esperado["contratos"])
    fibra = [c.identificador_externo for c in factura.contratos if c.categoria == "fibra"]
    assert fibra == [esperado["fibra"]]


def test_digi_2025_el_periodo_sigue_la_convencion_de_inicio_y_fin_incluidos():
    """Dos facturas consecutivas (2025 y 2026) imprimen 31 días con ambos extremos incluidos."""
    factura = _extraer("digi_2025_dos_moviles")
    assert comun.dias_inclusive(factura.periodo.inicio, factura.periodo.fin) == 31


def test_digi_2025_se_carga_y_pasa_los_invariantes(base):
    factura = _extraer("digi_2025_dos_moviles")
    factura_id = datos_prueba.insertar(base, _a_factura_de_prueba(base, factura))
    assert verificar(base, factura_id) == []
    gasto = base.execute(
        "SELECT sum(importe_centimos) FROM v_hecho_gasto_mensual WHERE categoria_codigo = 'movil'"
    ).fetchone()[0]
    assert gasto == sum(caso.importes("digi_2025_dos_moviles")["movil"])  # lo impreso de las dos líneas móviles, con IVA


# --- Gas: ajuste parcial (rectificativa por diferencias) ---------------------------------


def test_gas_ajuste_es_una_rectificativa_por_diferencias_de_la_factura_original():
    factura = _extraer("gas_ajuste")
    assert factura.formato == naturgy_gas.FORMATO
    assert factura.tipo == "rectificativa_diferencias"
    assert factura.numero_factura_corregida == _extraer("gas").numero
    assert (factura.periodo.inicio, factura.periodo.fin) == ("2026-04-30", "2026-06-25")


def test_gas_ajuste_lineas_y_total_con_signo():
    importes = caso.importes("gas_ajuste")
    factura = _extraer("gas_ajuste")
    assert factura.importe_total_centimos == importes["total"] < 0
    assert [l.texto for l in factura.lineas] == [
        "Consumo gas", "Impuesto Especial sobre hidrocarburos", "Consumo gas",
        "Impuesto Especial sobre hidrocarburos", "IVA (21%)",
    ]
    assert [l.importe_centimos for l in factura.lineas] == importes["lineas"]
    # Lo que se vuelve a facturar suma y lo que se acredita, con su IVA, resta.
    assert [l.importe_centimos > 0 for l in factura.lineas] == [True, True, False, False, False]


def test_gas_ajuste_mide_la_diferencia_de_energia_con_la_lectura_del_cliente_como_real():
    (medicion,) = _extraer("gas_ajuste").mediciones
    assert Decimal(medicion.cantidad) == -206  # 138 kWh que se vuelven a facturar menos 344 que se acreditan
    assert (medicion.lectura.fecha, medicion.lectura.valor, medicion.lectura.tipo) == ("2026-06-25", "15559", "real")
    # 12 m³ de la lectura nueva menos los 30 m³ de la estimada (344 kWh ÷ 11,470, derivados: no están impresos).
    assert (medicion.cantidad_contador, medicion.factor_conversion) == ("-18", "11.470")


def test_gas_ajuste_identificadores_exactos():
    esperado = _esperado("gas_ajuste")
    factura = _extraer("gas_ajuste")
    assert factura.numero == esperado["numero"]
    assert factura.numero_factura_corregida == esperado["numero_factura_corregida"]
    assert {c.categoria: c.identificador_externo for c in factura.contratos} == esperado["contratos"]


def test_gas_original_mas_ajuste_dan_el_gasto_y_el_consumo_reales(base):
    """El gasto de la original más el del ajuste, y 344 − 206 = 138 kWh: lo que dice la lectura real del cliente."""
    original, ajuste = _extraer("gas"), _extraer("gas_ajuste")
    ids = [datos_prueba.insertar(base, _a_factura_de_prueba(base, f)) for f in (original, ajuste)]
    for factura_id in ids:
        assert verificar(base, factura_id) == []
    gasto = base.execute("SELECT sum(importe_centimos) FROM v_hecho_gasto_mensual").fetchone()[0]
    assert gasto == caso.valores_esperados()["gas"]["total"] + caso.importes("gas_ajuste")["total"]
    consumo = base.execute("SELECT sum(cantidad_milesimas) FROM v_hecho_consumo_mensual").fetchone()[0]
    assert consumo == 138_000
    # La original sigue vigente junto con su rectificativa por diferencias: no se anulan (a diferencia de un abono).
    assert base.execute("SELECT count(*) FROM v_factura_vigente").fetchone()[0] == 2


def test_gas_ajuste_cargado_antes_que_la_original_da_lo_mismo(base):
    original, ajuste = _extraer("gas"), _extraer("gas_ajuste")
    ids = [datos_prueba.insertar(base, _a_factura_de_prueba(base, f)) for f in (ajuste, original)]
    for factura_id in ids:
        assert verificar(base, factura_id) == []
    gasto = base.execute("SELECT sum(importe_centimos) FROM v_hecho_gasto_mensual").fetchone()[0]
    assert gasto == caso.valores_esperados()["gas"]["total"] + caso.importes("gas_ajuste")["total"]


# --- Gas: el ajuste se valida como una ordinaria ------------------------------------------


def test_gas_ajuste_con_un_importe_que_no_cuadra_falla():
    documento = _leer("gas_ajuste")
    linea_iva = re.search(r"IVA \(21%\) -[\d.,]+ € x 21% -(\d+,\d{2}) €", documento.texto)
    cambiado = _modificada(documento, linea_iva[0], linea_iva[0].replace(f"-{linea_iva[1]} €", f"-{caso.mas_centimos(linea_iva[1])} €"))
    with pytest.raises(ErrorExtraccion, match="naturgy_gas.*suman"):
        naturgy_gas.extraer(cambiado)


def test_gas_ajuste_cuyo_consumo_a_facturar_no_coincide_falla():
    cambiado = _modificada(_leer("gas_ajuste"), "11,470 138", "11,470 139")
    with pytest.raises(ErrorExtraccion, match="naturgy_gas.*Consumo a facturar"):
        naturgy_gas.extraer(cambiado)


def test_gas_ajuste_con_kwh_acreditados_que_no_son_m3_enteros_falla():
    documento = _leer("gas_ajuste")
    consumo = re.search(r"-344 kWh x [^\n]*", documento.texto)[0]  # la primera: el consumo acreditado
    cambiado = _modificada(documento, consumo, consumo.replace("-344 kWh", "-340 kWh"))
    with pytest.raises(ErrorExtraccion, match="naturgy_gas.*m³"):
        naturgy_gas.extraer(cambiado)


def test_gas_ajuste_sin_la_factura_que_corrige_se_rechaza_como_no_ordinaria():
    """Sin el rótulo "Ajuste (…) s/ <factura>" el documento no es un ajuste: no se lo trata como ordinaria."""
    cambiado = _modificada(_leer("gas_ajuste"), "Ajuste (", "Ajustar (")
    with pytest.raises(ErrorExtraccion, match="naturgy_gas"):
        naturgy_gas.extraer(cambiado)


def test_una_lectura_del_cliente_es_real():
    assert comun.tipo_lectura("prueba", "Cliente") == "real"
    assert comun.tipo_lectura("prueba", "Real") == "real"
    assert comun.tipo_lectura("prueba", "Estimada") == "estimada"
    with pytest.raises(ErrorExtraccion):
        comun.tipo_lectura("prueba", "Otra")
