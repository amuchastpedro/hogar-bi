"""Estilo y gráficos compartidos del dashboard (skill dataviz).

Cada servicio tiene el mismo color en todas las páginas, el de bi-hogar. Los importes se muestran como `1.234,56 €`.
"""

import plotly.graph_objects as go
import streamlit as st

from facturas.dashboard.datos import Factura, GastoMes

# Servicios en el orden de los botones y del apilado (el del otro proyecto, bi-hogar).
ORDEN_SERVICIOS = ("gas", "luz", "agua", "fibra", "movil")
# Colores copiados de bi-hogar (`SERVICE_META`); el tema es oscuro fijo (.streamlit/config.toml).
COLORES = {
    "gas": "#d95926",
    "luz": "#c98500",
    "agua": "#3987e5",
    "fibra": "#199e70",
    "movil": "#d55181",
}
# Las ocho ranuras de la paleta de referencia de dataviz, modo oscuro (validadas sobre el
# fondo: CVD adyacente 8,4 y visión normal 19,3). Dentro de una pestaña de Analysis, cada
# grupo (o cada concepto, dentro de un grupo) toma la ranura de su posición en
# `semantica.toml`, así que su color es estable. Los gráficos de una sola serie usan, en
# cambio, el color del servicio.
RANURAS = ("#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767")
_AUMENTO, _DISMINUCION, _TOTAL = "#e66767", "#3987e5", "#898781"  # par divergente rojo-azul y gris
_FONDO = "#0d0d0d"
_SUPERFICIE = "#1a1a19"
_ACENTO = "#9085e9"
_TEXTO = "#ffffff"
_TEXTO_SECUNDARIO = "#c3c2b7"
_REJILLA = "#2c2c2a"
_SEPARADORES = ",."  # decimal «,» y miles «.»

# Botones de servicio (st.pills con key="service_filter"). Cada botón activo lleva su
# color de servicio, con el fondo transparentado. Streamlit pone a cada botón el id
# «<widget>-<posición>», y los botones van en el orden de ORDEN_SERVICIOS.
_ALFA_BOTON = 0.30


def _rgba(hex_color: str, alfa: float) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alfa})"


CSS = "<style>" + "".join(
    f'.st-key-service_filter button[id$="-{i}"][aria-checked="true"] {{'
    f" background-color: {_rgba(COLORES[c], _ALFA_BOTON)} !important;"
    f" border-color: {COLORES[c]} !important; color: {_TEXTO} !important; }}"
    for i, c in enumerate(ORDEN_SERVICIOS)
) + "</style>"


def inyectar_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def formato_importe(centimos: int) -> str:
    """1234567 → «12.345,67 €»."""
    signo = "-" if centimos < 0 else ""
    euros, resto = divmod(abs(centimos), 100)
    return f"{signo}{euros:,}".replace(",", ".") + f",{resto:02d} €"


_MESES = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def formato_numero(valor: float, decimales: int = 0) -> str:
    """12345.6 → «12.346» (miles con punto, decimales con coma)."""
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "\0").replace(".", ",").replace("\0", ".")


def formato_mes(anio_mes: str) -> str:
    """«2026-08» → «Aug 2026»."""
    return f"{_MESES[int(anio_mes[5:]) - 1]} {anio_mes[:4]}"


def formato_dia(fecha: str) -> str:
    """«2026-08-09» → «9 Aug»."""
    return f"{int(fecha[8:])} {_MESES[int(fecha[5:7]) - 1]}"


def formato_periodo(inicio: str, fin: str) -> str:
    """Un período de facturación: «11 Oct 2024 – 12 Dec 2024»."""
    return f"{formato_dia(inicio)} {inicio[:4]} – {formato_dia(fin)} {fin[:4]}"


def color_ranura(posicion: int) -> str:
    """El color de la ranura `posicion` (desde 0); pasadas las ocho, gris (la cola, «otros»)."""
    return RANURAS[posicion] if posicion < len(RANURAS) else _TEXTO_SECUNDARIO


