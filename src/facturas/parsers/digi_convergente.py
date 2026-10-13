"""DIGI (fibra y móvil). Una factura con un contrato por servicio; el IVA se imprime solo como total y se reparte (R5)."""

import re

from facturas.extraccion import Contrato, Linea, Periodo, TotalRepartido
from facturas.parsers import comun
from facturas.parsers.pdf import Documento

FORMATO = "digi_convergente"
VERSION = "1.2.0"
IDENTIFICADOR_FISCAL = "A84919760"
# Las facturas hasta 2025 imprimen el NIF de la razón social anterior (S.L.U., letra B); el número es el mismo
# y es la misma empresa, así que se emite con el NIF vigente y las facturas de las dos épocas comparten proveedor.
IDENTIFICADORES_ANTERIORES = ("B84919760",)
OPCIONALES_IMPRESOS = ("fecha_vencimiento", "seccion")

_FECHA = r"(\d{2}/\d{2}/\d{4})"
_IMPORTE = r"(-?[\d.]*\d,\d{2})"
# La cantidad es un número de unidades, un tiempo ("33:55") o un volumen con su unidad ("210,57 MB").
_ITEM = re.compile(
    rf"^(?P<texto>.+?)\s+(?P<cantidad>\d+(?::\d+)?|\d[\d.]*(?:,\d+)?\s?[KMG]B)\s+(?P<importe>-?[\d.]*\d,\d{{2}}) €$"
)
_TOTAL_SIN_IMPUESTOS = re.compile(rf"^Total sin impuestos\s+{_IMPORTE} €$")
_TOTAL_SERVICIO = re.compile(rf"^Total\s+{_IMPORTE} €$")
_INICIO_SERVICIO = re.compile(r"^([A-Z0-9]+)Servicios:")


def reconoce(documento: Documento) -> bool:
    return (
        any(comun.tiene_identificador(documento.texto, nif) for nif in (IDENTIFICADOR_FISCAL, *IDENTIFICADORES_ANTERIORES))
        and "DESGLOSE DE SERVICIOS POR LÍNEA" in documento.texto
    )


def extraer(documento: Documento):
    comun.rechazar_si_no_es_ordinaria(FORMATO, documento.texto)
    t = documento.texto
    buscar = lambda campo, patron: comun.buscar(FORMATO, campo, patron, t)  # noqa: E731

    numero = buscar("numero", r"FACTURA Número:\s*(\w+)")
    inicio, fin = (
        comun.fecha_dmy(FORMATO, "periodo", f) for f in buscar("periodo", rf"Periodo de consumo\s+{_FECHA} - {_FECHA}")
    )
    fecha_emision = comun.fecha_dmy(FORMATO, "fecha_emision", buscar("fecha_emision", rf"Fecha de emisión\s+{_FECHA}"))
    vencimiento = comun.fecha_dmy(
        FORMATO, "fecha_vencimiento", buscar("fecha_vencimiento", rf"Fecha de vencimiento\s+{_FECHA}")
    )
    total = comun.centimos(FORMATO, "importe_total", buscar("importe_total", rf"{_IMPORTE} ?€\s*TOTAL FACTURA"))
    base = comun.centimos(FORMATO, "base imponible", buscar("base imponible", rf"{_IMPORTE} ?€\s*IMPORTE \(base imponible\)"))
    iva_importe, iva_texto = buscar("impuestos", rf"{_IMPORTE} ?€\s*(IMPUESTOS \([^)]*\))")
    iva = comun.centimos(FORMATO, "impuestos", iva_importe)
    if base + iva != total:
        raise comun.error(FORMATO, f"base {base} más impuestos {iva} no suman el total impreso {total} (céntimos)")

    fibra = buscar("identificador de fibra", r"Identificador Fibra Digi\s+(\w+)")
    # Cada línea móvil figura como "importe €identificador"; la primera, a continuación del rótulo.
    bloque_movil = re.search(r"EN EL MÓVIL(.*?)(?:_{10,}|TOTAL FACTURA)", t, re.DOTALL)
    moviles = re.findall(r"[\d.,]+ ?€\s*(\w+)", bloque_movil[1]) if bloque_movil else []
    # "EN CASA" tiene la fibra y, en algunas facturas de 2025, un teléfono fijo ("DIGI tel"), que se cuenta
    # como fibra (decisión de la persona usuaria, 2026-10-06). La fibra se rotula con su nombre comercial,
    # no con su identificador: los demás servicios del bloque aparecen como "importe €identificador".
    bloque_casa = re.search(r"EN CASA(.*?)(?:_{10,}|EN EL MÓVIL|TOTAL FACTURA)", t, re.DOTALL)
    en_casa = re.findall(r"[\d.,]+ ?€\s*(\d+)\b", bloque_casa[1]) if bloque_casa else []
    categorias = {**dict.fromkeys(moviles, "movil"), **dict.fromkeys(en_casa, "fibra"), fibra: "fibra"}

    servicios = _servicios(t)
    contratos, lineas = [], []
    for identificador, items, sin_impuestos, con_impuestos in servicios:
        if identificador not in categorias:
            raise comun.error(FORMATO, f"el servicio {identificador} no figura como móvil ni como fibra en la primera página")
        contratos.append(Contrato(identificador, categorias[identificador]))
        for seccion, texto, importe in items:
            lineas.append(Linea(len(lineas) + 1, identificador, texto, importe, seccion=seccion))
        # IVA del servicio: total con impuestos menos total sin impuestos, ambos impresos (R5).
        lineas.append(
            Linea(len(lineas) + 1, identificador, iva_texto, con_impuestos - sin_impuestos, derivada_de=iva_texto)
        )
    if sum(con for _, _, _, con in servicios) != total:
        raise comun.error(FORMATO, "los totales por servicio no suman el total de la factura")
    comun.verificar_suma(FORMATO, [linea.importe_centimos for linea in lineas], total)

    return comun.construir(
        FORMATO, VERSION, OPCIONALES_IMPRESOS,
        identificador_fiscal=IDENTIFICADOR_FISCAL, numero=numero, tipo="ordinaria", moneda="EUR",
        fecha_emision=fecha_emision, fecha_vencimiento=vencimiento, periodo=Periodo(inicio, fin),
        importe_total_centimos=total, contratos=tuple(contratos), lineas=tuple(lineas),
        totales_repartidos=(TotalRepartido(iva_texto, iva),),
    )


