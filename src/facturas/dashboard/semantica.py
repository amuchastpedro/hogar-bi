"""Capa semántica del dashboard: cómo se interpretan los conceptos de cada categoría.

La interpretación vive en `semantica.toml`, no en la base: la base guarda solo los
hechos de las facturas, sin tipo de cargo ni cobertura. Este módulo:

- carga el TOML y verifica que sea coherente consigo mismo (`cargar`);
- lo verifica contra la base (`validar`): las categorías, los conceptos y las
  magnitudes existen. Un concepto de la base sin grupo no es un error: se devuelve
  para avisar, y los importes lo muestran en el grupo «Unclassified»;
- combina la cobertura de varios servicios (`meses_completos`).

Las incoherencias lanzan `ErrorSemantica`, con un mensaje que nombra el concepto
y la categoría (R34).
"""

import sqlite3
import tomllib
from dataclasses import dataclass
from pathlib import Path

RUTA_SEMANTICA = Path(__file__).with_name("semantica.toml")

SIN_CLASIFICAR = "sin_clasificar"
NOMBRE_SIN_CLASIFICAR = "Unclassified"

_CLAVES_CATEGORIA = {"nombre", "magnitud", "variables", "grupos"}
_CLAVES_GRUPO = {"nombre", "conceptos"}


class ErrorSemantica(Exception):
    """`semantica.toml` no es coherente consigo mismo o con la base."""


@dataclass(frozen=True)
class Grupo:
    codigo: str
    nombre: str
    conceptos: dict[str, str]  # código del concepto → nombre en la interfaz, en orden


@dataclass(frozen=True)
class Categoria:
    codigo: str
    nombre: str
    magnitud: str | None  # la que da el volumen; None si el servicio no tiene volumen
    variables: frozenset[str]  # conceptos que escalan con el volumen
    grupos: tuple[Grupo, ...]

    def grupo_de(self, concepto: str) -> str:
        """El código del grupo del concepto, o SIN_CLASIFICAR."""
        for grupo in self.grupos:
            if concepto in grupo.conceptos:
                return grupo.codigo
        return SIN_CLASIFICAR

    def nombre_grupo(self, codigo: str) -> str:
        for grupo in self.grupos:
            if grupo.codigo == codigo:
                return grupo.nombre
        return NOMBRE_SIN_CLASIFICAR

    def nombre_concepto(self, concepto: str) -> str | None:
        """El nombre en la interfaz; None si el concepto no tiene grupo."""
        for grupo in self.grupos:
            if concepto in grupo.conceptos:
                return grupo.conceptos[concepto]
        return None


# categoría → su interpretación, en el orden del TOML
Semantica = dict[str, Categoria]


@dataclass(frozen=True)
class ConceptoSinClasificar:
    categoria: str
    concepto: str
    concepto_nombre: str  # el de la base, en español


def cargar(ruta: Path = RUTA_SEMANTICA) -> Semantica:
    """Lee el TOML y verifica su coherencia interna."""
    with open(ruta, "rb") as archivo:
        try:
            datos = tomllib.load(archivo)
        except tomllib.TOMLDecodeError as error:
            raise ErrorSemantica(f"{Path(ruta).name} no es un TOML válido: {error}") from error
    return {codigo: _categoria(codigo, valor) for codigo, valor in datos.items()}


def _categoria(codigo: str, datos) -> Categoria:
    if not isinstance(datos, dict):
        raise ErrorSemantica(f"Categoría '{codigo}': tiene que ser una tabla [{codigo}]")
    _claves(datos, _CLAVES_CATEGORIA, f"Categoría '{codigo}'")
    nombre = _texto(datos.get("nombre"), f"Categoría '{codigo}': falta el nombre")
    if not isinstance(datos.get("grupos"), dict) or not datos["grupos"]:
        raise ErrorSemantica(f"Categoría '{codigo}': no tiene grupos")
    grupos = tuple(_grupo(codigo, g, valor) for g, valor in datos["grupos"].items())

    vistos: dict[str, str] = {}
    for grupo in grupos:
        for concepto in grupo.conceptos:
            if concepto in vistos:
                raise ErrorSemantica(
                    f"El concepto '{concepto}' de la categoría '{codigo}' está en dos grupos: "
                    f"'{vistos[concepto]}' y '{grupo.codigo}'"
                )
            vistos[concepto] = grupo.codigo

    magnitud = datos.get("magnitud")
    if magnitud is not None:
        magnitud = _texto(magnitud, f"Categoría '{codigo}': la magnitud tiene que ser un texto")
    variables = datos.get("variables", [])
    if not isinstance(variables, list) or not all(isinstance(v, str) for v in variables):
        raise ErrorSemantica(f"Categoría '{codigo}': 'variables' tiene que ser una lista de códigos")
    for concepto in variables:
        if concepto not in vistos:
            raise ErrorSemantica(
                f"El concepto variable '{concepto}' de la categoría '{codigo}' no está en ningún grupo"
            )
    if variables and magnitud is None:
        raise ErrorSemantica(f"Categoría '{codigo}': tiene conceptos variables pero no magnitud")
    return Categoria(codigo, nombre, magnitud, frozenset(variables), grupos)