def _base(altura: int) -> go.Figure:
    figura = go.Figure()
    figura.update_layout(
        height=altura,
        margin=dict(l=8, r=8, t=24, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=_TEXTO_SECUNDARIO, size=13),
        separators=_SEPARADORES,
        hoverlabel=dict(bgcolor=_SUPERFICIE, font=dict(color=_TEXTO)),
        legend=dict(orientation="h", y=1.1, x=0),
    )
    figura.update_xaxes(showgrid=False, linecolor=_REJILLA, ticks="")
    figura.update_yaxes(gridcolor=_REJILLA, zeroline=False, ticks="")
    return figura


def evolucion_mensual(serie: list[GastoMes], nombres: dict[str, str], completos: dict[str, bool]):
    """Barras apiladas por servicio y mes; los meses incompletos van a media opacidad."""
    figura = _base(380)
    meses = sorted({g.anio_mes for g in serie})
    etiquetas = [formato_mes(m) for m in meses]
    opacidad = [1.0 if completos.get(m, False) else 0.5 for m in meses]
    sufijo = ["" if completos.get(m, False) else " (partial)" for m in meses]
    for categoria, nombre in nombres.items():
        importes = {g.anio_mes: g.importe_centimos for g in serie if g.categoria == categoria}
        figura.add_bar(
            x=etiquetas,
            y=[importes.get(m, 0) / 100 for m in meses],
            name=nombre,
            marker=dict(
                color=COLORES[categoria],
                opacity=opacidad,
                line=dict(color=_FONDO, width=2),
            ),
            customdata=sufijo,
            hovertemplate="%{x}<br>" + nombre + ": %{y:,.2f} €%{customdata}<extra></extra>",
        )
    figura.update_layout(barmode="stack", showlegend=len(nombres) > 1)
    figura.update_xaxes(type="category")
    figura.update_yaxes(tickformat=",.0f", ticksuffix=" €")
    return figura


def tendencia(totales: dict[str, int], medias: dict[str, int]):
    """El total de cada mes (fino y tenue) y su media móvil de 3 meses (línea gruesa)."""
    figura = _base(320)
    meses = sorted(totales)
    figura.add_scatter(
        x=[formato_mes(m) for m in meses],
        y=[totales[m] / 100 for m in meses],
        name="Month total",
        mode="lines+markers",
        line=dict(color=_TEXTO_SECUNDARIO, width=1),
        marker=dict(size=6),
        opacity=0.6,
        hovertemplate="%{x}<br>Month total: %{y:,.2f} €<extra></extra>",
    )
    figura.add_scatter(
        x=[formato_mes(m) for m in meses if m in medias],
        y=[medias[m] / 100 for m in meses if m in medias],
        name="3-month average",
        mode="lines",
        line=dict(color=_ACENTO, width=3),
        hovertemplate="%{x}<br>3-month average: %{y:,.2f} €<extra></extra>",
    )
    figura.update_xaxes(type="category")
    figura.update_yaxes(tickformat=",.0f", ticksuffix=" €", rangemode="tozero")
    return figura


def interanual(filas: list[tuple[str, int, int]]):
    """Barras agrupadas: cada mes frente al mismo mes del año anterior."""
    figura = _base(320)
    etiquetas = [formato_mes(m) for m, _, _ in filas]
    figura.add_bar(
        x=etiquetas,
        y=[anterior / 100 for _, _, anterior in filas],
        name="Same month, previous year",
        marker=dict(color=_TEXTO_SECUNDARIO, opacity=0.45),
        hovertemplate="%{x}<br>Previous year: %{y:,.2f} €<extra></extra>",
    )
    figura.add_bar(
        x=etiquetas,
        y=[actual / 100 for _, actual, _ in filas],
        name="Month",
        marker=dict(color=_ACENTO),
        hovertemplate="%{x}<br>Month: %{y:,.2f} €<extra></extra>",
    )
    figura.update_layout(barmode="group")
    figura.update_xaxes(type="category")
    figura.update_yaxes(tickformat=",.0f", ticksuffix=" €")
    return figura


