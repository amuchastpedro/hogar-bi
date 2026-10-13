"""La factura extraída: validación de forma (diseño, 11.6) y serialización (11.1 a 11.5)."""

import copy
import json

import pytest

from facturas.extraccion import ErrorExtraccion, FacturaExtraida, verificar_opcionales

# La factura extraída de fibra_movil.pdf del diseño, sección 16.1 (identificadores e importes ficticios).
EJEMPLO = {
    "formato": "digi_convergente",
    "version_parser": "1.0.0",
    "identificador_fiscal": "A84919760",
    "numero": "DIGI-0001",
    "tipo": "ordinaria",
    "numero_factura_corregida": None,
    "moneda": "EUR",
    "fecha_emision": "2026-08-21",
    "fecha_vencimiento": "2026-08-28",
    "periodo": {"inicio": "2026-07-15", "fin": "2026-08-14"},
    "importe_total_centimos": 2979,
    "contratos": [
        {"identificador_externo": "MOVIL-FICTICIO", "categoria": "movil", "atributos": []},
        {"identificador_externo": "FIBRA-FICTICIA", "categoria": "fibra", "atributos": []},
    ],
    "totales_repartidos": [{"texto": "IMPUESTOS (21.00% IVA)", "importe_centimos": 517}],
    "lineas": [
        {"posicion": 1, "contrato": "MOVIL-FICTICIO", "seccion": "PRODUCTOS", "texto": "100 GB + Ilimitadas (15 Jul - 14 Ago)",
         "importe_centimos": 615, "periodo": None, "imputacion": None, "derivada_de": None},
        {"posicion": 2, "contrato": "MOVIL-FICTICIO", "seccion": "CONSUMO INCLUIDO EN EL PLAN",
         "texto": "Llamadas incluidas en tu producto", "importe_centimos": 0, "periodo": None, "imputacion": None,
         "derivada_de": None},
        {"posicion": 3, "contrato": "MOVIL-FICTICIO", "seccion": "CONSUMO ADICIONAL", "texto": "SMS",
         "importe_centimos": 7, "periodo": None, "imputacion": None, "derivada_de": None},
        {"posicion": 4, "contrato": "MOVIL-FICTICIO", "seccion": None, "texto": "IMPUESTOS (21.00% IVA)",
         "importe_centimos": 131, "periodo": None, "imputacion": None, "derivada_de": "IMPUESTOS (21.00% IVA)"},
        {"posicion": 5, "contrato": "FIBRA-FICTICIA", "seccion": "PRODUCTOS",
         "texto": "Fibra PRO-DIGI 10 Gb (15 Jul - 14 Ago)", "importe_centimos": 1840, "periodo": None,
         "imputacion": None, "derivada_de": None},
        {"posicion": 6, "contrato": "FIBRA-FICTICIA", "seccion": None, "texto": "IMPUESTOS (21.00% IVA)",
         "importe_centimos": 386, "periodo": None, "imputacion": None, "derivada_de": "IMPUESTOS (21.00% IVA)"},
    ],
    "mediciones": [],
}

MEDICION_GAS = {
    "contrato": "MOVIL-FICTICIO", "magnitud": "energia", "franja": None, "cantidad": "344",
    "cantidad_contador": "30", "factor_conversion": "11.470",
    "lectura": {"fecha": "2026-06-25", "valor": "15577", "tipo": "estimada"},
}


def con(**cambios) -> dict:
    datos = copy.deepcopy(EJEMPLO)
    datos.update(cambios)
    return datos


def con_linea(numero_de_linea: int, **cambios) -> dict:
    datos = copy.deepcopy(EJEMPLO)
    datos["lineas"][numero_de_linea - 1].update(cambios)
    return datos


def test_el_ejemplo_del_diseno_es_valido_y_se_serializa_igual():
    factura = FacturaExtraida.desde_dict(EJEMPLO)
    assert json.loads(factura.a_json()) == EJEMPLO


def test_el_json_se_reconstruye_con_mediciones():
    datos = con(mediciones=[MEDICION_GAS])
    factura = FacturaExtraida.desde_json(json.dumps(datos))
    assert factura.mediciones[0].lectura.tipo == "estimada"
    assert FacturaExtraida.desde_json(factura.a_json()) == factura


