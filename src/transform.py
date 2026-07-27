"""
Transformation layer of the ETL pipeline.

Single responsibility: flatten the nested JSON returned by the API
(or by the sample fallback) into rows ready for insertion into
Postgres. No business aggregation happens here - analytical answers
are computed via SQL (see sql/question*.sql), not in Python, keeping
this layer simple and the resulting logic auditable/re-runnable
directly against the database.
"""
from typing import Any


def _has_warranty(warranty_text: str) -> bool:
    """
    Treats any text that does not explicitly state the absence of a
    warranty as "has warranty".
    """
    if not warranty_text:
        return False
    return "sin garantía" not in warranty_text.strip().lower()


def transform_products(
    raw_products: list[dict[str, Any]],
    currency_ratio: float,
) -> list[dict[str, Any]]:
    """
    Transforms the list of raw products (from extract.py, already
    carrying job_run and data_source) into normalized rows ready for
    the `products` table.
    """
    rows = []

    for product in raw_products:
        seller = product.get("seller", {})
        shipping = product.get("shipping", {})
        price_ars = product.get("price", 0.0)
        warranty_text = product.get("warranty", "")

        rows.append(
            {
                "item_id": product["id"],
                "title": product.get("title"),
                "seller_id": seller.get("id"),
                "seller_nickname": seller.get("nickname"),
                "condition": product.get("condition"),
                "price_ars": price_ars,
                "price_usd": round(price_ars * currency_ratio, 2),
                "currency_id": product.get("currency_id"),
                "sold_quantity": product.get("sold_quantity", 0),
                "has_warranty": _has_warranty(warranty_text),
                "warranty_description": warranty_text,
                "free_shipping": shipping.get("free_shipping", False),
                "logistic_type": shipping.get("logistic_type"),
                "job_run": product.get("job_run"),
                "data_source": product.get("data_source"),
            }
        )

    return rows