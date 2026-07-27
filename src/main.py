from api import MercadoLibreAPI
from auth import MercadoLibreAuth
from config import load_config
from database import get_engine
from extract import (
    extract_products,
    extract_currency_conversion,
    with_job_run,
)
from load import load_products
from logger import setup_logger
from transform import transform_products


def main():
    config = load_config()
    logger = setup_logger(config)

    logger.info("Starting Mercado Libre ETL")

    client_id = config["oauth"]["client_id"]
    client_secret = config["oauth"]["client_secret"]

    auth = None
    if client_id and client_secret:
        auth = MercadoLibreAuth(
            base_url=config["api"]["base_url"],
            client_id=client_id,
            client_secret=client_secret,
            logger=logger,
        )
        logger.info("OAuth credentials found - client_credentials enabled.")
    else:
        logger.warning(
            "ML_CLIENT_ID/ML_CLIENT_SECRET not set in .env - "
            "requests will proceed without a token (token-required endpoints will use fallback)."
        )

    api = MercadoLibreAPI(
        base_url=config["api"]["base_url"],
        timeout=config["api"]["timeout"],
        logger=logger,
        auth=auth,
    )

    raw_products, products_source = extract_products(api, config, logger)
    currency_data, currency_source = extract_currency_conversion(api, config, logger)

    products = with_job_run(raw_products, products_source)
    rows = transform_products(products, currency_ratio=currency_data["ratio"])

    logger.info(
        f"Extraction finished | products={products_source} | "
        f"currency={currency_source} | records={len(rows)}"
    )

    engine = get_engine(config)
    load_products(engine, rows, logger)

    return rows


if __name__ == "__main__":
    main()