CASOS_INVALIDOS = {
    "falta un campo obligatorio": (con(numero=None), "numero"),
    "texto vacío": (con(numero="  "), "numero"),
    "NIF con guion": (con(identificador_fiscal="A-84919760"), "identificador_fiscal"),
    "tipo desconocido": (con(tipo="proforma"), "tipo"),
    "ordinaria con factura corregida": (con(numero_factura_corregida="X-1"), "numero_factura_corregida"),
    "rectificativa sin factura corregida": (con(tipo="abono"), "numero_factura_corregida"),
    "moneda en minúsculas": (con(moneda="eur"), "moneda"),
    "fecha inexistente": (con(fecha_emision="2026-02-30"), "fecha_emision"),
    "fecha con otro formato": (con(fecha_emision="21/08/2026"), "fecha_emision"),
    "vencimiento inválido": (con(fecha_vencimiento="mañana"), "fecha_vencimiento"),
    "período invertido": (con(periodo={"inicio": "2026-08-14", "fin": "2026-07-15"}), "empieza"),
    "importe con decimales": (con(importe_total_centimos=29.79), "importe_total_centimos"),
    "importe booleano": (con(importe_total_centimos=True), "importe_total_centimos"),
    "sin contratos": (con(contratos=[]), "contrato"),
    "sin líneas": (con(lineas=[]), "línea"),
    "contrato repetido": (
        con(contratos=[EJEMPLO["contratos"][0], EJEMPLO["contratos"][0]]), "mismo identificador",
    ),
    "hueco en las posiciones": (con_linea(6, posicion=7), "posiciones"),
    "línea de un contrato no declarado": (con_linea(1, contrato="OTRO"), "no está declarado"),
    "imputación desconocida": (con_linea(1, imputacion="siempre"), "imputación"),
    "línea derivada de un total inexistente": (con_linea(1, derivada_de="NO EXISTE"), "no es un total repartido"),
    # I8 admite 10 céntimos de diferencia (redondeo de Digi): 11 ya no.
    "derivadas que no suman el total": (con_linea(4, importe_centimos=142), "suman"),
    "totales con el mismo texto": (
        con(totales_repartidos=[EJEMPLO["totales_repartidos"][0]] * 2), "mismo texto",
    ),
    "medición con decimal con coma": (
        con(mediciones=[{**MEDICION_GAS, "factor_conversion": "11,470"}]), "factor_conversion",
    ),
    "medición con unidad en la cantidad": (con(mediciones=[{**MEDICION_GAS, "cantidad": "344 kWh"}]), "cantidad"),
    "cantidad del contador sin factor": (
        con(mediciones=[{**MEDICION_GAS, "factor_conversion": None}]), "van juntos",
    ),
    "tipo de lectura desconocido": (
        con(mediciones=[{**MEDICION_GAS, "lectura": {"fecha": "2026-06-25", "valor": "1", "tipo": "supuesta"}}]),
        "real o estimada",
    ),
    "medición de un contrato no declarado": (
        con(mediciones=[{**MEDICION_GAS, "contrato": "OTRO"}]), "no está declarado",
    ),
    "mediciones con y sin franja": (
        con(mediciones=[
            {**MEDICION_GAS, "cantidad_contador": None, "factor_conversion": None},
            {**MEDICION_GAS, "cantidad_contador": None, "factor_conversion": None, "franja": "punta"},
        ]),
        "con y sin franja",
    ),
    "atributo no decimal": (
        con(contratos=[{**EJEMPLO["contratos"][0], "atributos": [{"atributo": "potencia_p1", "valor": "4,4"}]},
                       EJEMPLO["contratos"][1]]),
        "potencia_p1",
    ),
}


@pytest.mark.parametrize("datos, fragmento", CASOS_INVALIDOS.values(), ids=CASOS_INVALIDOS.keys())
def test_forma_invalida_se_rechaza_nombrando_el_campo(datos, fragmento):
    with pytest.raises(ErrorExtraccion, match=fragmento):
        FacturaExtraida.desde_dict(datos)


def test_una_estructura_sin_la_forma_del_contrato_es_un_error_claro():
    sin_lineas = {k: v for k, v in EJEMPLO.items() if k != "lineas"}
    with pytest.raises(ErrorExtraccion, match="forma"):
        FacturaExtraida.desde_dict(sin_lineas)
    with pytest.raises(ErrorExtraccion, match="JSON"):
        FacturaExtraida.desde_json("{no es json")
    with pytest.raises(ErrorExtraccion, match="objeto"):
        FacturaExtraida.desde_json("[]")


def test_los_campos_opcionales_que_el_formato_imprime_tienen_que_estar():
    factura = FacturaExtraida.desde_dict(EJEMPLO)
    verificar_opcionales(factura, ("fecha_vencimiento", "seccion"))

    sin_vencimiento = FacturaExtraida.desde_dict(con(fecha_vencimiento=None))
    with pytest.raises(ErrorExtraccion, match="digi_convergente.*fecha_vencimiento"):
        verificar_opcionales(sin_vencimiento, ("fecha_vencimiento",))

    sin_seccion = FacturaExtraida.desde_dict(con_linea(1, seccion=None))
    with pytest.raises(ErrorExtraccion, match="seccion"):
        verificar_opcionales(sin_seccion, ("seccion",))

    with pytest.raises(ErrorExtraccion, match="franja"):  # sin mediciones no hay franja que imprimir
        verificar_opcionales(factura, ("franja",))
    with pytest.raises(ErrorExtraccion, match="atributo:potencia_p1"):
        verificar_opcionales(factura, ("atributo:potencia_p1",))
    with pytest.raises(ValueError):
        verificar_opcionales(factura, ("campo_inventado",))


def test_derivadas_que_difieren_del_total_hasta_10_centimos_se_aceptan():
    # Redondeo de Digi (jul 2025): el IVA derivado por servicio y el impreso difieren en 1 céntimo.
    FacturaExtraida.desde_dict(con_linea(4, importe_centimos=132))
    FacturaExtraida.desde_dict(con_linea(4, importe_centimos=141))
