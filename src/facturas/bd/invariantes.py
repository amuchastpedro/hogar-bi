"""Invariantes de una factura (R33), que la carga verifica antes del COMMIT.

`verificar(conexion, factura_id)` devuelve la lista de violaciones, vacía si la
factura cumple todos. Si no está vacía, la carga revierte la transacción.

La tolerancia de todos es 0, porque comparan enteros sin productos ni redondeos
de por medio (diseño, sección 10), salvo I8: el reparto de un total impreso admite
`TOLERANCIA_REPARTO_CENTIMOS` (10), porque Digi redondea el IVA por servicio y por
factura por separado (decisión de la persona usuaria, 2026-10-06). I2 (cantidad × precio) e I3 (base × tipo) no
aplican: las líneas no guardan cantidades, precios, bases ni tipos (desvío D1).

I5, I6 e I7 también los impone la base (claves foráneas compuestas, el trigger de
solapes y las claves foráneas). Se verifican igual como red de seguridad: con las
claves foráneas diferidas, una violación llega hasta acá, y el motivo es legible.

I9 no está en R33: hace cumplir la definición de abono del diseño (sección 10).
"""

import sqlite3

from facturas.extraccion import TOLERANCIA_REPARTO_CENTIMOS

_TIPOS_CONTROLADOS = "('ordinaria', 'rectificativa_sustitucion')"
_TIPOS_QUE_CORRIGEN = "('rectificativa_sustitucion', 'abono')"


def verificar(conexion: sqlite3.Connection, factura_id: int) -> list[str]:
    """Violaciones de I1, I4, I5, I6, I7, I8 e I9 para la factura indicada."""
    if conexion.execute("SELECT 1 FROM factura WHERE factura_id = ?", (factura_id,)).fetchone() is None:
        raise ValueError(f"No existe la factura {factura_id}")
    return [
        *_i1_total(conexion, factura_id),
        *_i4_prorrateo(conexion, factura_id),
        *_i5_categoria(conexion, factura_id),
        *_i6_solapes(conexion, factura_id),
        *_i7_claves_foraneas(conexion),
        *_i8_derivadas(conexion, factura_id),
        *_i9_abonos(conexion, factura_id),
    ]


def _i1_total(conexion, factura_id):
    total, suma = conexion.execute(
        """SELECT f.importe_total_centimos, coalesce(sum(l.importe_centimos), 0)
           FROM factura AS f LEFT JOIN linea AS l ON l.factura_id = f.factura_id
           WHERE f.factura_id = ?""",
        (factura_id,),
    ).fetchone()
    if suma != total:
        return [f"I1: las líneas suman {suma} céntimos y el total de la factura es {total}"]
    return []


def _i4_prorrateo(conexion, factura_id):
    lineas = conexion.execute(
        """WITH prorrateo AS (
               SELECT linea_id, sum(importe_centimos) AS importe_centimos
               FROM v_prorrateo_linea WHERE factura_id = :factura_id GROUP BY linea_id)
           SELECT l.posicion, l.importe_centimos, coalesce(p.importe_centimos, 0)
           FROM linea AS l LEFT JOIN prorrateo AS p ON p.linea_id = l.linea_id
           WHERE l.factura_id = :factura_id AND coalesce(p.importe_centimos, 0) <> l.importe_centimos
           ORDER BY l.posicion""",
        {"factura_id": factura_id},
    )
    violaciones = [
        f"I4: el prorrateo de la línea {posicion} suma {prorrateado} céntimos y su importe es {importe}"
        for posicion, importe, prorrateado in lineas
    ]
    mediciones = conexion.execute(
        """WITH prorrateo AS (
               SELECT medicion_id, sum(cantidad_milesimas) AS cantidad_milesimas
               FROM v_prorrateo_medicion WHERE factura_id = :factura_id GROUP BY medicion_id)
           SELECT m.medicion_id, m.cantidad_milesimas, coalesce(p.cantidad_milesimas, 0)
           FROM medicion AS m LEFT JOIN prorrateo AS p ON p.medicion_id = m.medicion_id
           WHERE m.factura_id = :factura_id AND coalesce(p.cantidad_milesimas, 0) <> m.cantidad_milesimas
           ORDER BY m.medicion_id""",
        {"factura_id": factura_id},
    )
    violaciones += [
        f"I4: el prorrateo de la medición {medicion_id} suma {prorrateada} milésimas y su cantidad es {cantidad}"
        for medicion_id, cantidad, prorrateada in mediciones
    ]
    return violaciones


def _i5_categoria(conexion, factura_id):
    filas = conexion.execute(
        """SELECT l.posicion
           FROM linea AS l
           LEFT JOIN contrato AS c ON c.contrato_id = l.contrato_id
           LEFT JOIN concepto AS co ON co.concepto_id = l.concepto_id
           WHERE l.factura_id = ?
             AND (c.categoria_id IS NOT l.categoria_id OR co.categoria_id IS NOT l.categoria_id)
           ORDER BY l.posicion""",
        (factura_id,),
    )
    return [
        f"I5: el concepto de la línea {posicion} no es de la categoría de su contrato"
        for (posicion,) in filas
    ]


