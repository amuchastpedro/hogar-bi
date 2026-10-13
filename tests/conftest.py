"""Fixtures compartidos: una base construida desde las semillas, vacía o con los ejemplos."""

import shutil
from pathlib import Path

import pytest

import datos_prueba
from facturas.bd.conexion import conectar
from facturas.bd.construir import construir


@pytest.fixture(scope="session")
def plantilla(tmp_path_factory) -> Path:
    """Una base construida una sola vez por sesión. Se copia cerrada, sin lectores."""
    ruta = tmp_path_factory.mktemp("plantilla") / "facturas.db"
    construir(ruta)
    return ruta


@pytest.fixture
def ruta_base(plantilla, tmp_path) -> Path:
    ruta = tmp_path / "facturas.db"
    shutil.copyfile(plantilla, ruta)
    return ruta


@pytest.fixture
def base(ruta_base):
    """Conexión de escritura a una base recién construida, sin facturas."""
    conexion = conectar(ruta_base, "escritura")
    yield conexion
    conexion.close()


@pytest.fixture
def base_ejemplos(base):
    """La base con las cuatro facturas de ejemplo del caso."""
    for factura in datos_prueba.EJEMPLOS:
        datos_prueba.insertar(base, factura)
    return base


@pytest.fixture
def base_completa(base_ejemplos):
    """Los ejemplos más un segundo período de agua y de gas, y una rectificativa del gas."""
    for factura in (datos_prueba.FACTURA_AGUA_2, datos_prueba.FACTURA_GAS_2, datos_prueba.RECTIFICATIVA_GAS):
        datos_prueba.insertar(base_ejemplos, factura)
    return base_ejemplos


@pytest.fixture
def rutas(plantilla, tmp_path):
    """Una raíz de proyecto temporal con sus carpetas de datos y una base recién construida."""
    from facturas.operacion.proceso import Rutas

    raiz = tmp_path / "proyecto"
    for carpeta in ("entrada", "procesadas", "pendientes", "duplicados"):
        (raiz / "datos" / carpeta).mkdir(parents=True)
    shutil.copyfile(plantilla, raiz / "datos" / "facturas.db")
    return Rutas(raiz)
