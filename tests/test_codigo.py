"""Reglas del código: sin `assert` (R34) y dependencias entre módulos (diseño, sección 14)."""

import ast
from pathlib import Path

import pytest

DIR_SRC = Path(__file__).resolve().parents[1] / "src"
MODULOS = sorted(DIR_SRC.rglob("*.py"))

# Qué paquetes del proyecto puede importar cada uno. operacion y __main__ importan todo.
PERMITIDOS = {
    "extraccion": set(),
    "parsers": {"extraccion"},
    "bd": {"extraccion"},
    "carga": {"extraccion", "bd"},
    "dashboard": {"bd"},
}


def _paquete(ruta: Path) -> str:
    """'bd' para src/facturas/bd/conexion.py; el nombre del módulo si está en la raíz del paquete."""
    partes = ruta.relative_to(DIR_SRC / "facturas").with_suffix("").parts
    return partes[0]


def _importados(arbol: ast.AST) -> set[str]:
    """Paquetes de `facturas` que importa el módulo: facturas.bd.conexion → 'bd'."""
    nombres = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres |= {alias.name for alias in nodo.names}
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            nombres.add(nodo.module)
    return {n.split(".")[1] for n in nombres if n.startswith("facturas.")}


@pytest.mark.parametrize("ruta", MODULOS, ids=lambda r: str(r.relative_to(DIR_SRC)))
def test_sin_assert(ruta):
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    lineas = [nodo.lineno for nodo in ast.walk(arbol) if isinstance(nodo, ast.Assert)]
    assert lineas == [], f"{ruta.name} usa assert en las líneas {lineas}: usar una excepción explícita"


@pytest.mark.parametrize("ruta", MODULOS, ids=lambda r: str(r.relative_to(DIR_SRC)))
def test_dependencias_entre_modulos(ruta):
    paquete = _paquete(ruta)
    if paquete not in PERMITIDOS:
        return
    ajenos = _importados(ast.parse(ruta.read_text(encoding="utf-8"))) - PERMITIDOS[paquete] - {paquete}
    assert ajenos == set(), f"{ruta.name} ({paquete}) no puede importar {sorted(ajenos)}"
