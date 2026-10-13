"""Página Analysis: ¿por qué gasto lo que gasto? Una pestaña por servicio.

Las pestañas con volumen (Water, Electricity y Gas) siguen un patrón común, `_servicio`:
composición por grupo, pesos, desglose por concepto, volumen, precio unitario y cascada.
La luz suma el consumo por franja, y las tres marcan las lecturas estimadas. DIGI (fibra y
móvil) sigue el mismo patrón sin volumen: sus grupos son las líneas, y suma los cambios de cuota.
"""

import contextlib

import streamlit as st

from facturas.dashboard import datos, graficos, semantica

PESTANAS = ("Water", "Electricity", "Gas", "DIGI")
_CATEGORIA = {"Water": "agua", "Electricity": "luz", "Gas": "gas"}  # pestaña → categoría con volumen
_DIGI = ("fibra", "movil")  # las categorías de la pestaña DIGI
_GRUPO_CUOTA = "cuota"  # el grupo de la cuota de una línea, en semantica.toml

# Las franjas de la luz, en el orden en que se apilan. Toman las ranuras 4 a 6 de la paleta:
# las 0 a 3 son de los cuatro grupos de la luz, que están en la misma pestaña. Con las líneas
# de DIGI pasa lo mismo: los grupos dentro de una línea (cuota, consumo adicional, IVA) toman
# las ranuras desde la 4.
_FRANJAS = {"punta": "Peak", "llano": "Standard", "valle": "Off-peak"}
_RANURA_SECUNDARIA = 4

# Decimales del precio unitario (€ por unidad): el agua ronda K,J €/m³; el gas y la luz, X,J €/kWh.
_DECIMALES_PRECIO = {"m³": 2, "kWh": 3}


@st.cache_data(ttl="5m")
def _cargar(ruta: str):
    """Todo lo que lee Analysis de la base: facturas, importes por concepto, consumos y conceptos sin clasificar."""
    sem = semantica.cargar()
    with contextlib.closing(datos.abrir()) as conexion:
        facturas = datos.facturas(conexion, sem)
        importes = datos.importes_por_factura(conexion, sem)
        consumo = datos.consumo_por_factura(conexion)
        sin_clasificar = semantica.validar(sem, conexion)
    return facturas, importes, consumo, sin_clasificar


def mostrar() -> None:
    sem = semantica.cargar()
    facturas, importes, consumo, sin_clasificar = _cargar(str(datos.RUTA_BASE))

    st.title("Analysis")
    for c in sin_clasificar:
        nombre = sem[c.categoria].nombre if c.categoria in sem else c.categoria
        st.warning(f"Unclassified charge: «{c.concepto_nombre}» ({nombre}).")
    for pestana, contenedor in zip(PESTANAS, st.tabs(list(PESTANAS))):
        with contenedor:
            if pestana in _CATEGORIA:
                _servicio(_CATEGORIA[pestana], sem, facturas, importes, consumo)
            else:
                _digi(sem, facturas, importes)


# --- Servicios con volumen: Water, Electricity y Gas -------------------------


