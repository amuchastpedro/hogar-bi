-- @C6 Análisis gas y luz: consumo mensual según lecturas reales o estimadas.
-- Parámetros: :categoria, :mes_desde y :mes_hasta. Ver docs/diseno.md, sección 15.
SELECT anio_mes, tipo_lectura, unidad, sum(cantidad_milesimas) AS cantidad_milesimas
FROM v_hecho_consumo_mensual
WHERE categoria_codigo = :categoria AND anio_mes BETWEEN :mes_desde AND :mes_hasta
GROUP BY anio_mes, tipo_lectura, unidad
ORDER BY anio_mes, tipo_lectura;
