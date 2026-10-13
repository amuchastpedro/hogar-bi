"""Aigües de Barcelona (agua). Detalle en la página 2; el período se normaliza con D10 (diseño, 11.7)."""

import re
from decimal import Decimal

from facturas.extraccion import Contrato, ErrorExtraccion, Lectura, Linea, Medicion, Periodo
from facturas.parsers import comun
from facturas.parsers.pdf import Documento

FORMATO = "aigues_agua"
VERSION = "1.2.0"
IDENTIFICADOR_FISCAL = "A66098435"
CATEGORIA = "agua"
OPCIONALES_IMPRESOS: tuple[str, ...] = ()

_FILA = re.compile(r"^(?P<resto>.*?)\s+(?P<importe>-?[\d.]*\d,\d{2})(?:\s+(?:\d+%|NS|\.\.\.))?(?:\s+\(\d+\))?$")
_NUMERO_SUELTO = re.compile(r"[\d.]+(?:,\d+)?")
_TOTAL_A_PAGAR = re.compile(r"^TOTAL A PAGAR\s+[\d.,]+$")


def reconoce(documento: Documento) -> bool:
    return comun.tiene_identificador(documento.texto, IDENTIFICADOR_FISCAL) and "DETALLE DE CONCEPTOS A PAGAR" in documento.texto


def extraer(documento: Documento):
    comun.rechazar_si_no_es_ordinaria(FORMATO, documento.texto)
    d = documento.diseno

    numero = comun.buscar(FORMATO, "numero", r"N\S{1,2}\s+factura\s+(\d+)", d)
    contrato = comun.buscar(FORMATO, "contrato", r"N\S{1,2}\s+contrato\s+(\d+)", d)
    impreso_inicio, impreso_fin = comun.buscar(FORMATO, "periodo", r"Periodo de facturaci.n\s+(\S+)\s*/\s*(\S+)", d)
    fecha_emision = comun.fecha_con_mes_abreviado(FORMATO, "fecha_emision", comun.buscar(FORMATO, "fecha_emision", r"Fecha emisi.n\s+(\S+)", d))
    fin = comun.fecha_con_mes_abreviado(FORMATO, "periodo.fin", impreso_fin)
    impreso = comun.fecha_con_mes_abreviado(FORMATO, "periodo.inicio", impreso_inicio)

    lineas, total = _lineas(d, contrato)
    medicion = _medicion(d, contrato)
    # D10: el período impreso va de lectura a lectura y el primer día no se factura: lo factura la anterior.
    # La primera factura de un contrato no tiene anterior y cuenta también el día del alta. Los promedios
    # por día impresos deciden cuál de los dos casos es.
    inicio = comun.dia_siguiente(impreso)
    try:
        _verificar_promedios(documento.texto, comun.dias_inclusive(inicio, fin), total, medicion, d)
    except ErrorExtraccion as error_d10:
        try:
            _verificar_promedios(documento.texto, comun.dias_inclusive(impreso, fin), total, medicion, d)
        except ErrorExtraccion:
            raise error_d10 from None
        inicio = impreso
    comun.verificar_suma(FORMATO, [linea.importe_centimos for linea in lineas], total)

    return comun.construir(
        FORMATO, VERSION, OPCIONALES_IMPRESOS,
        identificador_fiscal=IDENTIFICADOR_FISCAL, numero=numero, tipo="ordinaria", moneda="EUR",
        fecha_emision=fecha_emision, periodo=Periodo(inicio, fin), importe_total_centimos=total,
        contratos=(Contrato(contrato, CATEGORIA),), lineas=tuple(lineas), mediciones=(medicion,),
    )


