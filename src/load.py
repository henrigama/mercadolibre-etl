"""
Load layer of the ETL pipeline: inserts transformed rows into the
`products` table in PostgreSQL.
"""
from sqlalchemy import text
from sqlalchemy.engine import Engine


def load_products(engine: Engine, rows: list[dict], logger) -> int:
    """
    Inserts rows into the products table. Returns the number of rows
    inserted.
    """
    if not rows:
        logger.warning("No rows to load - load_products received an empty list.")
        return 0

    insert_sql = text(
        """
        INSERT INTO products (
            item_id, title, seller_id, seller_nickname, condition,
            price_ars, price_usd, currency_id, sold_quantity,
            has_warranty, warranty_description, free_shipping,
            logistic_type, data_source, job_run
        ) VALUES (
            :item_id, :title, :seller_id, :seller_nickname, :condition,
            :price_ars, :price_usd, :currency_id, :sold_quantity,
            :has_warranty, :warranty_description, :free_shipping,
            :logistic_type, :data_source, :job_run
        )
        ON CONFLICT (item_id, job_run) DO NOTHING
        """
    )

    with engine.begin() as conn:
        conn.execute(insert_sql, rows)

    logger.info(f"Load complete: {len(rows)} row(s) inserted into products.")
    return len(rows)