def _servicio(categoria: str, sem, facturas, importes, consumo) -> None:
    """El patrón común de una pestaña con volumen."""
    interpretacion = sem[categoria]
    serie = [f for f in facturas if f.categoria == categoria]
    if not serie:
        st.info(f"There are no {interpretacion.nombre.lower()} invoices loaded yet.")
        return
    color = graficos.COLORES[categoria]
    cambios = datos.cambios_de_contrato(serie)
    marcadas = datos.facturas_estimadas(consumo, sem)
    estimadas = {i for i, f in enumerate(serie) if _clave(f) in marcadas}
    _cabecera(serie)
    _avisar_cambios(serie, cambios)

    # --- Composición y pesos por grupo ---
    por_grupo = datos.importes_por_grupo(importes, categoria)
    grupos = _grupos(interpretacion, por_grupo)
    columnas = [
        (nombre, graficos.color_ranura(posicion), [por_grupo[_clave(f)].get(codigo, 0) / 100 for f in serie])
        for codigo, nombre, posicion in grupos
    ]
    _composicion_y_pesos(serie, columnas, cambios, estimadas, "group")

    # --- Desglose por concepto ---
    items = []
    for codigo, nombre, _ in grupos:
        por_concepto = datos.importes_por_concepto(importes, categoria, codigo)
        filas = [
            (
                interpretacion.nombre_concepto(c) or c,
                graficos.color_ranura(j),
                [por_concepto.get(_clave(f), {}).get(c, 0) / 100 for f in serie],
            )
            for j, c in enumerate(_conceptos_en_orden(interpretacion, codigo, por_concepto))
        ]
        items.append((nombre, filas))
    st.subheader("Breakdown by charge")
    st.caption("The charges inside each group (groups with a single charge are not repeated here).")
    _desgloses(items, serie, cambios, estimadas)

    if interpretacion.magnitud is None:
        return

    # --- Volumen, precio unitario y cascada ---
    unidad = next((f.unidad for f in serie if f.unidad), "")
    st.subheader(f"Volume ({unidad})")
    st.plotly_chart(
        graficos.volumen_por_factura(serie, color, cambios=cambios, estimadas=estimadas), width="stretch"
    )
    _lecturas(serie, estimadas, unidad)
    if categoria == "luz":
        _franjas(serie, interpretacion, consumo, cambios, estimadas)

    st.subheader("Effective unit price")
    variables = [
        nombre for g in interpretacion.grupos for c, nombre in g.conceptos.items() if c in interpretacion.variables
    ]
    st.caption(
        f"The charges that grow with the volume ({', '.join(variables)}) divided by the volume, "
        "before VAT: what each unit really costs."
    )
    st.plotly_chart(
        graficos.precio_unitario(
            serie, color, decimales=_DECIMALES_PRECIO.get(unidad, 3), cambios=cambios, estimadas=estimadas
        ),
        width="stretch",
    )

    _cascada(categoria, sem, serie, importes)


def _lecturas(serie, estimadas, unidad: str) -> None:
    """Cuántas facturas se basan en una lectura estimada (las barras a media opacidad)."""
    if not estimadas:
        st.caption("All the invoices are based on real readings.")
        return
    total = sum(f.volumen_milesimas or 0 for f in serie) / 1000
    de_estimadas = sum(serie[i].volumen_milesimas or 0 for i in estimadas) / 1000
    st.caption(
        f"{len(estimadas)} of {len(serie)} invoices are based on estimated readings "
        f"({graficos.formato_numero(de_estimadas)} of {graficos.formato_numero(total)} {unidad}): "
        "the faded bars, marked «estimated» on the axis."
    )


def _franjas(serie, interpretacion, consumo, cambios, estimadas) -> None:
    """El consumo de la luz en cada franja horaria (punta, llano y valle), en kWh."""
    por_franja = datos.consumo_por_franja(consumo, "luz", interpretacion.magnitud)
    presentes = {fr for d in por_franja.values() for fr in d}
    codigos = [f for f in _FRANJAS if f in presentes] + sorted(presentes - set(_FRANJAS))
    columnas = [
        (
            _FRANJAS.get(codigo, codigo),
            graficos.color_ranura(_RANURA_SECUNDARIA + i),
            [por_franja.get(_clave(f), {}).get(codigo, 0) / 1000 for f in serie],
        )
        for i, codigo in enumerate(codigos)
    ]
    st.subheader("Consumption by time band")
    st.caption("The kWh of each invoice in each tariff band: peak, standard and off-peak.")
    st.plotly_chart(
        graficos.apiladas(
            serie, columnas, cambios=cambios, estimadas=estimadas, unidad="kWh", decimales=0, altura=320
        ),
        width="stretch",
    )


# --- DIGI: fibra y móvil, sin volumen ----------------------------------------


