"""Logs en `datos/logs/` con rotación.

Todo va al archivo `facturas.log`, que rota al llegar a 1 MB y conserva 5 copias. La consola
no recibe logs: el comando imprime su resumen y sus errores.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

NOMBRE = "facturas"
MAX_BYTES = 1_000_000
COPIAS = 5
_FORMATO = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configurar(directorio: Path) -> logging.Logger:
    """Deja el logger `facturas` escribiendo en `directorio`; cada llamada reemplaza la anterior."""
    cerrar()
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(NOMBRE)
    logger.setLevel(logging.INFO)
    archivo = RotatingFileHandler(
        directorio / "facturas.log", maxBytes=MAX_BYTES, backupCount=COPIAS, encoding="utf-8"
    )
    archivo.setFormatter(logging.Formatter(_FORMATO))
    logger.addHandler(archivo)
    logger.propagate = False
    return logger


def cerrar() -> None:
    """Cierra los archivos del log (en Windows, un archivo abierto no se puede borrar)."""
    logger = logging.getLogger(NOMBRE)
    for manejador in list(logger.handlers):
        logger.removeHandler(manejador)
        manejador.close()
