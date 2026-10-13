-- @C5 Análisis agua, gas y luz: volumen o energía mensual y precio unitario efectivo.
-- Parámetros: :categoria, :conceptos (arreglo JSON de los códigos de concepto que escalan con el
-- volumen), :mes_desde y :mes_hasta. Ver docs/diseno.md, sección 15.
WITH consumo AS (
    SELECT anio_mes, magnitud_codigo, unidad, sum(cantidad_milesimas) AS cantidad_milesimas
    FROM v_hecho_consumo_mensual
    WHERE categoria_codigo = :categoria AND anio_mes BETWEEN :mes_desde AND :mes_hasta
    GROUP BY anio_mes, magnitud_codigo, unidad
),
gasto AS (
    SELECT anio_mes, sum(importe_centimos) AS importe_centimos
    FROM v_hecho_gasto_mensual
    WHERE categoria_codigo = :categoria AND concepto_codigo IN (SELECT value FROM json_each(:conceptos))
      AND anio_mes BETWEEN :mes_desde AND :mes_hasta
    GROUP BY anio_mes
)
SELECT c.anio_mes, c.magnitud_codigo, c.unidad, c.cantidad_milesimas,
       coalesce(g.importe_centimos, 0) AS importe_consumo_centimos,
       round((coalesce(g.importe_centimos, 0) / 100.0) / (c.cantidad_milesimas / 1000.0), 6) AS precio_efectivo
FROM consumo AS c
LEFT JOIN gasto AS g ON g.anio_mes = c.anio_mes
ORDER BY c.anio_mes;
