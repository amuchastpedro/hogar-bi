"""Página Overview: ¿cuánto gasto, en total y en cada servicio?"""

import contextlib
from datetime import date

import streamlit as st

from facturas.dashboard import datos, graficos, semantica

PERIODOS = {
    "month": "A month",
    "year": "A year",
    "all": "All history",
    "ytd": "Year to date",
    "last12": "Last 12 months",
    "range": "Custom range",
}


@st.cache_data(ttl="5m")
def _cargar(ruta: str):
    """Todo lo que lee el Overview de la base: gasto, cobertura y conceptos sin clasificar."""
    sem = semantica.cargar()
    with contextlib.closing(datos.abrir()) as conexion:
        gastos = datos.gasto_mensual(conexion)
        if not gastos:
            return gastos, [], []
        meses = datos.meses_entre(min(g.anio_mes for g in gastos), max(g.anio_mes for g in gastos))
        cobertura = datos.cobertura_mensual(conexion, list(sem), meses[0], meses[-1])
        sin_clasificar = semantica.validar(sem, conexion)
    return gastos, cobertura, sin_clasificar


def mostrar() -> None:
    sem = semantica.cargar()
    nombres = {c: sem[c].nombre for c in graficos.ORDEN_SERVICIOS if c in sem}
    gastos, cobertura, sin_clasificar = _cargar(str(datos.RUTA_BASE))

    st.title("Overview")
    for c in sin_clasificar:
        st.warning(f"Unclassified charge: «{c.concepto_nombre}» ({nombres.get(c.categoria, c.categoria)}).")
    if not gastos:
        st.info("There are no invoices loaded yet.")
        return

    con_gasto = sorted({g.anio_mes for g in gastos})
    historico = datos.meses_entre(con_gasto[0], con_gasto[-1])
    anios = sorted({m[:4] for m in historico})

    # --- Filtros, en una fila ---
    col_servicios, col_periodo, col_detalle, col_casilla = st.columns(
        [3, 2, 3, 2], vertical_alignment="bottom"
    )
    elegidos = col_servicios.pills(
        "Services",
        options=list(nombres),
        selection_mode="multi",
        default=list(nombres),
        format_func=nombres.get,
        label_visibility="collapsed",
        key="service_filter",
    )
    periodo = col_periodo.selectbox("Period", list(PERIODOS), format_func=PERIODOS.get, index=2)
    opciones = {}
    with col_detalle:
        if periodo == "month":
            opciones["mes"] = st.selectbox("Month", historico[::-1], format_func=graficos.formato_mes)
        elif periodo == "year":
            opciones["anio"] = st.selectbox("Year", anios[::-1])
        elif periodo == "range":
            desde_col, hasta_col = st.columns(2)
            opciones["desde"] = desde_col.selectbox("From", historico, format_func=graficos.formato_mes)
            opciones["hasta"] = hasta_col.selectbox(
                "To", historico, index=len(historico) - 1, format_func=graficos.formato_mes
            )
    excluir = col_casilla.checkbox("Exclude incomplete months")

    if not elegidos:
        st.info("Pick at least one service.")
        return
    if periodo == "range" and opciones["desde"] > opciones["hasta"]:
        st.warning("The start month is after the end month.")
        return

    # --- Meses del período ---
    meses = datos.meses_del_periodo(periodo, con_gasto, date.today(), **opciones)
    completos = semantica.meses_completos(cobertura, elegidos)
    incompletos = [m for m in meses if not completos.get(m, False)]
    if excluir:
        meses = datos.quitar_incompletos(meses, completos)
    if not meses:
        st.info("No months to show with these filters.")
        return

    totales = datos.total_por_categoria(gastos, meses, elegidos)
    total = sum(totales.values())

    # --- KPIs ---
    columnas = st.columns(2 + len(elegidos))
    columnas[0].metric("Total spend", graficos.formato_importe(total), border=True)
    columnas[1].metric(
        "Average per month", graficos.formato_importe(datos.gasto_medio(total, len(meses))), border=True
    )
    for columna, categoria in zip(columnas[2:], elegidos):
        columna.metric(nombres[categoria], graficos.formato_importe(totales[categoria]), border=True)
    if excluir and incompletos:
        st.caption(f"{len(incompletos)} incomplete month(s) excluded: {_lista(incompletos)}.")
    elif incompletos:
        st.warning(
            f"{len(incompletos)} of {len(meses)} months in this period are incomplete "
            f"(not every day is covered by an invoice): {_lista(incompletos)}. "
            "Totals and averages understate the real spend; tick «Exclude incomplete months» to leave them out."
        )

    # --- Gráficos ---
    st.subheader("Monthly spend")
    serie = datos.serie_mensual(gastos, meses, elegidos)
    st.plotly_chart(
        graficos.evolucion_mensual(serie, {c: nombres[c] for c in elegidos}, completos),
        width="stretch",
    )
    if incompletos and not excluir:
        st.caption("Faded bars are incomplete months (partial).")

    st.subheader("Trend")
    st.caption("Total spend per month and its 3-month average (only runs of consecutive months).")
    totales_mes = datos.total_mensual(gastos, meses, elegidos)
    st.plotly_chart(graficos.tendencia(totales_mes, datos.media_movil(totales_mes)), width="stretch")

    st.subheader("Year over year")
    st.caption("Each month against the same month a year earlier (months with no data a year back are left out).")
    filas = datos.interanual(gastos, meses, elegidos, con_gasto)
    if filas:
        st.plotly_chart(graficos.interanual(filas), width="stretch")
    else:
        st.info("No month in this period has a matching month a year earlier.")

    st.subheader("Service mix")
    st.caption("Share of each month's spend taken by each service.")
    st.plotly_chart(
        graficos.peso_mensual(serie, {c: nombres[c] for c in elegidos}, completos), width="stretch"
    )


def _lista(meses: list[str]) -> str:
    return ", ".join(graficos.formato_mes(m) for m in meses)
