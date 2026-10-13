"""Naturgy (gas). Detalle en la página 2; la página 3 tiene texto ilegible y no se usa."""

import re
from decimal import Decimal

from facturas.extraccion import Contrato, Lectura, Medicion, Periodo
from facturas.parsers import comun
from facturas.parsers.pdf import Documento

FORMATO = "naturgy_gas"
VERSION = "1.3.0"
IDENTIFICADOR_FISCAL = "A67760876"
CATEGORIA = "gas"
OPCIONALES_IMPRESOS = ("cantidad_contador",)

_FECHA = r"(\d{2}/\d{2}/\d{4})"


def reconoce(documento: Documento) -> bool:
    return comun.tiene_identificador(documento.texto, IDENTIFICADOR_FISCAL) and "Período gas" in documento.texto


def extraer(documento: Documento):
    t = documento.texto
    # Un ajuste parcial ("Ajuste (período) s/ <factura>") corrige solo los cargos que cambian, no toda la factura.
    ajuste = re.search(r"Ajuste \([^)]*\) s/ (\w+)", t)
    if ajuste is None:
        comun.rechazar_si_no_es_ordinaria(FORMATO, t)
    buscar = lambda campo, patron: comun.buscar(FORMATO, campo, patron, t)  # noqa: E731

    numero = buscar("numero", r"N\S{1,3}\s+de factura:\s*(\w+)")
    fecha_emision = comun.fecha_dmy(FORMATO, "fecha_emision", buscar("fecha_emision", rf"Fecha de emisi.n:\s*{_FECHA}"))
    inicio, fin = (comun.fecha_dmy(FORMATO, "periodo", f) for f in buscar("periodo", rf"Período gas\s*:?\s*del {_FECHA} al {_FECHA}"))
    dias = buscar("días del período", r"(\d+) días\s+Período gas del" if ajuste is None else r"Contrato:\s*\w+\s+(\d+) días")
    comun.verificar_dias(FORMATO, inicio, fin, int(dias))
    total = comun.centimos(
        FORMATO, "importe_total", buscar("importe_total", r"Total a pagar\s+([\d.,]+) €" if ajuste is None else r"(?m)^Total (-?[\d.]*\d,\d{2}) €$")
    )
    cups = comun.cups_suministro(FORMATO, buscar("contrato (CUPS)", r"Código CUPS:\s*(ES\w+)"))

    lineas = comun.lineas_de_detalle(FORMATO, t, cups, Periodo(inicio, fin))
    comun.verificar_suma(FORMATO, [linea.importe_centimos for linea in lineas], total)

    return comun.construir(
        FORMATO, VERSION, OPCIONALES_IMPRESOS,
        identificador_fiscal=IDENTIFICADOR_FISCAL, numero=numero, moneda="EUR",
        tipo="ordinaria" if ajuste is None else "rectificativa_diferencias",
        numero_factura_corregida=None if ajuste is None else ajuste[1],
        fecha_emision=fecha_emision, periodo=Periodo(inicio, fin), importe_total_centimos=total,
        contratos=(Contrato(cups, CATEGORIA),), lineas=tuple(lineas),
        mediciones=(_medicion(t, cups) if ajuste is None else _medicion_ajuste(t, cups),),
    )


def _medicion(texto: str, cups: str) -> Medicion:
    """Lectura de cierre ("hasta"), con el consumo en m³, el factor y los kWh facturados."""
    fecha, tipo, lectura, m3, factor, kwh = comun.buscar(
        FORMATO, "lectura de cierre",
        rf"{_FECHA}\s+(\w+)\s*\(hasta\)\s+([\d.]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)",
        texto,
    )
    anterior = re.search(rf"{_FECHA}\s+\w+\s*\(desde\)\s+([\d.]+)", texto)
    lectura_cierre = comun.decimal(FORMATO, "lectura", lectura)
    if anterior and float(lectura_cierre) - float(comun.decimal(FORMATO, "lectura anterior", anterior[2])) != float(comun.decimal(FORMATO, "consumo", m3)):
        raise comun.error(FORMATO, "las lecturas no dan el consumo en m³ impreso")
    return Medicion(
        contrato=cups, magnitud="energia", cantidad=comun.decimal(FORMATO, "consumo a facturar", kwh),
        cantidad_contador=comun.decimal(FORMATO, "consumo en m³", m3),
        factor_conversion=comun.decimal(FORMATO, "factor de conversión", factor),
        lectura=Lectura(comun.fecha_dmy(FORMATO, "lectura.fecha", fecha), lectura_cierre, comun.tipo_lectura(FORMATO, tipo)),
    )


def _medicion_ajuste(texto: str, cups: str) -> Medicion:
    """Medición de un ajuste: la diferencia entre lo que se vuelve a facturar y lo que se acredita.

    La energía sale de las filas "Consumo gas <kWh> x …", con su signo. De los m³ el documento imprime solo los
    de la lectura nueva; los del crédito se derivan de sus kWh y el factor (el contador lee m³ enteros) y se
    verifica que reproduzcan los kWh acreditados: el neto en m³ es un dato derivado, no impreso.
    """
    nueva = _medicion(texto, cups)
    kwh = [Decimal(comun.decimal(FORMATO, "kWh", k)) for k in re.findall(r"(?m)^Consumo gas (-?[\d.,]+) kWh x ", texto)]
    facturado, acreditado = sum(k for k in kwh if k > 0), sum(k for k in kwh if k < 0)
    if not kwh or facturado != Decimal(nueva.cantidad):
        raise comun.error(FORMATO, "el consumo que se vuelve a facturar no es el 'Consumo a facturar' impreso")
    factor = Decimal(nueva.factor_conversion)
    m3_acreditados = (-acreditado / factor).to_integral_value()
    if (m3_acreditados * factor).to_integral_value() != -acreditado:
        raise comun.error(FORMATO, f"{-acreditado} kWh acreditados no son un número entero de m³ con el factor {factor}")
    return Medicion(
        cups, "energia", format(facturado + acreditado, "f"), nueva.lectura,
        cantidad_contador=format(Decimal(nueva.cantidad_contador) - m3_acreditados, "f"), factor_conversion=nueva.factor_conversion,
    )
