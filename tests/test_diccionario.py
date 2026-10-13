"""Diccionario: docs/diccionario.md coincide con el caso y los textos se traducen sin ambigüedad (R29-R31)."""

import re

import pytest

import caso
import datos_prueba
from facturas.bd.diccionario import RUTA_DICCIONARIO, generar
from facturas.carga.traduccion import ErrorTraduccion, normalizar, traducir


def _diccionario_publicado() -> dict[str, dict[str, str]]:
    """{categoría: {concepto: código}}, leído de docs/diccionario.md."""
    diccionario, categoria = {}, None
    for linea in RUTA_DICCIONARIO.read_text(encoding="utf-8").splitlines():
        if encabezado := re.fullmatch(r"## .* \(`(\w+)`\)", linea):
            categoria = encabezado.group(1)
            diccionario[categoria] = {}
        elif fila := re.fullmatch(r"\| (.+) \| `(\w+)` \|", linea):
            diccionario[categoria][fila.group(1)] = fila.group(2)
    return diccionario


def test_diccionario_publicado_esta_al_dia(base):
    assert RUTA_DICCIONARIO.read_text(encoding="utf-8") == generar(base), (
        "docs/diccionario.md no coincide con las semillas: regenerarlo con python -m facturas.bd.diccionario")


def test_diccionario_coincide_con_los_conceptos_del_caso():
    diccionario = _diccionario_publicado()
    cubiertos = set()
    for categoria, concepto_caso, _ in caso.clasificacion():
        # El caso agrega aclaraciones entre paréntesis: "Consumo de agua (por tramos)".
        nombre = re.sub(r" \(.*\)$", "", concepto_caso)
        # D2 (aprobado): "Canon del agua, parte fija" y "…, parte variable" son un solo concepto.
        candidatos = [c for c in diccionario[categoria] if nombre == c or nombre.startswith(f"{c}, ")]
        assert len(candidatos) == 1, (categoria, concepto_caso)
        cubiertos.add((categoria, candidatos[0]))
    # Ningún concepto del diccionario falta en el caso.
    assert cubiertos == {(cat, c) for cat, conceptos in diccionario.items() for c in conceptos}


def test_todos_los_conceptos_se_imputan_por_periodo_salvo_la_inspeccion_del_gas(base):
    # Caso: "Todos los conceptos de los ejemplos tienen imputación periodo". La inspección periódica del gas,
    # aprobada después por la persona usuaria, es puntual.
    filas = base.execute(
        "SELECT co.codigo, co.imputacion_defecto FROM concepto AS co WHERE co.imputacion_defecto <> 'periodo'"
    ).fetchall()
    assert filas == [("inspeccion_periodica", "puntual")]


def _concepto(conexion, concepto_id):
    return conexion.execute(
        "SELECT ca.codigo, co.codigo FROM concepto AS co JOIN categoria AS ca USING (categoria_id) WHERE concepto_id = ?",
        (concepto_id,)).fetchone()


def test_ningun_texto_de_los_ejemplos_es_ambiguo(base):
    for factura in datos_prueba.EJEMPLOS:
        for linea in factura["lineas"]:
            categoria = factura["contratos"][linea["contrato"]]
            concepto_id = traducir(base, categoria, linea["seccion"], linea["texto"])
            assert _concepto(base, concepto_id) == (categoria, linea["concepto"]), linea["texto"]


