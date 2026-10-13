"""Variantes reales de formatos conocidos (facturas de 2025), que los ejemplos de 2026 no tenían.

Usa tres PDFs más de `ejemplos/` (fuera de git; si faltan, los tests se saltan):
- `gas_2025_cambio_precio.pdf`: el precio cambia el 1 de octubre y el consumo y el término fijo se
  parten en una fila por tramo de fechas, debajo de su rótulo;
- `agua_2025_litros_truncados.pdf`: 10 m³ en 61 días; imprime "163 litros por día" (163,9 truncado);
- `agua_2026_aviso_canon.pdf`: un aviso sobre el canon ocupa el lugar del mensaje de los litros por día;
- `agua_2024_alta.pdf`: la primera factura del contrato, que cuenta también el día del alta (63 días);
- `luz_2025_fechas_cortas.pdf`: todas las fechas con el año en dos cifras ("06/02/25");
- `luz_2025_lecturas_hasta.pdf`: la lectura de cierre con "(hasta)" y la de inicio con "(desde)";
- `luz_2025_tramo_un_dia.pdf`: el precio cambia el 1 de enero y el último tramo es de un día ("1 día x").
- `gas_2025_inspeccion.pdf`: cargos sin cuenta en "Otros conceptos" (la inspección periódica);
- `digi_2025_fijo_roaming.pdf`: un teléfono fijo en "EN CASA" (cuenta como fibra) y datos en roaming en MB;
- `digi_2025_redondeo_iva.pdf`: el IVA derivado por servicio difiere en 1 céntimo del impreso;
- `luz_2024_iberia.pdf` y `gas_2024_iberia.pdf`: el formato de 2024 de Naturgy Iberia. El gas trae antes una
  carta de revisión de precios, tramos por cambio de precio, inspección y un servicio aparte.

Los valores esperados son los impresos en cada PDF. Los importes no se versionan: están en
`ejemplos/importes_esperados.json` (`caso.importes`).
"""

import re
from pathlib import Path

import pytest

import caso
from facturas import parsers
from facturas.carga.traduccion import traducir
from facturas.parsers import comun
from facturas.extraccion import ErrorExtraccion, Periodo
from facturas.parsers.pdf import Documento, leer

DIR_EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos"


def _leer(nombre: str) -> Documento:
    ruta = DIR_EJEMPLOS / f"{nombre}.pdf"
    if not ruta.exists():
        pytest.skip(f"falta ejemplos/{nombre}.pdf: los PDFs de ejemplo no se versionan")
    return leer(ruta)


def _extraer(documento: Documento):
    return parsers.reconocer(documento).extraer(documento)


def _modificada(doc: Documento, anterior: str, nuevo: str) -> Documento:
    if anterior not in doc.texto and anterior not in doc.diseno:
        raise AssertionError(f"{anterior!r} no está en el documento")
    return Documento(doc.texto.replace(anterior, nuevo), doc.diseno.replace(anterior, nuevo))


def test_gas_con_cambio_de_precio_una_linea_por_tramo_con_su_rotulo():
    factura = _extraer(_leer("gas_2025_cambio_precio"))

    assert factura.periodo == Periodo("2025-08-26", "2025-10-23")
    importes = caso.importes("gas_2025_cambio_precio")
    assert factura.importe_total_centimos == importes["total"]
    primero, segundo = Periodo("2025-08-26", "2025-09-30"), Periodo("2025-10-01", "2025-10-23")
    assert [(l.texto, l.periodo) for l in factura.lineas] == [
        ("Consumo gas", primero),
        ("Consumo gas", segundo),
        ("Impuesto Especial sobre hidrocarburos", None),
        ("Término fijo", primero),
        ("Término fijo", segundo),
        ("IVA (21%)", None),
    ]
    assert [l.importe_centimos for l in factura.lineas] == importes["lineas"]
    assert [l.posicion for l in factura.lineas] == [1, 2, 3, 4, 5, 6]


def test_gas_un_tramo_fuera_del_periodo_de_la_factura_se_rechaza():
    documento = _modificada(_leer("gas_2025_cambio_precio"), "Del 01/10/2025 al 23/10/2025", "Del 01/10/2025 al 30/10/2025")

    with pytest.raises(ErrorExtraccion, match="no está dentro del período de la factura"):
        _extraer(documento)


def test_agua_con_litros_por_dia_truncados():
    factura = _extraer(_leer("agua_2025_litros_truncados"))

    assert factura.periodo == Periodo("2025-08-09", "2025-10-08")  # 61 días (D10)
    assert factura.importe_total_centimos == caso.importes("agua_2025_litros_truncados")["total"]
    assert factura.mediciones[0].cantidad == "10"


