"""Línea de comandos: `python -m facturas <comando>` (diseño, sección 14).

Códigos de salida (los bloques 5 y 6 dependen de ellos):

- 0: todo cargado, o nada que hacer;
- 1: hay PDFs nuevos rechazados, en `datos/pendientes/`;
- 2: error del sistema (la base no abre, no se pudo reconstruir, un archivo no se puede mover…).
"""

import argparse
import logging
import sqlite3
import sys

from facturas.bd import diccionario
from facturas.bd.conexion import ErrorBase, conectar
from facturas.bd.construir import leer_ajustes
from facturas.operacion import ajustes as datos_manuales
from facturas.operacion import registro
from facturas.operacion.bloqueo import BloqueoOcupado, bloqueo
from facturas.operacion.estado import generar_estado
from facturas.operacion.proceso import ESPERA_ESTABLE, Resumen, Rutas, listar_pdfs, procesar_lote
from facturas.operacion.reconstruccion import ErrorReconstruccion, preparar_base, reconstruir
from facturas.operacion.respaldo import ErrorRespaldo, Respaldo, SinConfiguracion, respaldar, restaurar

log = logging.getLogger("facturas.main")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m facturas", description="Facturas en PDF → base SQLite para BI.")
    comandos = parser.add_subparsers(dest="comando", required=True)
    comandos.add_parser("cargar", help="procesa los PDFs de datos/entrada/")
    reprocesar = comandos.add_parser("reprocesar", help="vuelve a procesar PDFs ya vistos")
    grupo = reprocesar.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--pendientes", action="store_true", help="reintenta los PDFs de datos/pendientes/")
    grupo.add_argument("--todo", action="store_true", help="reconstruye la base desde los PDFs de datos/procesadas/")
    comandos.add_parser("estado", help="resumen de la base y de los PDFs pendientes")
    comandos.add_parser("diccionario", help="regenera docs/diccionario.md")
    comandos.add_parser("contratos", help="lista los contratos con su alias, categoría y proveedor")
    contrato = comandos.add_parser("contrato", help="modifica los datos manuales de un contrato")
    contrato.add_argument("alias", help="el alias actual del contrato (`contratos` los lista)")
    contrato.add_argument("--alias", dest="alias_nuevo", help="alias nuevo")
    comandos.add_parser("respaldar", help="hace la copia de seguridad en la carpeta de datos/config.toml")
    restaurada = comandos.add_parser(
        "restaurar", help="restaura la base, los datos manuales y los PDFs desde una copia de seguridad")
    restaurada.add_argument("instantanea", help="ruta de un facturas_<marca>.db de la carpeta de respaldo, o su marca")
    return parser


