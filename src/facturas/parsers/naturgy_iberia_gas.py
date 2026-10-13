"""Naturgy Iberia (gas), el formato de 2024, antes de que facturara Naturgy Clientes (`naturgy_gas`).

Como en `naturgy_iberia_luz`: todo se lee del texto por columnas, las fechas van con puntos y el período
impreso incluye los dos extremos. Una factura puede traer antes una carta (la revisión de precios) y,
después del gas, "Otros productos y servicios" con su IVA incluido, que también se pagan en esta factura.
"""

import re

from facturas.extraccion import Contrato, Lectura, Medicion, Periodo
from facturas.parsers import comun
from facturas.parsers.pdf import Documento

FORMATO = "naturgy_iberia_gas"
VERSION = "1.0.0"
IDENTIFICADOR_FISCAL = "A08431090"
CATEGORIA = "gas"
OPCIONALES_IMPRESOS = ("cantidad_contador",)

_FECHA = r"(\d{2}\.\d{2}\.(?:\d{4}|\d{2}))(?!\d)"


def reconoce(documento: Documento) -> bool:
    return (
        comun.tiene_identificador(documento.texto, IDENTIFICADOR_FISCAL)
        and re.search(r"(?<!\w)Gas\s*:\s*del\s+\d", documento.diseno) is not None
    )


def extraer(documento: Documento):
    d = documento.diseno
    comun.rechazar_si_no_es_ordinaria(FORMATO, d)
    buscar = lambda campo, patron: comun.buscar(FORMATO, campo, patron, d)  # noqa: E731

    numero = buscar("numero", r"N\S{1,2}\s+factura:\s*(\w+)")
    fecha_emision = comun.fecha_con_puntos(FORMATO, "fecha_emision", buscar("fecha_emision", rf"Fecha de emisi.n:\s*{_FECHA}"))
    inicio, fin = (
        comun.fecha_con_puntos(FORMATO, "periodo", f) for f in buscar("periodo", rf"(?<!\w)Gas\s*:\s*del\s+{_FECHA}\s+al\s+{_FECHA}")
    )
    # Los días del período, en el recuadro de la izquierda del detalle ("86 días", al principio de la línea).
    comun.verificar_dias(FORMATO, inicio, fin, int(buscar("días del período", r"(?m)^\s*(\d+) días(?:\s{3,}|\s*$)")))
    totales = re.findall(r"Total a pagar\s+([\d.,]+)\s*€", d)
    if not totales:
        raise comun.error(FORMATO, "no se encontró 'importe_total' en el documento")
    total = comun.centimos(FORMATO, "importe_total", totales[-1])
    cups = comun.cups_suministro(FORMATO, buscar("contrato (CUPS)", r"C.digo CUPS:\s*(ES[0-9A-Z]+(?: [0-9A-Z]+)*)"))

    lineas = comun.lineas_por_columnas(FORMATO, d, cups, Periodo(inicio, fin))
    comun.verificar_suma(FORMATO, [linea.importe_centimos for linea in lineas], total)

    return comun.construir(
        FORMATO, VERSION, OPCIONALES_IMPRESOS,
        identificador_fiscal=IDENTIFICADOR_FISCAL, numero=numero, tipo="ordinaria", moneda="EUR",
        fecha_emision=fecha_emision, periodo=Periodo(inicio, fin), importe_total_centimos=total,
        contratos=(Contrato(cups, CATEGORIA),), lineas=tuple(lineas), mediciones=(_medicion(d, cups),),
    )


def _medicion(diseno: str, cups: str) -> Medicion:
    """La lectura actual ("Lectura actual: real 25.10.24 15.038 m³") y la conversión impresa
    ("Consumo kWh: 25 m³ x 11,56 kWh* 289 kWh"), que se verifica: m³ por factor, redondeado, son los kWh."""
    tipo, fecha, lectura = comun.buscar(FORMATO, "lectura actual", rf"Lectura actual:\s*(\w+)\s+{_FECHA}\s+([\d.]+)\s*m", diseno)
    m3, factor, kwh = comun.buscar(
        FORMATO, "consumo en kWh", r"Consumo kWh:\s*([\d.,]+)\s*m\S*\s*x\s*([\d.,]+)\s*kWh\*?\s+([\d.,]+)\s*kWh", diseno
    )
    m3, factor, kwh = (comun.decimal(FORMATO, campo, v) for campo, v in (("m³", m3), ("factor", factor), ("kWh", kwh)))
    if round(float(m3) * float(factor)) != round(float(kwh)):
        raise comun.error(FORMATO, f"{m3} m³ por {factor} kWh/m³ no dan los {kwh} kWh impresos")
    return Medicion(
        contrato=cups, magnitud="energia", cantidad=kwh, cantidad_contador=m3, factor_conversion=factor,
        lectura=Lectura(
            comun.fecha_con_puntos(FORMATO, "lectura.fecha", fecha),
            comun.decimal(FORMATO, "lectura", lectura),
            comun.tipo_lectura(FORMATO, tipo),
        ),
    )
