"""Una factura extraída → la base, en una sola transacción (R17, R18, R21, R33).

`cargar_factura()` traduce los textos a conceptos, registra los contratos nuevos,
inserta la carga, la cabecera, las líneas, las mediciones y los atributos, y verifica
los invariantes antes del `COMMIT`. Si algo falla, revierte todo y lanza `ErrorCarga`
con la etapa del rechazo (diseño, sección 13.3); `registrar_rechazo()` deja constancia
en `carga`. No conoce PDFs: recibe el hash y el nombre del archivo.

Los ids se obtienen con `RETURNING` o por clave natural, nunca con `lastrowid` (R17).
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from facturas.bd.construir import aplicar_ajustes
from facturas.bd.invariantes import verificar
from facturas.carga.traduccion import ErrorTraduccion, traducir
from facturas.extraccion import FacturaExtraida

ETAPAS = ("formato", "extraccion", "traduccion", "duplicado", "insercion", "invariantes")
_ETAPAS_SIN_EXTRACCION = ("formato", "extraccion")
_TIPOS_CONTROLADOS = "('ordinaria', 'rectificativa_sustitucion')"

registro = logging.getLogger("facturas.carga")


class ErrorCarga(Exception):
    """Una factura no se pudo cargar. `etapa` es la del rechazo en `carga.etapa_rechazo`."""

    def __init__(self, etapa: str, motivo: str):
        if etapa not in ETAPAS:
            raise ValueError(f"Etapa de rechazo desconocida: {etapa!r}")
        super().__init__(motivo)
        self.etapa = etapa
        self.motivo = motivo


def _ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _uno(conexion, sql, parametros=()):
    """El único valor que devuelve la sentencia. fetchall() termina de ejecutarla (RETURNING)."""
    (fila,) = conexion.execute(sql, parametros).fetchall()
    return fila[0]


def milesimas(texto: str, nombre: str) -> int:
    """Decimal en texto → entero en milésimas, sin pasar por float. Más de 3 decimales no se trunca (R11)."""
    try:
        valor = Decimal(texto).scaleb(3)
    except InvalidOperation as error:
        raise ErrorCarga("extraccion", f"{nombre}: {texto!r} no es un decimal") from error
    if valor != valor.to_integral_value():
        raise ErrorCarga("extraccion", f"{nombre}: {texto!r} tiene más de 3 decimales")
    return int(valor)


def estado_de_carga(conexion: sqlite3.Connection, sha256: str) -> str | None:
    """'cargada', 'rechazada' o None si el PDF no se vio nunca."""
    fila = conexion.execute("SELECT estado FROM carga WHERE sha256 = ?", (sha256,)).fetchone()
    return None if fila is None else fila[0]


def cargar_factura(
    conexion: sqlite3.Connection,
    factura: FacturaExtraida,
    *,
    sha256: str,
    nombre_archivo: str,
    ajustes: list[dict] = (),
) -> int:
    """Carga la factura en una transacción y devuelve su factura_id; si falla, no deja nada."""
    # Lo que no depende de la base se convierte antes de abrir la transacción.
    cantidades = _convertir_cantidades(factura)
    conexion.execute("BEGIN IMMEDIATE")
    try:
        conexion.execute("PRAGMA defer_foreign_keys = ON")
        resuelto = _resolver(conexion, factura)
        factura_id = _insertar(conexion, factura, resuelto, cantidades, sha256, nombre_archivo, ajustes)
        violaciones = verificar(conexion, factura_id)
        if violaciones:
            raise ErrorCarga("invariantes", "; ".join(violaciones))
        conexion.execute("COMMIT")
        return factura_id
    except ErrorCarga:
        raise
    except ErrorTraduccion as error:
        raise ErrorCarga("traduccion", str(error)) from error
    except sqlite3.Error as error:
        raise ErrorCarga("insercion", _describir(conexion, factura, str(error))) from error
    except Exception as error:
        registro.exception("Error inesperado al cargar la factura %s", factura.numero)
        raise ErrorCarga("insercion", f"error inesperado: {type(error).__name__}: {error}") from error
    finally:
        if conexion.in_transaction:
            conexion.execute("ROLLBACK")


def registrar_rechazo(
    conexion: sqlite3.Connection,
    *,
    sha256: str,
    nombre_archivo: str,
    etapa: str,
    motivo: str,
    formato: str | None = None,
    version_parser: str | None = None,
    factura: FacturaExtraida | None = None,
) -> None:
    """Deja la carga como rechazada, en una transacción corta. Un reintento actualiza su fila."""
    if etapa not in ETAPAS:
        raise ValueError(f"Etapa de rechazo desconocida: {etapa!r}")
    if etapa == "formato":
        formato = version_parser = None
    extraccion = factura.a_json() if factura is not None and etapa not in _ETAPAS_SIN_EXTRACCION else None
    conexion.execute("BEGIN IMMEDIATE")
    try:
        conexion.execute(
            """INSERT INTO carga (sha256, nombre_archivo, formato, version_parser, fecha_hora, estado,
                                  etapa_rechazo, motivo_rechazo, extraccion_json)
               VALUES (?, ?, ?, ?, ?, 'rechazada', ?, ?, ?)
               ON CONFLICT (sha256) DO UPDATE SET
                   nombre_archivo = excluded.nombre_archivo, formato = excluded.formato,
                   version_parser = excluded.version_parser, fecha_hora = excluded.fecha_hora,
                   estado = excluded.estado, etapa_rechazo = excluded.etapa_rechazo,
                   motivo_rechazo = excluded.motivo_rechazo, extraccion_json = excluded.extraccion_json""",
            (sha256, nombre_archivo, formato, version_parser, _ahora(), etapa, motivo, extraccion),
        )
        conexion.execute("COMMIT")
    finally:
        if conexion.in_transaction:
            conexion.execute("ROLLBACK")


def _convertir_cantidades(factura: FacturaExtraida) -> dict:
    """Cantidades, lecturas y atributos de la factura, en milésimas, por posición en su lista."""
    return {
        "mediciones": [
            (
                milesimas(m.cantidad, f"medición de {m.magnitud}: cantidad"),
                None
                if m.cantidad_contador is None
                else milesimas(m.cantidad_contador, f"medición de {m.magnitud}: cantidad_contador"),
                milesimas(m.lectura.valor, f"medición de {m.magnitud}: lectura"),
            )
            for m in factura.mediciones
        ],
        "atributos": {
            (c.identificador_externo, a.atributo): milesimas(a.valor, f"atributo {a.atributo}")
            for c in factura.contratos
            for a in c.atributos
        },
    }


def _resolver(conexion, factura: FacturaExtraida) -> dict:
    """Los ids que la factura necesita y el concepto de cada línea; falla si algo no existe."""
    proveedor_id = _buscar(
        conexion, "SELECT proveedor_id FROM proveedor WHERE identificador_fiscal = ?",
        (factura.identificador_fiscal,), f"proveedor desconocido: {factura.identificador_fiscal}",
    )
    moneda_id = _buscar(
        conexion, "SELECT moneda_id FROM moneda WHERE codigo = ?", (factura.moneda,),
        f"moneda no admitida: {factura.moneda}",
    )
    if conexion.execute(
        "SELECT 1 FROM factura WHERE proveedor_id = ? AND numero = ?", (proveedor_id, factura.numero)
    ).fetchone():
        raise ErrorCarga("duplicado", f"la factura {factura.numero} del proveedor {factura.identificador_fiscal} ya está cargada")

    categoria_de = {}
    for contrato in factura.contratos:
        categoria_de[contrato.identificador_externo] = contrato.categoria
    categorias = {
        codigo: _buscar(
            conexion, "SELECT categoria_id FROM categoria WHERE codigo = ?", (codigo,),
            f"categoría desconocida: {codigo}",
        )
        for codigo in set(categoria_de.values())
    }

    conceptos = []
    for linea in factura.lineas:
        concepto_id = traducir(conexion, categoria_de[linea.contrato], linea.seccion, linea.texto)
        imputacion_defecto = _uno(conexion, "SELECT imputacion_defecto FROM concepto WHERE concepto_id = ?", (concepto_id,))
        conceptos.append((concepto_id, linea.imputacion or imputacion_defecto))

    mediciones = []
    for m in factura.mediciones:
        categoria = categoria_de[m.contrato]
        magnitud_categoria_id = _buscar(
            conexion,
            """SELECT mc.magnitud_categoria_id FROM magnitud_categoria AS mc
               JOIN magnitud AS mg ON mg.magnitud_id = mc.magnitud_id
               WHERE mc.categoria_id = ? AND mg.codigo = ?""",
            (categorias[categoria], m.magnitud), f"magnitud desconocida en la categoría {categoria}: {m.magnitud}",
        )
        franja_id = None
        if m.franja is not None:
            franja_id = _buscar(conexion, "SELECT franja_id FROM franja WHERE codigo = ?", (m.franja,),
                                f"franja desconocida: {m.franja}")
        mediciones.append((magnitud_categoria_id, franja_id))

    atributos = {}
    for contrato in factura.contratos:
        for a in contrato.atributos:
            atributos[(contrato.identificador_externo, a.atributo)] = _buscar(
                conexion,
                "SELECT atributo_contrato_id FROM atributo_contrato WHERE categoria_id = ? AND codigo = ?",
                (categorias[contrato.categoria], a.atributo),
                f"atributo desconocido en la categoría {contrato.categoria}: {a.atributo}",
            )
    return {
        "proveedor_id": proveedor_id, "moneda_id": moneda_id, "categorias": categorias,
        "categoria_de": categoria_de, "conceptos": conceptos, "mediciones": mediciones, "atributos": atributos,
    }


def _buscar(conexion, sql, parametros, motivo):
    fila = conexion.execute(sql, parametros).fetchone()
    if fila is None:
        raise ErrorTraduccion(motivo)
    return fila[0]


def _insertar(conexion, factura, resuelto, cantidades, sha256, nombre_archivo, ajustes) -> int:
    carga_id = _uno(
        conexion,
        """INSERT INTO carga (sha256, nombre_archivo, formato, version_parser, fecha_hora, estado, extraccion_json)
           VALUES (?, ?, ?, ?, ?, 'cargada', ?)
           ON CONFLICT (sha256) DO UPDATE SET
               nombre_archivo = excluded.nombre_archivo, formato = excluded.formato,
               version_parser = excluded.version_parser, fecha_hora = excluded.fecha_hora,
               estado = excluded.estado, etapa_rechazo = NULL, motivo_rechazo = NULL,
               extraccion_json = excluded.extraccion_json
           RETURNING carga_id""",
        (sha256, nombre_archivo, factura.formato, factura.version_parser, _ahora(), factura.a_json()),
    )
    contratos = {
        contrato.identificador_externo: _contrato(conexion, factura, contrato, resuelto, ajustes)
        for contrato in factura.contratos
    }
    factura_id = _uno(
        conexion,
        """INSERT INTO factura (carga_id, proveedor_id, moneda_id, numero, tipo, numero_factura_corregida,
                                fecha_emision, fecha_vencimiento, fecha_inicio, fecha_fin, importe_total_centimos)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING factura_id""",
        (carga_id, resuelto["proveedor_id"], resuelto["moneda_id"], factura.numero, factura.tipo,
         factura.numero_factura_corregida, factura.fecha_emision, factura.fecha_vencimiento,
         factura.periodo.inicio, factura.periodo.fin, factura.importe_total_centimos),
    )
    for linea, (concepto_id, imputacion) in zip(factura.lineas, resuelto["conceptos"]):
        periodo = linea.periodo or factura.periodo
        conexion.execute(
            """INSERT INTO linea (factura_id, posicion, contrato_id, categoria_id, concepto_id, texto,
                                  importe_centimos, imputacion, fecha_inicio, fecha_fin, es_derivada)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (factura_id, linea.posicion, *contratos[linea.contrato], concepto_id, linea.texto,
             linea.importe_centimos, imputacion, periodo.inicio, periodo.fin, int(linea.derivada_de is not None)),
        )
    for m, (cantidad, cantidad_contador, lectura), (magnitud_categoria_id, franja_id) in zip(
        factura.mediciones, cantidades["mediciones"], resuelto["mediciones"]
    ):
        conexion.execute(
            """INSERT INTO medicion (factura_id, contrato_id, categoria_id, magnitud_categoria_id, franja_id,
                                     cantidad_milesimas, cantidad_contador_milesimas, factor_conversion,
                                     fecha_lectura, lectura_milesimas, tipo_lectura)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (factura_id, *contratos[m.contrato], magnitud_categoria_id, franja_id, cantidad, cantidad_contador,
             m.factor_conversion, m.lectura.fecha, lectura, m.lectura.tipo),
        )
    for (externo, atributo), valor in cantidades["atributos"].items():
        conexion.execute(
            """INSERT INTO valor_atributo (factura_id, contrato_id, categoria_id, atributo_contrato_id, valor_milesimas)
               VALUES (?, ?, ?, ?, ?)""",
            (factura_id, *contratos[externo], resuelto["atributos"][(externo, atributo)], valor),
        )
    return factura_id


def _contrato(conexion, factura, contrato, resuelto, ajustes) -> tuple[int, int]:
    """(contrato_id, categoria_id); lo registra si es nuevo (R21), con sus datos manuales (R41)."""
    categoria_id = resuelto["categorias"][contrato.categoria]
    fila = conexion.execute(
        "SELECT contrato_id, categoria_id FROM contrato WHERE proveedor_id = ? AND identificador_externo = ?",
        (resuelto["proveedor_id"], contrato.identificador_externo),
    ).fetchone()
    if fila is not None:
        return fila
    nuevo = conexion.execute(
        """INSERT INTO contrato (proveedor_id, categoria_id, identificador_externo, alias)
           VALUES (?, ?, ?, ?) RETURNING contrato_id, categoria_id""",
        (resuelto["proveedor_id"], categoria_id, contrato.identificador_externo,
         _alias_por_defecto(conexion, contrato.categoria, ajustes)),
    ).fetchall()[0]
    propios = [
        a for a in ajustes
        if a["identificador_fiscal"] == factura.identificador_fiscal
        and a["identificador_externo"] == contrato.identificador_externo
    ]
    aplicar_ajustes(conexion, propios)
    return nuevo


def _alias_por_defecto(conexion, categoria: str, ajustes) -> str:
    """`<categoría> <n>` con el menor n que no usa ningún contrato ni reserva un ajuste manual (D7)."""
    usados = {alias for (alias,) in conexion.execute("SELECT alias FROM contrato")}
    usados |= {ajuste["alias"] for ajuste in ajustes if ajuste.get("alias")}
    numero = 1
    while f"{categoria} {numero}" in usados:
        numero += 1
    return f"{categoria} {numero}"


def _describir(conexion, factura, mensaje: str) -> str:
    """El mensaje de la base; en un solape, agrega la factura con la que choca."""
    if not mensaje.startswith("solape"):
        return mensaje
    filas = conexion.execute(
        f"""SELECT DISTINCT otra.numero, otra.fecha_inicio, otra.fecha_fin, c.alias
            FROM factura AS nueva
            JOIN contrato AS c ON c.proveedor_id = nueva.proveedor_id AND c.identificador_externo IN
                 (SELECT value FROM json_each(?))
            JOIN linea AS lo ON lo.contrato_id = c.contrato_id AND lo.imputacion = 'periodo'
            JOIN factura AS otra ON otra.factura_id = lo.factura_id
            WHERE nueva.proveedor_id = c.proveedor_id AND nueva.numero = ?
              AND otra.factura_id <> nueva.factura_id
              AND otra.tipo IN {_TIPOS_CONTROLADOS}
              AND otra.fecha_inicio <= nueva.fecha_fin AND nueva.fecha_inicio <= otra.fecha_fin
            ORDER BY otra.fecha_inicio""",
        (json.dumps([c.identificador_externo for c in factura.contratos]), factura.numero),
    ).fetchall()
    if not filas:
        return mensaje
    choques = "; ".join(
        f"contrato '{alias}' con la factura {numero} ({inicio} a {fin})" for numero, inicio, fin, alias in filas
    )
    return f"{mensaje} ({choques})"

