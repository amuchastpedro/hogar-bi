"""Contrato parser → carga: la "factura extraída" (docs/diseno.md, sección 11).

Tipos, validación de forma y serialización a JSON. No importa nada del proyecto:
lo usan los parsers para producirla y la carga para leerla.
"""

import json
import re
from dataclasses import asdict, dataclass
from datetime import date

TIPOS_FACTURA = ("ordinaria", "rectificativa_sustitucion", "rectificativa_diferencias", "abono")
IMPUTACIONES = ("periodo", "puntual")
TIPOS_LECTURA = ("real", "estimada")
# I8: las líneas derivadas de un total repartido pueden diferir de ese total impreso hasta en esta cantidad.
# Digi redondea el IVA por servicio y por factura por separado (1 céntimo en jul 2025); la persona usuaria
# fijó el margen en 10 céntimos (2026-10-06). Las líneas siempre suman el total de la factura (I1, exacto).
TOLERANCIA_REPARTO_CENTIMOS = 10

_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")
_DECIMAL = re.compile(r"-?\d+(\.\d+)?")
_IDENTIFICADOR_FISCAL = re.compile(r"[A-Z0-9]+")
_MONEDA = re.compile(r"[A-Z]{3}")


class ErrorExtraccion(Exception):
    """Un PDF no se pudo convertir en una factura extraída válida."""


def _falla(mensaje: str):
    raise ErrorExtraccion(mensaje)


def _texto(valor, nombre: str, obligatorio: bool = True):
    if valor is None:
        if obligatorio:
            _falla(f"falta el campo obligatorio '{nombre}'")
        return
    if not isinstance(valor, str) or not valor.strip():
        _falla(f"'{nombre}' tiene que ser un texto no vacío, no {valor!r}")


def _fecha(valor, nombre: str, obligatorio: bool = True):
    _texto(valor, nombre, obligatorio)
    if valor is None:
        return
    try:
        if not _FECHA.fullmatch(valor):
            raise ValueError
        date.fromisoformat(valor)
    except ValueError:
        _falla(f"'{nombre}' no es una fecha AAAA-MM-DD válida: {valor!r}")


def _decimal(valor, nombre: str, obligatorio: bool = True):
    _texto(valor, nombre, obligatorio)
    if valor is not None and not _DECIMAL.fullmatch(valor):
        _falla(f"'{nombre}' no es un decimal con punto y sin separador de miles: {valor!r}")


def _entero(valor, nombre: str):
    if isinstance(valor, bool) or not isinstance(valor, int):
        _falla(f"'{nombre}' tiene que ser un entero (céntimos), no {valor!r}")


@dataclass(frozen=True)
class Periodo:
    inicio: str
    fin: str

    def __post_init__(self):
        _fecha(self.inicio, "periodo.inicio")
        _fecha(self.fin, "periodo.fin")
        if self.inicio > self.fin:
            _falla(f"el período empieza ({self.inicio}) después de terminar ({self.fin})")


@dataclass(frozen=True)
class Atributo:
    atributo: str
    valor: str

    def __post_init__(self):
        _texto(self.atributo, "atributo.atributo")
        _decimal(self.valor, f"atributo {self.atributo}")


@dataclass(frozen=True)
class Contrato:
    identificador_externo: str
    categoria: str
    atributos: tuple[Atributo, ...] = ()

    def __post_init__(self):
        _texto(self.identificador_externo, "contrato.identificador_externo")
        _texto(self.categoria, "contrato.categoria")


@dataclass(frozen=True)
class TotalRepartido:
    texto: str
    importe_centimos: int

    def __post_init__(self):
        _texto(self.texto, "total_repartido.texto")
        _entero(self.importe_centimos, "total_repartido.importe_centimos")


@dataclass(frozen=True)
class Linea:
    posicion: int
    contrato: str
    texto: str
    importe_centimos: int
    seccion: str | None = None
    periodo: Periodo | None = None
    imputacion: str | None = None
    derivada_de: str | None = None

    def __post_init__(self):
        _entero(self.posicion, "linea.posicion")
        _texto(self.contrato, f"linea {self.posicion}: contrato")
        _texto(self.texto, f"linea {self.posicion}: texto")
        _entero(self.importe_centimos, f"linea {self.posicion}: importe_centimos")
        if self.imputacion is not None and self.imputacion not in IMPUTACIONES:
            _falla(f"linea {self.posicion}: imputación inválida {self.imputacion!r}")


