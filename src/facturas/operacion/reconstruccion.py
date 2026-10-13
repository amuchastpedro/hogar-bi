"""Reconstrucción de la base desde cero (R19, diseño sección 13.4).

La base es descartable: se reconstruye con el esquema, las semillas versionadas, los datos
manuales y los PDFs de `datos/procesadas/`. Se hace cuando cambian las semillas (por ejemplo,
porque se aprobó un alias nuevo) o la versión del esquema, y a pedido con `reprocesar --todo`.

La base nueva se arma en un archivo temporal. Solo si todos los PDFs se cargan reemplaza a la
base en uso, **con la API de backup**: nunca se renombra ni se copia el archivo. En Windows,
con el dashboard abierto, `os.replace` falla, y copiar el archivo deja la base anterior sin
error, porque SQLite le aplica el WAL viejo. Este módulo solo lee `procesadas/`: no mueve,
renombra ni borra PDFs.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from facturas.bd.conexion import ErrorBase, conectar
from facturas.bd.construir import construir, huella_semillas, leer_ajustes
from facturas.bd.volcado import volcado_canonico
from facturas.carga.insercion import ErrorCarga, cargar_factura
from facturas.operacion.proceso import ErrorProceso, Rutas, extraer_pdf, sha256_de

registro = logging.getLogger("facturas.reconstruccion")

_ALIAS = """SELECT p.identificador_fiscal || '/' || c.identificador_externo, c.alias
            FROM contrato AS c JOIN proveedor AS p ON p.proveedor_id = c.proveedor_id"""


class ErrorReconstruccion(Exception):
    """La base no se pudo reconstruir; la base anterior sigue como estaba."""


@dataclass
class Reconstruccion:
    facturas: int = 0
    alias_cambiados: list[tuple[str, str]] = field(default_factory=list)  # (alias anterior, alias nuevo)


def preparar_base(rutas: Rutas) -> str | None:
    """Deja en `rutas.base` una base con el esquema y las semillas vigentes.

    Devuelve por qué hubo que construirla o reconstruirla, o None si ya estaba al día. Nunca se
    carga con un diccionario distinto del versionado (revisión H15). Si la base no existe, tiene
    otra versión del esquema o quedó a medio construir, también se reconstruye.
    """
    if not rutas.base.exists():
        motivo = "No había base: se construyó."
    else:
        try:
            conexion = conectar(rutas.base, "lectura")
        except ErrorBase:
            motivo = "La base tenía otra versión del esquema o estaba incompleta: se reconstruyó."
        else:
            try:
                fila = conexion.execute("SELECT huella_semillas FROM construccion").fetchone()
            finally:
                conexion.close()
            if fila is not None and fila[0] == huella_semillas(rutas.semillas):
                return None
            motivo = "Cambiaron las semillas: se reconstruyó la base."
    registro.info(motivo)
    reconstruir(rutas)
    return motivo


def reconstruir(rutas: Rutas) -> Reconstruccion:
    """Reconstruye la base desde los PDFs de `procesadas/`; si algo falla, deja la anterior intacta."""
    ajustes = leer_ajustes(rutas.ajustes)
    nombres, alias_anteriores = _leer_anterior(rutas.base)
    temporal = rutas.base.with_name(rutas.base.name + ".nueva")
    rutas.base.parent.mkdir(parents=True, exist_ok=True)
    _borrar(temporal)
    try:
        construir(temporal, rutas.semillas)
        facturas = _cargar_procesadas(rutas, temporal, ajustes, nombres)
        reemplazar_base(rutas.base, temporal)
    finally:
        _borrar(temporal)

    conexion = conectar(rutas.base, "lectura")
    try:
        alias_nuevos = dict(conexion.execute(_ALIAS).fetchall())
    finally:
        conexion.close()
    cambiados = [
        (alias_anteriores[clave], alias)
        for clave, alias in alias_nuevos.items()
        if clave in alias_anteriores and alias_anteriores[clave] != alias
    ]
    if cambiados:
        # Excepción conocida (D7): en una categoría con más de un contrato, el alias por defecto
        # depende del orden de carga. Los que se fijaron con `contrato` no cambian (R41).
        registro.warning("Cambiaron alias por defecto al reconstruir: %s", cambiados)
    return Reconstruccion(facturas=facturas, alias_cambiados=cambiados)


def _leer_anterior(base: Path):
    """Nombre original de cada PDF y alias de cada contrato de la base anterior, si se puede leer."""
    if not base.exists():
        return {}, {}
    try:
        conexion = sqlite3.connect(f"{base.resolve().as_uri()}?mode=ro", uri=True)
        try:
            nombres = dict(conexion.execute("SELECT sha256, nombre_archivo FROM carga WHERE estado = 'cargada'"))
            alias = dict(conexion.execute(_ALIAS))
        finally:
            conexion.close()
    except sqlite3.Error:
        return {}, {}
    return nombres, alias


def _cargar_procesadas(rutas: Rutas, temporal: Path, ajustes, nombres) -> int:
    fallos, extraidas = [], []
    for ruta in sorted(rutas.procesadas.rglob("*.pdf")):
        try:
            extraidas.append((extraer_pdf(ruta), ruta, sha256_de(ruta)))
        except ErrorProceso as error:
            fallos.append(f"{ruta.name}: etapa {error.etapa}: {error.motivo}")
    extraidas.sort(key=lambda e: (e[0].fecha_emision, str(e[1])))

    conexion = conectar(temporal, "escritura")
    try:
        # Los rechazos por solape se reintentan hasta que una vuelta no cargue ninguno (H17).
        con_solape = []
        for factura, ruta, sha in extraidas:
            try:
                cargar_factura(conexion, factura, sha256=sha, nombre_archivo=nombres.get(sha, ruta.name), ajustes=ajustes)
            except ErrorCarga as error:
                if error.etapa == "insercion" and error.motivo.startswith("solape"):
                    con_solape.append([factura, ruta, sha, error])
                else:
                    fallos.append(f"{ruta.name}: etapa {error.etapa}: {error.motivo}")
        progreso = True
        while con_solape and progreso:
            progreso = False
            for item in list(con_solape):
                factura, ruta, sha, _ = item
                try:
                    cargar_factura(conexion, factura, sha256=sha, nombre_archivo=nombres.get(sha, ruta.name), ajustes=ajustes)
                except ErrorCarga as error:
                    item[3] = error
                else:
                    con_solape.remove(item)
                    progreso = True
        fallos += [f"{ruta.name}: etapa {error.etapa}: {error.motivo}" for _, ruta, _, error in con_solape]
    finally:
        conexion.close()
    if fallos:
        raise ErrorReconstruccion(
            "No se reconstruyó la base: la anterior sigue como estaba. No se pudieron cargar:\n  " + "\n  ".join(fallos)
        )
    return len(extraidas)


def reemplazar_base(base: Path, temporal: Path) -> None:
    """La base en uso pasa a tener el contenido de `temporal`, con la API de backup.

    Lo usan la reconstrucción y `restaurar` (que reemplaza con una instantánea). `temporal` tiene
    que tener la versión actual del esquema; la verificación final compara los volcados canónicos.
    """
    if not base.exists():
        os.replace(temporal, base)
        return
    origen = sqlite3.connect(temporal)
    destino = conectar(base, "reemplazo")
    try:
        origen.backup(destino)
    finally:
        origen.close()
        destino.close()
    verificacion, esperada = conectar(base, "lectura"), conectar(temporal, "lectura")
    try:
        if verificacion.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ErrorReconstruccion("La base reemplazada no pasa PRAGMA integrity_check")
        if volcado_canonico(verificacion) != volcado_canonico(esperada):
            raise ErrorReconstruccion("El volcado de la base reemplazada no coincide con el del origen")
    finally:
        verificacion.close()
        esperada.close()


def _borrar(base: Path) -> None:
    for sufijo in ("", "-wal", "-shm"):
        Path(f"{base}{sufijo}").unlink(missing_ok=True)