def _digi(sem, facturas, importes) -> None:
    """DIGI: cada línea (contrato de fibra o de móvil) es un grupo, y cada grupo del TOML, un concepto."""
    filas = [f for f in facturas if f.categoria in _DIGI]
    if not filas:
        st.info("There are no DIGI invoices loaded yet.")
        return
    serie = datos.facturas_enteras(filas)  # una fila por factura, con todas sus líneas
    lineas = sorted({(_DIGI.index(f.categoria), f.contrato, f.contrato_id, f.categoria) for f in filas})
    total_linea = {_clave(f): f.importe_centimos for f in filas}
    _cabecera(serie)
    st.caption(
        "Lines: "
        + " · ".join(
            f"{alias} ({sem[categoria].nombre}, "
            f"{graficos.formato_mes(_extremo(serie, filas, cid, min)[:7])} to "
            f"{graficos.formato_mes(_extremo(serie, filas, cid, max)[:7])})"
            for _, alias, cid, categoria in lineas
        )
        + "."
    )

    # --- Composición y pesos por línea (con el IVA de cada una) ---
    columnas = [
        (alias, graficos.color_ranura(i), [total_linea.get((f.factura_id, cid), 0) / 100 for f in serie])
        for i, (_, alias, cid, _) in enumerate(lineas)
    ]
    _composicion_y_pesos(serie, columnas, [], set(), "line")

    # --- Desglose de cada línea por grupo (cuota, consumo adicional y el IVA aparte) ---
    codigos = []
    for categoria in _DIGI:
        codigos += [g.codigo for g in sem[categoria].grupos if g.codigo not in codigos]
    por_linea = {}
    items = []
    for _, alias, cid, categoria in lineas:
        por_grupo = {k: v for k, v in datos.importes_por_grupo(importes, categoria).items() if k[1] == cid}
        por_linea[cid] = por_grupo
        filas_linea = [
            (
                nombre,
                graficos.color_ranura(
                    _RANURA_SECUNDARIA + (codigos.index(codigo) if codigo in codigos else len(codigos))
                ),
                [por_grupo.get((f.factura_id, cid), {}).get(codigo, 0) / 100 for f in serie],
            )
            for codigo, nombre, _ in _grupos(sem[categoria], por_grupo)
        ]
        items.append((alias, filas_linea))
    st.subheader("Breakdown by charge")
    st.caption("What each line is made of: its fee, any extra usage and the VAT, apart.")
    _desgloses(items, serie, [], set())

    # --- Cambios de cuota ---
    st.subheader("Fee by line")
    st.caption(
        "The monthly fee of each line, before VAT. A diamond marks a fee that differs from the line's "
        "previous invoice (the first and last months of a line are usually prorated)."
    )
    cuotas, cambios_linea = [], []
    for i, (_, alias, cid, _) in enumerate(lineas):
        centimos = [
            por_linea[cid][(f.factura_id, cid)].get(_GRUPO_CUOTA, 0) if (f.factura_id, cid) in por_linea[cid] else None
            for f in serie
        ]
        cambios = datos.cambios_de_cuota(centimos)
        cuotas.append((alias, graficos.color_ranura(i), [None if c is None else c / 100 for c in centimos], cambios))
        cambios_linea += [(alias, serie[j], _previa(centimos, j), centimos[j]) for j in cambios]
    st.plotly_chart(graficos.cuotas_por_linea(serie, cuotas), width="stretch")
    if not cambios_linea:
        st.caption("No line changed its fee.")
    for alias, f, antes, despues in sorted(cambios_linea, key=lambda c: (c[1].fecha_inicio, c[0])):
        diferencia = despues - antes
        st.markdown(
            f"- **{alias}**, {graficos.formato_periodo(f.fecha_inicio, f.fecha_fin)}: "
            f"{graficos.formato_importe(antes)} → {graficos.formato_importe(despues)} "
            f"({'+' if diferencia > 0 else ''}{graficos.formato_importe(diferencia)})"
        )


def _extremo(serie, filas, contrato_id: int, elegir) -> str:
    """La fecha de fin de la primera o la última factura (según `elegir`: min o max) de una línea."""
    ids = {f.factura_id for f in filas if f.contrato_id == contrato_id}
    return elegir(f.fecha_fin for f in serie if f.factura_id in ids)


