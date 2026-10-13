"""Utilidades que comparten los parsers: números y fechas en formato español, búsqueda con error claro."""

import re
from datetime import date, timedelta

from facturas.extraccion import ErrorExtraccion, FacturaExtraida, Linea, Periodo, verificar_opcionales

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}
_IMPORTE = re.compile(r"-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2}")


def error(formato: str, mensaje: str) -> ErrorExtraccion:
    return ErrorExtraccion(f"{formato}: {mensaje}")


def buscar(formato: str, campo: str, patron: str, texto: str, flags: int = 0) -> str | tuple[str, ...]:
    """Primer grupo (o todos, si hay varios) del patrón; si no aparece, un error que nombra el campo."""
    encontrado = re.search(patron, texto, flags)
    if encontrado is None:
        raise error(formato, f"no se encontró '{campo}' en el documento")
    return encontrado.group(1) if len(encontrado.groups()) == 1 else encontrado.groups()


def tiene_identificador(texto: str, identificador: str) -> bool:
    """El NIF del proveedor figura en el texto, con o sin guion o espacio tras la letra inicial."""
    patron = re.escape(identificador[0]) + r"[\s-]?" + re.escape(identificador[1:])
    return re.search(rf"(?<![A-Z0-9]){patron}(?![A-Z0-9])", texto) is not None


def rechazar_si_no_es_ordinaria(formato: str, texto: str) -> None:
    """Las rectificativas y los abonos no se leen todavía: se rechazan en lugar de cargarse como ordinarias."""
    if re.search(r"\b(rectificativa|abono)\b", texto, re.IGNORECASE):
        raise error(formato, "el documento parece una factura rectificativa o un abono y este parser solo lee ordinarias")


def centimos(formato: str, campo: str, texto: str) -> int:
    """'1.234,56' → 123456."""
    texto = texto.strip()
    if not _IMPORTE.fullmatch(texto):
        raise error(formato, f"'{campo}' no es un importe en formato español: {texto!r}")
    return int(texto.replace(".", "").replace(",", ""))


def decimal(formato: str, campo: str, texto: str) -> str:
    """Decimal español → texto con punto y sin separador de miles, con los decimales impresos: '11,470' → '11.470'."""
    texto = texto.strip()
    if not re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?", texto):
        raise error(formato, f"'{campo}' no es un número en formato español: {texto!r}")
    return texto.replace(".", "").replace(",", ".")


def fecha_dmy(formato: str, campo: str, texto: str) -> str:
    """'29/06/2026' o '09/04/26' → '2026-06-29'."""
    encontrado = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4}|\d{2})", texto.strip())
    if encontrado is None:
        raise error(formato, f"'{campo}' no es una fecha dd/mm/aaaa: {texto!r}")
    dia, mes, anio = encontrado.groups()
    return _iso(formato, campo, int(anio) + (2000 if len(anio) == 2 else 0), int(mes), int(dia))


def fecha_con_mes_abreviado(formato: str, campo: str, texto: str) -> str:
    """'23-jun-2026' o '09-abr-26' → ISO."""
    encontrado = re.fullmatch(r"(\d{1,2})-([a-zA-Z]{3,4})\.?-(\d{4}|\d{2})", texto.strip())
    if encontrado is None or encontrado.group(2).lower()[:3] not in MESES:
        raise error(formato, f"'{campo}' no es una fecha dd-mmm-aa: {texto!r}")
    dia, mes, anio = encontrado.groups()
    return _iso(formato, campo, int(anio) + (2000 if len(anio) == 2 else 0), MESES[mes.lower()[:3]], int(dia))


def _iso(formato: str, campo: str, anio: int, mes: int, dia: int) -> str:
    try:
        return date(anio, mes, dia).isoformat()
    except ValueError as causa:
        raise error(formato, f"'{campo}' no es una fecha válida: {dia}/{mes}/{anio}") from causa


def dias_inclusive(inicio: str, fin: str) -> int:
    return (date.fromisoformat(fin) - date.fromisoformat(inicio)).days + 1


def dia_siguiente(fecha: str) -> str:
    return (date.fromisoformat(fecha) + timedelta(days=1)).isoformat()


def verificar_dias(formato: str, inicio: str, fin: str, impresos: int) -> None:
    calculados = dias_inclusive(inicio, fin)
    if calculados != impresos:
        raise error(formato, f"el período {inicio} a {fin} son {calculados} días y el documento imprime {impresos}")


def importe_final(linea: str) -> tuple[str, int] | None:
    """Separa 'texto … 1.234,56 €' en (resto, céntimos); None si la línea no termina en un importe con €."""
    encontrado = re.fullmatch(rf"(.*?)\s*({_IMPORTE.pattern})\s*€", linea.strip())
    if encontrado is None:
        return None
    return encontrado.group(1), int(encontrado.group(2).replace(".", "").replace(",", ""))


