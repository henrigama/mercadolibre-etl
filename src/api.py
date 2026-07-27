import requests


class MercadoLibreAPIError(Exception):
    """Generic error communicating with the Mercado Libre API."""


class MercadoLibreForbiddenError(MercadoLibreAPIError):
    """API returned 403 - endpoint blocked by current ML access policy."""


class MercadoLibreUnauthorizedError(MercadoLibreAPIError):
    """API returned 401 - missing or invalid access token."""


class MercadoLibreAPI:

    def __init__(self, base_url: str, timeout: int = 30, logger=None, auth=None):
        """
        auth: optional MercadoLibreAuth instance (auth.py). If provided,
        a token is obtained and sent automatically with every request.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.logger = logger
        self.auth = auth

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "mercadolibre-etl/1.0",
            }
        )

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        headers = {}
        if self.auth:
            headers["Authorization"] = f"Bearer {self.auth.get_token()}"

        response = self.session.get(
            url, params=params, headers=headers, timeout=self.timeout
        )

        if self.logger:
            self.logger.debug(f"GET {response.url} -> {response.status_code}")

        if response.status_code == 403:
            if self.logger:
                self.logger.warning(
                    f"403 Forbidden on {endpoint}. "
                    "Endpoint blocked by Mercado Libre's access policy "
                    "(restriction in effect since April 2025 for public /search and /items)."
                )
            raise MercadoLibreForbiddenError(endpoint)

        if response.status_code == 401:
            if self.logger:
                self.logger.warning(
                    f"401 Unauthorized on {endpoint}. "
                    "Missing or invalid token for this endpoint."
                )
            raise MercadoLibreUnauthorizedError(endpoint)

        response.raise_for_status()
        return response.json()