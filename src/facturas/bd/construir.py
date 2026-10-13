"""Construcción de la base desde cero (R19, R24, R29, R41).

`construir()` crea una base nueva con el esquema, las semillas, el calendario y la
huella de las semillas. Es determinista: con las mismas semillas, dos
construcciones dan el mismo contenido.

Los datos manuales (R41) son atributos de contratos, y una base recién construida
todavía no tiene ninguno. Por eso se aplican aparte, con `aplicar_ajustes()`, a
los contratos que ya existen. La carga la llama al registrar contratos nuevos,
también al reconstruir la base (bloque 4).
"""

import csv
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from facturas.bd.conexion import RAIZ, RUTA_ESQUEMA, conectar

DIR_SEMILLAS = Path(__file__).resolve().parents[1] / "semillas"
RUTA_AJUSTES = RAIZ / "datos" / "ajustes_manuales.json"
CALENDARIO_DESDE = "2000-01-01"
CALENDARIO_HASTA = "2099-12-31"

# Cada archivo de semillas, en el orden de carga (diseño, sección 12.5), con la
# sentencia que inserta una fila. Las referencias van por código: si un código no
# existe, la subconsulta da NULL y la base rechaza la fila (NOT NULL).
SEMILLAS = (
    ("moneda.csv", "INSERT INTO moneda (codigo) VALUES (:codigo)"),
    ("categoria.csv", "INSERT INTO categoria (codigo, nombre) VALUES (:codigo, :nombre)"),
    (
        "concepto.csv",
        """INSERT INTO concepto (categoria_id, codigo, nombre, imputacion_defecto)
           VALUES ((SELECT categoria_id FROM categoria WHERE codigo = :categoria),
                   :codigo, :nombre, :imputacion_defecto)""",
    ),
    (
        "alias_concepto.csv",
        """INSERT INTO alias_concepto (categoria_id, concepto_id, patron_seccion, patron_texto)
           VALUES ((SELECT categoria_id FROM categoria WHERE codigo = :categoria),
                   (SELECT co.concepto_id FROM concepto AS co
                    JOIN categoria AS ca ON ca.categoria_id = co.categoria_id
                    WHERE ca.codigo = :categoria AND co.codigo = :concepto),
                   :patron_seccion, :patron_texto)""",
    ),
    ("unidad.csv", "INSERT INTO unidad (codigo, simbolo) VALUES (:codigo, :simbolo)"),
    ("magnitud.csv", "INSERT INTO magnitud (codigo, nombre) VALUES (:codigo, :nombre)"),
    (
        "magnitud_categoria.csv",
        """INSERT INTO magnitud_categoria (categoria_id, magnitud_id, unidad_canonica_id, unidad_contador_id)
           VALUES ((SELECT categoria_id FROM categoria WHERE codigo = :categoria),
                   (SELECT magnitud_id FROM magnitud WHERE codigo = :magnitud),
                   (SELECT unidad_id FROM unidad WHERE codigo = :unidad_canonica),
                   (SELECT unidad_id FROM unidad WHERE codigo = :unidad_contador))""",
    ),
    ("franja.csv", "INSERT INTO franja (codigo, nombre) VALUES (:codigo, :nombre)"),
    (
        "atributo_contrato.csv",
        """INSERT INTO atributo_contrato (categoria_id, unidad_id, codigo, nombre)
           VALUES ((SELECT categoria_id FROM categoria WHERE codigo = :categoria),
                   (SELECT unidad_id FROM unidad WHERE codigo = :unidad),
                   :codigo, :nombre)""",
    ),
    (
        "proveedor.csv",
        "INSERT INTO proveedor (identificador_fiscal, nombre) VALUES (:identificador_fiscal, :nombre)",
    ),
)

_CAMPOS_AJUSTE = ("alias",)
_CLAVE_AJUSTE = ("identificador_fiscal", "identificador_externo")


class ErrorSemillas(Exception):
    """Un archivo de semillas no tiene el formato esperado o la base rechaza una fila."""


def huella_semillas(directorio: Path = DIR_SEMILLAS) -> str:
    """SHA-256 de los archivos de semillas, en orden de nombre.

    Incluye el nombre y el tamaño de cada archivo, para que mover una fila de un
    archivo a otro cambie la huella. Los saltos de línea se normalizan a LF: git
    (`core.autocrlf`) puede escribir los mismos archivos con CRLF.
    """
    huella = hashlib.sha256()
    for nombre in sorted(nombre for nombre, _ in SEMILLAS):
        contenido = (directorio / nombre).read_bytes().replace(b"\r\n", b"\n")
        huella.update(f"{nombre}\0{len(contenido)}\0".encode() + contenido)
    return huella.hexdigest()