def test_agua_con_litros_por_dia_que_no_corresponden_se_rechaza():
    documento = _modificada(_leer("agua_2025_litros_truncados"), "sido de 163", "sido de 161")

    with pytest.raises(ErrorExtraccion, match="promedios por día impresos no corresponden a un período de 61 días"):
        _extraer(documento)


def test_agua_sin_el_mensaje_de_litros_verifica_los_promedios_en_euros():
    documento = _leer("agua_2026_aviso_canon")
    factura = _extraer(documento)

    assert factura.periodo == Periodo("2025-12-10", "2026-02-05")  # 58 días
    assert factura.importe_total_centimos == caso.importes("agua_2026_aviso_canon")["total"]
    # Los promedios en euros se siguen verificando: el primero, con 6 céntimos más.
    promedio = re.search(r"(\d+,\d{2}) €/día", documento.texto)[1]
    with pytest.raises(ErrorExtraccion, match="promedios por día impresos"):
        _extraer(_modificada(documento, f"{promedio} €/día", f"{caso.mas_centimos(promedio, 6)} €/día"))


def test_agua_primera_factura_del_contrato_cuenta_el_dia_del_alta():
    factura = _extraer(_leer("agua_2024_alta"))

    # Impreso: 11-oct-24 / 12-dic-24. Los promedios en euros por día corresponden a 63 días, no a 62.
    assert factura.periodo == Periodo("2024-10-11", "2024-12-12")
    assert factura.importe_total_centimos == caso.importes("agua_2024_alta")["total"]


def test_luz_con_fechas_de_año_en_dos_cifras():
    factura = _extraer(_leer("luz_2025_fechas_cortas"))

    assert factura.fecha_emision == "2025-02-06"
    assert factura.periodo == Periodo("2025-01-01", "2025-02-01")
    assert factura.importe_total_centimos == caso.importes("luz_2025_fechas_cortas")["total"]
    assert [(m.franja, m.lectura.fecha) for m in factura.mediciones] == [
        ("punta", "2025-02-01"), ("llano", "2025-02-01"), ("valle", "2025-02-01")]


def test_luz_con_lecturas_hasta_y_desde():
    factura = _extraer(_leer("luz_2025_lecturas_hasta"))

    assert factura.periodo == Periodo("2025-03-31", "2025-04-30")
    # Solo las lecturas de cierre ("hasta"), con su consumo; las de inicio ("desde") no tienen consumo.
    assert [(m.franja, m.cantidad, m.lectura.valor) for m in factura.mediciones] == [
        ("punta", "39", "16240"), ("llano", "34", "1870"), ("valle", "50", "3754")]


def test_luz_con_un_tramo_de_un_dia():
    factura = _extraer(_leer("luz_2025_tramo_un_dia"))

    diciembre, enero = Periodo("2025-11-29", "2025-12-31"), Periodo("2026-01-01", "2026-01-01")
    importes = caso.importes("luz_2025_tramo_un_dia")
    assert [(l.texto, l.periodo) for l in factura.lineas[:8]] == [
        ("Consumo electricidad", diciembre),
        ("Consumo electricidad", enero),
        ("Término potencia P1", diciembre),
        ("Término potencia P1", enero),
        ("Término potencia P2", diciembre),
        ("Término potencia P2", enero),
        ("Financiación de Bono Social", diciembre),
        ("Financiación de Bono Social", enero),
    ]
    assert [l.importe_centimos for l in factura.lineas[:8]] == importes["lineas"]
    assert factura.importe_total_centimos == importes["total"]


def test_gas_con_cargos_sin_cuenta_en_otros_conceptos():
    factura = _extraer(_leer("gas_2025_inspeccion"))

    importes = caso.importes("gas_2025_inspeccion")
    assert [l.texto for l in factura.lineas[3:5]] == [
        "Gastos de gestión de inspección periódica de IRI",
        "Inspección física de la Inspección Periódica de IRI",
    ]
    assert [l.importe_centimos for l in factura.lineas[3:5]] == importes["inspeccion"]
    assert factura.importe_total_centimos == importes["total"]


def test_digi_con_telefono_fijo_y_roaming():
    factura = _extraer(_leer("digi_2025_fijo_roaming"))

    assert [c.categoria for c in factura.contratos] == ["movil", "fibra", "fibra"]
    importes = caso.importes("digi_2025_fijo_roaming")
    roaming = ("CONSUMO ADICIONAL", "Datos en roaming", importes["roaming"])
    assert roaming in [(l.seccion, l.texto, l.importe_centimos) for l in factura.lineas]
    fijo = next(l for l in factura.lineas if l.texto.startswith("DIGI tel"))
    assert fijo.importe_centimos == importes["fijo"]
    assert factura.importe_total_centimos == importes["total"]


