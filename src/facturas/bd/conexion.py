"""Conexión única a la base (R8, R39, R40).

`conectar()` es la única forma de abrir la base. En todos los modos activa las
claves foráneas, que SQLite trae desactivadas y hay que activar en cada conexión,
y espera hasta 5 segundos si la base está bloqueada. Hay tres modos:

- "lectura": dashboard, consultas de estado y respaldo. No puede escribir.
- "escritura": solo la carga. Usa el modo WAL, en el que leer y escribir a la vez
  no se bloquean entre sí.
- "nueva": solo `construir`. Crea el archivo, que no puede existir, y no verifica
  la versión del esquema, porque todavía no está creado.
- "reemplazo": solo la reconstrucción y la restauración. Abre para escribir una base
  que existe sin verificar su versión, porque es el destino de un backup que la
  sustituye: puede ser de otra versión o haber quedado a medio construir.

En "lectura" y "escritura" se verifica que la versión del esquema de la base
(`PRAGMA user_version`) es la de `esquema.sql`. Si no coincide, hay que
reconstruir la base (R19).

Las transacciones son explícitas (`isolation_level=None`): quien escribe abre
`BEGIN IMMEDIATE` y confirma con `COMMIT`.
"""

import re
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
RUTA_BASE = RAIZ / "datos" / "facturas.db"
RUTA_ESQUEMA = Path(__file__).with_name("esquema.sql")
ESPERA_BLOQUEO_MS = 5000

_MODO_URI = {"lectura": "ro", "escritura": "rw", "reemplazo": "rw", "nueva": "rwc"}


class ErrorBase(Exception):
    """La base no se puede usar: no existe, ya existe o tiene otra versión del esquema."""


def _leer_version_esquema() -> int:
    coincidencia = re.search(
        r"^PRAGMA user_version = (\d+);$", RUTA_ESQUEMA.read_text(encoding="utf-8"), re.MULTILINE
    )
    if coincidencia is None:
        raise ErrorBase(f"{RUTA_ESQUEMA.name} no declara la versión del esquema (PRAGMA user_version)")
    return int(coincidencia.group(1))


VERSION_ESQUEMA = _leer_version_esquema()


def conectar(ruta: Path = RUTA_BASE, modo: str = "lectura") -> sqlite3.Connection:
    """Abre la base en el modo indicado: "lectura", "escritura", "reemplazo" o "nueva"."""
    if modo not in _MODO_URI:
        raise ValueError(f"Modo de conexión desconocido: {modo!r}")
    ruta = Path(ruta)
    if modo == "nueva" and ruta.exists():
        raise ErrorBase(f"La base {ruta} ya existe")
    if modo != "nueva" and not ruta.exists():
        raise ErrorBase(f"No existe la base {ruta}: hay que construirla")

    uri = f"{ruta.resolve().as_uri()}?mode={_MODO_URI[modo]}"
    conexion = sqlite3.connect(uri, uri=True, isolation_level=None)
    try:
        conexion.execute(f"PRAGMA busy_timeout = {ESPERA_BLOQUEO_MS}")
        conexion.execute("PRAGMA foreign_keys = ON")
        if modo in ("lectura", "escritura"):
            _verificar_version(conexion, ruta)
        if modo == "lectura":
            # mode=ro protege el archivo; query_only cierra además la vía de un ATTACH.
            conexion.execute("PRAGMA query_only = ON")
        elif modo != "reemplazo":
            # En "reemplazo" el modo de journal lo trae la base que se copia encima.
            conexion.execute("PRAGMA journal_mode = WAL")
    except BaseException:
        conexion.close()
        raise
    return conexion


def _verificar_version(conexion: sqlite3.Connection, ruta: Path) -> None:
    (encontrada,) = conexion.execute("PRAGMA user_version").fetchone()
    if encontrada != VERSION_ESQUEMA:
        raise ErrorBase(
            f"La base {ruta} tiene la versión {encontrada} del esquema y el código espera la "
            f"{VERSION_ESQUEMA}: hay que reconstruirla desde los PDFs procesados (R19)"
        )