def lineas_de_detalle(formato: str, texto: str, contrato: str, periodo: Periodo) -> list[Linea]:
    """Las líneas del detalle "Concepto  Cálculo  Importe" de Naturgy (gas y luz).

    Una fila es una línea que termina en un importe y tiene una cuenta ("344 kWh x J,XKXZ €/kWh"):
    así quedan fuera los subtotales y totales. Un rótulo que sigue en minúscula en la línea siguiente
    ("Impuesto Especial sobre" / "hidrocarburos …") se une con la línea anterior.

    Si el precio cambia dentro del período, el concepto se parte en filas por tramo de fechas, debajo
    de su rótulo ("Consumo gas" / "Del 26/08/2025 al 30/09/2025 106 kWh x …"): cada fila lleva el
    rótulo como texto y el tramo como período, que tiene que estar dentro del de la factura.

    Debajo de "Otros conceptos" puede haber cargos sin cuenta, con el rótulo en una o varias líneas
    ("Gastos de gestión de inspección" / "periódica de IRI KZ,ZX €"): también son filas.
    """
    lineas = [" ".join(linea.split()) for linea in texto.splitlines()]
    try:
        inicio = next(i for i, linea in enumerate(lineas) if linea.startswith("Concepto Cálculo Importe"))
        # El detalle termina en "Total a pagar", o en "Total <importe>" en un ajuste (sin "a pagar").
        fin = next(
            i for i in range(inicio, len(lineas))
            if lineas[i].startswith("Total a pagar") or re.fullmatch(rf"Total (?:{_IMPORTE.pattern}) €", lineas[i])
        )
    except StopIteration:
        raise error(formato, "no se encontró el detalle 'Concepto Cálculo Importe' o su total") from None
    resultado = []
    rotulo_vigente = None
    otros, rotulo_otros = False, []
    for i in range(inicio + 1, fin):
        encontrada = importe_final(lineas[i])
        if lineas[i] == "Otros conceptos":
            otros, rotulo_otros = True, []
            continue
        if encontrada is None:
            if lineas[i] and not lineas[i][0].islower():
                rotulo_vigente = lineas[i]
            if otros and lineas[i]:
                rotulo_otros.append(lineas[i])
            continue
        if " x " not in encontrada[0]:
            if re.match(r"(?:Sub)?[Tt]otal\b", lineas[i]):
                otros = False
            elif otros:
                texto_fila = " ".join([*rotulo_otros, encontrada[0]]).strip()
                resultado.append(Linea(len(resultado) + 1, contrato, texto_fila, encontrada[1]))
                rotulo_otros = []
            continue
        rotulo_otros = []
        rotulo = re.match(r"(.*?)\s+-?[\d.,]+\s*(?:kWh|kW|días?|€|%)", encontrada[0])
        if rotulo is None or not rotulo[1]:
            raise error(formato, f"no se pudo separar el rótulo de la fila {lineas[i]!r}")
        texto_fila, periodo_fila = rotulo[1], None
        tramo = re.fullmatch(r"Del (\d{2}/\d{2}/\d{4}) al (\d{2}/\d{2}/\d{4})", texto_fila)
        if tramo:
            if rotulo_vigente is None:
                raise error(formato, f"la fila {lineas[i]!r} no tiene un rótulo encima")
            periodo_fila = Periodo(*(fecha_dmy(formato, "tramo de la fila", f) for f in tramo.groups()))
            if not periodo.inicio <= periodo_fila.inicio <= periodo_fila.fin <= periodo.fin:
                raise error(formato, f"el tramo de la fila {lineas[i]!r} no está dentro del período de la factura")
            texto_fila = rotulo_vigente
        elif texto_fila[0].islower():
            texto_fila = f"{lineas[i - 1]} {texto_fila}"
        resultado.append(Linea(len(resultado) + 1, contrato, texto_fila, encontrada[1], periodo=periodo_fila))
    if not resultado:
        raise error(formato, "el detalle no tiene filas")
    return resultado


def verificar_suma(formato: str, importes: list[int], total: int) -> None:
    """Las líneas emitidas tienen que sumar el total a pagar impreso: si no, se omitió o se leyó mal una línea."""
    if sum(importes) != total:
        raise error(formato, f"las líneas suman {sum(importes)} céntimos y el total impreso es {total}")


def tipo_lectura(formato: str, texto: str) -> str:
    """'Real' o 'Cliente' → 'real'; 'Estimada' o 'estimado' → 'estimada'.

    'Cliente' es la lectura que informó la persona usuaria: es una lectura medida, no una estimación.
    """
    clave = texto.strip().lower()
    if clave in ("real", "cliente"):
        return "real"
    if clave.startswith("estimad"):
        return "estimada"
    raise error(formato, f"tipo de lectura desconocido: {texto!r}")


