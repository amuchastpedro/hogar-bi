"""Copias de seguridad y restauración (R43, diseño sección 14.2).

La carpeta de respaldo (fuera del proyecto: una carpeta de Google Drive para escritorio) está en
`datos/config.toml`, en la clave `carpeta_respaldo`. Tiene que existir: nunca se crea.

    <carpeta de respaldo>/
        instantaneas/facturas_<marca>.db     base consistente, hecha con VACUUM INTO
        instantaneas/ajustes_<marca>.json    los datos manuales de la misma marca de tiempo
        procesadas/…                         los PDFs de `procesadas/`, con la misma estructura

Ni el respaldo ni la restauración copian nunca el archivo de la base en uso. La instantánea se
arma y se verifica en una carpeta temporal local y de ahí se copia a la carpeta de respaldo con
un nombre provisional, que cambia al definitivo cuando el hash de la copia coincide con el
original: Drive nunca ve un archivo a medias con el nombre de una instantánea.
`restaurar` escribe la instantánea sobre la base en uso con la API de backup de SQLite, que es
lo que hace la reconstrucción (`reemplazar_base`).
"""

import hashlib
import logging
import re
import shutil
import sqlite3
import tempfile
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from facturas.bd.conexion import conectar
from facturas.operacion.proceso import Rutas, sha256_de
from facturas.operacion.reconstruccion import reemplazar_base

registro = logging.getLogger("facturas.respaldo")

CONSERVAR = 30
_FORMATO_MARCA = "%Y%m%d_%H%M%S"
_NOMBRE_INSTANTANEA = re.compile(r"^facturas_(\d{8}_\d{6})\.db$")


class ErrorRespaldo(Exception):
    """El respaldo o la restauración no se pudo hacer; la base en uso no cambió (salvo que se diga lo contrario)."""


class SinConfiguracion(ErrorRespaldo):
    """No hay carpeta de respaldo configurada."""


@dataclass
class Respaldo:
    instantanea: Path
    pdfs_copiados: int = 0
    eliminadas: list[str] = field(default_factory=list)


@dataclass
class Restauracion:
    instantanea: Path
    pdfs_copiados: int = 0
    pdfs_posteriores: int = 0  # PDFs de procesadas/ que la instantánea no tiene


def carpeta_de_respaldo(rutas: Rutas) -> Path:
    """La carpeta de `datos/config.toml`; tiene que existir."""
    if not rutas.config.exists():
        raise SinConfiguracion(
            f"no hay carpeta de respaldo: creá {rutas.config.relative_to(rutas.raiz)} con una línea "
            "carpeta_respaldo = 'ruta de la carpeta'"
        )
    try:
        config = tomllib.loads(rutas.config.read_text(encoding="utf-8-sig"))  # acepta el BOM de PowerShell 5.1
    except tomllib.TOMLDecodeError as error:
        raise ErrorRespaldo(f"{rutas.config.name} no es un TOML válido: {error}") from error
    ruta = config.get("carpeta_respaldo")
    if not isinstance(ruta, str) or not ruta.strip():
        raise ErrorRespaldo(f"{rutas.config.name}: falta carpeta_respaldo, o no es un texto")
    carpeta = Path(ruta)
    if not carpeta.is_dir():
        raise ErrorRespaldo(f"la carpeta de respaldo no existe: {carpeta} (¿Google Drive está sincronizado?)")
    return carpeta


def respaldar(rutas: Rutas, *, conservar: int = CONSERVAR, ahora: datetime | None = None) -> Respaldo:
    """Escribe una instantánea de la base, los ajustes y los PDFs que falten; rota las instantáneas viejas.

    No toma el bloqueo: lo toma quien lo llama (`cargar`, o el comando `respaldar`).
    """
    carpeta = carpeta_de_respaldo(rutas)
    instantaneas = carpeta / "instantaneas"
    instantaneas.mkdir(exist_ok=True)
    marca = _marca_libre(instantaneas, ahora or datetime.now())

    with tempfile.TemporaryDirectory(dir=rutas.datos, prefix="respaldo_") as temporal:
        local = Path(temporal) / f"facturas_{marca}.db"
        _instantanea_local(rutas.base, local)
        ajustes = Path(temporal) / f"ajustes_{marca}.json"
        if rutas.ajustes.exists():
            shutil.copyfile(rutas.ajustes, ajustes)
        else:
            ajustes.write_text("[]\n", encoding="utf-8")
        _copiar_verificando(ajustes, instantaneas / ajustes.name)
        destino = _copiar_verificando(local, instantaneas / local.name)

    resultado = Respaldo(instantanea=destino)
    resultado.pdfs_copiados = _copiar_pdfs(rutas.procesadas, carpeta / "procesadas")
    resultado.eliminadas = _rotar(instantaneas, conservar)
    registro.info("Respaldo %s: %d PDFs nuevos, %d instantáneas eliminadas", destino.name, resultado.pdfs_copiados,
                  len(resultado.eliminadas))
    return resultado


