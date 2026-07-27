-- ¿Hay algún vendedor con múltiples publicaciones? En caso de que sí, ¿con cuántas?
-- (Is there a seller with multiple listings? If so, how many?)
SELECT
    seller_id,
    seller_nickname,
    COUNT(*) AS total_publicaciones
FROM etl.products
WHERE job_run = (SELECT MAX(job_run) FROM etl.products)
GROUP BY seller_id, seller_nickname
HAVING COUNT(*) > 1
ORDER BY total_publicaciones DESC;