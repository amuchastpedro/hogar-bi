"""Facturas de prueba: los cuatro ejemplos del caso, escritos a mano, con importes ficticios.

Tienen la forma de los "Valores esperados de los ejemplos" de `caso_hogar.md`: las
mismas líneas, conceptos, fechas y mediciones, con los desvíos aprobados en el bloque 1:
- D1: las líneas guardan solo texto e importe;
- D2 y D3: el canon y el alcantarillado del agua van como su subtotal impreso;
- D5: cada medición guarda solo la lectura de cierre.

Los importes son inventados, porque los reales no se versionan (están en
`ejemplos/valores_esperados.md`, para los tests que leen los PDFs). Son coherentes:
las líneas suman el total y el IVA de Digi suma lo repartido. Sus controles de
prorrateo están en `CONTROLES`, calculados a mano como en el caso.

Los números de factura y los identificadores de contrato también son ficticios, y
las lecturas de cierre de la luz, porque el caso no las da.

Se insertan directamente en la base, sin pasar por parsers ni por la carga
(bloque 4): `insertar()` resuelve los códigos a ids y escribe las filas en una
transacción.
"""

import copy
import hashlib
import json
import sqlite3

NIF_AIGUES, NIF_NATURGY, NIF_DIGI = "A66098435", "A67760876", "A84919760"


def linea(contrato, concepto, texto, importe, seccion=None, derivada=False, imputacion="periodo", periodo=None):
    return {
        "contrato": contrato, "concepto": concepto, "texto": texto, "importe": importe,
        "seccion": seccion, "derivada": derivada, "imputacion": imputacion, "periodo": periodo,
    }


def medicion(contrato, magnitud, cantidad, fecha_lectura, lectura, tipo_lectura, franja=None,
             cantidad_contador=None, factor=None):
    return {
        "contrato": contrato, "magnitud": magnitud, "franja": franja, "cantidad": cantidad,
        "cantidad_contador": cantidad_contador, "factor": factor,
        "fecha_lectura": fecha_lectura, "lectura": lectura, "tipo_lectura": tipo_lectura,
    }


def factura(proveedor, numero, emision, inicio, fin, total, contratos, lineas, mediciones=(),
            atributos=(), totales_repartidos=(), tipo="ordinaria", corregida=None,
            vencimiento=None, moneda="EUR", formato="prueba"):
    return {
        "proveedor": proveedor, "numero": numero, "tipo": tipo, "corregida": corregida,
        "moneda": moneda, "emision": emision, "vencimiento": vencimiento,
        "inicio": inicio, "fin": fin, "total": total, "contratos": contratos,
        "lineas": list(lineas), "mediciones": list(mediciones), "atributos": list(atributos),
        "totales_repartidos": list(totales_repartidos), "formato": formato,
    }


# Importes en céntimos; cantidades y lecturas en milésimas de su unidad.

FACTURA_AGUA = factura(
    NIF_AIGUES, "AGUA-PRUEBA-1", "2026-06-23", "2026-04-10", "2026-06-08", 6718,
    contratos={"CONTRATO-AGUA-PRUEBA": "agua"},
    lineas=[
        linea("CONTRATO-AGUA-PRUEBA", "cuota_servicio", "Cuota del servicio", 1523),
        linea("CONTRATO-AGUA-PRUEBA", "consumo_agua", "Tramo hasta 12 m³", 1104),
        linea("CONTRATO-AGUA-PRUEBA", "consumo_agua", "Tramo de 12 a 15 m³", 372),
        # D2: parte fija más parte variable, en una sola línea.
        linea("CONTRATO-AGUA-PRUEBA", "canon_agua", "CANON DEL AGUA(*)", 812),
        linea("CONTRATO-AGUA-PRUEBA", "iva", "IVA del 10% de la base sujeta", 300),
        linea("CONTRATO-AGUA-PRUEBA", "alcantarillado",
              "TASA DE ALCANTARILLADO (Ayuntamiento de Barcelona P0801900B)", 389),
        linea("CONTRATO-AGUA-PRUEBA", "residuos_municipales",
              "TASA DE RECOGIDA RESIDUOS MUNICIPALES GENERADOS EN LOS DOMICILIOS", 1250),
        linea("CONTRATO-AGUA-PRUEBA", "tmtr",
              "TASA METROPOLITANA TRATAMIENTO RESIDUOS MUNICIPALES (T.M.T.R.)", 968),
    ],
    mediciones=[medicion("CONTRATO-AGUA-PRUEBA", "volumen", 15000, "2026-06-08", 657000, "real")],
)