def peso_mensual(serie: list[GastoMes], nombres: dict[str, str], completos: dict[str, bool]):
    """Barras al 100 %: qué parte del gasto de cada mes se lleva cada servicio."""
    figura = _base(380)
    meses = sorted({g.anio_mes for g in serie})
    etiquetas = [formato_mes(m) for m in meses]
    opacidad = [1.0 if completos.get(m, False) else 0.5 for m in meses]
    sufijo = ["" if completos.get(m, False) else " (partial)" for m in meses]
    for categoria, nombre in nombres.items():
        importes = {g.anio_mes: g.importe_centimos for g in serie if g.categoria == categoria}
        figura.add_bar(
            x=etiquetas,
            y=[importes.get(m, 0) / 100 for m in meses],
            name=nombre,
            marker=dict(color=COLORES[categoria], opacity=opacidad, line=dict(color=_FONDO, width=2)),
            customdata=[(importes.get(m, 0) / 100, x) for m, x in zip(meses, sufijo)],
            hovertemplate=(
                "%{x}<br>" + nombre + ": %{y:.1f} % (%{customdata[0]:,.2f} €)%{customdata[1]}<extra></extra>"
            ),
        )
    figura.update_layout(barmode="stack", barnorm="percent", showlegend=len(nombres) > 1)
    figura.update_xaxes(type="category")
    figura.update_yaxes(ticksuffix=" %", tickformat=".0f")
    return figura


# --- Analysis: un punto por factura -----------------------------------------
#
# En Analysis cada barra o punto es un período de facturación. El eje x usa posiciones
# 0..n-1 con el texto del período, no categorías: dos facturas pueden tener el mismo texto.


def _eje_facturas(figura: go.Figure, serie: list[Factura], cambios, estimadas=()) -> None:
    """El eje x de una serie de facturas, con los cambios de contrato y las lecturas estimadas marcados."""
    n = len(serie)
    if n <= 12:
        textos = [f"{formato_dia(f.fecha_inicio)}–{formato_dia(f.fecha_fin)}<br>{f.fecha_fin[:4]}" for f in serie]
        textos = [t + ("<br>estimated" if i in estimadas else "") for i, t in enumerate(textos)]
    else:
        textos = [formato_mes(f.fecha_fin[:7]) + (" (est.)" if i in estimadas else "") for i, f in enumerate(serie)]
    figura.update_xaxes(
        tickmode="array", tickvals=list(range(n)), ticktext=textos, range=[-0.6, n - 0.4],
        tickangle=0 if n <= 12 else -45,
    )
    for i in cambios:
        figura.add_vline(
            x=i - 0.5, line=dict(color=_TEXTO_SECUNDARIO, width=1),
            annotation_text="Contract change", annotation_position="top",
            annotation_font=dict(color=_TEXTO_SECUNDARIO, size=12),
        )


def _datos_hover(serie: list[Factura]) -> list[tuple[str, int]]:
    return [(formato_periodo(f.fecha_inicio, f.fecha_fin), f.dias) for f in serie]


