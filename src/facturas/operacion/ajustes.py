"""Datos manuales de los contratos: el alias (R41, diseño sección 14.2).

`contrato` escribe el cambio en la base y en `datos/ajustes_manuales.json` dentro de la misma
operación: primero la base (en una transacción sin confirmar), después el archivo (reemplazándolo
de una vez) y al final el `COMMIT`. Si algo falla, la base se revierte y el archivo vuelve a como
estaba. La carga y la reconstrucción leen el archivo al registrar cada contrato, así que
`reprocesar --todo` no pierde nada.
"""

import json
import os
import sqlite3
from pathlib import Path

from facturas.bd.conexion import conectar
from facturas.bd.construir import leer_ajustes
from facturas.operacion.proceso import Rutas


class ErrorAjuste(Exception):
    """El cambio pedido no es válido; no se modificó nada."""


def contratos(rutas: Rutas) -> str:
    """La lista de contratos con su alias, categoría y proveedor."""
    conexion = conectar(rutas.base, "lectura")
    try:
        filas = conexion.execute(
            """SELECT c.alias, ca.codigo, p.nombre
               FROM contrato AS c
               JOIN categoria AS ca ON ca.categoria_id = c.categoria_id
               JOIN proveedor AS p ON p.proveedor_id = c.proveedor_id
               ORDER BY ca.codigo, c.alias"""
        ).fetchall()
    finally:
        conexion.close()
    if not filas:
        return "No hay contratos: todavía no se cargó ninguna factura.\n"
    encabezado = ("alias", "categoría", "proveedor")
    anchos = [max(len(str(fila[i])) for fila in [encabezado, *filas]) for i in range(3)]
    lineas = ["  ".join(str(valor).ljust(ancho) for valor, ancho in zip(fila, anchos)).rstrip()
              for fila in [encabezado, *filas]]
    return "\n".join(lineas) + "\n"


def modificar_contrato(rutas: Rutas, alias: str, *, alias_nuevo: str | None = None) -> str:
    """Cambia los datos manuales del contrato `alias` (hoy, solo el alias), en la base y en el archivo de ajustes.

    None significa «no tocar». Devuelve una línea que dice cómo quedó el contrato.
    """
    cambios = {} if alias_nuevo is None else {"alias": alias_nuevo}
    if not cambios:
        raise ErrorAjuste("indicá la opción --alias")
    ajustes = leer_ajustes(rutas.ajustes)
    anterior = rutas.ajustes.read_bytes() if rutas.ajustes.exists() else None

    conexion = conectar(rutas.base, "escritura")
    try:
        conexion.execute("BEGIN IMMEDIATE")
        try:
            clave = _buscar(conexion, alias)
            if "alias" in cambios:
                _comprobar_alias(conexion, cambios["alias"], clave, ajustes)
            _actualizar(conexion, clave, cambios)
            _guardar(rutas.ajustes, ajustes, clave, cambios)
            try:
                conexion.execute("COMMIT")
            except BaseException:
                _restaurar_archivo(rutas.ajustes, anterior)
                raise
        except BaseException:
            if conexion.in_transaction:
                conexion.execute("ROLLBACK")
            raise
        return _describir(conexion, clave)
    finally:
        conexion.close()


def _buscar(conexion, alias: str) -> tuple[str, str]:
    """(identificador fiscal del proveedor, identificador externo) del contrato con ese alias."""
    fila = conexion.execute(
        """SELECT p.identificador_fiscal, c.identificador_externo
           FROM contrato AS c JOIN proveedor AS p ON p.proveedor_id = c.proveedor_id
           WHERE c.alias = ?""",
        (alias,),
    ).fetchone()
    if fila is None:
        raise ErrorAjuste(f"no hay ningún contrato con el alias '{alias}' (`contratos` los lista)")
    return fila


def _comprobar_alias(conexion, nuevo: str, clave, ajustes) -> None:
    if not nuevo or nuevo != nuevo.strip():
        raise ErrorAjuste("el alias no puede estar vacío ni empezar o terminar con espacios")
    otro = conexion.execute(
        """SELECT 1 FROM contrato AS c JOIN proveedor AS p ON p.proveedor_id = c.proveedor_id
           WHERE c.alias = ? AND NOT (p.identificador_fiscal = ? AND c.identificador_externo = ?)""",
        (nuevo, *clave),
    ).fetchone()
    if otro is not None:
        raise ErrorAjuste(f"el alias '{nuevo}' ya lo usa otro contrato")
    for ajuste in ajustes:
        if ajuste.get("alias") == nuevo and (ajuste["identificador_fiscal"], ajuste["identificador_externo"]) != clave:
            raise ErrorAjuste(f"el alias '{nuevo}' está reservado en ajustes_manuales.json para otro contrato")


def _actualizar(conexion, clave, cambios: dict) -> None:
    asignaciones = ", ".join(f"{campo} = :{campo}" for campo in cambios)
    try:
        conexion.execute(
            f"""UPDATE contrato SET {asignaciones}
                WHERE proveedor_id = (SELECT proveedor_id FROM proveedor WHERE identificador_fiscal = :fiscal)
                  AND identificador_externo = :externo""",
            {**cambios, "fiscal": clave[0], "externo": clave[1]},
        )
    except sqlite3.IntegrityError as error:
        raise ErrorAjuste(f"la base rechazó el cambio: {error}") from error


def _guardar(ruta: Path, ajustes: list[dict], clave, cambios: dict) -> None:
    """Escribe los cambios en la entrada del contrato (la crea si no está) y reemplaza el archivo de una vez."""
    for ajuste in ajustes:
        if (ajuste["identificador_fiscal"], ajuste["identificador_externo"]) == clave:
            ajuste.update(cambios)
            break
    else:
        ajustes.append({"identificador_fiscal": clave[0], "identificador_externo": clave[1], **cambios})
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".nuevo")
    temporal.write_text(json.dumps(ajustes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporal, ruta)


def _restaurar_archivo(ruta: Path, anterior: bytes | None) -> None:
    if anterior is None:
        ruta.unlink(missing_ok=True)
    else:
        ruta.write_bytes(anterior)


def _describir(conexion, clave) -> str:
    alias, categoria = conexion.execute(
        """SELECT c.alias, ca.codigo
           FROM contrato AS c
           JOIN proveedor AS p ON p.proveedor_id = c.proveedor_id
           JOIN categoria AS ca ON ca.categoria_id = c.categoria_id
           WHERE p.identificador_fiscal = ? AND c.identificador_externo = ?""",
        clave,
    ).fetchone()
    return f"Contrato '{alias}' ({categoria})."