FACTURA_GAS = factura(
    NIF_NATURGY, "GAS-PRUEBA-1", "2026-06-29", "2026-04-30", "2026-06-25", 4271,
    contratos={"CUPS-GAS-PRUEBA": "gas"},
    lineas=[
        linea("CUPS-GAS-PRUEBA", "consumo_gas", "Consumo gas", 2412),
        linea("CUPS-GAS-PRUEBA", "impuesto_hidrocarburos", "Impuesto Especial sobre hidrocarburos", 41),
        linea("CUPS-GAS-PRUEBA", "termino_fijo", "Término fijo", 1077),
        linea("CUPS-GAS-PRUEBA", "iva", "IVA (21%)", 741),
    ],
    mediciones=[
        medicion("CUPS-GAS-PRUEBA", "energia", 344000, "2026-06-25", 15577000, "estimada",
                 cantidad_contador=30000, factor="11.470"),
    ],
)

FACTURA_LUZ = factura(
    NIF_NATURGY, "LUZ-PRUEBA-1", "2026-07-03", "2026-05-27", "2026-06-28", 4279,
    contratos={"CUPS-LUZ-PRUEBA": "luz"},
    lineas=[
        linea("CUPS-LUZ-PRUEBA", "consumo_electricidad", "Consumo electricidad", 1253),
        linea("CUPS-LUZ-PRUEBA", "potencia_p1", "Término potencia P1", 1388),
        linea("CUPS-LUZ-PRUEBA", "potencia_p2", "Término potencia P2", 562),
        linea("CUPS-LUZ-PRUEBA", "bono_social", "Financiación de Bono Social", 71),
        linea("CUPS-LUZ-PRUEBA", "impuesto_electricidad", "Impuesto electricidad", 167),
        linea("CUPS-LUZ-PRUEBA", "alquiler_contador", "Alquiler de contador", 95),
        linea("CUPS-LUZ-PRUEBA", "iva", "IVA (21%)", 743),
    ],
    mediciones=[
        medicion("CUPS-LUZ-PRUEBA", "energia", 20000, "2026-06-28", 3020000, "real", franja="punta"),
        medicion("CUPS-LUZ-PRUEBA", "energia", 21000, "2026-06-28", 3521000, "real", franja="llano"),
        medicion("CUPS-LUZ-PRUEBA", "energia", 40000, "2026-06-28", 6040000, "real", franja="valle"),
    ],
    atributos=[("CUPS-LUZ-PRUEBA", "potencia_p1", 4400), ("CUPS-LUZ-PRUEBA", "potencia_p2", 4400)],
)

IVA_DIGI = "IMPUESTOS (21.00% IVA)"
FACTURA_DIGI = factura(
    NIF_DIGI, "DIGI-PRUEBA-1", "2026-08-21", "2026-07-15", "2026-08-14", 2979,
    vencimiento="2026-08-28",
    contratos={"LINEA-MOVIL-PRUEBA": "movil", "FIBRA-PRUEBA": "fibra"},
    totales_repartidos=[(IVA_DIGI, 517)],
    lineas=[
        linea("LINEA-MOVIL-PRUEBA", "cuota_plan", "100 GB + Ilimitadas (15 Jul - 14 Ago)", 615,
              seccion="PRODUCTOS"),
        linea("LINEA-MOVIL-PRUEBA", "consumo_incluido", "Llamadas incluidas en tu producto", 0,
              seccion="CONSUMO INCLUIDO EN EL PLAN"),
        linea("LINEA-MOVIL-PRUEBA", "consumo_adicional", "SMS", 7, seccion="CONSUMO ADICIONAL"),
        linea("LINEA-MOVIL-PRUEBA", "iva", IVA_DIGI, 131, derivada=True),
        linea("FIBRA-PRUEBA", "cuota_fibra", "Fibra PRO-DIGI 10 Gb (15 Jul - 14 Ago)", 1840,
              seccion="PRODUCTOS"),
        linea("FIBRA-PRUEBA", "iva", IVA_DIGI, 386, derivada=True),
    ],
)

