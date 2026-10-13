-- @C1 Overview, scorecards: gasto por categoría y total del período.
-- Parámetros: :categorias (arreglo JSON de códigos), :mes_desde y :mes_hasta (AAAA-MM, inclusive). Ver docs/diseno.md, sección 15.
WITH seleccion AS (SELECT value AS categoria_codigo FROM json_each(:categorias)),
por_categoria AS (
    SELECT g.categoria_codigo, sum(g.importe_centimos) AS importe_centimos
    FROM v_hecho_gasto_mensual AS g
    JOIN seleccion AS s ON s.categoria_codigo = g.categoria_codigo
    WHERE g.anio_mes BETWEEN :mes_desde AND :mes_hasta
    GROUP BY g.categoria_codigo
)
SELECT categoria_codigo, importe_centimos FROM por_categoria
UNION ALL
SELECT 'total', coalesce(sum(importe_centimos), 0) FROM por_categoria;
