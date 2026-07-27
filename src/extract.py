from datetime import datetime, timezone

from api import (
    MercadoLibreAPI,
    MercadoLibreForbiddenError,
    MercadoLibreUnauthorizedError,
)
from sample_data import SAMPLE_SEARCH_RESULTS, SAMPLE_CURRENCY_CONVERSION


def extract_products(api: MercadoLibreAPI, config: dict, logger) -> tuple[list, str]:
    """
    Extracts products from the search endpoint, paginating 50 at a time.
    Only new products are considered, via the `condition` parameter
    already sent in the query.
    If the API returns 403 (public access block, see decision.md), uses
    the sample dataset as a fallback so the pipeline doesn't stop.

    Returns: (product_list, source) where source is "live" or "sample".
    """
    site = config["api"]["site"]
    query = config["search"]["query"]
    condition = config["search"]["condition"]
    page_size = config["search"]["page_size"]
    max_records = config["search"]["max_records"]

    endpoint_template = config["api"]["endpoints"]["search"]
    endpoint = endpoint_template.format(site=site)

    results = []
    offset = 0

    try:
        while offset < max_records:
            page = api.get(
                endpoint=endpoint,
                params={
                    "q": query,
                    "condition": condition,
                    "limit": page_size,
                    "offset": offset,
                },
            )
            batch = page.get("results", [])
            if not batch:
                break

            results.extend(batch)
            offset += page_size

        logger.info(f"Live extraction completed: {len(results)} records.")
        return results, "live"

    except MercadoLibreForbiddenError:
        logger.warning(
            "Fallback activated: using sample dataset "
            "(search endpoint blocked by Mercado Libre's current access policy)."
        )
        return SAMPLE_SEARCH_RESULTS, "sample"


def extract_item(api: MercadoLibreAPI, config: dict, item_id: str, logger) -> dict | None:
    """
    Extracts details for a specific item via the /items/{item_id}
    endpoint. Returns None (instead of raising) if the endpoint is
    blocked, so it doesn't stop processing of other items in the batch.
    """
    endpoint_template = config["api"]["endpoints"]["item"]
    endpoint = endpoint_template.format(item_id=item_id)

    try:
        return api.get(endpoint=endpoint)
    except MercadoLibreForbiddenError:
        logger.warning(f"Fallback: item {item_id} could not be detailed (403).")
        return None


def extract_currency_conversion(api: MercadoLibreAPI, config: dict, logger) -> tuple[dict, str]:
    """
    Extracts the ARS -> USD conversion rate via /currency_conversions,
    required to compute the average price in dollars. Follows the 
    same fallback pattern as the other endpoints: on 403 or 401, 
    uses the sample rate documented in sample_data.py.

    Returns: (dict with from/to/ratio, source) where source is "live" or "sample".
    """
    endpoint = config["api"]["endpoints"]["currency_conversions"]
    from_currency = config["currency"]["from"]
    to_currency = config["currency"]["to"]

    try:
        data = api.get(
            endpoint=endpoint,
            params={"from": from_currency, "to": to_currency},
        )
        logger.info(
            f"Live currency conversion: 1 {from_currency} = "
            f"{data.get('ratio')} {to_currency}"
        )
        return data, "live"

    except (MercadoLibreForbiddenError, MercadoLibreUnauthorizedError):
        logger.warning(
            "Fallback activated: using sample exchange rate "
            "(/currency_conversions required a valid token that was not available)."
        )
        return SAMPLE_CURRENCY_CONVERSION, "sample"


def with_job_run(records: list, source: str) -> list:
    """
    Adds the JOB_RUN (required by the challenge) and data_source
    fields to each record, with the SAME timestamp for the whole run.
    """
    job_run = datetime.now(timezone.utc)

    return [
        {**record, "job_run": job_run, "data_source": source}
        for record in records
    ]