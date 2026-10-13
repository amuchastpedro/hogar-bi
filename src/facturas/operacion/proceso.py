"""Procesamiento de los PDFs: entrada → hash → parser → carga → procesadas, pendientes o duplicados.

Es uno de los pocos módulos que conecta PDFs con la base (diseño, secciones 13.1 a 13.3).
Un lote se procesa en tres fases:

1. cada PDF estable se identifica por su hash y se extrae; lo que falla acá va a pendientes;
2. las facturas extraídas se cargan por fecha de emisión y, a igual fecha, por ruta, cada una
   en su transacción (así una factura original suele cargarse antes que su rectificativa);
3. si el lote cargó algo, se reintentan los PDFs de pendientes rechazados por solape, porque
   el abono o la sustitución que los resuelve puede haber llegado en este lote.

Nunca se borra un archivo de la persona usuaria: los PDFs solo se mueven.
"""

import hashlib
import logging
import re
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from facturas.bd.conexion import RAIZ
from facturas.bd.construir import DIR_SEMILLAS
from facturas.carga.insercion import ErrorCarga, cargar_factura, estado_de_carga, registrar_rechazo
from facturas.extraccion import ErrorExtraccion, FacturaExtraida
from facturas.parsers import reconocer
from facturas.parsers.pdf import leer

ESPERA_ESTABLE = 3.0
LIMITE_ESPERA = 120.0

registro = logging.getLogger("facturas.proceso")


@dataclass(frozen=True)
class Rutas:
    """Dónde está cada cosa del proyecto, a partir de su raíz (siempre relativas a ella)."""

    raiz: Path = RAIZ
    semillas: Path = DIR_SEMILLAS

    @property
    def datos(self) -> Path:
        return self.raiz / "datos"

    @property
    def entrada(self) -> Path:
        return self.datos / "entrada"

    @property
    def procesadas(self) -> Path:
        return self.datos / "procesadas"

    @property
    def pendientes(self) -> Path:
        return self.datos / "pendientes"

    @property
    def duplicados(self) -> Path:
        return self.datos / "duplicados"

    @property
    def logs(self) -> Path:
        return self.datos / "logs"

    @property
    def base(self) -> Path:
        return self.datos / "facturas.db"

    @property
    def ajustes(self) -> Path:
        return self.datos / "ajustes_manuales.json"

    @property
    def config(self) -> Path:
        return self.datos / "config.toml"

    @property
    def bloqueo(self) -> Path:
        return self.datos / "ejecucion.lock"


@dataclass
class Resumen:
    """Lo que pasó con los PDFs de una ejecución."""

    cargadas: list[str] = field(default_factory=list)
    duplicadas: list[str] = field(default_factory=list)
    rechazadas: dict[str, tuple[str, str, str]] = field(default_factory=dict)  # hash → (archivo, etapa, motivo)
    omitidas: list[str] = field(default_factory=list)


class ErrorProceso(Exception):
    """El PDF no se pudo convertir en una factura extraída: etapa `formato` o `extraccion`."""

    def __init__(self, etapa: str, motivo: str, formato: str | None = None, version_parser: str | None = None):
        super().__init__(motivo)
        self.etapa = etapa
        self.motivo = motivo
        self.formato = formato
        self.version_parser = version_parser