def _lineas(diseno: str, contrato: str) -> tuple[list[Linea], int]:
    """Filas del detalle (página 2), por su sangría.

    Las filas con sangría son el desglose de un grupo, y el grupo termina en una fila sin sangría que
    lo subtotaliza. El suministro se emite por sus tramos y su subtotal se descarta; el resto de los
    grupos (canon, alcantarillado) se emite por su subtotal (D2, D3). Cada subtotal se verifica
    contra la suma de su desglose.
    """
    filas = diseno.splitlines()
    try:
        inicio = next(i for i, f in enumerate(filas) if f.startswith("DETALLE DE CONCEPTOS A PAGAR"))
        fin = next(
            i for i in range(inicio, len(filas))
            if not filas[i].startswith(" ") and _TOTAL_A_PAGAR.match(" ".join(filas[i].split()))
        )
    except StopIteration:
        raise comun.error(FORMATO, "no se encontró el detalle de conceptos o su 'TOTAL A PAGAR'") from None
    total = comun.centimos(FORMATO, "importe_total", filas[fin].split()[-1])

    emitidas: list[tuple[str, int]] = []
    desglose: list[tuple[str, int]] = []
    encabezado = ""
    for fila in filas[inicio + 1:fin]:
        con_sangria = fila.startswith(" ")
        texto_fila = " ".join(fila.split())
        encontrada = _FILA.match(texto_fila)
        if encontrada is None:
            if not con_sangria:
                encabezado = texto_fila
            continue
        texto = _sin_cifras_finales(encontrada["resto"])
        if texto.startswith("("):  # la fila continúa el rótulo de la anterior: "(Ayuntamiento …)"
            texto = encabezado
        importe = comun.centimos(FORMATO, f"importe de '{texto}'", encontrada["importe"])
        if con_sangria:
            desglose.append((texto, importe))
            continue
        if texto.startswith("SUMINISTRO DE AGUA"):
            _verificar_subtotal(texto, importe, desglose)
            emitidas += desglose
        elif not texto.startswith("TOTAL FACTURA"):
            if desglose:
                _verificar_subtotal(texto, importe, desglose)
            emitidas.append((texto, importe))
        desglose = []
    if desglose:
        raise comun.error(FORMATO, f"filas del detalle sin subtotal: {[t for t, _ in desglose]}")
    if not emitidas:
        raise comun.error(FORMATO, "el detalle de conceptos no tiene líneas")
    return [Linea(i, contrato, texto, importe) for i, (texto, importe) in enumerate(emitidas, start=1)], total


def _sin_cifras_finales(resto: str) -> str:
    """Quita volumen, precio o base que la fila imprime después del rótulo."""
    palabras = resto.split()
    while len(palabras) > 1 and _NUMERO_SUELTO.fullmatch(palabras[-1]):
        palabras.pop()
    return " ".join(palabras)


def _verificar_subtotal(texto: str, importe: int, desglose: list[tuple[str, int]]) -> None:
    suma = sum(i for _, i in desglose)
    if suma != importe:
        raise comun.error(FORMATO, f"el desglose de '{texto}' suma {suma} céntimos y el subtotal impreso es {importe}")


def _medicion(diseno: str, contrato: str) -> Medicion:
    _, anterior, fecha_actual, actual, consumo, tipo = comun.buscar(
        FORMATO, "lecturas",
        r"(\d{2}/\d{2}/\d{2})\s+(\d+)\s+(\d{2}/\d{2}/\d{2})\s+(\d+)\s+(\d+)\s+Lectura\s+(\w+)",
        diseno,
    )
    if int(actual) - int(anterior) != int(consumo):
        raise comun.error(FORMATO, f"las lecturas {anterior} y {actual} no dan el consumo impreso de {consumo} m³")
    lectura = Lectura(comun.fecha_dmy(FORMATO, "lectura.fecha", fecha_actual), actual, comun.tipo_lectura(FORMATO, tipo))
    return Medicion(contrato=contrato, magnitud="volumen", cantidad=consumo, lectura=lectura)


def _verificar_promedios(texto: str, dias: int, total: int, medicion: Medicion, diseno: str) -> None:
    """Los días del período salen de las fechas de las lecturas: se cotejan con los promedios impresos.

    Los dos promedios en euros (gasto y suministro) están siempre y van redondeados. Los litros por día
    pueden faltar (un aviso ocupa su lugar en el mensaje) y van truncados: 10.000 l en 61 días se
    imprimen como "163", no "164". Se acepta una diferencia de menos de un litro.
    """
    gasto, suministro = comun.buscar(
        FORMATO, "promedios por día", r"([\d,]+)\s*€/d.a de los\s+cuales\s+([\d,]+)\s*€/d.a", texto,
    )
    suministro_total = comun.buscar(FORMATO, "suministro de agua", r"^SUMINISTRO DE AGUA\s+([\d.,]+)\s*$", diseno, re.MULTILINE)
    esperados = [
        (Decimal(total) / 100 / dias, Decimal(gasto.replace(",", ".")), Decimal("0.005")),
        (Decimal(comun.centimos(FORMATO, "suministro", suministro_total)) / 100 / dias,
         Decimal(suministro.replace(",", ".")), Decimal("0.005")),
    ]
    litros = re.search(r"([\d.]+)\s+litros por d.a", texto)
    if litros:
        esperados.append((Decimal(int(medicion.cantidad) * 1000) / dias, Decimal(litros[1].replace(".", "")), Decimal("0.999")))
    if any(abs(calculado - impreso) > tolerancia for calculado, impreso, tolerancia in esperados):
        raise comun.error(FORMATO, f"los promedios por día impresos no corresponden a un período de {dias} días")