def _previa(valores: list, i: int):
    """El último valor que no es None antes de la posición `i`."""
    return next(v for v in reversed(valores[:i]) if v is not None)


# --- Piezas comunes -------------------------------------------------------------


def _cabecera(serie) -> None:
    st.caption(
        f"{len(serie)} invoice(s), from {graficos.formato_periodo(serie[0].fecha_inicio, serie[0].fecha_fin)} "
        f"to {graficos.formato_periodo(serie[-1].fecha_inicio, serie[-1].fecha_fin)}. "
        "Each bar or point is one billing period."
    )


def _grupos(interpretacion, por_grupo) -> list[tuple[str, str, int]]:
    """Los grupos de una categoría que tienen importes: (código, nombre, posición en `semantica.toml`).

    La posición decide el color, así que un grupo sin importes conserva su ranura. «Unclassified»
    va al final, y solo si hace falta.
    """
    presentes = {g for d in por_grupo.values() for g in d}
    todos = [(g.codigo, g.nombre) for g in interpretacion.grupos]
    todos.append((semantica.SIN_CLASIFICAR, semantica.NOMBRE_SIN_CLASIFICAR))
    return [(codigo, nombre, i) for i, (codigo, nombre) in enumerate(todos) if codigo in presentes]


def _composicion_y_pesos(serie, columnas, cambios, estimadas, que: str) -> None:
    """Las dos primeras secciones de toda pestaña: la composición y los pesos de cada `que` (group o line)."""
    st.subheader(f"Composition by {que}")
    st.caption("What each invoice is made of, in euros.")
    st.plotly_chart(
        graficos.apiladas(serie, columnas, cambios=cambios, estimadas=estimadas), width="stretch"
    )
    st.subheader(f"Weight of each {que}")
    st.caption(f"Each {que}'s share of the invoice: the weights w₁, w₂… always add up to 100 %.")
    ultimo = len(serie) - 1
    total = sum(valores[ultimo] for _, _, valores in columnas)
    if total:
        pesos = " · ".join(
            f"{nombre} {graficos.formato_numero(100 * valores[ultimo] / total, 1)} %" for nombre, _, valores in columnas
        )
        st.caption(f"Latest invoice: {pesos}.")
    st.plotly_chart(
        graficos.apiladas(serie, columnas, cambios=cambios, estimadas=estimadas, normalizar=True),
        width="stretch",
    )


def _desgloses(items, serie, cambios, estimadas) -> None:
    """Un gráfico apilado por elemento (título, columnas), en dos columnas. Con un solo componente no se repite."""
    columnas = st.columns(2)
    mostrados = 0
    for titulo, filas in items:
        if len(filas) < 2:
            continue
        with columnas[mostrados % 2]:
            st.markdown(f"**{titulo}**")
            st.plotly_chart(
                graficos.apiladas(serie, filas, cambios=cambios, estimadas=estimadas, altura=320),
                width="stretch",
            )
        mostrados += 1


def _clave(factura) -> tuple[int, int]:
    return (factura.factura_id, factura.contrato_id)


def _conceptos_en_orden(interpretacion, grupo: str, por_concepto) -> list[str]:
    """Los conceptos del grupo que aparecen en alguna factura, en el orden de `semantica.toml`."""
    presentes = {c for d in por_concepto.values() for c in d}
    declarados = next((list(g.conceptos) for g in interpretacion.grupos if g.codigo == grupo), [])
    return [c for c in declarados if c in presentes] + sorted(presentes - set(declarados))


def _avisar_cambios(serie, cambios) -> None:
    """Un aviso por cada cambio de contrato o de comercializadora (marcado también en los ejes)."""
    for i in cambios:
        anterior, f = serie[i - 1], serie[i]
        st.caption(
            f"Contract change before the period {graficos.formato_periodo(f.fecha_inicio, f.fecha_fin)}: "
            f"{anterior.contrato} ({anterior.proveedor}) → {f.contrato} ({f.proveedor}). "
            "The series continues as one."
        )


