"""El comando `estado`: un resumen legible de lo que hay en la base y de lo que está pendiente.

Lee la base en modo solo lectura. Además de informar, comprueba I1 (las líneas suman el total)
en todas las facturas, para detectar un `INSERT OR REPLACE` hecho a mano (revisión H4): la base
impide editar un hecho suelto, pero no que alguien reemplace la fila de una factura.
"""

from datetime import date

from facturas.bd.conexion import conectar
from facturas.dashboard import datos
from facturas.operacion.proceso import Rutas, listar_pdfs


def euros(centimos: int) -> str:
    """1234567 → '12.345,67 €'."""
    signo = "-" if centimos < 0 else ""
    enteros, decimales = divmod(abs(centimos), 100)
    return f"{signo}{enteros:,}".replace(",", ".") + f",{decimales:02d} €"


def generar_estado(rutas: Rutas) -> tuple[str, int]:
    """El texto del estado y la cantidad de facturas cuyas líneas no suman su total."""
    conexion = conectar(rutas.base, "lectura")
    try:
        lineas = [f"Estado de la base al {date.today().isoformat()}", ""]
        lineas += _por_categoria(conexion)
        lineas += _ultimo_periodo(conexion)
        lineas += _meses_incompletos(conexion)
        lineas += _pendientes(rutas)
        inconsistentes, seccion = _integridad(conexion)
        return "\n".join(lineas + seccion) + "\n", inconsistentes
    finally:
        conexion.close()


def _por_categoria(conexion):
    facturas = dict(conexion.execute("SELECT categoria_codigo, count(DISTINCT factura_id) FROM v_linea GROUP BY 1"))
    importes = conexion.execute(
        "SELECT categoria_codigo, sum(importe_centimos) FROM v_hecho_gasto_mensual GROUP BY 1 ORDER BY 1"
    ).fetchall()
    salida = ["Facturas vigentes por categoría"]
    if not importes:
        return salida + ["  (ninguna)", ""]
    ancho = max(len(categoria) for categoria, _ in importes)
    for categoria, importe in importes:
        n = facturas.get(categoria, 0)
        salida.append(f"  {categoria:<{ancho}}  {n} {'factura' if n == 1 else 'facturas'}, {euros(importe)}")
    salida.append(f"  {'total':<{ancho}}  {euros(sum(importe for _, importe in importes))}")
    return salida + [""]


def _ultimo_periodo(conexion):
    filas = conexion.execute(
        """SELECT c.alias, ca.codigo, max(f.fecha_fin)
           FROM contrato AS c
           JOIN categoria AS ca ON ca.categoria_id = c.categoria_id
           JOIN linea AS l ON l.contrato_id = c.contrato_id
           JOIN v_factura_vigente AS f ON f.factura_id = l.factura_id
           WHERE f.tipo IN ('ordinaria', 'rectificativa_sustitucion') AND l.imputacion = 'periodo'
           GROUP BY c.contrato_id ORDER BY ca.codigo, c.alias"""
    ).fetchall()
    salida = ["Último período cubierto por contrato"]
    salida += [f"  {alias} ({categoria}): hasta el {fin}" for alias, categoria, fin in filas] or ["  (ninguno)"]
    return salida + [""]


def _meses_incompletos(conexion):
    """Los meses con días sin cubrir por categoría, con la regla del dashboard (`datos.cobertura_mensual`)."""
    salida = ["Meses incompletos (días cubiertos / días del mes)"]
    gastos = datos.gasto_mensual(conexion)
    por_categoria = {}
    if gastos:
        categorias = sorted({g.categoria for g in gastos})
        desde, hasta = min(g.anio_mes for g in gastos), max(g.anio_mes for g in gastos)
        for c in datos.cobertura_mensual(conexion, categorias, desde, hasta):
            if not c.completo:
                por_categoria.setdefault(c.categoria, []).append(
                    f"{c.anio_mes} {c.dias_cubiertos}/{c.dias_mes}")
    salida += [f"  {categoria}: {', '.join(meses)}" for categoria, meses in por_categoria.items()]
    return salida + ([] if por_categoria else ["  (ninguno)"]) + [""]


def _pendientes(rutas):
    pdfs = listar_pdfs(rutas.pendientes)
    salida = [f"PDFs pendientes: {len(pdfs)}"]
    for pdf in pdfs:
        motivo = pdf.with_suffix(".motivo.txt")
        detalle = " ".join(
            linea.split(": ", 1)[1]
            for linea in (motivo.read_text(encoding="utf-8").splitlines() if motivo.exists() else [])
            if linea.startswith(("Etapa: ", "Motivo: "))
        )
        salida.append(f"  {pdf.name}: {detalle or 'sin motivo registrado'}")
    return salida + [""]


def _integridad(conexion):
    filas = conexion.execute(
        """SELECT f.numero, f.importe_total_centimos, coalesce(sum(l.importe_centimos), 0)
           FROM factura AS f LEFT JOIN linea AS l ON l.factura_id = f.factura_id
           GROUP BY f.factura_id HAVING f.importe_total_centimos <> coalesce(sum(l.importe_centimos), 0)
           ORDER BY f.numero"""
    ).fetchall()
    (total,) = conexion.execute("SELECT count(*) FROM factura").fetchone()
    if not filas:
        return 0, [f"Integridad: las líneas suman el total en las {total} facturas (I1)."]
    salida = [f"ATENCIÓN: {len(filas)} de {total} facturas no cumplen I1 (las líneas no suman el total):"]
    salida += [f"  {numero}: total {euros(esperado)}, líneas {euros(suma)}" for numero, esperado, suma in filas]
    return len(filas), salida