def construir(ruta: Path, directorio: Path = DIR_SEMILLAS) -> None:
    """Crea la base en `ruta`, que no puede existir. Si algo falla, no deja el archivo.

    Todo va en una sola transacción, incluida la versión del esquema
    (`PRAGMA user_version`, que también se revierte). Si el proceso se interrumpe y
    el archivo queda, queda vacío y con la versión 0, y `conectar()` lo rechaza.
    """
    ruta = Path(ruta)
    sobrantes = {p.name for p in directorio.glob("*.csv")} - {nombre for nombre, _ in SEMILLAS}
    if sobrantes:
        raise ErrorSemillas(f"Archivos de semillas desconocidos: {', '.join(sorted(sobrantes))}")

    conexion = conectar(ruta, "nueva")
    try:
        # El BEGIN va dentro del script: executescript confirma antes lo que esté pendiente.
        conexion.executescript("BEGIN IMMEDIATE;\n" + RUTA_ESQUEMA.read_text(encoding="utf-8"))
        for nombre, sentencia in SEMILLAS:
            _cargar_semilla(conexion, directorio / nombre, sentencia)
        _cargar_calendario(conexion)
        conexion.execute(
            "INSERT INTO construccion (construccion_id, huella_semillas) VALUES (1, ?)",
            (huella_semillas(directorio),),
        )
        conexion.execute("COMMIT")
    except BaseException:
        conexion.close()
        _borrar_base(ruta)
        raise
    conexion.close()


def _borrar_base(ruta: Path) -> None:
    for sufijo in ("", "-wal", "-shm"):
        Path(f"{ruta}{sufijo}").unlink(missing_ok=True)


def _cargar_semilla(conexion: sqlite3.Connection, archivo: Path, sentencia: str) -> None:
    columnas = set(re.findall(r":(\w+)", sentencia))
    with archivo.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        if set(lector.fieldnames or ()) != columnas:
            raise ErrorSemillas(
                f"{archivo.name}: columnas {lector.fieldnames}; se esperaban {sorted(columnas)}"
            )
        for fila in lector:
            try:
                conexion.execute(sentencia, fila)
            except sqlite3.Error as error:
                raise ErrorSemillas(
                    f"{archivo.name}, línea {lector.line_num}: {error} (¿código inexistente?)"
                ) from error


def _cargar_calendario(conexion: sqlite3.Connection) -> None:
    conexion.execute(
        """INSERT INTO calendario (calendario_id, fecha, anio, mes, dia, anio_mes, dias_mes)
           WITH RECURSIVE dia (fecha) AS (
               SELECT :desde
               UNION ALL
               SELECT date(fecha, '+1 day') FROM dia WHERE fecha < :hasta)
           SELECT CAST(strftime('%Y%m%d', fecha) AS INTEGER), fecha,
                  CAST(strftime('%Y', fecha) AS INTEGER), CAST(strftime('%m', fecha) AS INTEGER),
                  CAST(strftime('%d', fecha) AS INTEGER), strftime('%Y-%m', fecha),
                  CAST(strftime('%d', fecha, 'start of month', '+1 month', '-1 day') AS INTEGER)
           FROM dia""",
        {"desde": CALENDARIO_DESDE, "hasta": CALENDARIO_HASTA},
    )


def leer_ajustes(ruta: Path = RUTA_AJUSTES) -> list[dict]:
    """Lee los datos manuales (R41). Si el archivo no existe, no hay ajustes.

    El archivo es una lista de objetos. Cada uno identifica un contrato por
    `identificador_fiscal` (del proveedor) e `identificador_externo`, y puede
    traer `alias`. Solo se cambian los campos presentes.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return []
    ajustes = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(ajustes, list):
        raise ValueError(f"{ruta.name}: se esperaba una lista de contratos")
    for numero, ajuste in enumerate(ajustes, start=1):
        if not isinstance(ajuste, dict):
            raise ValueError(f"{ruta.name}, entrada {numero}: se esperaba un objeto")
        faltan = set(_CLAVE_AJUSTE) - ajuste.keys()
        sobran = ajuste.keys() - set(_CLAVE_AJUSTE) - set(_CAMPOS_AJUSTE)
        if faltan or sobran:
            raise ValueError(
                f"{ruta.name}, entrada {numero}: faltan {sorted(faltan)}, sobran {sorted(sobran)}"
            )
    return ajustes


def aplicar_ajustes(conexion: sqlite3.Connection, ajustes: list[dict]) -> None:
    """Aplica los datos manuales a los contratos que existen en la base.

    Un ajuste de un contrato que todavía no está en la base no hace nada: se
    aplicará cuando la carga lo registre. La regla (alias
    único) la hace cumplir la base.
    """
    for ajuste in ajustes:
        campos = [campo for campo in _CAMPOS_AJUSTE if campo in ajuste]
        if not campos:
            continue
        asignaciones = ", ".join(f"{campo} = :{campo}" for campo in campos)
        conexion.execute(
            f"""UPDATE contrato SET {asignaciones}
                WHERE proveedor_id = (SELECT proveedor_id FROM proveedor
                                      WHERE identificador_fiscal = :identificador_fiscal)
                  AND identificador_externo = :identificador_externo""",
            ajuste,
        )