@dataclass(frozen=True)
class Lectura:
    fecha: str
    valor: str
    tipo: str

    def __post_init__(self):
        _fecha(self.fecha, "lectura.fecha")
        _decimal(self.valor, "lectura.valor")
        if self.tipo not in TIPOS_LECTURA:
            _falla(f"lectura.tipo tiene que ser real o estimada, no {self.tipo!r}")


@dataclass(frozen=True)
class Medicion:
    contrato: str
    magnitud: str
    cantidad: str
    lectura: Lectura
    franja: str | None = None
    cantidad_contador: str | None = None
    factor_conversion: str | None = None

    def __post_init__(self):
        _texto(self.contrato, "medicion.contrato")
        _texto(self.magnitud, "medicion.magnitud")
        _decimal(self.cantidad, f"medicion {self.magnitud}: cantidad")
        _texto(self.franja, "medicion.franja", obligatorio=False)
        _decimal(self.cantidad_contador, "medicion.cantidad_contador", obligatorio=False)
        _decimal(self.factor_conversion, "medicion.factor_conversion", obligatorio=False)
        if (self.cantidad_contador is None) != (self.factor_conversion is None):
            _falla(f"medicion {self.magnitud}: cantidad_contador y factor_conversion van juntos")


@dataclass(frozen=True)
class FacturaExtraida:
    formato: str
    version_parser: str
    identificador_fiscal: str
    numero: str
    tipo: str
    moneda: str
    fecha_emision: str
    periodo: Periodo
    importe_total_centimos: int
    contratos: tuple[Contrato, ...]
    lineas: tuple[Linea, ...]
    numero_factura_corregida: str | None = None
    fecha_vencimiento: str | None = None
    totales_repartidos: tuple[TotalRepartido, ...] = ()
    mediciones: tuple[Medicion, ...] = ()

    def __post_init__(self):
        """Validaciones de forma (diseño, 11.6). Las de los campos propios, en cada tipo."""
        _texto(self.formato, "formato")
        _texto(self.version_parser, "version_parser")
        _texto(self.numero, "numero")
        if not isinstance(self.identificador_fiscal, str) or not _IDENTIFICADOR_FISCAL.fullmatch(self.identificador_fiscal):
            _falla(f"'identificador_fiscal' tiene que ser solo [A-Z0-9], no {self.identificador_fiscal!r}")
        if self.tipo not in TIPOS_FACTURA:
            _falla(f"'tipo' inválido: {self.tipo!r}")
        if (self.tipo == "ordinaria") != (self.numero_factura_corregida is None):
            _falla("'numero_factura_corregida' va si y solo si la factura no es ordinaria")
        if not isinstance(self.moneda, str) or not _MONEDA.fullmatch(self.moneda):
            _falla(f"'moneda' tiene que ser un código ISO 4217, no {self.moneda!r}")
        _fecha(self.fecha_emision, "fecha_emision")
        _fecha(self.fecha_vencimiento, "fecha_vencimiento", obligatorio=False)
        _entero(self.importe_total_centimos, "importe_total_centimos")
        self._validar_contratos_y_lineas()
        self._validar_derivadas()
        self._validar_mediciones()

    def _validar_contratos_y_lineas(self):
        if not self.contratos:
            _falla("falta al menos un contrato")
        if not self.lineas:
            _falla("falta al menos una línea")
        ids = [c.identificador_externo for c in self.contratos]
        if len(set(ids)) != len(ids):
            _falla("hay contratos con el mismo identificador externo")
        posiciones = [linea.posicion for linea in self.lineas]
        if posiciones != list(range(1, len(posiciones) + 1)):
            _falla(f"las posiciones de las líneas tienen que ser 1…n sin huecos: {posiciones}")
        for linea in self.lineas:
            if linea.contrato not in ids:
                _falla(f"linea {linea.posicion}: el contrato {linea.contrato!r} no está declarado")
        for medicion in self.mediciones:
            if medicion.contrato not in ids:
                _falla(f"medicion {medicion.magnitud}: el contrato {medicion.contrato!r} no está declarado")

    def _validar_derivadas(self):
        textos = [t.texto for t in self.totales_repartidos]
        if len(set(textos)) != len(textos):
            _falla("hay totales repartidos con el mismo texto")
        suma = dict.fromkeys(textos, 0)
        for linea in self.lineas:
            if linea.derivada_de is None:
                continue
            if linea.derivada_de not in suma:
                _falla(f"linea {linea.posicion}: deriva de {linea.derivada_de!r}, que no es un total repartido")
            suma[linea.derivada_de] += linea.importe_centimos
        for total in self.totales_repartidos:
            if abs(suma[total.texto] - total.importe_centimos) > TOLERANCIA_REPARTO_CENTIMOS:
                _falla(
                    f"las líneas derivadas de {total.texto!r} suman {suma[total.texto]} y el total impreso es "
                    f"{total.importe_centimos} (céntimos)"
                )

    def _validar_mediciones(self):
        con_franja = {}
        for m in self.mediciones:
            con_franja.setdefault((m.contrato, m.magnitud), set()).add(m.franja is not None)
        for (contrato, magnitud), valores in con_franja.items():
            if len(valores) > 1:
                _falla(f"el contrato {contrato!r} mezcla mediciones de {magnitud} con y sin franja")

    def a_dict(self) -> dict:
        return asdict(self)

    def a_json(self) -> str:
        return json.dumps(self.a_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def desde_dict(cls, datos: dict) -> "FacturaExtraida":
        """Reconstruye (y valida) la estructura desde su forma serializada."""
        try:
            datos = dict(datos)
            datos["periodo"] = Periodo(**datos["periodo"])
            datos["contratos"] = tuple(
                Contrato(**{**c, "atributos": tuple(Atributo(**a) for a in c["atributos"])}) for c in datos["contratos"]
            )
            datos["totales_repartidos"] = tuple(TotalRepartido(**t) for t in datos.get("totales_repartidos", ()))
            datos["lineas"] = tuple(
                Linea(**{**linea, "periodo": Periodo(**linea["periodo"]) if linea.get("periodo") else None})
                for linea in datos["lineas"]
            )
            datos["mediciones"] = tuple(
                Medicion(**{**m, "lectura": Lectura(**m["lectura"])}) for m in datos.get("mediciones", ())
            )
            return cls(**datos)
        except (TypeError, KeyError) as error:
            raise ErrorExtraccion(f"la estructura no tiene la forma de una factura extraída: {error!r}") from error

    @classmethod
    def desde_json(cls, texto: str) -> "FacturaExtraida":
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as error:
            raise ErrorExtraccion(f"JSON inválido: {error}") from error
        if not isinstance(datos, dict):
            raise ErrorExtraccion("el JSON no es un objeto")
        return cls.desde_dict(datos)


def verificar_opcionales(factura: FacturaExtraida, impresos: tuple[str, ...]) -> None:
    """Los campos opcionales que el formato imprime tienen que estar presentes (11.6, H14).

    Nombres admitidos: `fecha_vencimiento`, `seccion` (de las líneas no derivadas), `franja`,
    `cantidad_contador` (con su factor) y `atributo:<código>`.
    """
    faltan = []
    for nombre in impresos:
        if nombre == "fecha_vencimiento":
            ok = factura.fecha_vencimiento is not None
        elif nombre == "seccion":
            ok = all(linea.seccion is not None for linea in factura.lineas if linea.derivada_de is None)
        elif nombre == "franja":
            ok = bool(factura.mediciones) and all(m.franja is not None for m in factura.mediciones)
        elif nombre == "cantidad_contador":
            ok = bool(factura.mediciones) and all(m.cantidad_contador is not None for m in factura.mediciones)
        elif nombre.startswith("atributo:"):
            codigo = nombre.split(":", 1)[1]
            ok = all(any(a.atributo == codigo for a in c.atributos) for c in factura.contratos)
        else:
            raise ValueError(f"campo opcional desconocido: {nombre}")
        if not ok:
            faltan.append(nombre)
    if faltan:
        _falla(f"el formato {factura.formato} imprime {', '.join(faltan)} y no se encontró")
