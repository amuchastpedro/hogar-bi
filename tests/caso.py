"""Referencias leídas de `caso_hogar.md` y de `ejemplos/valores_esperados.md`.

Los tests comparan contra las tablas del caso y no contra valores copiados a
mano: si el caso se corrige, los tests usan la versión corregida.

Los importes reales de los ejemplos no se versionan: `caso_hogar.md` los muestra en
letras, y las mismas secciones con los importes reales están en
`ejemplos/valores_esperados.md`, fuera de git como los PDFs. Sin ese archivo, los
tests que los necesitan se saltan.
"""

import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ARCHIVO_CASO = RAIZ / "caso_hogar.md"
ARCHIVO_VALORES = RAIZ / "ejemplos" / "valores_esperados.md"
ARCHIVO_IMPORTES = RAIZ / "ejemplos" / "importes_esperados.json"
ANIO_EJEMPLOS = 2026  # la tabla de controles nombra los meses sin el año
MESES = {
    nombre: numero
    for numero, nombre in enumerate(
        ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"),
        start=1,
    )
}


def _valores() -> Path:
    """El archivo local con los importes reales de los ejemplos; si falta, salta el test."""
    if not ARCHIVO_VALORES.exists():
        pytest.skip("falta ejemplos/valores_esperados.md: los importes reales de los ejemplos no se versionan")
    return ARCHIVO_VALORES


def _tabla(encabezado: str, archivo: Path = ARCHIVO_CASO) -> list[list[str]]:
    """Filas (sin encabezado ni separador) de la tabla cuyo encabezado es `encabezado`."""
    lineas = archivo.read_text(encoding="utf-8").splitlines()
    filas = []
    for linea in lineas[lineas.index(encabezado) + 2:]:
        if not linea.startswith("|"):
            break
        filas.append([celda.strip() for celda in linea.strip().strip("|").split("|")])
    return filas


def _centimos(euros: str) -> int:
    entero, decimales = euros.replace(".", "").split(",")
    return int(entero) * 100 + int(decimales)


def mas_centimos(euros: str, centimos: int = 1) -> str:
    """Un importe impreso ("1,23") con algunos céntimos más ("1,24"), para alterar un PDF en un test."""
    total = _centimos(euros) + centimos
    return f"{total // 100},{total % 100:02d}"


def importes(pdf: str) -> dict:
    """Los importes reales (en céntimos) de un PDF de ejemplo que el caso no describe.

    Están en `ejemplos/importes_esperados.json`, fuera de git como los PDFs, con lo impreso en
    cada uno; si falta el archivo o el PDF, el test se salta.
    """
    if not ARCHIVO_IMPORTES.exists():
        pytest.skip("falta ejemplos/importes_esperados.json: los importes reales de los ejemplos no se versionan")
    datos = json.loads(ARCHIVO_IMPORTES.read_text(encoding="utf-8"))
    if pdf not in datos:
        pytest.skip(f"falta {pdf!r} en ejemplos/importes_esperados.json")
    return datos[pdf]


def clasificacion() -> list[tuple[str, str, str]]:
    """(categoría, concepto, tipo de cargo) de la sección "Clasificación de conceptos"."""
    return [tuple(fila) for fila in _tabla("| Categoría | Concepto | Tipo de cargo |")]


def controles_prorrateo() -> tuple[dict[str, int], dict[tuple[str, str], int]]:
    """Total de cada categoría y su reparto por mes, de "Controles de prorrateo y cobertura".

    Cada fila del caso es una factura de una sola categoría, por ejemplo
    "agua (12,34) | abril, 21 días ≈ 4,32 · mayo, …". Devuelve
    ({categoría: céntimos}, {(categoría, "AAAA-MM"): céntimos}).
    """
    totales, reparto = {}, {}
    for factura, meses in _tabla("| Factura | Reparto mensual |", _valores()):
        categoria, total = re.fullmatch(r"(\w+) \(([\d.,]+)\)", factura).groups()
        totales[categoria] = _centimos(total)
        for mes, importe in re.findall(r"(\w+), \d+ días? ≈ ([\d.,]+)", meses):
            reparto[(categoria, f"{ANIO_EJEMPLOS}-{MESES[mes]:02d}")] = _centimos(importe)
    return totales, reparto


def valores_esperados() -> dict[str, dict]:
    """Los "Valores esperados de los ejemplos", por nombre de PDF (`agua`, `gas`, `luz`, `fibra_movil`).

    Cada uno: `formato`, `inicio`, `fin`, `emision`, `vencimiento` (o None), `total` (céntimos),
    `filas` (una por fila de la tabla, con las columnas del caso: "Texto en el PDF", "Importe",
    "Concepto", "Tipo de cargo" y, en Digi, "Contrato") y `texto`, la sección entera, para las
    mediciones y los atributos, que el caso describe en prosa.
    """
    lineas = _valores().read_text(encoding="utf-8").splitlines()
    inicio = lineas.index("## Valores esperados de los ejemplos")
    fin = next(i for i in range(inicio + 1, len(lineas)) if lineas[i].startswith("## "))
    secciones, actual = {}, None
    for linea in lineas[inicio + 1:fin]:
        encabezado = re.fullmatch(r"### `(\w+)\.pdf`", linea)
        if encabezado:
            actual = secciones.setdefault(encabezado[1], [])
        elif actual is not None:
            actual.append(linea)

    resultado = {}
    for nombre, cuerpo in secciones.items():
        texto = "\n".join(cuerpo)
        filas_tabla = [[c.strip() for c in f.strip().strip("|").split("|")] for f in cuerpo if f.startswith("|")]
        columnas = filas_tabla[0]
        periodo = re.search(r"del (\d{4}-\d{2}-\d{2}) al (\d{4}-\d{2}-\d{2})", texto)
        vencimiento = re.search(r"Vencimiento: (\d{4}-\d{2}-\d{2})", texto)
        resultado[nombre] = {
            "formato": re.search(r"Formato `(\w+)`", texto)[1],
            "inicio": periodo[1],
            "fin": periodo[2],
            "emision": re.search(r"Emisión: (\d{4}-\d{2}-\d{2})", texto)[1],
            "vencimiento": vencimiento[1] if vencimiento else None,
            "total": _centimos(re.search(r"Total a pagar: ([\d.,]+)", texto)[1]),
            "filas": [dict(zip(columnas, fila)) for fila in filas_tabla[2:]],
            "texto": texto,
        }
    return resultado
