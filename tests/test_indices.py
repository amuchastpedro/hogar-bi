"""Índices (R38): cada clave foránea tiene el suyo y los recorridos completos que quedan están justificados.

Un recorrido completo se detecta en el bytecode de la sentencia (EXPLAIN): un
cursor que se abre sobre una tabla o un índice (OpenRead) y se rebobina al
principio (Rewind o Last). Así no depende de los alias que muestra EXPLAIN QUERY
PLAN, que en las vistas se repiten (por ejemplo, `c` es contrato o calendario).
"""

import json
import re
from pathlib import Path

import pytest

from facturas.bd.invariantes import verificar
from facturas.carga.traduccion import traducir

DIR_CONSULTAS = Path(__file__).resolve().parents[1] / "src" / "facturas" / "bd" / "consultas"

# Las únicas tablas que se recorren enteras, y por qué (docs/diseno.md, sección 6.3).
RECORRIDOS_JUSTIFICADOS = {
    "linea": "el prorrateo reparte todas las líneas por grupos; el mes sale del prorrateo, después",
    "medicion": "lo mismo, para las mediciones",
}


def recorridos(conexion, sql, parametros=()) -> set[str]:
    """Tablas que la sentencia recorre enteras (directamente o por uno de sus índices)."""
    tabla_de_raiz = dict(conexion.execute("SELECT rootpage, tbl_name FROM sqlite_schema WHERE rootpage > 0"))
    cursores, tablas = {}, set()
    for _, opcode, p1, p2, *_ in conexion.execute("EXPLAIN " + sql, parametros):
        if opcode == "OpenRead":
            cursores[p1] = tabla_de_raiz[p2]
        elif opcode in ("Rewind", "Last") and p1 in cursores:
            tablas.add(cursores[p1])
    return tablas


class Espia:
    """Conexión que anota las sentencias que se ejecutan con ella."""

    def __init__(self, conexion):
        self.conexion, self.sentencias = conexion, []

    def execute(self, sql, parametros=()):
        self.sentencias.append((sql, parametros))
        return self.conexion.execute(sql, parametros)


def cuerpo_de_trigger(conexion, trigger):
    """El cuerpo de un trigger, tal como está en la base, como sentencia suelta.

    NEW.x y OLD.x pasan a ser parámetros, y RAISE (que solo vale dentro de un
    trigger) pasa a ser 1. La condición WHEN, si la hay, se agrega como otra consulta.
    """
    (sql,) = conexion.execute("SELECT sql FROM sqlite_schema WHERE name = ?", (trigger,)).fetchone()
    cuerpo = re.search(r"\bBEGIN\b(.*);\s*END$", sql, re.DOTALL).group(1)
    cuerpo = re.sub(r"RAISE\(ABORT, '[^']*'\)", "1", cuerpo)
    if (condicion := re.search(r"\bWHEN\b(.*)\bBEGIN\b", sql, re.DOTALL)) is not None:
        cuerpo = f"SELECT ({condicion.group(1)}) UNION ALL {cuerpo}"
    cuerpo = re.sub(r"\b(?:NEW|OLD)\.(\w+)", r":\1", cuerpo)
    return cuerpo, dict.fromkeys(re.findall(r":(\w+)", cuerpo), 1)


def test_cada_clave_foranea_tiene_un_indice(base):
    sin_indice = []
    tablas = [t for (t,) in base.execute("SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    for tabla in tablas:
        # Un índice parcial no sirve para buscar las filas hijas de cualquier fila padre.
        indices = [
            [columna for _, _, columna in base.execute("SELECT * FROM pragma_index_info(?)", (nombre,))]
            for _, nombre, _, _, parcial in base.execute("SELECT * FROM pragma_index_list(?)", (tabla,))
            if not parcial
        ]
        claves = {}
        for fk_id, _, padre, desde, *_ in base.execute("SELECT * FROM pragma_foreign_key_list(?)", (tabla,)):
            claves.setdefault((fk_id, padre), []).append(desde)
        for (_, padre), columnas in claves.items():
            if not any(set(indice[:len(columnas)]) == set(columnas) for indice in indices):
                sin_indice.append(f"{tabla} ({', '.join(columnas)}) → {padre}")
    assert sin_indice == []


@pytest.mark.parametrize("archivo", sorted(DIR_CONSULTAS.glob("*.sql")), ids=lambda a: a.stem)
def test_consultas_de_referencia_solo_recorren_lo_justificado(base_ejemplos, archivo):
    parametros = {"categorias": json.dumps(["agua", "gas"]), "categoria": "luz",
                  "conceptos": json.dumps(["consumo_electricidad"]),
                  "mes_desde": "2026-01", "mes_hasta": "2026-12"}
    assert recorridos(base_ejemplos, archivo.read_text(encoding="utf-8"), parametros) <= set(RECORRIDOS_JUSTIFICADOS)


def test_invariantes_solo_recorren_lo_justificado(base_ejemplos):
    espia = Espia(base_ejemplos)
    verificar(espia, 1)
    consultas = [(sql, p) for sql, p in espia.sentencias if not sql.lstrip().startswith("PRAGMA")]
    assert len(consultas) == 9
    for sql, parametros in consultas:
        assert recorridos(base_ejemplos, sql, parametros) <= set(RECORRIDOS_JUSTIFICADOS), sql


def test_los_triggers_no_recorren_tablas(base_ejemplos):
    triggers = [t for (t,) in base_ejemplos.execute("SELECT name FROM sqlite_schema WHERE type = 'trigger'")]
    assert len(triggers) == 13
    for trigger in triggers:
        assert recorridos(base_ejemplos, *cuerpo_de_trigger(base_ejemplos, trigger)) == set(), trigger


@pytest.mark.parametrize("sql, parametros", [
    # Búsquedas de la carga (diseño, sección 6.2).
    ("SELECT carga_id FROM carga WHERE sha256 = ?", ("a" * 64,)),
    ("SELECT factura_id FROM factura WHERE proveedor_id = ? AND numero = ?", (1, "X")),
    ("SELECT contrato_id FROM contrato WHERE proveedor_id = ? AND identificador_externo = ?", (1, "X")),
    ("SELECT proveedor_id FROM proveedor WHERE identificador_fiscal = ?", ("A84919760",)),
    ("SELECT linea_id FROM linea WHERE factura_id = ?", (1,)),
    ("SELECT medicion_id FROM medicion WHERE factura_id = ?", (1,)),
    ("SELECT valor_atributo_id FROM valor_atributo WHERE factura_id = ?", (1,)),
])
def test_busquedas_de_la_carga_usan_indices(base_ejemplos, sql, parametros):
    assert recorridos(base_ejemplos, sql, parametros) == set()


def test_la_traduccion_usa_indices(base_ejemplos):
    espia = Espia(base_ejemplos)
    traducir(espia, "movil", "PRODUCTOS", "100 GB + Ilimitadas (15 Jul - 14 Ago)")
    ((sql, parametros),) = espia.sentencias
    assert recorridos(base_ejemplos, sql, parametros) == set()


def test_el_detector_ve_un_recorrido_completo(base_ejemplos):
    # Control del propio detector: filtrar por una columna sin índice recorre la tabla.
    assert recorridos(base_ejemplos, "SELECT * FROM factura WHERE importe_total_centimos = 1") == {"factura"}
