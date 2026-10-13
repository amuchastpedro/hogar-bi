"""Genera `docs/diccionario.md` desde la base (R29).

Es un mapa: los conceptos de cada categoría, con su código. Las
justificaciones están en `docs/diseno.md` (sección 12).

Uso, desde la raíz del proyecto:

    $env:PYTHONPATH = "src"; .venv\\Scripts\\python -m facturas.bd.diccionario

El diccionario sale de las semillas: se construye una base temporal con ellas y
se lee de ahí. La base en uso tiene el mismo diccionario, porque se reconstruye
cuando cambian las semillas (diseño, sección 13.2).
"""

import sqlite3
import tempfile
from pathlib import Path

from facturas.bd.conexion import RAIZ, conectar
from facturas.bd.construir import DIR_SEMILLAS, construir

RUTA_DICCIONARIO = RAIZ / "docs" / "diccionario.md"


def generar(conexion: sqlite3.Connection) -> str:
    lineas = [
        "# Diccionario de conceptos",
        "",
        "Generado desde la base con `python -m facturas.bd.diccionario`; no se edita a mano.",
        "Los conceptos de cada categoría de gasto, con su código.",
    ]
    categorias = conexion.execute(
        "SELECT categoria_id, categoria_codigo, categoria_nombre FROM v_dim_categoria ORDER BY categoria_id"
    ).fetchall()
    for categoria_id, codigo, nombre in categorias:
        lineas += ["", f"## {nombre} (`{codigo}`)", "", "| Concepto | Código |", "|---|---|"]
        conceptos = conexion.execute(
            """SELECT concepto_nombre, concepto_codigo FROM v_dim_concepto
               WHERE categoria_id = ? ORDER BY concepto_id""",
            (categoria_id,),
        )
        lineas += [f"| {concepto} | `{codigo_concepto}` |" for concepto, codigo_concepto in conceptos]
    return "\n".join(lineas) + "\n"


def escribir(destino: Path = RUTA_DICCIONARIO, semillas: Path = DIR_SEMILLAS) -> Path:
    """Genera el diccionario de las semillas y lo escribe en `destino`."""
    with tempfile.TemporaryDirectory() as directorio:
        ruta = Path(directorio) / "facturas.db"
        construir(ruta, semillas)
        conexion = conectar(ruta, "lectura")
        try:
            texto = generar(conexion)
        finally:
            conexion.close()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(texto, encoding="utf-8", newline="\n")
    return destino


def main() -> None:
    print(f"Escrito {escribir().relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
