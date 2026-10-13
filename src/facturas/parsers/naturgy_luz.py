"""Naturgy (luz). Detalle, lecturas y datos de suministro en la página 2; las 3 y 4 son informativas."""

import re

from facturas.extraccion import Atributo, Contrato, Lectura, Medicion, Periodo
from facturas.parsers import comun
from facturas.parsers.pdf import Documento

FORMATO = "naturgy_luz"
VERSION = "1.2.0"
IDENTIFICADOR_FISCAL = "A67760876"
CATEGORIA = "luz"
OPCIONALES_IMPRESOS = ("franja", "atributo:potencia_p1", "atributo:potencia_p2")

# Las facturas de principios de 2025 imprimen las fechas con el año en dos cifras ("06/02/25").
_FECHA = r"(\d{2}/\d{2}/(?:\d{4}|\d{2}))(?!\d)"


def reconoce(documento: Documento) -> bool:
    return comun.tiene_identificador(documento.texto, IDENTIFICADOR_FISCAL) and "Período electricidad" in documento.texto


def extraer(documento: Documento):
    comun.rechazar_si_no_es_ordinaria(FORMATO, documento.texto)
    t = documento.texto
    buscar = lambda campo, patron: comun.buscar(FORMATO, campo, patron, t)  # noqa: E731

    numero = buscar("numero", r"N\S{1,3}\s+de factura:\s*(\w+)")
    fecha_emision = comun.fecha_dmy(FORMATO, "fecha_emision", buscar("fecha_emision", rf"Fecha de emisi.n:\s*{_FECHA}"))
    inicio, fin = (
        comun.fecha_dmy(FORMATO, "periodo", f)
        for f in buscar("periodo", rf"Período electricidad\s*:?\s*del {_FECHA} al {_FECHA}")
    )
    comun.verificar_dias(FORMATO, inicio, fin, int(buscar("días del período", r"(\d+) días\s+Período electricidad del")))
    total = comun.centimos(FORMATO, "importe_total", buscar("importe_total", r"Total a pagar\s+([\d.,]+) €"))
    cups = comun.cups_suministro(FORMATO, buscar("contrato (CUPS)", r"Código CUPS:\s*(ES\w+)"))
    potencias = tuple(
        Atributo(f"potencia_p{franja}", comun.decimal(FORMATO, f"potencia P{franja}", valor))
        for franja, valor in re.findall(r"Potencia contratada P([12]):\s*([\d.,]+) kW", t)
    )

    lineas = comun.lineas_de_detalle(FORMATO, t, cups, Periodo(inicio, fin))
    comun.verificar_suma(FORMATO, [linea.importe_centimos for linea in lineas], total)

    return comun.construir(
        FORMATO, VERSION, OPCIONALES_IMPRESOS,
        identificador_fiscal=IDENTIFICADOR_FISCAL, numero=numero, tipo="ordinaria", moneda="EUR",
        fecha_emision=fecha_emision, periodo=Periodo(inicio, fin), importe_total_centimos=total,
        contratos=(Contrato(cups, CATEGORIA, potencias),), lineas=tuple(lineas),
        mediciones=tuple(_mediciones(t, cups)),
    )


def _mediciones(texto: str, cups: str) -> list[Medicion]:
    """Una medición por franja, con su lectura de cierre; solo la luz desglosa por franja.

    Desde 2025 la lectura de cierre lleva "(hasta)" y se imprime también la de inicio, "(desde)", sin consumo.
    """
    encontradas = re.findall(rf"{_FECHA}\s+(Punta|Llano|Valle)\s+(\w+)(?:\s*\(hasta\))?\s+([\d.]+)\s+([\d.,]+)\s*kWh", texto)
    if not encontradas:
        raise comun.error(FORMATO, "no se encontraron las lecturas por franja")
    mediciones = [
        Medicion(
            contrato=cups, magnitud="energia", franja=franja.lower(),
            cantidad=comun.decimal(FORMATO, "consumo", kwh),
            lectura=Lectura(
                comun.fecha_dmy(FORMATO, "lectura.fecha", fecha),
                comun.decimal(FORMATO, "lectura", lectura),
                comun.tipo_lectura(FORMATO, tipo),
            ),
        )
        for fecha, franja, tipo, lectura, kwh in encontradas
    ]
    impreso = comun.buscar(FORMATO, "total consumo", r"Total consumo\s+([\d.,]+) kWh", texto)
    if sum(float(m.cantidad) for m in mediciones) != float(comun.decimal(FORMATO, "total consumo", impreso)):
        raise comun.error(FORMATO, f"las franjas no suman el consumo total impreso de {impreso} kWh")
    return mediciones
