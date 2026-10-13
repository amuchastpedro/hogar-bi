"""Construcción desde cero: semillas, calendario, huella y datos manuales (R19, R24, R29, R41)."""

import json
import shutil

import pytest

import datos_prueba
from facturas.bd.conexion import conectar
from facturas.bd.construir import (
    DIR_SEMILLAS, ErrorSemillas, aplicar_ajustes, construir, huella_semillas, leer_ajustes,
)


def _volcado(ruta):
    conexion = conectar(ruta, "lectura")
    volcado = list(conexion.iterdump())
    conexion.close()
    return volcado


def test_construir_dos_veces_da_el_mismo_resultado(tmp_path):
    construir(tmp_path / "a.db")
    construir(tmp_path / "b.db")
    assert _volcado(tmp_path / "a.db") == _volcado(tmp_path / "b.db")


def test_calendario_un_registro_por_dia(base):
    filas = base.execute("SELECT count(*), min(fecha), max(fecha) FROM calendario").fetchone()
    assert filas == (36525, "2000-01-01", "2099-12-31")
    assert base.execute("SELECT * FROM calendario WHERE fecha = '2028-02-29'").fetchone() == (
        20280229, "2028-02-29", 2028, 2, 29, "2028-02", 29)


def test_semillas_cargadas(base):
    assert base.execute("SELECT codigo FROM moneda").fetchall() == [("EUR",)]
    assert base.execute("SELECT count(*) FROM concepto").fetchone() == (26,)
    assert base.execute("SELECT count(*) FROM alias_concepto").fetchone() == (28,)
    assert base.execute("SELECT count(*) FROM proveedor").fetchone() == (4,)


def test_huella_de_las_semillas(base, tmp_path):
    assert base.execute("SELECT huella_semillas FROM construccion").fetchone() == (huella_semillas(),)

    copia = tmp_path / "semillas"
    shutil.copytree(DIR_SEMILLAS, copia)
    concepto = copia / "concepto.csv"
    # Los mismos datos con saltos de línea CRLF dan la misma huella; otros datos, otra.
    concepto.write_bytes(concepto.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert huella_semillas(copia) == huella_semillas()
    concepto.write_text(concepto.read_text(encoding="utf-8").replace("Cuota del plan", "Cuota"),
                        encoding="utf-8")
    assert huella_semillas(copia) != huella_semillas()


def test_semilla_con_codigo_inexistente_falla_sin_dejar_la_base(tmp_path):
    copia = tmp_path / "semillas"
    shutil.copytree(DIR_SEMILLAS, copia)
    alias = copia / "alias_concepto.csv"
    alias.write_text(alias.read_text(encoding="utf-8") + "agua,no_existe,*,texto nuevo\n", encoding="utf-8")
    with pytest.raises(ErrorSemillas, match="alias_concepto.csv, línea 30"):
        construir(tmp_path / "facturas.db", copia)
    assert list(tmp_path.glob("facturas.db*")) == []


def test_semilla_con_columnas_distintas_falla(tmp_path):
    copia = tmp_path / "semillas"
    shutil.copytree(DIR_SEMILLAS, copia)
    (copia / "franja.csv").write_text("codigo,descripcion\npunta,Punta\n", encoding="utf-8")
    with pytest.raises(ErrorSemillas, match="franja.csv: columnas"):
        construir(tmp_path / "facturas.db", copia)


def _construir_con_ejemplos_y_ajustes(ruta, ruta_ajustes):
    construir(ruta)
    conexion = conectar(ruta, "escritura")
    for factura in datos_prueba.EJEMPLOS:
        datos_prueba.insertar(conexion, factura)
    aplicar_ajustes(conexion, leer_ajustes(ruta_ajustes))
    contratos = conexion.execute(
        """SELECT p.identificador_fiscal, c.identificador_externo, c.alias
           FROM contrato AS c JOIN proveedor AS p USING (proveedor_id)
           ORDER BY 1, 2""").fetchall()
    conexion.close()
    return contratos


def test_base_reconstruida_conserva_los_datos_manuales(tmp_path):
    ruta_ajustes = tmp_path / "ajustes_manuales.json"
    ruta_ajustes.write_text(json.dumps([
        {"identificador_fiscal": datos_prueba.NIF_DIGI, "identificador_externo": "LINEA-MOVIL-PRUEBA",
         "alias": "movil de casa"},
        {"identificador_fiscal": datos_prueba.NIF_NATURGY, "identificador_externo": "CUPS-GAS-PRUEBA"},
        # Un contrato que todavía no está en la base: se aplicará cuando aparezca.
        {"identificador_fiscal": datos_prueba.NIF_AIGUES, "identificador_externo": "OTRO-CONTRATO",
         "alias": "agua del garaje"},
    ]), encoding="utf-8")

    original = _construir_con_ejemplos_y_ajustes(tmp_path / "original.db", ruta_ajustes)
    reconstruida = _construir_con_ejemplos_y_ajustes(tmp_path / "reconstruida.db", ruta_ajustes)

    assert reconstruida == original
    por_contrato = {fila[1]: fila[2:] for fila in reconstruida}
    assert por_contrato["LINEA-MOVIL-PRUEBA"] == ("movil de casa",)
    assert por_contrato["CUPS-GAS-PRUEBA"] == ("gas 1",)
    assert _volcado(tmp_path / "original.db") == _volcado(tmp_path / "reconstruida.db")


def test_sin_archivo_de_ajustes_no_hay_ajustes(tmp_path):
    assert leer_ajustes(tmp_path / "no_existe.json") == []


@pytest.mark.parametrize("contenido, mensaje", [
    ({"alias": "x"}, "lista"),
    ([{"identificador_fiscal": "A84919760", "alias": "x"}], "faltan"),
    ([{"identificador_fiscal": "A84919760", "identificador_externo": "X", "color": "rojo"}], "sobran"),
])
def test_ajustes_mal_formados(tmp_path, contenido, mensaje):
    ruta = tmp_path / "ajustes_manuales.json"
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    with pytest.raises(ValueError, match=mensaje):
        leer_ajustes(ruta)
