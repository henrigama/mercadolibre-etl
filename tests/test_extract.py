"""
Unit tests for the extraction layer.
Mock the HTTP session (unittest.mock), so they run without internet
access or real credentials.
"""
from unittest.mock import MagicMock, patch

import pytest

from api import MercadoLibreAPI
from extract import extract_currency_conversion, extract_products, with_job_run
from logger import setup_logger
from sample_data import SAMPLE_SEARCH_RESULTS

CONFIG = {
    "api": {
        "site": "MLA",
        "endpoints": {
            "search": "sites/{site}/search",
            "item": "items/{item_id}",
            "currency_conversions": "currency_conversions/search",
        },
    },
    "search": {
        "query": "Samsung Galaxy S24",
        "condition": "new",
        "page_size": 50,
        "max_records": 500,
    },
    "currency": {"from": "ARS", "to": "USD"},
}


def _fake_response(status_code, json_data):
    resp = MagicMock()
    resp.status_code = status_code
    resp.url = "https://api.mercadolibre.com/fake"
    resp.json.return_value = json_data
    resp.raise_for_status.side_effect = (
        None if status_code < 400 else Exception(f"HTTP {status_code}")
    )
    return resp


@pytest.fixture
def logger():
    return setup_logger()


def test_extract_products_fallback_on_403(logger):
    """A real 403 (ML policy block) should trigger the sample fallback
    without breaking the pipeline."""
    api = MercadoLibreAPI(base_url="https://api.mercadolibre.com", logger=logger)

    with patch.object(api.session, "get", return_value=_fake_response(403, {})):
        products, source = extract_products(api, CONFIG, logger)

    assert source == "sample"
    assert len(products) == len(SAMPLE_SEARCH_RESULTS)


def test_extract_products_live_when_available(logger):
    """When the API responds 200, real data should be used, with
    pagination stopping on the first empty page."""
    api = MercadoLibreAPI(base_url="https://api.mercadolibre.com", logger=logger)

    page1 = {"results": [{"id": "MLA999", "title": "Real test item"}]}
    page2 = {"results": []}

    with patch.object(
        api.session,
        "get",
        side_effect=[_fake_response(200, page1), _fake_response(200, page2)],
    ):
        products, source = extract_products(api, CONFIG, logger)

    assert source == "live"
    assert len(products) == 1
    assert products[0]["id"] == "MLA999"


def test_extract_currency_conversion_fallback_on_401(logger):
    """A 401 (missing/invalid token) on the currency endpoint should
    also trigger the fallback, without breaking the pipeline."""
    api = MercadoLibreAPI(base_url="https://api.mercadolibre.com", logger=logger)

    with patch.object(api.session, "get", return_value=_fake_response(401, {})):
        data, source = extract_currency_conversion(api, CONFIG, logger)

    assert source == "sample"
    assert "ratio" in data


def test_extract_currency_conversion_live_when_available(logger):
    api = MercadoLibreAPI(base_url="https://api.mercadolibre.com", logger=logger)
    live_data = {"from": "ARS", "to": "USD", "ratio": 0.000668}

    with patch.object(api.session, "get", return_value=_fake_response(200, live_data)):
        data, source = extract_currency_conversion(api, CONFIG, logger)

    assert source == "live"
    assert data["ratio"] == 0.000668


def test_with_job_run_adds_consistent_timestamp():
    """All records from the same run must receive exactly the same
    job_run timestamp."""
    records = [{"id": "A"}, {"id": "B"}, {"id": "C"}]

    enriched = with_job_run(records, "sample")

    job_runs = {r["job_run"] for r in enriched}
    assert len(job_runs) == 1
    assert all(r["data_source"] == "sample" for r in enriched)