-- @C2 Overview, evolución mensual del gasto por categoría.
-- Parámetros: :categorias, :mes_desde y :mes_hasta. Ver docs/diseno.md, sección 15.
-- La completitud de los meses no está en la base: la calcula el dashboard (dashboard/datos.py).
WITH seleccion AS (SELECT value AS categoria_codigo FROM json_each(:categorias))
SELECT g.anio_mes, g.categoria_codigo, sum(g.importe_centimos) AS importe_centimos
FROM v_hecho_gasto_mensual AS g
JOIN seleccion AS s ON s.categoria_codigo = g.categoria_codigo
WHERE g.anio_mes BETWEEN :mes_desde AND :mes_hasta
GROUP BY g.anio_mes, g.categoria_codigo
ORDER BY g.anio_mes, g.categoria_codigo;
