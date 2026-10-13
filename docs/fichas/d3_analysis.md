# Ficha de la etapa 3 del dashboard: Analysis (3a, 3b y 3c)

Complementa [`task_dashboard.md`](../../task_dashboard.md), «Etapa 3». **Las tres partes están hechas** (2026-10-06) y pendientes de que la persona usuaria las vea y las apruebe, juntas. Esta ficha sirve para retocarlas tras verlas.

## Leer (solo esto)

- `task_dashboard.md`, por secciones: «Cómo se usa», «Objetivo», «Etapas» (la tabla y la lista de lectura), «Forma de trabajo», «Interfaz» (se corta en su primera subsección), «Página 2: Analysis» y «Etapa 3». Comandos `awk`, en «Etapas».
- `tarea.md`: «Forma de trabajo», «Definición de terminado» y «Punto de control».
- Las entradas de la bitácora «Dashboard, etapa 3a», «3b» y «3c», solo «Decisiones no previstas».
- Skills: `dataviz` solo si se cambia el estilo (la paleta y las marcas están en `graficos.py`); de `developing-with-streamlit`, solo la referencia del tema que haga falta.

## Lo que dejó la etapa 2

- **Archivos:** `src/facturas/dashboard/app.py` (navegación con `st.navigation`; cada página es una función `mostrar()`), `paginas/overview.py`, `paginas/analysis.py` y `graficos.py`. Se lanza con `scripts\dashboard.ps1`.
- **Caché:** `@st.cache_data(ttl="5m")` con la ruta de la base como argumento (`str(datos.RUTA_BASE)`); la función abre su conexión con `datos.abrir()` dentro de `contextlib.closing`.
- **Tests de la app:** `AppTest` con `monkeypatch.setattr(datos, "RUTA_BASE", ruta_base)`.
- Estilo: tema oscuro fijo (`.streamlit/config.toml`), fondo transparente, rejilla tenue, borde de 2 px del color del fondo, `separators=",."`, importes `1.234,56 €` (`graficos.formato_importe`).

## Lo que dejó la etapa 3

**`datos.py`** (sin Streamlit; todo con tests en `test_dashboard_datos.py`):

- `importes_por_grupo(importes, categoria)` y `importes_por_concepto(importes, categoria, grupo)` → `{(factura_id, contrato_id): {grupo|concepto: céntimos}}`.
- `cambios_de_contrato(serie)` → posiciones donde cambia el alias o el proveedor respecto de la factura anterior.
- `factura_del_anio_anterior(serie, referencia)` → la factura de la misma categoría (cualquier contrato) que solapa el período de la referencia desplazado un año atrás, con el punto medio más cercano; `None` si no hay.
- `facturas_estimadas(consumo, semantica)` → `{(factura_id, contrato_id)}` con alguna medición estimada de la magnitud del servicio; `consumo_por_franja(consumo, categoria, magnitud)`.
- `facturas_enteras(filas)` (una fila por factura, sumando sus líneas; para DIGI) y `cambios_de_cuota(cuotas)`.

**`graficos.py`**:

- `RANURAS` (las ocho de la paleta de `dataviz`, modo oscuro, validadas sobre el fondo) y `color_ranura(i)`. Los grupos de una pestaña toman la ranura de su posición en `semantica.toml` (un grupo sin importes conserva la suya); los conceptos, la de su posición dentro del grupo. Las franjas de la luz y los grupos dentro de una línea de DIGI usan desde la ranura 4. Los gráficos de una sola serie usan el color del servicio.
- `apiladas(serie, columnas, *, cambios, estimadas, unidad, decimales, normalizar, altura)` (barras por factura, en euros o al 100 %), `volumen_por_factura`, `precio_unitario`, `cascada(nombres, importes, *, ampliar)` y `cuotas_por_linea`. `serie` es una lista de `Factura`; el eje x son posiciones 0..n−1 con el texto del período (dos facturas pueden tener el mismo texto).
- Formatos: `formato_numero(valor, decimales)`, `formato_periodo`, `formato_dia`.

**`paginas/analysis.py`**: `_servicio(categoria, …)` es el patrón común (Water, Electricity y Gas); `_digi(…)` es el de DIGI. Las piezas compartidas son `_grupos`, `_composicion_y_pesos`, `_desgloses` y `_cascada`. Las claves de los widgets llevan el prefijo de la categoría (`agua_comparison`, `agua_a`, `agua_b`, `agua_zoom`).

## Pendientes heredados (resueltos)

- **Cascada por defecto:** `factura_del_anio_anterior`. Sin factura un año atrás, la comparación empieza por «Previous invoice».
- **Gas, abr–jun 2026:** cuenta como real (`facturas_estimadas` parte de `consumo_por_factura`, que ya suma la rectificativa).
- **Cambio de contrato:** línea vertical «Contract change» en los gráficos por factura y un aviso con los alias y proveedores. En DIGI no aplica: las líneas aparecen y desaparecen, y se listan con sus meses.
- **DIGI:** cada línea (contrato) es un grupo; dentro de cada una, los grupos del TOML (cuota, consumo adicional, IVA).
- **Precio unitario:** sin IVA; 2 decimales en €/m³ y 3 en €/kWh.

## Pendientes

- La aprobación visual de la persona usuaria (el agente no abre la app). Mirar sobre todo: la etiqueta «Contract change» frente a la leyenda, el eje x de la luz (22 facturas, texto en vertical) y que la cascada se lea bien (hay un conmutador para ampliar los cambios).
- Los gráficos por factura muestran toda la historia; Analysis no tiene filtro de período (la especificación no lo pide). Si la persona usuaria lo quiere, es un filtro más en `analysis.py`.

## Tests

- De la etapa: `.venv\Scripts\python -m pytest -q --tb=short tests\test_dashboard_app.py tests\test_dashboard_datos.py tests\test_dashboard_semantica.py tests\test_codigo.py`.
- Al cerrar, todos: `.venv\Scripts\python -m pytest -q --tb=line` (unos 3 min).