@pytest.mark.parametrize("categoria, seccion, texto, concepto", [
    ("agua", None, "Tramo de 15 a 20 m³", "consumo_agua"),
    ("agua", None, "IVA del 21% de la base sujeta", "iva"),
    ("gas", None, "IVA (5%)", "iva"),
    ("luz", None, "IVA (10%)", "iva"),
    # Cada texto se reconoce por sus palabras clave y se tolera cualquier detalle alrededor
    # (decisión de la persona usuaria en el punto de control del bloque 2).
    ("agua", None, "CANON DEL AGUA (*)", "canon_agua"),
    ("agua", None, "Canon del agua - ACA 2027", "canon_agua"),
    ("agua", None, "TASA DE RESIDUOS MUNICIPALES GENERADOS EN DOMICILIOS PARTICULARES", "residuos_municipales"),
    ("agua", None, "TASA METROPOLITANA DE TRATAMIENTO DE RESIDUOS MUNICIPALES (T.M.T.R)", "tmtr"),
    ("agua", None, "Tasa de alcantarillado (Àrea Metropolitana de Barcelona)", "alcantarillado"),
    ("agua", None, "Cuota de servicio", "cuota_servicio"),
    ("gas", None, "Término fijo (57 días)", "termino_fijo"),
    ("gas", None, "Impuesto especial hidrocarburos 2027", "impuesto_hidrocarburos"),
    ("gas", None, "Consumo de gas natural", "consumo_gas"),
    ("luz", None, "Término potencia P1 (4,4 kW x 33 días)", "potencia_p1"),
    ("luz", None, "Impuesto especial sobre la electricidad", "impuesto_electricidad"),
    ("luz", None, "Financiación del bono social fijo", "bono_social"),
    ("movil", "CONSUMO INCLUIDO EN EL PLAN", "Datos incluidos en tu producto", "consumo_incluido"),
    ("movil", "CONSUMO ADICIONAL", "Datos adicionales (01 Sep - 14 Sep)", "consumo_adicional"),
    ("movil", "CONSUMO ADICIONAL", "Roaming zona 1", "consumo_adicional"),
    ("movil", "PRODUCTOS", "50 GB + Ilimitadas (15 Ago - 14 Sep)", "cuota_plan"),
    ("fibra", "PRODUCTOS", "Fibra 1 Gb (15 Ago - 14 Sep)", "cuota_fibra"),
])
def test_partes_variables_no_generan_conceptos_nuevos(base, categoria, seccion, texto, concepto):
    assert _concepto(base, traducir(base, categoria, seccion, texto)) == (categoria, concepto)


@pytest.mark.parametrize("categoria, seccion, texto", [
    ("movil", "DESCUENTOS", "Descuento promoción (15 Jul - 14 Ago)"),
    ("movil", "OTROS CONCEPTOS", "Penalización permanencia (15 Jul - 14 Ago)"),
    ("movil", None, "100 GB + Ilimitadas (15 Jul - 14 Ago)"),  # un producto fuera de PRODUCTOS
    ("movil", None, "Llamadas"),
    ("agua", None, "Regularización de lecturas"),
    ("gas", None, "Cuota del servicio"),  # existe en agua, no en gas
    # Un cargo de otra naturaleza, sin ninguna palabra clave conocida, sigue sin traducirse.
    ("agua", None, "Recargo por demora"),
    ("agua", None, "Alta del suministro"),
    ("agua", None, "Fianza"),
    ("gas", None, "Alquiler de contador"),  # existe en la luz, no en el gas
])
def test_texto_sin_alias_se_rechaza_con_el_texto_en_el_motivo(base, categoria, seccion, texto):
    with pytest.raises(ErrorTraduccion, match="sin alias") as error:
        traducir(base, categoria, seccion, texto)
    assert repr(texto) in str(error.value)


def test_texto_ambiguo_se_rechaza(base):
    base.execute(
        """INSERT INTO alias_concepto (categoria_id, concepto_id, patron_seccion, patron_texto)
           SELECT categoria_id, concepto_id, '*', 'tramo de *' FROM concepto WHERE codigo = 'canon_agua'""")
    with pytest.raises(ErrorTraduccion, match="ambiguo"):
        traducir(base, "agua", None, "Tramo de 12 a 15 m³")


@pytest.mark.parametrize("texto, normalizado", [
    ("Tramo de 12 a 15 m³", "tramo de 12 a 15 m3"),
    ("  Término   fijo ", "termino fijo"),
    ("Financiación de Bono Social", "financiacion de bono social"),
    (None, ""),
])
def test_normalizar(texto, normalizado):
    assert normalizar(texto) == normalizado
