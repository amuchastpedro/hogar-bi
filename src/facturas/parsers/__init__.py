"""Registro de parsers: cada uno reconoce un formato de documento y lo convierte en una factura extraída.

Un parser es un módulo con `FORMATO`, `VERSION`, `reconoce(documento) -> bool` y
`extraer(documento) -> FacturaExtraida`. Los parsers solo conocen PDFs: nada de base ni de diccionario.
"""

from pathlib import Path

from facturas.extraccion import ErrorExtraccion, FacturaExtraida
from facturas.parsers import aigues_agua, digi_convergente, naturgy_gas, naturgy_iberia_gas, naturgy_iberia_luz, naturgy_luz
from facturas.parsers.pdf import Documento, leer

PARSERS = (aigues_agua, naturgy_gas, naturgy_luz, digi_convergente, naturgy_iberia_gas, naturgy_iberia_luz)


def reconocer(documento: Documento):
    """El único parser que reconoce el documento; error si ninguno o más de uno."""
    candidatos = [parser for parser in PARSERS if parser.reconoce(documento)]
    if not candidatos:
        raise ErrorExtraccion("ningún parser reconoce el documento: formato o proveedor desconocido")
    if len(candidatos) > 1:
        raise ErrorExtraccion(f"el documento lo reconocen varios parsers: {[p.FORMATO for p in candidatos]}")
    return candidatos[0]


def extraer(ruta: Path | str) -> FacturaExtraida:
    """PDF → factura extraída."""
    documento = leer(ruta)
    return reconocer(documento).extraer(documento)