# --- Cascada -----------------------------------------------------------------

_COMPARACIONES = ("Same period last year", "Previous invoice", "Pick two invoices")


def _cascada(categoria: str, sem, serie, importes) -> None:
    interpretacion = sem[categoria]
    st.subheader("What changed between two invoices")
    st.caption(
        "From invoice A to invoice B: the volume effect (using more or less, at A's price), "
        "the price effect (each unit costing more or less, for B's volume) and the change in "
        "the charges that do not depend on volume. Red means the bill went up; blue, down."
    )
    if len(serie) < 2:
        st.info("A comparison needs at least two invoices.")
        return
    ultima = serie[-1]
    del_anio_anterior = datos.factura_del_anio_anterior(serie, ultima)
    eleccion = st.radio(
        "Compare the latest invoice with",
        _COMPARACIONES,
        index=0 if del_anio_anterior else 1,
        horizontal=True,
        key=f"{categoria}_comparison",
    )
    if eleccion == _COMPARACIONES[0]:
        if del_anio_anterior is None:
            st.info("No invoice covers the same period a year before the latest one.")
            return
        a, b = del_anio_anterior, ultima
    elif eleccion == _COMPARACIONES[1]:
        a, b = serie[-2], ultima
    else:
        posiciones = list(range(len(serie)))[::-1]  # la más reciente primero
        etiqueta = {
            i: f"{graficos.formato_periodo(f.fecha_inicio, f.fecha_fin)} · {graficos.formato_importe(f.importe_centimos)}"
            for i, f in enumerate(serie)
        }
        col_a, col_b = st.columns(2)
        i = col_a.selectbox("Invoice A (from)", posiciones, index=1, format_func=etiqueta.get, key=f"{categoria}_a")
        j = col_b.selectbox("Invoice B (to)", posiciones, index=0, format_func=etiqueta.get, key=f"{categoria}_b")
        if i == j:
            st.info("Pick two different invoices.")
            return
        a, b = serie[i], serie[j]

    try:
        pasos = datos.cascada(a, b, importes, sem)
    except datos.ErrorCascada:
        st.warning("Invoice A has no volume, so there is nothing to compare.")
        return
    nombres = [_nombre_paso(p.paso, interpretacion, a, b) for p in pasos]
    for columna, rotulo, f in zip(st.columns(2), ("Invoice A", "Invoice B"), (a, b)):
        columna.metric(
            f"{rotulo}: {graficos.formato_periodo(f.fecha_inicio, f.fecha_fin)}",
            graficos.formato_importe(f.importe_centimos),
            border=True,
        )
        columna.caption(_resumen(f))
    ampliar = st.toggle("Zoom in on the changes (the axis then does not start at zero)", key=f"{categoria}_zoom")
    st.plotly_chart(
        graficos.cascada(nombres, [p.importe_centimos for p in pasos], ampliar=ampliar), width="stretch"
    )


def _resumen(f) -> str:
    """Días, volumen y precio unitario de una factura, en una línea."""
    if not f.volumen_milesimas:
        return f"{f.dias} days · no volume"
    precio = graficos.formato_numero(f.precio_unitario, _DECIMALES_PRECIO.get(f.unidad, 3))
    volumen = graficos.formato_numero(f.volumen_milesimas / 1000)
    return f"{f.dias} days · {volumen} {f.unidad} · {precio} €/{f.unidad}"


def _nombre_paso(paso: str, interpretacion, a, b) -> str:
    """El texto del eje para un paso de la cascada."""
    if paso == "total_a":
        return f"Invoice A<br>{a.dias} days"
    if paso == "total_b":
        return f"Invoice B<br>{b.dias} days"
    if paso == "volumen":
        return "Volume effect"
    if paso == "precio":
        return "Price effect"
    nombre = interpretacion.nombre_grupo(paso)
    con_variables = any(
        paso == g.codigo and set(g.conceptos) & interpretacion.variables for g in interpretacion.grupos
    )
    return f"{nombre}<br>(fixed part)" if con_variables else nombre
