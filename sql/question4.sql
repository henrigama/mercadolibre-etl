-- ¿Porcentaje de artículos con garantía?
-- (Percentage of items with warranty?)
SELECT
    COUNT(*) FILTER (WHERE has_warranty) AS con_garantia,
    COUNT(*) FILTER (WHERE NOT has_warranty) AS sin_garantia,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE has_warranty) / COUNT(*),
        1
    ) AS porcentaje_con_garantia
FROM etl.products
WHERE job_run = (SELECT MAX(job_run) FROM etl.products);