"""Punto de entrada del dashboard: navegación entre Overview y Analysis.

Se lanza con `scripts/dashboard.ps1` (que fija PYTHONPATH=src).
"""

import streamlit as st

from facturas.dashboard.paginas import analysis, overview
from facturas.dashboard import graficos

st.set_page_config(page_title="Household bills", layout="wide")

graficos.inyectar_css()

pagina = st.navigation(
    [
        st.Page(overview.mostrar, title="Overview", url_path="overview", default=True),
        st.Page(analysis.mostrar, title="Analysis", url_path="analysis"),
    ]
)
pagina.run()
