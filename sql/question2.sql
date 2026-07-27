-- ¿Promedio de ventas por seller?
-- (Average sales per seller?)
--
-- Note: sold_quantity is a referential value from the ML public API
-- (it does not represent real transaction volume), used as the best
-- available proxy for this question. See decision.md, section 5.
SELECT
    seller_id,
    seller_nickname,
    COUNT(*) AS total_publicaciones,
    ROUND(AVG(sold_quantity), 2) AS promedio_sold_quantity
FROM etl.products
WHERE job_run = (SELECT MAX(job_run) FROM etl.products)
GROUP BY seller_id, seller_nickname
ORDER BY promedio_sold_quantity DESC;