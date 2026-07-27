"""
Authentication via OAuth Client Credentials.

Used only for endpoints that require *some* valid token but do not
require authorization from a specific user (e.g. /currency_conversions).
It does not unlock /search or /items, which are blocked by policy
regardless of token validity - see decision.md.
"""
import time

import requests


class TokenError(Exception):
    """Failed to obtain an access_token via client_credentials."""


class MercadoLibreAuth:

    def __init__(self, base_url: str, client_id: str, client_secret: str, logger=None):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.logger = logger

        self._token = None
        self._expires_at = 0

    def get_token(self) -> str:
        """
        Returns a valid access_token, reusing the cached token if it
        has not yet expired (with a 60s safety margin).
        """
        if self._token and time.time() < self._expires_at - 60:
            return self._token

        response = requests.post(
            f"{self.base_url}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"accept": "application/json"},
            timeout=15,
        )

        if response.status_code != 200:
            if self.logger:
                self.logger.error(
                    f"Failed to obtain access_token: {response.status_code} - {response.text}"
                )
            raise TokenError(response.text)

        data = response.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600)

        if self.logger:
            self.logger.info("Access token obtained via client_credentials.")

        return self._token