def main(argv=None, rutas: Rutas | None = None, espera: float = ESPERA_ESTABLE) -> int:
    """Ejecuta un comando y devuelve el código de salida. `espera`: segundos de estabilidad de un PDF."""
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(errors="replace")
    args = _parser().parse_args(argv)
    rutas = rutas or Rutas()
    registro.configurar(rutas.logs)
    try:
        if args.comando == "cargar":
            return _procesar(rutas, rutas.entrada, espera)
        if args.comando == "reprocesar":
            return _procesar(rutas, rutas.pendientes, 0) if args.pendientes else _reconstruir(rutas)
        if args.comando == "estado":
            return _estado(rutas)
        if args.comando == "contratos":
            print(datos_manuales.contratos(rutas), end="")
            return 0
        if args.comando == "contrato":
            return _contrato(rutas, args)
        if args.comando == "respaldar":
            return _respaldar(rutas)
        if args.comando == "restaurar":
            return _restaurar(rutas, args.instantanea)
        return _diccionario(rutas)
    except BloqueoOcupado as error:
        print(f"No se hizo nada: {error}.")
        return 0
    except datos_manuales.ErrorAjuste as error:
        print(f"No se cambió nada: {error}.", file=sys.stderr)
        return 2
    except (ErrorBase, ErrorReconstruccion, ErrorRespaldo, sqlite3.Error, OSError, ValueError) as error:
        log.error("%s", error)
        print(f"Error del sistema: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        log.exception("Error inesperado")
        print(f"Error inesperado: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    finally:
        registro.cerrar()


def _procesar(rutas: Rutas, carpeta, espera: float) -> int:
    with bloqueo(rutas.bloqueo):
        motivo = preparar_base(rutas)
        if motivo:
            print(motivo)
        ajustes = leer_ajustes(rutas.ajustes)
        conexion = conectar(rutas.base, "escritura")
        try:
            resumen = procesar_lote(rutas, conexion, listar_pdfs(carpeta), ajustes, espera=espera)
        finally:
            conexion.close()
        print(_formatear(resumen))
        if resumen.cargadas:
            _respaldar_tras_cargar(rutas)
    return 1 if resumen.rechazadas else 0


def _respaldar_tras_cargar(rutas: Rutas) -> None:
    """R43: después de una carga que cambió algo. Sin carpeta configurada avisa y sigue; si falla, es un error."""
    try:
        resultado = respaldar(rutas)
    except SinConfiguracion as error:
        log.warning("Sin respaldo: %s", error)
        print(f"AVISO: no se hizo la copia de seguridad: {error}.")
    except (ErrorRespaldo, ErrorReconstruccion, OSError, sqlite3.Error) as error:
        raise ErrorRespaldo(f"las facturas se cargaron, pero no se pudo hacer la copia de seguridad: {error}") from error
    else:
        print(_formatear_respaldo(resultado))


def _formatear_respaldo(resultado: Respaldo) -> str:
    return (f"Respaldo: {resultado.instantanea.name} y {resultado.pdfs_copiados} "
            f"{'PDF nuevo' if resultado.pdfs_copiados == 1 else 'PDFs nuevos'} en {resultado.instantanea.parent.parent}")


def _formatear(resumen: Resumen) -> str:
    lineas = [
        f"Resumen: {len(resumen.cargadas)} cargadas, {len(resumen.duplicadas)} duplicadas, "
        f"{len(resumen.rechazadas)} rechazadas, {len(resumen.omitidas)} omitidas."
    ]
    lineas += [f"  cargada: {nombre}" for nombre in resumen.cargadas]
    lineas += [f"  duplicada: {nombre}" for nombre in resumen.duplicadas]
    lineas += [f"  RECHAZADA {nombre} (etapa {etapa}): {motivo}" for nombre, etapa, motivo in resumen.rechazadas.values()]
    lineas += [f"  omitida (sigue cambiando): {nombre}" for nombre in resumen.omitidas]
    return "\n".join(lineas)


def _reconstruir(rutas: Rutas) -> int:
    with bloqueo(rutas.bloqueo):
        resultado = reconstruir(rutas)
    print(f"Base reconstruida con {resultado.facturas} facturas de {rutas.procesadas.name}/.")
    for anterior, nuevo in resultado.alias_cambiados:
        print(f"  Cambió el alias por defecto de un contrato: '{anterior}' → '{nuevo}'. Para fijarlo, usá `contrato`.")
    return 0


def _estado(rutas: Rutas) -> int:
    texto, inconsistentes = generar_estado(rutas)
    print(texto, end="")
    return 2 if inconsistentes else 0


def _contrato(rutas: Rutas, args) -> int:
    with bloqueo(rutas.bloqueo):
        print(datos_manuales.modificar_contrato(
            rutas, args.alias, alias_nuevo=args.alias_nuevo))
    return 0


def _respaldar(rutas: Rutas) -> int:
    with bloqueo(rutas.bloqueo):
        print(_formatear_respaldo(respaldar(rutas)))
    return 0


def _restaurar(rutas: Rutas, instantanea: str) -> int:
    with bloqueo(rutas.bloqueo):
        resultado = restaurar(rutas, instantanea)
    print(f"Restaurada {resultado.instantanea.name}: la base y los datos manuales son los de esa copia; "
          f"se repusieron {resultado.pdfs_copiados} PDFs de {rutas.procesadas.name}/.")
    if resultado.pdfs_posteriores:
        print(f"AVISO: {resultado.pdfs_posteriores} PDFs de {rutas.procesadas.name}/ no están en esa copia, así que la base "
              "no los tiene. `reprocesar --todo` los incorpora.")
    return 0


def _diccionario(rutas: Rutas) -> int:
    destino = diccionario.escribir(rutas.raiz / "docs" / "diccionario.md", rutas.semillas)
    print(f"Escrito {destino.relative_to(rutas.raiz)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