def restaurar(rutas: Rutas, instantanea: str) -> Restauracion:
    """Deja la base y los datos manuales como estaban en la instantánea, y repone los PDFs que falten.

    `instantanea` es la ruta de un `facturas_<marca>.db` o solo su marca (`AAAAMMDD_HHMMSS`), que se
    busca en la carpeta de respaldo. No toma el bloqueo: lo toma quien lo llama.
    """
    origen = _resolver(rutas, instantanea)
    marca = _NOMBRE_INSTANTANEA.match(origen.name).group(1)
    ajustes = origen.with_name(f"ajustes_{marca}.json")
    if not ajustes.is_file():
        raise ErrorRespaldo(f"falta {ajustes.name} junto a la instantánea: no se puede restaurar sin los datos manuales")

    rutas.datos.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=rutas.datos, prefix="restauracion_") as temporal:
        local = Path(temporal) / origen.name
        shutil.copyfile(origen, local)
        _comprobar_instantanea(local)
        reemplazar_base(rutas.base, local)  # si no hay base (equipo nuevo), la copia verificada pasa a ser la base

    shutil.copyfile(ajustes, rutas.ajustes)
    resultado = Restauracion(instantanea=origen)
    carpeta_pdfs = origen.parent.parent / "procesadas"
    resultado.pdfs_copiados = _copiar_pdfs(carpeta_pdfs, rutas.procesadas)
    resultado.pdfs_posteriores = _pdfs_que_la_base_no_tiene(rutas)
    registro.info("Restaurada %s: %d PDFs repuestos, %d PDFs posteriores", origen.name, resultado.pdfs_copiados,
                  resultado.pdfs_posteriores)
    return resultado


def _marca_libre(instantaneas: Path, ahora: datetime) -> str:
    marca = ahora.strftime(_FORMATO_MARCA)
    while (instantaneas / f"facturas_{marca}.db").exists():
        ahora += timedelta(seconds=1)
        marca = ahora.strftime(_FORMATO_MARCA)
    return marca


def _instantanea_local(base: Path, destino: Path) -> None:
    """VACUUM INTO desde una conexión de solo archivo (`mode=ro`): es consistente con lectores y escritores."""
    conexion = conectar(base, "lectura")
    try:
        # `query_only` también impide VACUUM INTO; el archivo sigue protegido por `mode=ro`.
        conexion.execute("PRAGMA query_only = OFF")
        conexion.execute("VACUUM INTO ?", (str(destino),))
    finally:
        conexion.close()
    verificacion = sqlite3.connect(destino)
    try:
        if verificacion.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ErrorRespaldo("la instantánea no pasa PRAGMA integrity_check: no se copió")
    finally:
        verificacion.close()


def _comprobar_instantanea(local: Path) -> None:
    try:
        conexion = conectar(local, "lectura")  # también verifica la versión del esquema
    except Exception as error:
        raise ErrorRespaldo(
            f"la instantánea no se puede usar: {error}. Si es de una versión anterior del esquema, "
            "restaurá los PDFs y los datos manuales a mano y ejecutá `reprocesar --todo`"
        ) from error
    try:
        if conexion.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ErrorRespaldo("la instantánea no pasa PRAGMA integrity_check")
    except sqlite3.DatabaseError as error:
        raise ErrorRespaldo(f"la instantánea está dañada: {error}") from error
    finally:
        conexion.close()


def _copiar_verificando(origen: Path, destino: Path) -> Path:
    """Copia con nombre provisional y lo cambia al definitivo si el hash coincide."""
    provisional = destino.with_name(destino.name + ".parcial")
    shutil.copyfile(origen, provisional)
    if sha256_de(provisional) != sha256_de(origen):
        provisional.unlink(missing_ok=True)
        raise ErrorRespaldo(f"la copia de {origen.name} no coincide con el original")
    provisional.replace(destino)
    return destino


def _copiar_pdfs(origen: Path, destino: Path) -> int:
    """Copia los PDFs de `origen` que no están en `destino` (misma ruta relativa). Devuelve cuántos."""
    copiados = 0
    for pdf in sorted(origen.rglob("*.pdf")) if origen.is_dir() else []:
        copia = destino / pdf.relative_to(origen)
        if copia.exists():
            continue
        copia.parent.mkdir(parents=True, exist_ok=True)
        _copiar_verificando(pdf, copia)
        copiados += 1
    return copiados


def _rotar(instantaneas: Path, conservar: int) -> list[str]:
    """Deja las últimas `conservar` instantáneas, cada una con sus ajustes. Devuelve las marcas eliminadas."""
    marcas = sorted(m.group(1) for p in instantaneas.iterdir() if (m := _NOMBRE_INSTANTANEA.match(p.name)))
    eliminadas = marcas[: max(len(marcas) - conservar, 0)]
    for marca in eliminadas:
        (instantaneas / f"facturas_{marca}.db").unlink()
        (instantaneas / f"ajustes_{marca}.json").unlink(missing_ok=True)
    return eliminadas


def _resolver(rutas: Rutas, instantanea: str) -> Path:
    candidata = Path(instantanea)
    if not candidata.is_file() and re.fullmatch(r"\d{8}_\d{6}", instantanea):
        candidata = carpeta_de_respaldo(rutas) / "instantaneas" / f"facturas_{instantanea}.db"
    if not candidata.is_file():
        raise ErrorRespaldo(f"no existe la instantánea '{instantanea}': usá la ruta de un facturas_<marca>.db o su marca")
    if not _NOMBRE_INSTANTANEA.match(candidata.name):
        raise ErrorRespaldo(f"'{candidata.name}' no tiene el nombre de una instantánea (facturas_AAAAMMDD_HHMMSS.db)")
    return candidata


def _pdfs_que_la_base_no_tiene(rutas: Rutas) -> int:
    conexion = conectar(rutas.base, "lectura")
    try:
        cargadas = {sha for (sha,) in conexion.execute("SELECT sha256 FROM carga WHERE estado = 'cargada'")}
    finally:
        conexion.close()
    return sum(1 for pdf in rutas.procesadas.rglob("*.pdf") if sha256_de(pdf) not in cargadas)