def apiladas(
    serie: list[Factura],
    columnas: list[tuple[str, str, list[float]]],
    *,
    cambios=(),
    estimadas=(),
    unidad: str = "€",
    decimales: int = 2,
    normalizar: bool = False,
    altura: int = 360,
) -> go.Figure:
    """Barras apiladas por factura. Cada columna es (nombre, color, un valor por factura).

    Con `normalizar`, cada barra se lleva al 100 %: los pesos wᵢ de las columnas, que
    suman 1. El hover da entonces el porcentaje y el valor.
    """
    figura = _base(altura)
    x = list(range(len(serie)))
    hover = _datos_hover(serie)
    totales = [sum(valores[i] for _, _, valores in columnas) for i in x]
    for nombre, color, valores in columnas:
        if normalizar:
            y = [100 * v / t if t else 0 for v, t in zip(valores, totales)]
            plantilla = (
                "%{customdata[0]}<br>" + nombre + ": %{y:.1f} % (%{customdata[2]:,." + str(decimales)
                + "f} " + unidad + ")<extra></extra>"
            )
        else:
            y = valores
            plantilla = (
                "%{customdata[0]} (%{customdata[1]} days)<br>" + nombre + ": %{y:,." + str(decimales)
                + "f} " + unidad + "<extra></extra>"
            )
        figura.add_bar(
            x=x, y=y, name=nombre,
            marker=dict(color=color, line=dict(color=_FONDO, width=2)),
            customdata=[(*h, v) for h, v in zip(hover, valores)],
            hovertemplate=plantilla,
        )
    figura.update_layout(barmode="stack", bargap=0.5, showlegend=len(columnas) > 1)
    figura.update_yaxes(
        ticksuffix=" %" if normalizar else f" {unidad}", tickformat=".0f" if normalizar else ",.0f",
    )
    _eje_facturas(figura, serie, cambios, estimadas)
    return figura


def volumen_por_factura(
    serie: list[Factura], color: str, *, cambios=(), estimadas=(), altura: int = 320
) -> go.Figure:
    """El volumen de cada factura (m³ o kWh), con su valor sobre la barra.

    Las facturas con lectura estimada (posiciones en `estimadas`) van a media opacidad,
    como serie aparte, para verlas frente a las de lectura real.
    """
    figura = _base(altura)
    unidad = next((f.unidad for f in serie if f.unidad), "")
    valores = [(f.volumen_milesimas or 0) / 1000 for f in serie]
    hover = _datos_hover(serie)
    estimadas = set(estimadas)
    lecturas = (
        ("Real reading", 1.0, [i for i in range(len(serie)) if i not in estimadas]),
        ("Estimated reading", 0.45, sorted(estimadas)),
    )
    for nombre, opacidad, posiciones in lecturas:
        if not posiciones:
            continue
        figura.add_bar(
            x=posiciones, y=[valores[i] for i in posiciones], name=nombre,
            marker=dict(color=color, opacity=opacidad, line=dict(color=_FONDO, width=2)),
            text=[formato_numero(valores[i]) for i in posiciones], textposition="outside",
            textfont=dict(color=_TEXTO_SECUNDARIO),
            customdata=[(*hover[i], valores[i] / serie[i].dias) for i in posiciones],
            hovertemplate=(
                "%{customdata[0]} (%{customdata[1]} days)<br>" + nombre + ": %{y:,.0f} " + unidad
                + " (%{customdata[2]:,.2f} per day)<extra></extra>"
            ),
        )
    figura.update_layout(barmode="overlay", bargap=0.5, showlegend=bool(estimadas))
    figura.update_yaxes(ticksuffix=f" {unidad}", tickformat=",.0f", rangemode="tozero")
    _eje_facturas(figura, serie, cambios, estimadas)
    return figura


def precio_unitario(
    serie: list[Factura], color: str, *, decimales: int, cambios=(), estimadas=(), altura: int = 320
) -> go.Figure:
    """El precio unitario efectivo de cada factura (€ por m³ o kWh, sin IVA)."""
    figura = _base(altura)
    unidad = next((f.unidad for f in serie if f.unidad), "")
    puntos = [(i, f.precio_unitario) for i, f in enumerate(serie) if f.precio_unitario is not None]
    hover = _datos_hover(serie)
    figura.add_scatter(
        x=[i for i, _ in puntos], y=[p for _, p in puntos], name="Unit price", mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=9, color=color, line=dict(color=_FONDO, width=2)),
        customdata=[hover[i] for i, _ in puntos],
        hovertemplate=(
            "%{customdata[0]} (%{customdata[1]} days)<br>%{y:,." + str(decimales) + "f} €/" + unidad
            + "<extra></extra>"
        ),
    )
    figura.update_layout(showlegend=False)
    figura.update_yaxes(tickformat=f",.{decimales}f", ticksuffix=f" €/{unidad}")
    _eje_facturas(figura, serie, cambios, estimadas)
    return figura