EJEMPLOS = (FACTURA_AGUA, FACTURA_GAS, FACTURA_LUZ, FACTURA_DIGI)

# Controles de prorrateo de los cuatro ejemplos ficticios, como los del caso: el total de cada
# categoría y su reparto por mes (importe × días del mes ÷ días del período, redondeado; ±1 céntimo).
# agua 67,18 (60 días): abril 21 → 23,51 · mayo 31 → 34,71 · junio 8 → 8,96
# gas 42,71 (57 días): abril 1 → 0,75 · mayo 31 → 23,23 · junio 25 → 18,73
# luz 42,79 (33 días): mayo 5 → 6,48 · junio 28 → 36,31
# movil 7,53 y fibra 22,26 (31 días): julio 17 → 4,13 y 12,21 · agosto 14 → 3,40 y 10,05
CONTROLES = (
    {"agua": 6718, "gas": 4271, "luz": 4279, "movil": 753, "fibra": 2226},
    {
        ("agua", "2026-04"): 2351, ("agua", "2026-05"): 3471, ("agua", "2026-06"): 896,
        ("gas", "2026-04"): 75, ("gas", "2026-05"): 2323, ("gas", "2026-06"): 1873,
        ("luz", "2026-05"): 648, ("luz", "2026-06"): 3631,
        ("movil", "2026-07"): 413, ("movil", "2026-08"): 340,
        ("fibra", "2026-07"): 1221, ("fibra", "2026-08"): 1005,
    },
)


def variante(original, numero, emision, inicio, fin, contratos=None, lineas=None, mediciones=None):
    """Otra factura del mismo servicio: copia de un ejemplo con otro número y otras fechas."""
    f = copy.deepcopy(original)
    f.update(numero=numero, emision=emision, inicio=inicio, fin=fin)
    if contratos is not None:
        f["contratos"] = contratos
    if lineas is not None:
        f["lineas"] = lineas
    if mediciones is not None:
        f["mediciones"] = mediciones
    f["total"] = sum(l["importe"] for l in f["lineas"])
    return f


# Agua, segundo período (contiguo al ejemplo), con otro contrato: 18 m³ y otros importes.
AGUA_2 = "CONTRATO-AGUA-PRUEBA-2"
FACTURA_AGUA_2 = variante(
    FACTURA_AGUA, "AGUA-PRUEBA-2", "2026-08-20", "2026-06-09", "2026-08-07",
    contratos={AGUA_2: "agua"},
    lineas=[
        linea(AGUA_2, "cuota_servicio", "Cuota del servicio", 1523),
        linea(AGUA_2, "consumo_agua", "Tramo hasta 12 m³", 1104),
        linea(AGUA_2, "consumo_agua", "Tramo de 12 a 18 m³", 744),
        linea(AGUA_2, "canon_agua", "CANON DEL AGUA(*)", 1250),
        linea(AGUA_2, "iva", "IVA del 10% de la base sujeta", 337),
        linea(AGUA_2, "alcantarillado", "TASA DE ALCANTARILLADO", 467),
        linea(AGUA_2, "residuos_municipales", "TASA DE RECOGIDA RESIDUOS", 1250),
        linea(AGUA_2, "tmtr", "TASA METROPOLITANA TRATAMIENTO RESIDUOS", 968),
    ],
    mediciones=[medicion(AGUA_2, "volumen", 18000, "2026-08-07", 675000, "real")],
)  # total 7643

