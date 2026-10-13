"""Una sola ejecución a la vez.

El bloqueo es un bloqueo del sistema operativo sobre un archivo. Lo libera el sistema
cuando el proceso termina, aunque muera sin pasar por el `finally`, así que nunca queda
un bloqueo huérfano.
"""

import os
from contextlib import contextmanager
from pathlib import Path

try:
    import msvcrt

    def _tomar(descriptor):
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)

    def _soltar(descriptor):
        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)

except ImportError:  # no es Windows
    import fcntl

    def _tomar(descriptor):
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _soltar(descriptor):
        fcntl.flock(descriptor, fcntl.LOCK_UN)


class BloqueoOcupado(Exception):
    """Ya hay otra ejecución en curso."""


@contextmanager
def bloqueo(ruta: Path):
    """Toma el bloqueo o lanza `BloqueoOcupado`; lo libera al salir, también si hubo un error."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(ruta, os.O_RDWR | os.O_CREAT)
    try:
        try:
            _tomar(descriptor)
        except OSError as error:
            raise BloqueoOcupado(f"hay otra ejecución en curso ({ruta.name})") from error
        try:
            yield
        finally:
            _soltar(descriptor)
    finally:
        os.close(descriptor)
