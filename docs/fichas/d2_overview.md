# Ficha de la etapa 2 del dashboard: esqueleto y Overview

Complementa [`task_dashboard.md`](../../task_dashboard.md), «Etapa 2», con lo de este proyecto.

## Leer (solo esto)

- `task_dashboard.md`, por secciones (no entero): «Cómo se usa», «Objetivo», «Etapas» (la tabla y la lista de lectura), «Forma de trabajo», «Interfaz» (se corta en su primera subsección), «Página 1: Overview», «Organización del código» y «Etapa 2». Comandos `awk`, en «Etapas».
- `tarea.md`: «Forma de trabajo», «Definición de terminado» y «Punto de control».
- La entrada de la bitácora «Dashboard, etapa 1», solo «Decisiones no previstas»: `awk '/^### Dashboard, etapa 1/{p=1;print;next} p&&/^### /{exit} p' bitacora.md`.
- Skills: `dataviz` (fija el estilo en `graficos.py`); de `developing-with-streamlit`, solo la referencia de `AppTest` y la de la caché.

## Archivos

- **Crea:**
  - `src/facturas/dashboard/app.py`, `paginas/__init__.py`, `paginas/overview.py`, `paginas/analysis.py` (vacía, con sus cuatro pestañas) y `graficos.py`;
  - `scripts/dashboard.ps1`;
  - `tests/test_dashboard_app.py`.
- **Modifica:**
  - `requirements.txt`: `streamlit` y `plotly`, con versión fijada;
  - `src/facturas/dashboard/datos.py`: las funciones de período que pide el criterio de aceptación (meses de cada período y exclusión de los incompletos), con sus tests en `tests/test_dashboard_datos.py`;
  - `CLAUDE.md`, «Comandos de este proyecto»: `scripts\dashboard.ps1`;
  - `docs/diseno.md` §14: el árbol de `dashboard/`.
- **No toca:** la base, sus vistas, las semillas ni `semantica.toml` (salvo un nombre en inglés, si la persona usuaria lo pide).

## Interfaces (etapa 1)

Importes en céntimos (`int`); cantidades en milésimas de la unidad canónica. Todas las filas son dataclasses congeladas, así que `pd.DataFrame(filas)` las convierte.

- `facturas.bd.conexion.conectar()`: sin argumentos abre `datos/facturas.db` en solo lectura (`mode=ro` y `query_only`), con la ruta resuelta desde la raíz del proyecto.
- `semantica.py`:
  - `cargar(ruta=RUTA_SEMANTICA) -> Semantica`: `dict[str, Categoria]`, en el orden del TOML (`agua`, `luz`, `gas`, `fibra`, `movil`);
  - `Categoria(codigo, nombre, magnitud, variables, grupos)`, con `grupo_de(concepto)`, `nombre_grupo(codigo)` y `nombre_concepto(concepto)`. `nombre` es el nombre en inglés (Water, Electricity, Gas, Fiber, Mobile);
  - `Grupo(codigo, nombre, conceptos: dict[codigo, nombre])`;
  - `validar(semantica, conexion) -> list[ConceptoSinClasificar(categoria, concepto, concepto_nombre)]`: lanza `ErrorSemantica` si el TOML no cuadra con la base. Lo que devuelve se muestra como aviso, en inglés;
  - `meses_completos(cobertura, categorias) -> dict[anio_mes, bool]`: un mes está completo para varios servicios si lo está para todos;
  - `SIN_CLASIFICAR = "sin_clasificar"` y `NOMBRE_SIN_CLASIFICAR = "Unclassified"`.
- `datos.py`:
  - `gasto_mensual(conexion) -> list[GastoMes(anio_mes, categoria, importe_centimos)]`: solo los meses con gasto. Un mes sin facturas no aparece: hay que completarlo con 0;
  - `cobertura_mensual(conexion, categorias, mes_desde, mes_hasta) -> list[CoberturaMes(anio_mes, categoria, dias_mes, dias_cubiertos)]`, con la propiedad `completo`. Hay una fila por categoría y mes del rango, aunque no haya facturas (0 días). Los meses posteriores a la última factura (hoy, desde julio de 2026 en el agua) salen incompletos;
  - las funciones por factura (`facturas`, `importes_por_factura`, `consumo_por_factura` y `cascada`) son de la etapa 3.

## Pendientes heredados

- Confirmado al aprobar la etapa 1: `otros_servicios` (ServiElectric, 2024, Q,QZ €) va en «Other fixed» del gas.
- **Hilos y caché:** `conectar()` crea la conexión con `check_same_thread` activo y Streamlit ejecuta en varios hilos. Por eso, cada función cacheada con `st.cache_data` abre y cierra su conexión (`contextlib.closing(conectar())`); no se cachea la conexión. La `Semantica` se pasa a una función cacheada como parámetro con guion bajo (`_semantica`), que no se hashea, o se carga dentro de ella.
- **Evidencia de la etapa 1** (la referencia del criterio de aceptación): con todo el histórico y todos los servicios, el total es Q.JKQ,KZ € (QZQKZQ céntimos), igual a la suma de `v_factura_vigente`.
- Meses incompletos hoy, con la regla de la etapa 1 (meses desde la primera factura de cada servicio):
  - agua: 2024-10 y desde 2026-06;
  - luz: 2024-10 y desde 2026-06;
  - gas: desde 2026-06;
  - fibra y móvil: 2024-12 y desde 2026-08.

## Tests

- De la etapa: `.venv\Scripts\python -m pytest -q --tb=short tests\test_dashboard_app.py tests\test_dashboard_datos.py tests\test_dashboard_semantica.py tests\test_codigo.py`
- Al cerrar, todos: `.venv\Scripts\python -m pytest -q --tb=line` (unos 2,5 min).
