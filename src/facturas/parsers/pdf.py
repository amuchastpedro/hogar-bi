"""Lectura del texto de un PDF con pypdf (Python puro, sin dependencias del sistema)."""

import logging
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from facturas.extraccion import ErrorExtraccion

# pypdf avisa por el log de cosas que no importan acá (texto rotado en páginas informativas).
logging.getLogger("pypdf").setLevel(logging.ERROR)


@dataclass(frozen=True)
class Documento:
    """El texto de un PDF, en las dos formas que usan los parsers.

    `texto`: el orden de lectura del PDF; sirve para párrafos y listas.
    `diseno`: respeta las columnas de la página, una fila por línea, con su sangría; sirve para
    tablas donde la etiqueta y el valor están en la misma fila.
    """

    texto: str
    diseno: str


def leer(ruta: Path | str) -> Documento:
    ruta = Path(ruta)
    try:
        lector = PdfReader(str(ruta))
        texto = "\n".join(pagina.extract_text() or "" for pagina in lector.pages)
        if not texto.strip():
            raise ErrorExtraccion(f"{ruta.name} no tiene texto: está vacío o es una imagen")
        diseno = "\n".join(pagina.extract_text(extraction_mode="layout") or "" for pagina in lector.pages)
    except FileNotFoundError as error:
        raise ErrorExtraccion(f"no existe el archivo {ruta.name}") from error
    except (PyPdfError, ValueError, OSError, KeyError, IndexError, TypeError) as error:
        raise ErrorExtraccion(f"{ruta.name} no se pudo leer como PDF: {error}") from error
    diseno = "\n".join(linea.rstrip() for linea in diseno.splitlines() if linea.strip())
    return Documento(texto=texto, diseno=diseno)
