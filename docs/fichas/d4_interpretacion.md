# Ficha de la etapa 4 del dashboard: interpretación fuera de la base

Complementa [`task_dashboard.md`](../../task_dashboard.md), «Etapa 4». Tiene lo que dejaron las etapas 1 y 3 (la etapa 2 no dejó nada para esta).

## Pendientes heredados

- (Etapa 1) `src/facturas/dashboard/` no lee `tipo_cargo` ni las vistas de cobertura: lee `v_linea`, `v_factura_vigente`, `v_dim_contrato`, `v_dim_concepto`, `v_dim_fecha`, `v_hecho_gasto_mensual`, `v_hecho_consumo_diario` y `v_hecho_consumo_mensual`, sin las columnas de `tipo_cargo`. Quitar esas columnas de las vistas no cambia sus consultas.
- (Etapa 1) La evidencia que se repite al cerrar: el total de todos los meses es QZQKZQ céntimos, igual a la suma de `importe_total_centimos` de `v_factura_vigente`; I1 se cumple en el grano por factura y las 40 cascadas entre facturas consecutivas de agua, gas y luz cuadran.
- (Etapa 1) `operacion/estado.py` informa la cobertura con las vistas de la base. La regla de la capa semántica está en `dashboard/datos.py` (`cobertura_mensual`) y `operacion` puede importar todo. Decidir si `estado` la reutiliza o deja de informar la cobertura.
- (Etapa 3) `analysis.py`, `graficos.py` y las funciones nuevas de `datos.py` tampoco leen `tipo_cargo` ni las vistas de cobertura: usan `v_linea`, `v_factura_vigente`, `v_dim_contrato`, `v_hecho_consumo_diario` y las demás vistas de la etapa 1. El test estático de R32 (`test_solo_lee_vistas`) cubre `datos.py` y `semantica.py`.
- (Etapa 3) Números de referencia sobre la base real, para comparar antes y después (no cambian al quitar `tipo_cargo`):
  - lo que suma cada pestaña de Analysis, que coincide factura a factura con `v_factura_vigente` (con la rectificativa sumada a su original): agua 10 facturas y JJQ,ZJ €, luz 22 y JXJ,QJ €, gas 11 y ZXQ,ZZ € y DIGI 20 y QXQ,QK € (en total, los Q.JKQ,KZ € de siempre);
  - las cascadas por defecto: agua QX,XQ → ZX,KK € (volumen −K,QQ y precio +X,JZ), luz KK,KX → XJ,ZZ € (−Z,JJ y +Z,ZX) y gas XZQ,JQ → QJ,KX € (−JX,QJ y −Q,KZ).
- (Etapa 3) `tests/test_dashboard_app.py` tiene 29 tests de la app y `tests/test_dashboard_datos.py` tiene 39. Son los tests de humo que tienen que seguir pasando tras quitar `tipo_cargo`.