def cascada(nombres: list[str], importes: list[int], *, ampliar: bool = False) -> go.Figure:
    """De la factura A a la B: el total de A, cada cambio (en céntimos) y el total de B.

    `nombres` e `importes` van alineados: el primero es el total de A, el último el de B y
    los del medio son los cambios. Subir el gasto va en rojo y bajarlo, en azul. Con
    `ampliar`, el eje no parte de cero, para ver los cambios pequeños frente a los totales.
    """
    figura = _base(400)
    n = len(importes)
    textos = [
        formato_importe(importe) if i in (0, n - 1) else f"{'+' if importe > 0 else ''}{formato_importe(importe)}"
        for i, importe in enumerate(importes)
    ]
    figura.add_trace(
        go.Waterfall(
            x=nombres, y=[i / 100 for i in importes],
            measure=["absolute"] + ["relative"] * (n - 2) + ["total"],
            text=textos, textposition="outside", textfont=dict(color=_TEXTO_SECUNDARIO),
            increasing=dict(marker=dict(color=_AUMENTO, line=dict(color=_FONDO, width=2))),
            decreasing=dict(marker=dict(color=_DISMINUCION, line=dict(color=_FONDO, width=2))),
            totals=dict(marker=dict(color=_TOTAL, line=dict(color=_FONDO, width=2))),
            connector=dict(line=dict(color=_REJILLA, width=1)),
            hovertemplate="%{x}<br>%{text}<extra></extra>",
        )
    )
    figura.update_layout(showlegend=False, bargap=0.4)
    figura.update_xaxes(type="category")
    figura.update_yaxes(tickformat=",.0f", ticksuffix=" €")
    niveles = [sum(importes[: i + 1]) / 100 for i in range(n - 1)]  # el nivel tras cada paso
    if ampliar:
        bajo, alto = min(niveles), max(niveles)
        margen = max(alto - bajo, 1) * 0.6
        figura.update_yaxes(range=[bajo - margen, alto + margen])
    else:
        figura.update_yaxes(rangemode="tozero")
    return figura


def cuotas_por_linea(
    serie: list[Factura], lineas: list[tuple[str, str, list[float | None], list[int]]], *, altura: int = 340
) -> go.Figure:
    """La cuota (sin IVA) de cada línea en cada factura, con los cambios de cuota marcados.

    Cada línea es (nombre, color, cuotas, cambios): `cuotas` trae un valor en euros por factura
    (None donde la línea no está) y `cambios` son las posiciones donde la cuota difiere de la
    anterior de esa línea, que llevan un rombo grande.
    """
    figura = _base(altura)
    hover = _datos_hover(serie)
    for nombre, color, cuotas, cambios in lineas:
        anterior: dict[int, float] = {}
        previa = None
        for i, cuota in enumerate(cuotas):
            if cuota is not None:
                anterior[i] = previa
                previa = cuota
        figura.add_scatter(
            x=list(range(len(serie))), y=cuotas, name=nombre, mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(
                color=color,
                size=[13 if i in cambios else 8 for i in range(len(serie))],
                symbol=["diamond" if i in cambios else "circle" for i in range(len(serie))],
                line=dict(color=_FONDO, width=2),
            ),
            customdata=[
                (*hover[i], f" (changed from {formato_importe(round(100 * anterior[i]))})" if i in cambios else "")
                for i in range(len(serie))
            ],
            hovertemplate="%{customdata[0]}<br>" + nombre + ": %{y:,.2f} €%{customdata[2]}<extra></extra>",
        )
    figura.update_layout(showlegend=len(lineas) > 1)
    figura.update_yaxes(tickformat=",.0f", ticksuffix=" €", rangemode="tozero")
    _eje_facturas(figura, serie, ())
    return figura