GAS = "CUPS-GAS-PRUEBA"
FACTURA_GAS_2 = variante(
    FACTURA_GAS, "GAS-PRUEBA-2", "2026-08-30", "2026-06-26", "2026-08-25",
    lineas=[
        linea(GAS, "consumo_gas", "Consumo gas", 1350),
        linea(GAS, "impuesto_hidrocarburos", "Impuesto Especial sobre hidrocarburos", 22),
        linea(GAS, "termino_fijo", "Término fijo", 1077),
        linea(GAS, "iva", "IVA (21%)", 514),
    ],
    mediciones=[medicion(GAS, "energia", 183520, "2026-08-25", 15760520, "real",
                         cantidad_contador=16000, factor="11.470")],
)  # total 2963

# Rectificativa por diferencias del gas del ejemplo: 1 m³ (11,47 kWh) real menos.
RECTIFICATIVA_GAS = variante(
    FACTURA_GAS, "GAS-PRUEBA-1R", "2026-07-15", FACTURA_GAS["inicio"], FACTURA_GAS["fin"],
    lineas=[linea(GAS, "consumo_gas", "Consumo gas", -912), linea(GAS, "iva", "IVA (21%)", -192)],
    mediciones=[medicion(GAS, "energia", -11470, "2026-06-25", 15565530, "real",
                         cantidad_contador=-1000, factor="11.470")],
)
RECTIFICATIVA_GAS.update(tipo="rectificativa_diferencias", corregida="GAS-PRUEBA-1")  # total -1104


def abono_de(factura, numero):
    """El abono que anula `factura`: la misma factura con el signo cambiado, también en el consumo."""
    abono = copy.deepcopy(factura)
    abono.update(numero=numero, tipo="abono", corregida=factura["numero"], total=-factura["total"])
    for linea in abono["lineas"]:
        linea["importe"] = -linea["importe"]
    for medicion in abono["mediciones"]:
        medicion["cantidad"] = -medicion["cantidad"]
        if medicion["cantidad_contador"] is not None:
            medicion["cantidad_contador"] = -medicion["cantidad_contador"]
    return abono

# Cobertura de los controles del caso ("Controles de prorrateo y cobertura"):
# (categoría, mes) -> (días cubiertos, días esperados).
COBERTURA_CASO = {
    ("agua", "2026-05"): (31, 31), ("gas", "2026-05"): (31, 31), ("luz", "2026-05"): (5, 31),
    ("agua", "2026-06"): (8, 30), ("gas", "2026-06"): (25, 30), ("luz", "2026-06"): (28, 30),
}


def insertar(conexion: sqlite3.Connection, f: dict) -> int:
    """Inserta una factura de prueba en una transacción y devuelve su factura_id."""
    conexion.execute("BEGIN IMMEDIATE")
    try:
        factura_id = insertar_filas(conexion, f)
    except BaseException:
        conexion.execute("ROLLBACK")
        raise
    conexion.execute("COMMIT")
    return factura_id


def _uno(conexion, sql, parametros):
    """El único valor que devuelve la sentencia. fetchall() termina de ejecutarla (RETURNING)."""
    (fila,) = conexion.execute(sql, parametros).fetchall()
    return fila[0]