def _servicios(texto: str) -> list[tuple[str, list[tuple[str, str, int]], int, int]]:
    """Por servicio: (identificador, [(sección, texto, céntimos)], total sin impuestos, total con impuestos).

    Los rótulos de sección se imprimen subrayados con guiones bajos, a veces intercalados dentro de la
    palabra ("P__R_O__D…"): se quitan antes de usarlos. Los items de un servicio tienen que sumar su
    "Total sin impuestos".
    """
    servicios, actual, seccion = [], None, None
    lineas = texto.split("DESGLOSE DE SERVICIOS POR LÍNEA", 1)[-1].splitlines()
    for linea in (linea.strip() for linea in lineas):
        sin_guiones = linea.rstrip("_")
        if (inicio := _INICIO_SERVICIO.match(linea)):
            actual = {"id": inicio[1], "items": [], "sin": None, "con": None}
            servicios.append(actual)
            seccion = None
        elif actual is None:
            continue
        elif "_" in linea and re.fullmatch(r"[A-ZÁÉÍÓÚÜÑ ]{3,}", linea.replace("_", "").strip()):
            seccion = linea.replace("_", "").strip()
        elif (m := _TOTAL_SIN_IMPUESTOS.match(sin_guiones)):
            actual["sin"] = comun.centimos(FORMATO, "total sin impuestos", m[1])
        elif (m := _TOTAL_SERVICIO.match(sin_guiones)):
            actual["con"] = comun.centimos(FORMATO, "total del servicio", m[1])
        elif (m := _ITEM.match(sin_guiones)):
            if seccion is None:
                raise comun.error(FORMATO, f"la línea {m['texto']!r} no está dentro de una sección")
            importe = comun.centimos(FORMATO, f"importe de '{m['texto']}'", m["importe"])
            actual["items"].append((seccion, m["texto"], importe))
    if not servicios:
        raise comun.error(FORMATO, "no se encontró el desglose de servicios por línea")
    resultado = []
    for s in servicios:
        if s["sin"] is None or s["con"] is None or not s["items"]:
            raise comun.error(FORMATO, f"el servicio {s['id']} no tiene líneas o sus totales")
        if sum(i for _, _, i in s["items"]) != s["sin"]:
            raise comun.error(FORMATO, f"las líneas del servicio {s['id']} no suman su total sin impuestos")
        resultado.append((s["id"], s["items"], s["sin"], s["con"]))
    return resultado