def listar_pdfs(carpeta: Path) -> list[Path]:
    """Los PDFs de una carpeta (sin subcarpetas), en orden de nombre."""
    if not carpeta.is_dir():
        return []
    return sorted(p for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def sha256_de(ruta: Path) -> str:
    huella = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            huella.update(bloque)
    return huella.hexdigest()


def extraer_pdf(ruta: Path) -> FacturaExtraida:
    """PDF → factura extraída. Si no se puede, `ErrorProceso` con la etapa del rechazo."""
    try:
        documento = leer(ruta)
        parser = reconocer(documento)
    except ErrorExtraccion as error:
        raise ErrorProceso("formato", str(error)) from error
    except Exception as error:
        registro.exception("Error inesperado al leer %s", ruta.name)
        raise ErrorProceso("formato", f"error inesperado al leer el PDF: {type(error).__name__}: {error}") from error
    try:
        return parser.extraer(documento)
    except ErrorExtraccion as error:
        raise ErrorProceso("extraccion", str(error), parser.FORMATO, parser.VERSION) from error
    except Exception as error:
        registro.exception("Error inesperado al extraer %s con %s", ruta.name, parser.FORMATO)
        raise ErrorProceso(
            "extraccion", f"error inesperado en el parser: {type(error).__name__}: {error}", parser.FORMATO, parser.VERSION
        ) from error


def _firma(ruta: Path):
    try:
        estado = ruta.stat()
    except OSError:
        return None
    return estado.st_size, estado.st_mtime_ns


def _se_puede_abrir(ruta: Path) -> bool:
    try:
        with ruta.open("rb") as archivo:
            archivo.read(1)
    except OSError:
        return False
    return True


def esperar_estables(pdfs, segundos: float = ESPERA_ESTABLE, limite: float = LIMITE_ESPERA, dormir=time.sleep):
    """Separa los PDFs cuyo tamaño no cambió durante `segundos` y se pueden abrir, de los que no (1 del diseño 13.2).

    Un archivo que se está copiando cambia de tamaño o está bloqueado. Los que no se estabilizan
    dentro de `limite` segundos se devuelven aparte y se procesan en una ejecución posterior.
    """
    antes = {ruta: _firma(ruta) for ruta in pdfs}
    esperando = [ruta for ruta in pdfs if antes[ruta] is not None]
    estables = []
    transcurrido = 0.0
    while esperando:
        dormir(segundos)
        transcurrido += max(segundos, 0.001)
        todavia = []
        for ruta in esperando:
            ahora = _firma(ruta)
            if ahora is None:
                continue
            if ahora == antes[ruta] and _se_puede_abrir(ruta):
                estables.append(ruta)
            else:
                antes[ruta] = ahora
                todavia.append(ruta)
        esperando = todavia
        if esperando and transcurrido >= limite:
            break
    return sorted(estables), sorted(esperando)


def _motivo_de(ruta_pdf: Path) -> Path:
    return ruta_pdf.with_suffix(".motivo.txt")


def _mover(origen: Path, carpeta: Path, nombre: str | None = None) -> Path:
    """Mueve el archivo a `carpeta` sin pisar nada: si el nombre existe, agrega _2, _3…"""
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = nombre or origen.name
    destino = carpeta / nombre
    if destino != origen:
        base, sufijo, numero = destino.stem, destino.suffix, 2
        while destino.exists():
            destino = carpeta / f"{base}_{numero}{sufijo}"
            numero += 1
        shutil.move(str(origen), str(destino))
    # Un motivo de un rechazo anterior ya no vale en el nuevo destino.
    if _motivo_de(origen).exists() and origen != destino:
        _motivo_de(origen).unlink()
    return destino


def _escribir_motivo(pdf: Path, etapa: str, motivo: str) -> None:
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _motivo_de(pdf).write_text(
        f"Etapa: {etapa}\nMotivo: {' '.join(motivo.split())}\nFecha: {ahora}\n", encoding="utf-8"
    )


def _a_duplicados(rutas: Rutas, ruta: Path, motivo: str, resumen: Resumen) -> None:
    destino = _mover(ruta, rutas.duplicados)
    _escribir_motivo(destino, "duplicado", motivo)
    resumen.duplicadas.append(destino.name)
    registro.info("Duplicado %s: %s", destino.name, motivo)


def _rechazar(rutas, conexion, ruta, sha, etapa, motivo, resumen, *, formato=None, version_parser=None,
              factura=None, reintento=False) -> None:
    registrar_rechazo(
        conexion, sha256=sha, nombre_archivo=ruta.name, etapa=etapa, motivo=motivo,
        formato=formato, version_parser=version_parser, factura=factura,
    )
    if etapa == "duplicado":
        _a_duplicados(rutas, ruta, motivo, resumen)
        return
    destino = _mover(ruta, rutas.pendientes)
    _escribir_motivo(destino, etapa, motivo)
    if not reintento or sha in resumen.rechazadas:
        resumen.rechazadas[sha] = (destino.name, etapa, motivo)
    registro.warning("Rechazado %s en la etapa %s: %s", destino.name, etapa, motivo)


def _nombre_procesada(factura: FacturaExtraida) -> str:
    nombre = f"{factura.periodo.inicio}_{factura.periodo.fin}_{factura.formato}_{factura.numero}.pdf"
    return re.sub(r"[^\w.\-]", "_", nombre)


def carpeta_procesada(rutas: Rutas, factura: FacturaExtraida) -> Path:
    """`procesadas/<categorías>/<año de emisión>/`, con los códigos de categoría ordenados y unidos con `_`."""
    categorias = "_".join(sorted({c.categoria for c in factura.contratos}))
    return rutas.procesadas / categorias / factura.fecha_emision[:4]


def _cargar_archivo(rutas, conexion, ruta, sha, factura, ajustes, resumen, *, reintento=False) -> bool:
    """Carga la factura y mueve el PDF según el resultado. Devuelve si se cargó."""
    try:
        cargar_factura(conexion, factura, sha256=sha, nombre_archivo=ruta.name, ajustes=ajustes)
    except ErrorCarga as error:
        _rechazar(rutas, conexion, ruta, sha, error.etapa, error.motivo, resumen,
                  formato=factura.formato, version_parser=factura.version_parser, factura=factura,
                  reintento=reintento)
        return False
    destino = _mover(ruta, carpeta_procesada(rutas, factura), _nombre_procesada(factura))
    resumen.rechazadas.pop(sha, None)
    resumen.cargadas.append(destino.name)
    registro.info("Cargada %s (factura %s)", destino.name, factura.numero)
    return True


def procesar_lote(rutas: Rutas, conexion: sqlite3.Connection, pdfs, ajustes, *, espera: float = ESPERA_ESTABLE,
                  dormir=time.sleep) -> Resumen:
    """Procesa los PDFs indicados (de entrada o de pendientes) y devuelve qué pasó con cada uno."""
    resumen = Resumen()
    estables, inestables = esperar_estables(list(pdfs), espera, dormir=dormir)
    for ruta in inestables:
        resumen.omitidas.append(ruta.name)
        registro.warning("%s sigue cambiando o bloqueado: se procesará en otra ejecución", ruta.name)

    candidatos, vistos = [], set()
    for ruta in estables:
        try:
            sha = sha256_de(ruta)
        except OSError as error:
            resumen.omitidas.append(ruta.name)
            registro.warning("No se pudo leer %s: %s", ruta.name, error)
            continue
        if sha in vistos or estado_de_carga(conexion, sha) == "cargada":
            _a_duplicados(rutas, ruta, "el mismo PDF ya está cargado (mismo hash)", resumen)
            continue
        vistos.add(sha)
        try:
            factura = extraer_pdf(ruta)
        except ErrorProceso as error:
            _rechazar(rutas, conexion, ruta, sha, error.etapa, error.motivo, resumen,
                      formato=error.formato, version_parser=error.version_parser)
            continue
        candidatos.append((ruta, sha, factura))

    candidatos.sort(key=lambda c: (c[2].fecha_emision, str(c[0])))
    for ruta, sha, factura in candidatos:
        _cargar_archivo(rutas, conexion, ruta, sha, factura, ajustes, resumen)

    if resumen.cargadas:
        reintentar_solapes(rutas, conexion, ajustes, resumen)
    return resumen


def reintentar_solapes(rutas: Rutas, conexion: sqlite3.Connection, ajustes, resumen: Resumen) -> None:
    """Reintenta los PDFs de pendientes rechazados por solape, hasta que una vuelta no cargue ninguno.

    Un solape puede deberse a que el abono o la sustitución que lo resuelve llegó después (H17).
    Con sustituciones encadenadas, cada factura cargada puede destrabar a otra: por eso se repite.
    """
    progreso = True
    while progreso:
        progreso = False
        for ruta in listar_pdfs(rutas.pendientes):
            sha = sha256_de(ruta)
            fila = conexion.execute(
                """SELECT extraccion_json FROM carga
                   WHERE sha256 = ? AND estado = 'rechazada' AND etapa_rechazo = 'insercion'
                     AND motivo_rechazo LIKE 'solape%'""",
                (sha,),
            ).fetchone()
            if fila is None:
                continue
            try:
                factura = FacturaExtraida.desde_json(fila[0])
            except ErrorExtraccion:
                continue
            if _cargar_archivo(rutas, conexion, ruta, sha, factura, ajustes, resumen, reintento=True):
                progreso = True