def _i6_solapes(conexion, factura_id):
    # La misma condición que el trigger tg_linea_bi_solape (diseño, sección 3.4).
    filas = conexion.execute(
        f"""SELECT DISTINCT c.alias, otra.numero, otra.fecha_inicio, otra.fecha_fin
            FROM factura AS nueva
            JOIN linea AS ln ON ln.factura_id = nueva.factura_id AND ln.imputacion = 'periodo'
            JOIN linea AS lo ON lo.contrato_id = ln.contrato_id AND lo.factura_id <> nueva.factura_id
                            AND lo.imputacion = 'periodo'
            JOIN factura AS otra ON otra.factura_id = lo.factura_id
            JOIN contrato AS c ON c.contrato_id = ln.contrato_id
            WHERE nueva.factura_id = ?
              AND nueva.tipo IN {_TIPOS_CONTROLADOS}
              AND otra.tipo IN {_TIPOS_CONTROLADOS}
              AND otra.fecha_inicio <= nueva.fecha_fin AND nueva.fecha_inicio <= otra.fecha_fin
              AND NOT EXISTS (
                  SELECT 1 FROM factura AS k
                  WHERE k.proveedor_id = nueva.proveedor_id AND k.numero_factura_corregida = nueva.numero
                    AND k.tipo IN {_TIPOS_QUE_CORRIGEN})
              AND NOT EXISTS (
                  SELECT 1 FROM factura AS k
                  WHERE k.proveedor_id = otra.proveedor_id AND k.numero_factura_corregida = otra.numero
                    AND k.tipo IN {_TIPOS_QUE_CORRIGEN})
            ORDER BY c.alias, otra.fecha_inicio""",
        (factura_id,),
    )
    return [
        f"I6: en el contrato '{alias}', el período se superpone con la factura {numero} ({inicio} a {fin})"
        for alias, numero, inicio, fin in filas
    ]


def _i7_claves_foraneas(conexion):
    violaciones = []
    for tabla, fila, padre, fk_id in conexion.execute("PRAGMA foreign_key_check").fetchall():
        columnas = [
            columna
            for (columna,) in conexion.execute(
                'SELECT "from" FROM pragma_foreign_key_list(?) WHERE id = ? ORDER BY seq', (tabla, fk_id)
            )
        ]
        violaciones.append(f"I7: {tabla} → {padre} ({', '.join(columnas)}), fila {fila} de {tabla}")
    return violaciones


def _i8_derivadas(conexion, factura_id):
    # Una línea derivada lleva como texto el rótulo del total repartido del que sale
    # (diseño, sección 11.4), y el total impreso solo está en la extracción.
    totales = conexion.execute(
        """SELECT json_extract(t.value, '$.texto'), json_extract(t.value, '$.importe_centimos'),
                  (SELECT coalesce(sum(l.importe_centimos), 0) FROM linea AS l
                   WHERE l.factura_id = f.factura_id AND l.es_derivada = 1
                     AND l.texto = json_extract(t.value, '$.texto'))
           FROM factura AS f
           JOIN carga AS ca ON ca.carga_id = f.carga_id
           JOIN json_each(ca.extraccion_json, '$.totales_repartidos') AS t
           WHERE f.factura_id = ?""",
        (factura_id,),
    )
    violaciones = [
        f"I8: las líneas derivadas de '{texto}' suman {suma} céntimos y el total impreso es {total}"
        for texto, total, suma in totales
        if abs(suma - total) > TOLERANCIA_REPARTO_CENTIMOS
    ]
    huerfanas = conexion.execute(
        """SELECT l.posicion
           FROM linea AS l
           JOIN factura AS f ON f.factura_id = l.factura_id
           JOIN carga AS ca ON ca.carga_id = f.carga_id
           WHERE l.factura_id = ? AND l.es_derivada = 1
             AND l.texto NOT IN (SELECT json_extract(t.value, '$.texto')
                                 FROM json_each(ca.extraccion_json, '$.totales_repartidos') AS t)
           ORDER BY l.posicion""",
        (factura_id,),
    )
    violaciones += [
        f"I8: la línea derivada {posicion} no corresponde a ningún total repartido" for (posicion,) in huerfanas
    ]
    return violaciones


def _i9_abonos(conexion, factura_id):
    # Un abono anula entera la factura que corrige: si los dos están en la base, sus
    # líneas suman 0 en cada contrato. Se verifica al cargar cualquiera de los dos, así
    # que no depende del orden en que lleguen. Un crédito parcial es una rectificativa
    # por diferencias, no un abono.
    filas = conexion.execute(
        """WITH par AS (
               -- La factura es el abono…
               SELECT a.factura_id AS abono_id, a.numero AS abono, o.factura_id AS original_id, o.numero AS original
               FROM factura AS a
               JOIN factura AS o ON o.proveedor_id = a.proveedor_id AND o.numero = a.numero_factura_corregida
               WHERE a.factura_id = :factura_id AND a.tipo = 'abono'
               UNION
               -- …o es la factura que un abono corrige.
               SELECT a.factura_id, a.numero, o.factura_id, o.numero
               FROM factura AS o
               JOIN factura AS a ON a.proveedor_id = o.proveedor_id AND a.numero_factura_corregida = o.numero
                                AND a.tipo = 'abono'
               WHERE o.factura_id = :factura_id)
           SELECT p.abono, p.original, c.alias, sum(l.importe_centimos)
           FROM par AS p
           JOIN linea AS l ON l.factura_id IN (p.abono_id, p.original_id)
           JOIN contrato AS c ON c.contrato_id = l.contrato_id
           GROUP BY p.abono_id, p.original_id, l.contrato_id
           HAVING sum(l.importe_centimos) <> 0
           ORDER BY p.abono, c.alias""",
        {"factura_id": factura_id},
    )
    return [
        f"I9: el abono {abono} no anula entera la factura {original}: "
        f"en el contrato '{alias}' suman {suma} céntimos"
        for abono, original, alias, suma in filas
    ]
