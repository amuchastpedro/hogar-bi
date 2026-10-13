"""Naturgy Iberia (luz), el formato de 2024, antes de que facturara Naturgy Clientes (`naturgy_luz`).

El texto en orden de lectura sale palabra por palabra: todo se lee del texto por columnas (`diseno`).
Las fechas van con puntos ("02.11.2024"; las lecturas, "02.11.24"). El período impreso incluye los dos
extremos: "del 02.10.2024 al 02.11.2024" son los 32 días que se facturan.
"""

import re

from facturas.extraccion import Atributo, Contrato, Lectura, Medicion, Periodo
from facturas.parsers import comun
from facturas.parsers.pdf import Documento

FORMATO = "naturgy_iberia_luz"
VERSION = "1.0.0"
IDENTIFICADOR_FISCAL = "A08431090"
CATEGORIA = "luz"
OPCIONALES_IMPRESOS = ("franja", "atributo:potencia_p1", "atributo:potencia_p2")

_FECHA = r"(\d{2}\.\d{2}\.(?:\d{4}|\d{2}))(?!\d)"


def reconoce(documento: Documento) -> bool:
    return (
        comun.tiene_identificador(documento.texto, IDENTIFICADOR_FISCAL)
        and re.search(r"Electricidad\s*:\s*del\s+\d", documento.diseno) is not None
    )


def extraer(documento: Documento):
    d = documento.diseno
    comun.rechazar_si_no_es_ordinaria(FORMATO, d)
    buscar = lambda campo, patron: comun.buscar(FORMATO, campo, patron, d)  # noqa: E731

    numero = buscar("numero", r"N\S{1,2}\s+factura:\s*(\w+)")
    fecha_emision = comun.fecha_con_puntos(FORMATO, "fecha_emision", buscar("fecha_emision", rf"Fecha de emisi.n:\s*{_FECHA}"))
    inicio, fin = (
        comun.fecha_con_puntos(FORMATO, "periodo", f) for f in buscar("periodo", rf"Electricidad\s*:\s*del\s+{_FECHA}\s+al\s+{_FECHA}")
    )
    # Los días del período, en el recuadro de la izquierda del detalle ("27 días", sola en su línea).
    comun.verificar_dias(FORMATO, inicio, fin, int(buscar("días del período", r"(?m)^\s*(\d+) días\s*$")))
    totales = re.findall(r"Total a pagar\s+([\d.,]+)\s*€", d)
    if not totales:
        raise comun.error(FORMATO, "no se encontró 'importe_total' en el documento")
    total = comun.centimos(FORMATO, "importe_total", totales[-1])
    cups = comun.cups_suministro(FORMATO, buscar("contrato (CUPS)", r"C.digo CUPS:\s*(ES[0-9A-Z]+(?: [0-9A-Z]+)*)"))
    potencias = tuple(
        Atributo(f"potencia_p{franja}", comun.decimal(FORMATO, f"potencia P{franja}", valor))
        for franja, valor in re.findall(r"Potencia contratada P([12])\s+([\d.,]+)\s*kW", d)
    )

    lineas = comun.lineas_por_columnas(FORMATO, d, cups, Periodo(inicio, fin))
    comun.verificar_suma(FORMATO, [linea.importe_centimos for linea in lineas], total)

    return comun.construir(
        FORMATO, VERSION, OPCIONALES_IMPRESOS,
        identificador_fiscal=IDENTIFICADOR_FISCAL, numero=numero, tipo="ordinaria", moneda="EUR",
        fecha_emision=fecha_emision, periodo=Periodo(inicio, fin), importe_total_centimos=total,
        contratos=(Contrato(cups, CATEGORIA, potencias),), lineas=tuple(lineas),
        mediciones=tuple(_mediciones(d, cups)),
    )


def _mediciones(diseno: str, cups: str) -> list[Medicion]:
    """Una medición por franja: la lectura actual ("Lectura actual: Punta real 02.11.24 16.074 kWh") y el
    consumo de la franja ("Consumo: Punta 26 kWh"), que tienen que sumar el "Total consumo" impreso."""
    lecturas = {
        franja: (fecha, tipo, valor)
        for franja, tipo, fecha, valor in re.findall(rf"Lectura actual:\s*(Punta|Llano|Valle)\s+(\w+)\s+{_FECHA}\s+([\d.]+)\s*kWh", diseno)
    }
    consumos = dict(re.findall(r"Consumo:\s*(Punta|Llano|Valle)\s+([\d.,]+)\s*kWh", diseno))
    if not lecturas or set(lecturas) != set(consumos):
        raise comun.error(FORMATO, "no se encontraron las lecturas y los consumos por franja")
    mediciones = [
        Medicion(
            contrato=cups, magnitud="energia", franja=franja.lower(),
            cantidad=comun.decimal(FORMATO, "consumo", consumos[franja]),
            lectura=Lectura(
                comun.fecha_con_puntos(FORMATO, "lectura.fecha", fecha),
                comun.decimal(FORMATO, "lectura", valor),
                comun.tipo_lectura(FORMATO, tipo),
            ),
        )
        for franja, (fecha, tipo, valor) in lecturas.items()
    ]
    impreso = comun.buscar(FORMATO, "total consumo", r"Total consumo\s+([\d.,]+)\s*kWh", diseno)
    if sum(float(m.cantidad) for m in mediciones) != float(comun.decimal(FORMATO, "total consumo", impreso)):
        raise comun.error(FORMATO, f"las franjas no suman el consumo total impreso de {impreso} kWh")
    return mediciones
