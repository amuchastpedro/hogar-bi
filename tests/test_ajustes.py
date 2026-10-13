"""Datos manuales: `contratos` y `contrato` (bloque 4, parte B; R41)."""

import json

import pytest

import apoyo_carga
from facturas.__main__ import main
from facturas.operacion import ajustes as modulo_ajustes
from facturas.operacion.bloqueo import bloqueo


@pytest.fixture
def cargadas(rutas, capsys):
    """Rutas con la factura de agua y la de luz cargadas: dos contratos, `agua 1` y `luz 1`."""
    apoyo_carga.poner(rutas, "agua.pdf", "luz.pdf")
    assert main(["cargar"], rutas, espera=0) == 0
    capsys.readouterr()
    return rutas


def _contratos(rutas):
    return apoyo_carga.consulta(rutas.base, "SELECT alias FROM contrato ORDER BY alias")


def _alias(rutas):
    return [alias for (alias,) in _contratos(rutas)]


def _archivo(rutas):
    return json.loads(rutas.ajustes.read_text(encoding="utf-8"))


def test_contratos_lista_alias_categoria_y_proveedor(cargadas, capsys):
    assert main(["contratos"], cargadas) == 0

    lineas = capsys.readouterr().out.splitlines()
    assert lineas[0].split() == ["alias", "categoría", "proveedor"]
    assert [linea.split()[:2] for linea in lineas[1:]] == [["agua", "1"], ["luz", "1"]]


def test_contratos_sin_facturas_lo_dice(rutas, capsys):
    assert main(["contratos"], rutas) == 0
    assert "No hay contratos" in capsys.readouterr().out


def test_un_cambio_de_alias_queda_en_la_base_y_en_el_archivo_y_sobrevive_a_reprocesar_todo(cargadas, capsys):
    assert main(["contrato", "agua 1", "--alias", "casa"], cargadas) == 0
    assert "Contrato 'casa' (agua)" in capsys.readouterr().out

    assert _alias(cargadas) == ["casa", "luz 1"]
    (entrada,) = _archivo(cargadas)
    assert entrada["alias"] == "casa"
    assert set(entrada) == {"identificador_fiscal", "identificador_externo", "alias"}

    assert main(["reprocesar", "--todo"], cargadas, espera=0) == 0
    assert _alias(cargadas) == ["casa", "luz 1"]


def test_un_segundo_cambio_de_alias_reemplaza_la_misma_entrada_del_archivo(cargadas):
    assert main(["contrato", "agua 1", "--alias", "casa"], cargadas) == 0
    assert main(["contrato", "casa", "--alias", "piso"], cargadas) == 0
    (entrada,) = _archivo(cargadas)
    assert entrada["alias"] == "piso"
    assert main(["reprocesar", "--todo"], cargadas, espera=0) == 0
    assert _alias(cargadas) == ["luz 1", "piso"]


def test_cada_contrato_tiene_su_entrada_en_el_archivo(cargadas):
    assert main(["contrato", "agua 1", "--alias", "casa"], cargadas) == 0
    assert main(["contrato", "luz 1", "--alias", "piso"], cargadas) == 0
    assert sorted(entrada["alias"] for entrada in _archivo(cargadas)) == ["casa", "piso"]


def _estado_de_los_datos(rutas):
    return _contratos(rutas), rutas.ajustes.read_bytes() if rutas.ajustes.exists() else None


def _sin_cambios(rutas, argumentos, capsys, texto):
    antes = _estado_de_los_datos(rutas)
    capsys.readouterr()
    assert main(argumentos, rutas) == 2
    assert texto in capsys.readouterr().err
    assert _estado_de_los_datos(rutas) == antes


def test_rechaza_un_alias_que_ya_usa_otro_contrato(cargadas, capsys):
    _sin_cambios(cargadas, ["contrato", "luz 1", "--alias", "agua 1"], capsys, "ya lo usa otro contrato")


def test_rechaza_un_alias_reservado_en_el_archivo_para_otro_contrato(cargadas, capsys):
    cargadas.ajustes.write_text(json.dumps([
        {"identificador_fiscal": "proveedor-ficticio", "identificador_externo": "otro", "alias": "reservado"}]), encoding="utf-8")
    _sin_cambios(cargadas, ["contrato", "agua 1", "--alias", "reservado"], capsys, "reservado en ajustes_manuales.json")


def test_aceptar_el_propio_alias_no_es_un_conflicto(cargadas):
    assert main(["contrato", "agua 1", "--alias", "agua 1"], cargadas) == 0
    assert _alias(cargadas) == ["agua 1", "luz 1"]


@pytest.mark.parametrize("argumentos, texto", [
    (["contrato", "no existe", "--alias", "x"], "no hay ningún contrato con el alias 'no existe'"),
    (["contrato", "agua 1"], "indicá la opción --alias"),
    (["contrato", "agua 1", "--alias", ""], "no puede estar vacío"),
    (["contrato", "agua 1", "--alias", " casa"], "no puede estar vacío ni empezar"),
])
def test_los_cambios_invalidos_no_modifican_nada(cargadas, capsys, argumentos, texto):
    _sin_cambios(cargadas, argumentos, capsys, texto)


def test_si_falla_la_escritura_del_archivo_la_base_no_cambia(cargadas, monkeypatch, capsys):
    def falla(*args, **kwargs):
        raise OSError("disco lleno")

    antes = _contratos(cargadas)
    monkeypatch.setattr(modulo_ajustes.os, "replace", falla)
    assert main(["contrato", "agua 1", "--alias", "casa"], cargadas) == 2
    assert "disco lleno" in capsys.readouterr().err
    assert _contratos(cargadas) == antes
    assert not cargadas.ajustes.exists()


def test_si_falla_el_commit_el_archivo_vuelve_a_como_estaba(cargadas, monkeypatch):
    assert main(["contrato", "agua 1", "--alias", "casa"], cargadas) == 0
    antes = cargadas.ajustes.read_bytes()
    conectar_real = modulo_ajustes.conectar

    class ConexionQueNoConfirma:
        def __init__(self, conexion):
            self._conexion = conexion

        def execute(self, sql, *args):
            if sql == "COMMIT":
                raise OSError("falló el commit")
            return self._conexion.execute(sql, *args)

        def __getattr__(self, nombre):
            return getattr(self._conexion, nombre)

    monkeypatch.setattr(modulo_ajustes, "conectar", lambda *a, **k: ConexionQueNoConfirma(conectar_real(*a, **k)))
    assert main(["contrato", "casa", "--alias", "otra"], cargadas) == 2
    assert cargadas.ajustes.read_bytes() == antes
    monkeypatch.undo()
    assert _alias(cargadas) == ["casa", "luz 1"]


def test_contrato_toma_el_bloqueo_de_la_carga(cargadas, capsys):
    with bloqueo(cargadas.bloqueo):
        assert main(["contrato", "agua 1", "--alias", "casa"], cargadas) == 0
    assert "No se hizo nada" in capsys.readouterr().out
    assert _alias(cargadas) == ["agua 1", "luz 1"]