def construir(formato: str, version: str, opcionales_impresos: tuple[str, ...], **datos) -> FacturaExtraida:
    """Arma la factura extraída: falla con el formato en el mensaje si la forma o los opcionales no cumplen."""
    try:
        factura = FacturaExtraida(formato=formato, version_parser=version, **datos)
        verificar_opcionales(factura, opcionales_impresos)
    except ErrorExtraccion as causa:
        if str(causa).startswith(f"{formato}:"):
            raise
        raise error(formato, str(causa)) from causa
    return factura


def cups_suministro(formato: str, texto: str) -> str:
    """El CUPS que identifica el suministro: "ES", 16 dígitos y 2 letras de control (20 caracteres).

    Algunas facturas agregan 2 caracteres más, el punto frontera ("0F"), y otras no: sin quitarlos, el mismo
    suministro quedaría en dos contratos.
    """
    cups = texto.replace(" ", "")
    if not re.fullmatch(r"ES\d{16}[A-Z]{2}(?:\d[FPCRXYZ])?", cups):
        raise error(formato, "el CUPS no tiene el formato ES + 16 dígitos + 2 letras")
    return cups[:20]


def fecha_con_puntos(formato: str, campo: str, texto: str) -> str:
    """'02.11.2024' o '02.11.24' (formato de Naturgy de 2024) → '2024-11-02'."""
    return fecha_dmy(formato, campo, texto.strip().replace(".", "/"))


_TOTALES_IBERIA = re.compile(r"Subtotal|Base imponible|Total (?!IVA)")


def lineas_por_columnas(formato: str, diseno: str, contrato: str, periodo: Periodo) -> list[Linea]:
    """Las líneas del detalle de Naturgy de 2024 ("Detalle de tu factura"), leídas del texto por columnas.

    Cada fila termina en su importe ("KJ,XJ€"). Las columnas se separan por 3 espacios o más; los puntos de
    relleno se quitan antes. El rótulo es la última columna que no empieza por un número, sin contar las
    referencias ("Contrato: …"): a la izquierda puede haber texto de otro recuadro ("Tarifa Por Uso Luz",
    "27 días"). Los subtotales, la base imponible y los totales no son filas; "Total IVA 21%" sí lo es.

    Si el precio cambia dentro del período, el concepto se parte en filas "Período de 01.08.2024 a
    30.09.2024", debajo de su rótulo: cada una lleva el rótulo como texto y el tramo como período.
    """
    filas = diseno.splitlines()
    try:
        inicio = next(i for i, fila in enumerate(filas) if re.search(r"Concepto\s+Cálculo\s+Importe", fila))
        fin = next(i for i in range(inicio, len(filas)) if re.search(r"Total a pagar\s+[\d.,]+\s*€", filas[i]))
    except StopIteration:
        raise error(formato, "no se encontró el detalle 'Concepto Cálculo Importe' o su 'Total a pagar'") from None
    resultado, rotulo_vigente = [], None
    for fila in filas[inicio + 1:fin]:
        columnas = [c.strip() for c in re.split(r"\s{3,}", re.sub(r"(?:\.\s*){3,}", "   ", fila)) if c.strip()]
        if not columnas:
            continue
        importe = re.fullmatch(rf"({_IMPORTE.pattern})\s*€", columnas[-1])
        textos = [c for c in columnas if not re.match(r"-?\d", c) and not c.startswith("Contrato:")]
        if importe is None:
            if textos:
                rotulo_vigente = textos[-1]
            continue
        if not textos:
            raise error(formato, f"la fila {' '.join(columnas)!r} no tiene rótulo")
        rotulo, periodo_fila = textos[-1], None
        if _TOTALES_IBERIA.match(rotulo):
            continue
        tramo = re.fullmatch(r"Período de (\d{2}\.\d{2}\.\d{4}) a (\d{2}\.\d{2}\.\d{4})", rotulo)
        if tramo:
            if rotulo_vigente is None:
                raise error(formato, f"la fila {rotulo!r} no tiene un rótulo encima")
            periodo_fila = Periodo(*(fecha_con_puntos(formato, "tramo de la fila", f) for f in tramo.groups()))
            if not periodo.inicio <= periodo_fila.inicio <= periodo_fila.fin <= periodo.fin:
                raise error(formato, f"el tramo {rotulo!r} no está dentro del período de la factura")
            rotulo = rotulo_vigente
        resultado.append(Linea(len(resultado) + 1, contrato, rotulo, centimos(formato, "importe", importe[1]), periodo=periodo_fila))
    if not resultado:
        raise error(formato, "el detalle no tiene filas")
    return resultado
