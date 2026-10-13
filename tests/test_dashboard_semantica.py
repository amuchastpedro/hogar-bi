"""Capa semántica del dashboard: el TOML, sus validaciones y la combinación de la cobertura."""

import re

import pytest

from facturas.dashboard import semantica
from facturas.dashboard.datos import CoberturaMes
from facturas.dashboard.semantica import SIN_CLASIFICAR, ErrorSemantica

# Un TOML mínimo y válido: solo el agua, con dos de sus conceptos.
MINIMO = """
[agua]
nombre = "Water"
magnitud = "volumen"
variables = ["consumo_agua"]

[agua.grupos.ciclo]
nombre = "Water cycle"

[agua.grupos.ciclo.conceptos]
cuota_servicio = "Service fee"
consumo_agua = "Water consumption"
"""


def _cargar(tmp_path, texto):
    ruta = tmp_path / "semantica.toml"
    ruta.write_text(texto, encoding="utf-8")
    return semantica.cargar(ruta)


def test_el_toml_del_proyecto_clasifica_todos_los_conceptos_de_la_base(base_ejemplos):
    sem = semantica.cargar()
    assert semantica.validar(sem, base_ejemplos) == []
    # No solo los de los ejemplos: todos los del diccionario tienen grupo.
    for categoria, concepto in base_ejemplos.execute("SELECT categoria_codigo, concepto_codigo FROM v_dim_concepto"):
        assert sem[categoria].grupo_de(concepto) != SIN_CLASIFICAR, (categoria, concepto)


def test_grupos_y_conceptos_conservan_el_orden_del_toml(tmp_path):
    sem = _cargar(tmp_path, MINIMO + '\n[agua.grupos.residuos]\nnombre = "Waste"\n'
                  '[agua.grupos.residuos.conceptos]\ntmtr = "TMTR"\n')
    agua = sem["agua"]
    assert [g.codigo for g in agua.grupos] == ["ciclo", "residuos"]
    assert list(agua.grupos[0].conceptos) == ["cuota_servicio", "consumo_agua"]
    assert agua.grupo_de("tmtr") == "residuos"
    assert agua.nombre_grupo(SIN_CLASIFICAR) == "Unclassified"
    assert agua.variables == {"consumo_agua"}


def test_un_concepto_sin_grupo_no_es_un_error_sino_un_aviso(tmp_path, base_ejemplos):
    sin_clasificar = semantica.validar(_cargar(tmp_path, MINIMO), base_ejemplos)
    agua = [(f.concepto, f.concepto_nombre) for f in sin_clasificar if f.categoria == "agua"]
    assert ("tmtr", "Tasa metropolitana de tratamiento de residuos") in agua
    assert ("consumo_agua", "Consumo de agua") not in agua
    # Una categoría que no está en el TOML: todos sus conceptos, sin grupo.
    assert {f.concepto for f in sin_clasificar if f.categoria == "gas"} == {
        "consumo_gas", "impuesto_hidrocarburos", "termino_fijo", "iva"}


@pytest.mark.parametrize("texto, mensaje", [
    (MINIMO + '\n[agua.grupos.otro]\nnombre = "Other"\n[agua.grupos.otro.conceptos]\nconsumo_agua = "x"\n',
     "El concepto 'consumo_agua' de la categoría 'agua' está en dos grupos: 'ciclo' y 'otro'"),
    (MINIMO.replace('variables = ["consumo_agua"]', 'variables = ["canon_agua"]'),
     "El concepto variable 'canon_agua' de la categoría 'agua' no está en ningún grupo"),
    (MINIMO.replace('magnitud = "volumen"\n', ""),
     "Categoría 'agua': tiene conceptos variables pero no magnitud"),
    (MINIMO.replace('variables =', 'variable ='),
     "Categoría 'agua': claves desconocidas ['variable']"),
    (MINIMO.replace('nombre = "Water cycle"\n', ""),
     "Grupo 'ciclo' de la categoría 'agua': falta el nombre"),
    (MINIMO + "\n[luz]\nnombre = 'Electricity'\n", "Categoría 'luz': no tiene grupos"),
    (MINIMO.replace('consumo_agua = "Water consumption"', 'consumo_agua = ""'),
     "El concepto 'consumo_agua' de la categoría 'agua': falta el nombre"),
    (MINIMO + "\n[agua", "no es un TOML válido"),
])
def test_incoherencias_del_toml(tmp_path, texto, mensaje):
    with pytest.raises(ErrorSemantica, match=re.escape(mensaje)):
        _cargar(tmp_path, texto)


@pytest.mark.parametrize("cambio, mensaje", [
    (("cuota_servicio =", "cuota_inventada ="),
     "El concepto 'cuota_inventada' de la categoría 'agua' no existe en la base"),
    (("[agua", "[aguas"), "La categoría 'aguas' de semantica.toml no existe en la base"),
    (('magnitud = "volumen"', 'magnitud = "energia"'),
     "La magnitud 'energia' de la categoría 'agua' no aparece en sus mediciones (hay ['volumen'])"),
])
def test_codigos_que_no_existen_en_la_base(tmp_path, base_ejemplos, cambio, mensaje):
    sem = _cargar(tmp_path, MINIMO.replace(*cambio))
    with pytest.raises(ErrorSemantica, match=re.escape(mensaje)):
        semantica.validar(sem, base_ejemplos)


def test_magnitud_sin_mediciones_no_se_puede_comprobar_y_se_acepta(tmp_path, base):
    sem = _cargar(tmp_path, MINIMO.replace('magnitud = "volumen"', 'magnitud = "energia"'))
    assert semantica.validar(sem, base) == []


def test_varios_servicios_completan_un_mes_solo_si_lo_completan_todos():
    cobertura = [
        CoberturaMes("2026-05", "agua", 31, 31), CoberturaMes("2026-05", "luz", 31, 5),
        CoberturaMes("2026-06", "agua", 30, 30), CoberturaMes("2026-06", "luz", 30, 30),
    ]
    assert semantica.meses_completos(cobertura, ["agua"]) == {"2026-05": True, "2026-06": True}
    assert semantica.meses_completos(cobertura, ["agua", "luz"]) == {"2026-05": False, "2026-06": True}
    assert semantica.meses_completos(cobertura, []) == {}

