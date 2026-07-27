-- ¿Cuál es el precio promedio en dólares?
-- (What is the average price in US dollars?)
SELECT
    ROUND(AVG(price_usd), 2) AS precio_promedio_usd,
    COUNT(*) AS total_publicaciones,
    MIN(price_usd) AS precio_minimo_usd,
    MAX(price_usd) AS precio_maximo_usd
FROM etl.products
WHERE job_run = (SELECT MAX(job_run) FROM etl.products);