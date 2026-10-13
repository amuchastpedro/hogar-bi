# Ficha de la etapa 1 del dashboard: capa semántica y datos

Complementa [`task_dashboard.md`](../../task_dashboard.md), «Etapa 1», con lo de este proyecto.

## Leer (solo esto)

- `task_dashboard.md`, por secciones (no entero): «Cómo se usa», «Objetivo», «Interfaz» con «Página 1» y «Página 2», «Capa semántica», «Organización del código», «Etapas» (la tabla y la lista de lectura), «Etapa 1» y «Forma de trabajo». Comandos `awk`, en «Etapas».
- `tarea.md`: «Forma de trabajo», «Definición de terminado» y «Punto de control».
- `docs/diseno.md`:
  - §7 «Vistas»: las columnas de cada vista;
  - §8.1 «Regla» (prorrateo);
  - §9 «Cobertura», para entender lo que se reemplaza;
  - §14 «Organización de `src/`», que esta etapa actualiza.
- `docs/diccionario.md`: los conceptos de cada categoría.
- `requisitos.md`: R21, R32, R34 y R39 (`grep -n 'R21\.\|R32\.\|R34\.\|R39\.' requisitos.md`).

## Archivos

- **Crea:**
  - `src/facturas/dashboard/__init__.py`, `semantica.toml`, `semantica.py` y `datos.py`;
  - `tests/test_dashboard_semantica.py` y `tests/test_dashboard_datos.py`.
- **Modifica:**
  - `tests/test_codigo.py`: agregar `"dashboard": {"bd"}` a `PERMITIDOS`;
  - `docs/diseno.md` §14: el árbol, la regla de dependencias y «lo específico del caso vive solo en…».
- **No toca:** la base, sus vistas ni las semillas. Si hace falta una vista nueva, se plantea en el punto de control.

## Interfaces

- **Conexión:** `facturas.bd.conexion.conectar(ruta=RUTA_BASE, modo="lectura")`. `RUTA_BASE` es `datos/facturas.db`, resuelta desde la raíz del proyecto. En modo lectura abre con `mode=ro` y `query_only`, y verifica la versión del esquema.
- **Vistas útiles** (todas filtran las facturas vigentes, salvo las de prorrateo):
  - `v_linea`: una línea por fila, con `factura_id`, `contrato_id`, `categoria_codigo`, `concepto_codigo`, `importe_centimos`, `fecha_inicio`, `fecha_fin`, `dias` y `es_derivada`. Es la base del grano por factura.
  - `v_factura_vigente`: `importe_total_centimos`, `tipo` y `numero_factura_corregida`, para sumar una rectificativa por diferencias a la factura que corrige. Los números de factura no se muestran.
  - `v_hecho_gasto_mensual`: gasto prorrateado, por mes × contrato × concepto. Es la base del Overview.
  - `v_hecho_consumo_diario` / `v_hecho_consumo_mensual`: la cantidad en milésimas de la unidad canónica, con `factura_id`, `magnitud_codigo`, `unidad`, `franja_codigo` y `tipo_lectura`.
  - `v_dim_contrato`: alias y proveedor.
- **Unidades de la base:**
  - Los importes van en céntimos (enteros) y las cantidades, en milésimas.
  - Magnitudes: agua `volumen` (m³), sin franja y con lecturas reales; gas `energia` (kWh), sin franja y con lecturas reales y estimadas; luz `energia` (kWh), con las franjas `punta`, `llano` y `valle`.
- **Consultas de referencia** (`src/facturas/bd/consultas/`): C2–C5 usan `tipo_cargo` o las vistas de cobertura, así que **no se reutilizan**. C1, C6 y C7 se pueden tomar como punto de partida.
- **Fixtures de `tests/conftest.py`:**
  - `base`: una base vacía, con conexión de escritura;
  - `base_ejemplos`: la anterior con las cuatro facturas de ejemplo (agua, gas, luz y Digi) de `tests/datos_prueba.py`, con sus totales reales;
  - `datos_prueba.abono_de(factura, numero)` arma un abono.

  Para el grano por factura y la cascada hacen falta dos facturas del mismo servicio: se arman en el test, copiando un ejemplo con otras fechas.
- **Python 3.12:** `tomllib` está en la biblioteca estándar, así que esta etapa no necesita dependencias nuevas.

## Pendientes heredados

- (Carga del histórico, 2026-10-06) Confirmar con la persona usuaria `otros_servicios` (ServiElectric, 2024), que en la capa semántica va en «Otros fijos» del gas.
- Los contratos de luz y gas de 2024 («luz 2», «gas 2», Naturgy Iberia) son aparte de los de 2025 en adelante. En el Analysis forman una sola serie por servicio, con el cambio marcado.
- No hay fechas de baja, por decisión. La cobertura de la capa semántica no las usa.
- I8 admite 10 céntimos de diferencia en el reparto del IVA de Digi. I1, en cambio, es exacta: los grupos de cada factura suman su total sin tolerancia.
- `concepto.tipo_cargo` sigue en la base hasta la etapa 4. El dashboard no lo lee.

## Tests

- De la etapa: `.venv\Scripts\python -m pytest -q --tb=short tests\test_dashboard_semantica.py tests\test_dashboard_datos.py tests\test_codigo.py`
- Al cerrar, todos: `.venv\Scripts\python -m pytest -q --tb=line` (unos 2,5 min).
