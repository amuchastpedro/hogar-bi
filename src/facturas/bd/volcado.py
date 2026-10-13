"""Volcado canónico de la base (diseño, sección 13.4).

Dos bases tienen el mismo contenido si sus volcados son iguales. Cada fila aparece con
sus claves foráneas resueltas a claves naturales y ordenada por ellas, porque los ids
sustitutos dependen del orden de carga. Se excluyen:

- `carga.fecha_hora`, que dice cuándo se procesó el PDF y no qué contiene;
- las cargas rechazadas, que viven en `datos/pendientes/` y `datos/duplicados/` con su
  `.motivo.txt` y se regeneran al reintentarlas.

Las dimensiones (semillas) no se vuelcan: `construccion.huella_semillas` garantiza que
son las mismas.
"""

import sqlite3

_CONSULTAS = {
    "construccion": "SELECT huella_semillas FROM construccion",
    "carga": """
        SELECT sha256, nombre_archivo, formato, version_parser, estado, extraccion_json
        FROM carga WHERE estado = 'cargada' ORDER BY sha256""",
    "contrato": """
        SELECT p.identificador_fiscal, c.identificador_externo, ca.codigo, c.alias
        FROM contrato AS c
        JOIN proveedor AS p ON p.proveedor_id = c.proveedor_id
        JOIN categoria AS ca ON ca.categoria_id = c.categoria_id
        ORDER BY p.identificador_fiscal, c.identificador_externo""",
    "factura": """
        SELECT p.identificador_fiscal, f.numero, ca.sha256, m.codigo, f.tipo, f.numero_factura_corregida,
               f.fecha_emision, f.fecha_vencimiento, f.fecha_inicio, f.fecha_fin, f.importe_total_centimos
        FROM factura AS f
        JOIN proveedor AS p ON p.proveedor_id = f.proveedor_id
        JOIN carga AS ca ON ca.carga_id = f.carga_id
        JOIN moneda AS m ON m.moneda_id = f.moneda_id
        ORDER BY p.identificador_fiscal, f.numero""",
    "linea": """
        SELECT p.identificador_fiscal, f.numero, l.posicion, c.identificador_externo, ca.codigo, co.codigo,
               l.texto, l.importe_centimos, l.imputacion, l.fecha_inicio, l.fecha_fin, l.es_derivada
        FROM linea AS l
        JOIN factura AS f ON f.factura_id = l.factura_id
        JOIN proveedor AS p ON p.proveedor_id = f.proveedor_id
        JOIN contrato AS c ON c.contrato_id = l.contrato_id
        JOIN categoria AS ca ON ca.categoria_id = l.categoria_id
        JOIN concepto AS co ON co.concepto_id = l.concepto_id
        ORDER BY p.identificador_fiscal, f.numero, l.posicion""",
    "medicion": """
        SELECT p.identificador_fiscal, f.numero, c.identificador_externo, mg.codigo, coalesce(fr.codigo, ''),
               m.cantidad_milesimas, m.cantidad_contador_milesimas, m.factor_conversion,
               m.fecha_lectura, m.lectura_milesimas, m.tipo_lectura
        FROM medicion AS m
        JOIN factura AS f ON f.factura_id = m.factura_id
        JOIN proveedor AS p ON p.proveedor_id = f.proveedor_id
        JOIN contrato AS c ON c.contrato_id = m.contrato_id
        JOIN magnitud_categoria AS mc ON mc.magnitud_categoria_id = m.magnitud_categoria_id
        JOIN magnitud AS mg ON mg.magnitud_id = mc.magnitud_id
        LEFT JOIN franja AS fr ON fr.franja_id = m.franja_id
        ORDER BY p.identificador_fiscal, f.numero, c.identificador_externo, mg.codigo, coalesce(fr.codigo, '')""",
    "valor_atributo": """
        SELECT p.identificador_fiscal, f.numero, c.identificador_externo, a.codigo, v.valor_milesimas
        FROM valor_atributo AS v
        JOIN factura AS f ON f.factura_id = v.factura_id
        JOIN proveedor AS p ON p.proveedor_id = f.proveedor_id
        JOIN contrato AS c ON c.contrato_id = v.contrato_id
        JOIN atributo_contrato AS a ON a.atributo_contrato_id = v.atributo_contrato_id
        ORDER BY p.identificador_fiscal, f.numero, c.identificador_externo, a.codigo""",
}


def volcado_canonico(conexion: sqlite3.Connection) -> dict[str, list[tuple]]:
    """Las filas de cada tabla de datos, con claves naturales y en orden canónico."""
    return {tabla: conexion.execute(consulta).fetchall() for tabla, consulta in _CONSULTAS.items()}
