-- ¿Métodos de Shipping que ofrecen?
-- (Shipping methods offered?)
SELECT
    logistic_type,
    COUNT(*) AS total_publicaciones,
    COUNT(*) FILTER (WHERE free_shipping) AS con_envio_gratis,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS porcentaje
FROM etl.products
WHERE job_run = (SELECT MAX(job_run) FROM etl.products)
GROUP BY logistic_type
ORDER BY total_publicaciones DESC;