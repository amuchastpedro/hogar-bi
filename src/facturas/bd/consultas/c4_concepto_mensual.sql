-- @C4 Análisis: desglose mensual por concepto.
-- Parámetros: :categorias, :mes_desde y :mes_hasta. Ver docs/diseno.md, sección 15.
WITH seleccion AS (SELECT value AS categoria_codigo FROM json_each(:categorias))
SELECT g.anio_mes, g.categoria_codigo, g.concepto_codigo, g.concepto_nombre,
       sum(g.importe_centimos) AS importe_centimos
FROM v_hecho_gasto_mensual AS g
JOIN seleccion AS s ON s.categoria_codigo = g.categoria_codigo
WHERE g.anio_mes BETWEEN :mes_desde AND :mes_hasta
GROUP BY g.anio_mes, g.categoria_codigo, g.concepto_codigo, g.concepto_nombre
ORDER BY g.anio_mes, g.categoria_codigo, g.concepto_codigo;
