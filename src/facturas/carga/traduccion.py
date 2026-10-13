"""Traducción de las líneas de una factura a conceptos (R30, R31).

Los alias son patrones GLOB sobre la sección y el texto normalizados de cada
línea, dentro de la categoría de su contrato (diseño, sección 12.3). Un texto
sin alias, o que coincide con más de uno, hace rechazar la factura: nunca se
descarta ni se asigna a un concepto genérico.

Se escribió en el bloque 2 para probar que las semillas no son ambiguas; la
carga del bloque 4 la usa al traducir cada línea.
"""

import sqlite3
import unicodedata


class ErrorTraduccion(Exception):
    """Un texto sin alias, o con más de uno, en la categoría de su contrato."""


def normalizar(texto: str | None) -> str:
    """Minúsculas, sin tildes (NFKD) y con los espacios colapsados. None da ''.

    Por ejemplo, "Tramo de 12 a 15 m³" da "tramo de 12 a 15 m3".
    """
    if texto is None:
        return ""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())


def traducir(conexion: sqlite3.Connection, categoria: str, seccion: str | None, texto: str) -> int:
    """concepto_id de la línea, según los alias de su categoría (código)."""
    coincidencias = conexion.execute(
        """SELECT a.concepto_id, a.patron_seccion, a.patron_texto
           FROM alias_concepto AS a
           JOIN categoria AS ca ON ca.categoria_id = a.categoria_id
           WHERE ca.codigo = ? AND ? GLOB a.patron_seccion AND ? GLOB a.patron_texto
           ORDER BY a.alias_concepto_id""",
        (categoria, normalizar(seccion), normalizar(texto)),
    ).fetchall()
    if not coincidencias:
        raise ErrorTraduccion(
            f"Texto sin alias en la categoría {categoria}: sección {seccion!r}, texto {texto!r}"
        )
    if len(coincidencias) > 1:
        patrones = "; ".join(f"sección {s!r}, texto {t!r}" for _, s, t in coincidencias)
        raise ErrorTraduccion(
            f"Texto ambiguo en la categoría {categoria}: sección {seccion!r}, texto {texto!r} "
            f"coincide con los alias {patrones}"
        )
    return coincidencias[0][0]