def insertar_filas(conexion, f):
    """Escribe las filas de una factura de prueba en la transacción en curso; no confirma."""
    extraccion = {"totales_repartidos": [{"texto": t, "importe_centimos": i} for t, i in f["totales_repartidos"]]}
    carga_id = _uno(
        conexion,
        """INSERT INTO carga (sha256, nombre_archivo, formato, version_parser, fecha_hora, estado, extraccion_json)
           VALUES (?, ?, ?, 'prueba', '2026-10-02 12:00:00', 'cargada', ?) RETURNING carga_id""",
        # El "PDF" de una factura de prueba es su contenido: dos facturas distintas, dos hashes.
        (hashlib.sha256(json.dumps(f, sort_keys=True).encode()).hexdigest(), f"{f['numero']}.pdf", f["formato"],
         json.dumps(extraccion)),
    )
    proveedor_id = _uno(conexion, "SELECT proveedor_id FROM proveedor WHERE identificador_fiscal = ?",
                        (f["proveedor"],))
    contratos = {
        externo: _contrato(conexion, proveedor_id, externo, categoria)
        for externo, categoria in f["contratos"].items()
    }
    factura_id = _uno(
        conexion,
        """INSERT INTO factura (carga_id, proveedor_id, moneda_id, numero, tipo, numero_factura_corregida,
                                fecha_emision, fecha_vencimiento, fecha_inicio, fecha_fin, importe_total_centimos)
           VALUES (?, ?, (SELECT moneda_id FROM moneda WHERE codigo = ?), ?, ?, ?, ?, ?, ?, ?, ?)
           RETURNING factura_id""",
        (carga_id, proveedor_id, f["moneda"], f["numero"], f["tipo"], f["corregida"], f["emision"],
         f["vencimiento"], f["inicio"], f["fin"], f["total"]),
    )
    for posicion, l in enumerate(f["lineas"], start=1):
        contrato_id, categoria_id = contratos[l["contrato"]]
        inicio, fin = l["periodo"] or (f["inicio"], f["fin"])
        conexion.execute(
            """INSERT INTO linea (factura_id, posicion, contrato_id, categoria_id, concepto_id, texto,
                                  importe_centimos, imputacion, fecha_inicio, fecha_fin, es_derivada)
               VALUES (?, ?, ?, ?, (SELECT concepto_id FROM concepto WHERE categoria_id = ? AND codigo = ?),
                       ?, ?, ?, ?, ?, ?)""",
            (factura_id, posicion, contrato_id, categoria_id, categoria_id, l["concepto"], l["texto"],
             l["importe"], l["imputacion"], inicio, fin, int(l["derivada"])),
        )
    for m in f["mediciones"]:
        contrato_id, categoria_id = contratos[m["contrato"]]
        conexion.execute(
            """INSERT INTO medicion (factura_id, contrato_id, categoria_id, magnitud_categoria_id, franja_id,
                                     cantidad_milesimas, cantidad_contador_milesimas, factor_conversion,
                                     fecha_lectura, lectura_milesimas, tipo_lectura)
               VALUES (?, ?, ?,
                       (SELECT magnitud_categoria_id FROM magnitud_categoria
                        WHERE categoria_id = ? AND magnitud_id = (SELECT magnitud_id FROM magnitud WHERE codigo = ?)),
                       (SELECT franja_id FROM franja WHERE codigo = ?), ?, ?, ?, ?, ?, ?)""",
            (factura_id, contrato_id, categoria_id, categoria_id, m["magnitud"], m["franja"], m["cantidad"],
             m["cantidad_contador"], m["factor"], m["fecha_lectura"], m["lectura"], m["tipo_lectura"]),
        )
    for externo, atributo, valor in f["atributos"]:
        contrato_id, categoria_id = contratos[externo]
        conexion.execute(
            """INSERT INTO valor_atributo (factura_id, contrato_id, categoria_id, atributo_contrato_id, valor_milesimas)
               VALUES (?, ?, ?, (SELECT atributo_contrato_id FROM atributo_contrato
                                 WHERE categoria_id = ? AND codigo = ?), ?)""",
            (factura_id, contrato_id, categoria_id, categoria_id, atributo, valor),
        )
    return factura_id


def _contrato(conexion, proveedor_id, externo, categoria):
    """(contrato_id, categoria_id) del contrato; lo registra si es nuevo, con alias "<categoría> <n>"."""
    categoria_id = _uno(conexion, "SELECT categoria_id FROM categoria WHERE codigo = ?", (categoria,))
    fila = conexion.execute(
        "SELECT contrato_id, categoria_id FROM contrato WHERE proveedor_id = ? AND identificador_externo = ?",
        (proveedor_id, externo),
    ).fetchone()
    if fila is not None:
        return fila
    numero = _uno(conexion, "SELECT count(*) + 1 FROM contrato WHERE categoria_id = ?", (categoria_id,))
    return conexion.execute(
        """INSERT INTO contrato (proveedor_id, categoria_id, identificador_externo, alias)
           VALUES (?, ?, ?, ?) RETURNING contrato_id, categoria_id""",
        (proveedor_id, categoria_id, externo, f"{categoria} {numero}"),
    ).fetchall()[0]