def test_luz_de_naturgy_iberia_2024():
    factura = _extraer(_leer("luz_2024_iberia"))

    assert factura.formato == "naturgy_iberia_luz"
    assert factura.fecha_emision == "2024-11-07"
    assert factura.periodo == Periodo("2024-10-02", "2024-11-02")  # 32 días
    importes = caso.importes("luz_2024_iberia")
    assert factura.importe_total_centimos == importes["total"]
    assert [l.texto for l in factura.lineas] == [
        "Consumo electricidad",
        "Término de potencia P1 (4,400 kW)",
        "Término de potencia P2 (4,400 kW)",
        "Financiación del Bono Social",
        "Impuesto electricidad",
        "Alquiler de contador",
        "Total IVA 10%",
    ]
    assert [l.importe_centimos for l in factura.lineas] == importes["lineas"]
    assert [(m.franja, m.cantidad, m.lectura.fecha) for m in factura.mediciones] == [
        ("punta", "26", "2024-11-02"), ("llano", "20", "2024-11-02"), ("valle", "41", "2024-11-02")]
    assert [a.atributo for a in factura.contratos[0].atributos] == ["potencia_p1", "potencia_p2"]


def test_gas_de_naturgy_iberia_2024_con_tramos_inspeccion_y_otro_servicio():
    factura = _extraer(_leer("gas_2024_iberia"))

    assert factura.formato == "naturgy_iberia_gas"
    assert factura.periodo == Periodo("2024-08-01", "2024-10-25")  # 86 días
    agosto, octubre = Periodo("2024-08-01", "2024-09-30"), Periodo("2024-10-01", "2024-10-25")
    importes = caso.importes("gas_2024_iberia")
    assert [(l.texto, l.periodo) for l in factura.lineas] == [
        ("Consumo gas", agosto),
        ("Consumo gas", octubre),
        ("Impuesto Especial sobre hidrocarburos", None),
        ("Término fijo", agosto),
        ("Término fijo", octubre),
        ("Gastos de gestión Inspección Periódica IRC", None),
        ("Gastos de inspección física IRC", None),
        ("Total IVA 21%", None),
        ("ServiElectric Xpress", None),  # otro servicio, con su IVA incluido
    ]
    assert [l.importe_centimos for l in factura.lineas] == importes["lineas"]
    assert factura.importe_total_centimos == importes["total"]
    (medicion,) = factura.mediciones
    assert (medicion.cantidad, medicion.cantidad_contador, medicion.factor_conversion) == ("289", "25", "11.56")


def test_el_mismo_suministro_es_un_solo_contrato_con_o_sin_punto_frontera():
    # Las facturas de 2024 y 2025 imprimen el CUPS con el punto frontera ("…0F"); las de 2026, sin él.
    contratos = {_extraer(_leer(n)).contratos[0].identificador_externo for n in ("luz_2024_iberia", "luz_2025_fechas_cortas", "luz")}
    assert len(contratos) == 1
    cups = "ES" + "0" * 16 + "AB"
    assert comun.cups_suministro("prueba", cups + "0F") == comun.cups_suministro("prueba", cups) == cups


def test_los_textos_nuevos_se_traducen_a_su_concepto(base):
    def concepto(categoria, seccion, texto):
        concepto_id = traducir(base, categoria, seccion, texto)
        return base.execute("SELECT codigo FROM concepto WHERE concepto_id = ?", (concepto_id,)).fetchone()[0]

    assert concepto("luz", None, "Total IVA 10%") == "iva"
    assert concepto("gas", None, "Total IVA 21%") == "iva"
    assert concepto("luz", None, "Término de potencia P1 (4,400 kW)") == "potencia_p1"
    assert concepto("gas", None, "Gastos de gestión Inspección Periódica IRC") == "inspeccion_periodica"
    assert concepto("gas", None, "Inspección física de la Inspección Periódica de IRI") == "inspeccion_periodica"
    assert concepto("gas", None, "ServiElectric Xpress") == "otros_servicios"
    assert concepto("fibra", "PRODUCTOS", "DIGI tel (16 Dic - 15 Ene)") == "cuota_fibra"
    assert concepto("movil", "CONSUMO ADICIONAL", "Datos en roaming") == "consumo_adicional"


def test_digi_con_un_centimo_de_redondeo_en_el_iva_se_acepta():
    factura = _extraer(_leer("digi_2025_redondeo_iva"))

    (iva,) = factura.totales_repartidos
    derivadas = sum(l.importe_centimos for l in factura.lineas if l.derivada_de == iva.texto)
    importes = caso.importes("digi_2025_redondeo_iva")
    assert (iva.importe_centimos, derivadas) == (importes["iva_impreso"], importes["iva_derivado"])
    assert iva.importe_centimos - derivadas == 1
    # Las líneas suman exactamente el total de la factura (I1); el céntimo queda dentro del margen de I8.
    assert sum(l.importe_centimos for l in factura.lineas) == factura.importe_total_centimos == importes["total"]