def _grupo(categoria: str, codigo: str, datos) -> Grupo:
    donde = f"Grupo '{codigo}' de la categoría '{categoria}'"
    if not isinstance(datos, dict):
        raise ErrorSemantica(f"{donde}: tiene que ser una tabla")
    _claves(datos, _CLAVES_GRUPO, donde)
    nombre = _texto(datos.get("nombre"), f"{donde}: falta el nombre")
    conceptos = datos.get("conceptos")
    if not isinstance(conceptos, dict) or not conceptos:
        raise ErrorSemantica(f"{donde}: no tiene conceptos")
    for concepto, nombre_concepto in conceptos.items():
        _texto(nombre_concepto, f"El concepto '{concepto}' de la categoría '{categoria}': falta el nombre")
    return Grupo(codigo, nombre, dict(conceptos))


def _claves(datos: dict, permitidas: set[str], donde: str) -> None:
    sobran = sorted(set(datos) - permitidas)
    if sobran:
        raise ErrorSemantica(f"{donde}: claves desconocidas {sobran}")


def _texto(valor, mensaje: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorSemantica(mensaje)
    return valor


def validar(semantica: Semantica, conexion: sqlite3.Connection) -> list[ConceptoSinClasificar]:
    """Verifica el TOML contra la base y devuelve los conceptos de `v_linea` sin grupo.

    Lanza ErrorSemantica si una categoría, un concepto o una magnitud del TOML no
    existe en la base. No hay vista de magnitudes: la magnitud se compara con las
    mediciones de la categoría, cuando las hay.
    """
    conceptos_base: dict[str, set[str]] = {}
    for categoria, concepto in conexion.execute(
        "SELECT categoria_codigo, concepto_codigo FROM v_dim_concepto"
    ):
        conceptos_base.setdefault(categoria, set()).add(concepto)
    magnitudes_base: dict[str, set[str]] = {}
    for categoria, magnitud in conexion.execute(
        "SELECT DISTINCT categoria_codigo, magnitud_codigo FROM v_hecho_consumo_mensual"
    ):
        magnitudes_base.setdefault(categoria, set()).add(magnitud)

    for codigo, categoria in semantica.items():
        if codigo not in conceptos_base:
            raise ErrorSemantica(f"La categoría '{codigo}' de semantica.toml no existe en la base")
        for grupo in categoria.grupos:
            for concepto in grupo.conceptos:
                if concepto not in conceptos_base[codigo]:
                    raise ErrorSemantica(
                        f"El concepto '{concepto}' de la categoría '{codigo}' no existe en la base"
                    )
        medidas = magnitudes_base.get(codigo)
        if categoria.magnitud is not None and medidas and categoria.magnitud not in medidas:
            raise ErrorSemantica(
                f"La magnitud '{categoria.magnitud}' de la categoría '{codigo}' no aparece en sus "
                f"mediciones (hay {sorted(medidas)})"
            )

    sin_clasificar = []
    for categoria, concepto, nombre in conexion.execute(
        """SELECT DISTINCT categoria_codigo, concepto_codigo, concepto_nombre FROM v_linea
           ORDER BY categoria_codigo, concepto_codigo"""
    ):
        interpretacion = semantica.get(categoria)
        if interpretacion is None or interpretacion.grupo_de(concepto) == SIN_CLASIFICAR:
            sin_clasificar.append(ConceptoSinClasificar(categoria, concepto, nombre))
    return sin_clasificar


def meses_completos(cobertura, categorias) -> dict[str, bool]:
    """Mes → completo, para una combinación de servicios: lo está si lo está para todos.

    `cobertura` son las filas de `datos.cobertura_mensual`; solo cuentan las de
    `categorias`.
    """
    elegidas = set(categorias)
    completos: dict[str, bool] = {}
    for fila in cobertura:
        if fila.categoria in elegidas:
            completos[fila.anio_mes] = completos.get(fila.anio_mes, True) and fila.completo
    return completos
