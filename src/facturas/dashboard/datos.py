"""Consultas del dashboard: vistas de la base → tablas por mes y por factura.

No usa Streamlit, así que se puede testear; la app envuelve estas funciones con
`st.cache_data`. Lee solo vistas (R32), con la conexión de solo lectura de
`facturas.bd.conexion.conectar()` (R39). Los importes van en céntimos y las
cantidades en milésimas de la unidad canónica, como en la base.

Dos granos:

- **Por mes** (Overview): el gasto prorrateado por días y la cobertura.
- **Por factura** (Analysis): cada fila es una factura vigente × contrato. Una
  rectificativa por diferencias se suma a la factura que corrige y toma su
  `factura_id`, sus fechas y sus días. Una factura con varios contratos (varias
  líneas de un mismo operador) da una fila por contrato.

La interpretación (grupos, conceptos variables, magnitud) sale de la capa
semántica, nunca de la base.
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from fractions import Fraction

from facturas.bd import conexion as _conexion
from facturas.dashboard.semantica import SIN_CLASIFICAR, Semantica

# Base que lee el dashboard. Los tests la reemplazan por una base de prueba.
RUTA_BASE = _conexion.RUTA_BASE

# Cada factura vigente → la que representa en el grano por factura: ella misma o,
# si es una rectificativa por diferencias, la factura vigente que corrige.
_REFERENCIA = """
referencia AS (
    SELECT f.factura_id, coalesce(o.factura_id, f.factura_id) AS factura_ref
    FROM v_factura_vigente AS f
    LEFT JOIN v_factura_vigente AS o
      ON f.tipo = 'rectificativa_diferencias'
     AND o.proveedor_id = f.proveedor_id AND o.numero = f.numero_factura_corregida
)"""


class ErrorCascada(Exception):
    """No se puede calcular la cascada entre dos facturas."""


# --- Por mes -----------------------------------------------------------------


@dataclass(frozen=True)
class GastoMes:
    anio_mes: str  # AAAA-MM
    categoria: str
    importe_centimos: int


def gasto_mensual(conexion: sqlite3.Connection) -> list[GastoMes]:
    """El gasto de cada categoría en cada mes con gasto, prorrateado por días."""
    filas = conexion.execute(
        """SELECT anio_mes, categoria_codigo, sum(importe_centimos)
           FROM v_hecho_gasto_mensual
           GROUP BY anio_mes, categoria_codigo
           ORDER BY anio_mes, categoria_codigo"""
    )
    return [GastoMes(*fila) for fila in filas]


@dataclass(frozen=True)
class CoberturaMes:
    anio_mes: str
    categoria: str
    dias_mes: int
    dias_cubiertos: int

    @property
    def completo(self) -> bool:
        return self.dias_cubiertos == self.dias_mes


def cobertura_mensual(
    conexion: sqlite3.Connection, categorias, mes_desde: str, mes_hasta: str
) -> list[CoberturaMes]:
    """Los días cubiertos de cada categoría en cada mes de [mes_desde, mes_hasta] (AAAA-MM).

    Un día está cubierto si cae en el período de una factura vigente que tiene
    alguna línea `periodo` de la categoría, con cualquier contrato. Sin fechas de
    alta ni de baja: el mes está completo si se cubren todos sus días. Una
    rectificativa por diferencias no cubre días: corrige un período ya facturado.
    Devuelve una fila por categoría y mes, aunque no haya facturas.
    """
    meses = conexion.execute(
        """SELECT anio_mes, max(dias_mes) FROM v_dim_fecha
           WHERE anio_mes BETWEEN ? AND ? GROUP BY anio_mes ORDER BY anio_mes""",
        (mes_desde, mes_hasta),
    ).fetchall()
    cubiertos = dict(
        ((anio_mes, categoria), dias)
        for anio_mes, categoria, dias in conexion.execute(
            """WITH periodo AS (
                   SELECT DISTINCT l.categoria_codigo, f.fecha_inicio, f.fecha_fin
                   FROM v_linea AS l
                   JOIN v_factura_vigente AS f ON f.factura_id = l.factura_id
                   WHERE l.imputacion = 'periodo' AND f.tipo <> 'rectificativa_diferencias'
               )
               SELECT d.anio_mes, p.categoria_codigo, count(DISTINCT d.fecha)
               FROM v_dim_fecha AS d
               JOIN periodo AS p ON d.fecha BETWEEN p.fecha_inicio AND p.fecha_fin
               WHERE d.anio_mes BETWEEN ? AND ?
               GROUP BY d.anio_mes, p.categoria_codigo""",
            (mes_desde, mes_hasta),
        )
    )
    return [
        CoberturaMes(anio_mes, categoria, dias_mes, cubiertos.get((anio_mes, categoria), 0))
        for categoria in categorias
        for anio_mes, dias_mes in meses
    ]


def abrir() -> sqlite3.Connection:
    """La conexión de solo lectura a la base del dashboard."""
    return _conexion.conectar(RUTA_BASE)


# --- Períodos del Overview ---------------------------------------------------

PERIODOS = ("month", "year", "all", "ytd", "last12", "range")


def meses_entre(desde: str, hasta: str) -> list[str]:
    """Todos los meses AAAA-MM de [desde, hasta]."""
    anio, mes = int(desde[:4]), int(desde[5:])
    meses = []
    while f"{anio:04d}-{mes:02d}" <= hasta:
        meses.append(f"{anio:04d}-{mes:02d}")
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return meses


def meses_del_periodo(
    periodo: str, con_gasto: list[str], hoy: date, *, mes=None, anio=None, desde=None, hasta=None
) -> list[str]:
    """Los meses (AAAA-MM) de un período, dentro del histórico con datos.

    El histórico va del primer al último mes con gasto: no cuenta los meses futuros
    ni los anteriores a la primera factura. `periodo` es uno de `PERIODOS`:

    - `month`: el mes `mes`; `year`: el año `anio` (entero);
    - `all`: todo el histórico; `ytd`: el año en curso hasta hoy;
    - `last12`: los 12 últimos meses con datos (terminan en el último mes con gasto);
    - `range`: de `desde` a `hasta`, ambos incluidos.
    """
    if not con_gasto:
        return []
    historico = meses_entre(min(con_gasto), max(con_gasto))
    actual = f"{hoy.year:04d}-{hoy.month:02d}"
    if periodo == "all":
        return historico
    if periodo == "month":
        return [m for m in historico if m == mes]
    if periodo == "year":
        return [m for m in historico if m[:4] == str(anio)]
    if periodo == "ytd":
        return [m for m in historico if m[:4] == str(hoy.year) and m <= actual]
    if periodo == "last12":
        return historico[-12:]
    if periodo == "range":
        return [m for m in historico if desde <= m <= hasta]
    raise ValueError(f"Período desconocido: {periodo!r}")


def quitar_incompletos(meses: list[str], completos: dict[str, bool]) -> list[str]:
    """Los meses que están completos (un mes sin dato de cobertura no lo está)."""
    return [m for m in meses if completos.get(m, False)]


def serie_mensual(gastos: list[GastoMes], meses: list[str], categorias) -> list[GastoMes]:
    """Una fila por mes y categoría, con 0 donde no hubo gasto."""
    por_clave = {(g.anio_mes, g.categoria): g.importe_centimos for g in gastos}
    return [
        GastoMes(m, c, por_clave.get((m, c), 0)) for m in meses for c in categorias
    ]


def total_por_categoria(gastos: list[GastoMes], meses: list[str], categorias) -> dict[str, int]:
    """El gasto de cada categoría elegida en los meses dados, en céntimos."""
    serie = serie_mensual(gastos, meses, categorias)
    totales = {c: 0 for c in categorias}
    for g in serie:
        totales[g.categoria] += g.importe_centimos
    return totales


def total_mensual(gastos: list[GastoMes], meses: list[str], categorias) -> dict[str, int]:
    """El gasto total de las categorías elegidas en cada mes dado, en céntimos."""
    totales = {m: 0 for m in meses}
    for g in serie_mensual(gastos, meses, categorias):
        totales[g.anio_mes] += g.importe_centimos
    return totales


def media_movil(totales: dict[str, int], ventana: int = 3) -> dict[str, int]:
    """La media de los últimos `ventana` meses, para los meses que los tienen todos.

    Solo cuenta ventanas de meses seguidos: si falta un mes (porque se excluyó por
    incompleto), esa media no se calcula.
    """
    meses = sorted(totales)
    medias = {}
    for i in range(ventana - 1, len(meses)):
        tramo = meses[i - ventana + 1 : i + 1]
        if meses_entre(tramo[0], tramo[-1]) == tramo:
            medias[meses[i]] = gasto_medio(sum(totales[m] for m in tramo), ventana)
    return medias


def hace_un_anio(anio_mes: str) -> str:
    """«2026-03» → «2025-03»."""
    return f"{int(anio_mes[:4]) - 1:04d}{anio_mes[4:]}"


def interanual(gastos: list[GastoMes], meses: list[str], categorias, con_gasto: list[str]) -> list[tuple[str, int, int]]:
    """(mes, gasto del mes, gasto del mismo mes un año antes) de los meses con ese dato.

    Solo entran los meses cuyo mes de hace un año está dentro del histórico (desde
    el primer mes con gasto). El año anterior se toma de todo el histórico, aunque
    quede fuera del período elegido.
    """
    primero = min(con_gasto)
    con_previo = [m for m in meses if hace_un_anio(m) >= primero]
    actuales = total_mensual(gastos, con_previo, categorias)
    anteriores = total_mensual(gastos, [hace_un_anio(m) for m in con_previo], categorias)
    return [(m, actuales[m], anteriores[hace_un_anio(m)]) for m in sorted(actuales)]


def gasto_medio(total_centimos: int, n_meses: int) -> int:
    """El gasto medio mensual en céntimos, redondeado (0 si no hay meses)."""
    if n_meses == 0:
        return 0
    return (2 * total_centimos + n_meses) // (2 * n_meses)


# --- Por factura -------------------------------------------------------------


@dataclass(frozen=True)
class ImporteConcepto:
    factura_id: int
    contrato_id: int
    categoria: str
    grupo: str  # código del grupo en la capa semántica, o SIN_CLASIFICAR
    concepto: str
    variable: bool
    importe_centimos: int


def importes_por_factura(conexion: sqlite3.Connection, semantica: Semantica) -> list[ImporteConcepto]:
    """El importe de cada concepto en cada factura × contrato, con su grupo."""
    filas = conexion.execute(
        f"""WITH {_REFERENCIA}
            SELECT r.factura_ref, l.contrato_id, l.categoria_codigo, l.concepto_codigo,
                   sum(l.importe_centimos)
            FROM v_linea AS l
            JOIN referencia AS r ON r.factura_id = l.factura_id
            GROUP BY r.factura_ref, l.contrato_id, l.categoria_codigo, l.concepto_codigo
            ORDER BY r.factura_ref, l.contrato_id, min(l.posicion)"""
    )
    importes = []
    for factura_id, contrato_id, categoria, concepto, importe in filas:
        interpretacion = semantica.get(categoria)
        grupo = interpretacion.grupo_de(concepto) if interpretacion else SIN_CLASIFICAR
        variable = interpretacion is not None and concepto in interpretacion.variables
        importes.append(ImporteConcepto(factura_id, contrato_id, categoria, grupo, concepto, variable, importe))
    return importes


@dataclass(frozen=True)
class ConsumoFactura:
    factura_id: int
    contrato_id: int
    categoria: str
    magnitud: str
    unidad: str
    franja: str  # 'sin_franja' si la medición no tiene franja
    tipo_lectura: str  # 'real' o 'estimada'
    cantidad_milesimas: int


def consumo_por_factura(conexion: sqlite3.Connection) -> list[ConsumoFactura]:
    """El consumo de cada factura × contrato, por magnitud, franja y tipo de lectura.

    Una rectificativa por diferencias suma sus mediciones a la factura que corrige y
    su tipo de lectura manda: una factura estimada que se rectifica con una lectura
    real queda con el consumo neto y lectura real (criterio de la persona usuaria).
    """
    filas = conexion.execute(
        f"""WITH {_REFERENCIA}
            SELECT r.factura_ref, m.contrato_id, m.categoria_codigo, m.magnitud_codigo, m.unidad,
                   m.franja_codigo, m.tipo_lectura, r.factura_id <> r.factura_ref,
                   sum(m.cantidad_milesimas)
            FROM v_hecho_consumo_diario AS m
            JOIN referencia AS r ON r.factura_id = m.factura_id
            GROUP BY r.factura_ref, m.contrato_id, m.categoria_codigo, m.magnitud_codigo, m.unidad,
                     m.franja_codigo, m.tipo_lectura, r.factura_id <> r.factura_ref
            ORDER BY r.factura_ref, m.contrato_id, m.magnitud_codigo, m.franja_codigo, m.tipo_lectura"""
    ).fetchall()
    # Tipo de lectura de la rectificativa en cada factura × contrato × magnitud × franja
    # (real si alguna de sus mediciones lo es).
    de_rectificativa: dict[tuple, str] = {}
    for *clave, tipo, es_rectificativa, _ in filas:
        clave = tuple(clave)
        if es_rectificativa and de_rectificativa.get(clave) != "real":
            de_rectificativa[clave] = tipo
    consumo: dict[tuple, int] = {}
    for *clave, tipo, _, cantidad in filas:
        clave = tuple(clave)
        clave_tipo = (*clave, de_rectificativa.get(clave, tipo))
        consumo[clave_tipo] = consumo.get(clave_tipo, 0) + cantidad
    return [ConsumoFactura(*clave, cantidad) for clave, cantidad in consumo.items()]


def facturas_estimadas(consumo: list[ConsumoFactura], semantica: Semantica) -> set[tuple[int, int]]:
    """Las facturas (factura, contrato) cuyo volumen sale de alguna lectura estimada.

    Solo cuentan las mediciones de la magnitud que la capa semántica asigna a la categoría.
    Una factura estimada que se rectificó con una lectura real ya figura como real
    (`consumo_por_factura` suma las dos y toma el tipo de lectura de la rectificativa).
    """
    estimadas = set()
    for fila in consumo:
        interpretacion = semantica.get(fila.categoria)
        if fila.tipo_lectura == "estimada" and interpretacion is not None and fila.magnitud == interpretacion.magnitud:
            estimadas.add((fila.factura_id, fila.contrato_id))
    return estimadas


def consumo_por_franja(
    consumo: list[ConsumoFactura], categoria: str, magnitud: str
) -> dict[tuple[int, int], dict[str, int]]:
    """(factura, contrato) → franja → cantidad en milésimas, para la magnitud de una categoría.

    Suma los tipos de lectura de cada franja. Sin franjas, la única es `sin_franja`.
    """
    resultado: dict[tuple[int, int], dict[str, int]] = {}
    for fila in consumo:
        if fila.categoria == categoria and fila.magnitud == magnitud:
            por_franja = resultado.setdefault((fila.factura_id, fila.contrato_id), {})
            por_franja[fila.franja] = por_franja.get(fila.franja, 0) + fila.cantidad_milesimas
    return resultado


@dataclass(frozen=True)
class Factura:
    factura_id: int
    contrato_id: int
    categoria: str
    contrato: str  # alias, nunca el identificador (R21)
    proveedor: str
    fecha_emision: str
    fecha_inicio: str
    fecha_fin: str
    dias: int
    importe_centimos: int
    importe_variable_centimos: int  # el de los conceptos variables
    volumen_milesimas: int | None  # None si el servicio no tiene volumen
    unidad: str | None

    @property
    def precio_unitario(self) -> float | None:
        """Euros por unidad (m³ o kWh) de los conceptos variables; None sin volumen."""
        if not self.volumen_milesimas:
            return None
        return self.importe_variable_centimos * 10 / self.volumen_milesimas


def facturas(conexion: sqlite3.Connection, semantica: Semantica) -> list[Factura]:
    """Cada factura vigente × contrato: importe, parte variable, volumen, días y contrato.

    Ordenadas por categoría, inicio del período y contrato. El volumen es la suma
    de las mediciones de la magnitud que la capa semántica asigna a la categoría.
    """
    importe: dict[tuple, int] = defaultdict(int)
    variable: dict[tuple, int] = defaultdict(int)
    for fila in importes_por_factura(conexion, semantica):
        clave = (fila.factura_id, fila.contrato_id)
        importe[clave] += fila.importe_centimos
        if fila.variable:
            variable[clave] += fila.importe_centimos

    volumen: dict[tuple, int] = defaultdict(int)
    unidad: dict[tuple, str] = {}
    for fila in consumo_por_factura(conexion):
        interpretacion = semantica.get(fila.categoria)
        if interpretacion is not None and fila.magnitud == interpretacion.magnitud:
            clave = (fila.factura_id, fila.contrato_id)
            volumen[clave] += fila.cantidad_milesimas
            unidad[clave] = fila.unidad

    filas = conexion.execute(
        f"""WITH {_REFERENCIA}
            SELECT DISTINCT r.factura_ref, l.contrato_id, l.categoria_codigo, c.alias, c.proveedor_nombre,
                   f.fecha_emision, f.fecha_inicio, f.fecha_fin,
                   CAST(julianday(f.fecha_fin) - julianday(f.fecha_inicio) AS INTEGER) + 1
            FROM v_linea AS l
            JOIN referencia AS r ON r.factura_id = l.factura_id
            JOIN v_factura_vigente AS f ON f.factura_id = r.factura_ref
            JOIN v_dim_contrato AS c ON c.contrato_id = l.contrato_id
            ORDER BY l.categoria_codigo, f.fecha_inicio, c.alias"""
    )
    resultado = []
    for factura_id, contrato_id, categoria, *cabecera in filas:
        clave = (factura_id, contrato_id)
        interpretacion = semantica.get(categoria)
        con_volumen = interpretacion is not None and interpretacion.magnitud is not None
        resultado.append(
            Factura(
                factura_id, contrato_id, categoria, *cabecera,
                importe_centimos=importe[clave],
                importe_variable_centimos=variable[clave],
                volumen_milesimas=volumen[clave] if con_volumen else None,
                unidad=unidad.get(clave),
            )
        )
    return resultado


def importes_por_grupo(
    importes: list[ImporteConcepto], categoria: str
) -> dict[tuple[int, int], dict[str, int]]:
    """(factura, contrato) → grupo → importe, para una categoría. Los grupos, en el orden de la factura."""
    resultado: dict[tuple[int, int], dict[str, int]] = {}
    for fila in importes:
        if fila.categoria == categoria:
            por_grupo = resultado.setdefault((fila.factura_id, fila.contrato_id), {})
            por_grupo[fila.grupo] = por_grupo.get(fila.grupo, 0) + fila.importe_centimos
    return resultado


def importes_por_concepto(
    importes: list[ImporteConcepto], categoria: str, grupo: str
) -> dict[tuple[int, int], dict[str, int]]:
    """(factura, contrato) → concepto → importe, para un grupo de una categoría."""
    resultado: dict[tuple[int, int], dict[str, int]] = {}
    for fila in importes:
        if fila.categoria == categoria and fila.grupo == grupo:
            por_concepto = resultado.setdefault((fila.factura_id, fila.contrato_id), {})
            por_concepto[fila.concepto] = por_concepto.get(fila.concepto, 0) + fila.importe_centimos
    return resultado


def cambios_de_contrato(serie: list[Factura]) -> list[int]:
    """Las posiciones de la serie donde cambia el contrato o la comercializadora.

    `serie` son las facturas de un servicio, ordenadas por fecha. Una posición `i` está en
    la lista si su contrato (alias) o su proveedor difieren de los de la factura anterior.
    """
    return [
        i for i in range(1, len(serie))
        if (serie[i].contrato, serie[i].proveedor) != (serie[i - 1].contrato, serie[i - 1].proveedor)
    ]


def facturas_enteras(filas: list[Factura]) -> list[Factura]:
    """Una fila por factura, ordenadas por fecha: suma los contratos (líneas) de cada una.

    Sirve para los servicios con varias líneas por factura (DIGI: fibra y móvil). La fila
    toma las fechas, los días y el proveedor de la primera línea; `contrato_id` es 0 y
    `contrato` lista los alias. No tiene volumen.
    """
    por_factura: dict[int, list[Factura]] = {}
    for fila in filas:
        por_factura.setdefault(fila.factura_id, []).append(fila)
    enteras = [
        replace(
            lineas[0],
            contrato_id=0,
            contrato=", ".join(sorted({f.contrato for f in lineas})),
            importe_centimos=sum(f.importe_centimos for f in lineas),
            importe_variable_centimos=0,
            volumen_milesimas=None,
            unidad=None,
        )
        for lineas in por_factura.values()
    ]
    return sorted(enteras, key=lambda f: (f.fecha_inicio, f.factura_id))


def cambios_de_cuota(cuotas: list[int | None]) -> list[int]:
    """Las posiciones donde la cuota de una línea difiere de la de su factura anterior con esa línea.

    `cuotas` trae un valor por factura de la serie, o None si la línea no está en esa factura.
    La primera factura de una línea no cuenta como cambio.
    """
    cambios, anterior = [], None
    for i, cuota in enumerate(cuotas):
        if cuota is None:
            continue
        if anterior is not None and cuota != anterior:
            cambios.append(i)
        anterior = cuota
    return cambios


def _fecha_hace_un_anio(fecha: date) -> date:
    try:
        return fecha.replace(year=fecha.year - 1)
    except ValueError:  # 29 de febrero
        return fecha.replace(year=fecha.year - 1, day=28)


def factura_del_anio_anterior(serie: list[Factura], referencia: Factura) -> Factura | None:
    """La factura de `serie` que cubre el mismo período del año anterior que `referencia`, o None.

    Se desplaza el período de la referencia un año atrás. Entre las facturas de la misma
    categoría (con cualquier contrato) que lo solapan, se elige la de punto medio más
    cercano al del período desplazado. Si ninguna lo solapa (por ejemplo, el histórico no
    llega tan atrás), no hay factura comparable.
    """
    inicio = _fecha_hace_un_anio(date.fromisoformat(referencia.fecha_inicio))
    fin = _fecha_hace_un_anio(date.fromisoformat(referencia.fecha_fin))
    medio = (inicio.toordinal() + fin.toordinal()) / 2
    candidatas = []
    for f in serie:
        if f.categoria != referencia.categoria or f.factura_id == referencia.factura_id:
            continue
        f_inicio, f_fin = date.fromisoformat(f.fecha_inicio), date.fromisoformat(f.fecha_fin)
        if f_fin < inicio or f_inicio > fin:
            continue
        candidatas.append((abs((f_inicio.toordinal() + f_fin.toordinal()) / 2 - medio), f.fecha_inicio, f))
    return min(candidatas, key=lambda c: c[:2])[2] if candidatas else None


# --- Cascada -----------------------------------------------------------------


@dataclass(frozen=True)
class PasoCascada:
    paso: str  # 'total_a', 'volumen', 'precio', el código de un grupo o 'total_b'
    importe_centimos: int


def cascada(
    a: Factura, b: Factura, importes: list[ImporteConcepto], semantica: Semantica
) -> list[PasoCascada]:
    """De la factura A a la B: total de A, efecto volumen, efecto precio, cada grupo y total de B.

    Con q el volumen, p el precio unitario y V = p·q el importe variable:
    efecto volumen = (q_B − q_A)·p_A y efecto precio = (p_B − p_A)·q_B, que suman
    V_B − V_A. El efecto volumen se redondea al céntimo y el de precio es la
    diferencia, así que cada paso queda a menos de medio céntimo de su fórmula y
    la cascada cuadra exacta. Cada grupo aporta la diferencia de su parte no
    variable; un grupo sin conceptos fijos (solo el consumo, por ejemplo) no tiene paso.
    """
    if a.categoria != b.categoria:
        raise ErrorCascada(f"Las facturas son de categorías distintas: '{a.categoria}' y '{b.categoria}'")
    interpretacion = semantica.get(a.categoria)
    if interpretacion is None or interpretacion.magnitud is None:
        raise ErrorCascada(f"La categoría '{a.categoria}' no tiene volumen: no hay cascada")
    if not a.volumen_milesimas:
        raise ErrorCascada(f"La factura A ({a.fecha_inicio} a {a.fecha_fin}) no tiene volumen")

    precio_a = Fraction(a.importe_variable_centimos, a.volumen_milesimas)
    efecto_volumen = round((b.volumen_milesimas - a.volumen_milesimas) * precio_a)
    efecto_precio = b.importe_variable_centimos - a.importe_variable_centimos - efecto_volumen

    fijo: dict[tuple, int] = defaultdict(int)  # (factura, contrato, grupo) → parte no variable
    for fila in importes:
        if not fila.variable:
            fijo[(fila.factura_id, fila.contrato_id, fila.grupo)] += fila.importe_centimos
    grupos = [
        g.codigo for g in interpretacion.grupos if set(g.conceptos) - interpretacion.variables
    ]
    if any((f.factura_id, f.contrato_id, SIN_CLASIFICAR) in fijo for f in (a, b)):
        grupos.append(SIN_CLASIFICAR)

    pasos = [
        PasoCascada("total_a", a.importe_centimos),
        PasoCascada("volumen", efecto_volumen),
        PasoCascada("precio", efecto_precio),
    ]
    for grupo in grupos:
        diferencia = fijo[(b.factura_id, b.contrato_id, grupo)] - fijo[(a.factura_id, a.contrato_id, grupo)]
        pasos.append(PasoCascada(grupo, diferencia))
    pasos.append(PasoCascada("total_b", b.importe_centimos))
    return pasos
