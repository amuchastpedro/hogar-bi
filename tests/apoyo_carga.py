"""Apoyo de los tests de carga y operación: PDFs de ejemplo copiados a carpetas temporales.

Los tests trabajan siempre sobre copias de `ejemplos/` en una raíz temporal, nunca sobre `datos/`.
Los PDFs de ejemplo no se versionan: sin ellos, los tests que los usan se saltan con un mensaje.
`ejemplos/` tiene 21 PDFs pero solo 18 distintos: `gas.pdf`, `gas_ajuste.pdf` y
`digi_2025_dos_moviles.pdf` repiten el contenido de otro archivo con otro nombre.
"""

import shutil
from pathlib import Path

import pytest

from facturas.bd.conexion import conectar
from facturas.bd.volcado import volcado_canonico

DIR_EJEMPLOS = Path(__file__).resolve().parents[1] / "ejemplos"

# Los cuatro ejemplos del caso (los que tienen valores esperados) y los demás.
CASO = ("agua.pdf", "gas.pdf", "luz.pdf", "fibra_movil.pdf")
TODOS = tuple(sorted(p.name for p in DIR_EJEMPLOS.glob("*.pdf")))
DISTINTOS = 18  # PDFs con contenido distinto entre los de `TODOS`


def ejemplo(nombre: str) -> Path:
    """La ruta de un PDF de ejemplo; si falta, salta el test."""
    ruta = DIR_EJEMPLOS / nombre
    if not ruta.exists():
        pytest.skip(f"falta ejemplos/{nombre}: los PDFs de ejemplo no se versionan")
    return ruta


def poner(rutas, *nombres, como=None) -> list[Path]:
    """Copia ejemplos a `datos/entrada/`; `como` renombra el primero."""
    if not (nombres or TODOS):
        pytest.skip("falta ejemplos/: los PDFs de ejemplo no se versionan")
    copiados = []
    for nombre in nombres or TODOS:
        destino = rutas.entrada / (como or nombre)
        shutil.copyfile(ejemplo(nombre), destino)
        copiados.append(destino)
    return copiados


def pdf_con_texto(texto: str) -> bytes:
    """Un PDF mínimo y válido de una página con el texto dado (sin paréntesis ni barras)."""
    contenido = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET".encode("latin-1")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(contenido), contenido),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    salida, posiciones = bytearray(b"%PDF-1.4\n"), []
    for numero, objeto in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += b"%d 0 obj\n%s\nendobj\n" % (numero, objeto)
    inicio_xref = len(salida)
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for posicion in posiciones:
        salida += b"%010d 00000 n \n" % posicion
    salida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, inicio_xref)
    return bytes(salida)


def volcado(ruta_base):
    """El volcado canónico de la base en `ruta_base` (dos bases tienen el mismo contenido si coinciden)."""
    conexion = conectar(ruta_base, "lectura")
    try:
        return volcado_canonico(conexion)
    finally:
        conexion.close()


def consulta(ruta_base, sql, parametros=()):
    conexion = conectar(ruta_base, "lectura")
    try:
        return conexion.execute(sql, parametros).fetchall()
    finally:
        conexion.close()
