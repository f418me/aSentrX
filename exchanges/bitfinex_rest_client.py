import hashlib
import hmac
import json
import time
from typing import Any

import requests


class BitfinexRestClient:
    """Minimal authenticated Bitfinex REST v2 client for required endpoints only."""

    def __init__(self, api_key: str, api_secret: str, rest_host: str = "https://api.bitfinex.com/v2"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.rest_host = rest_host.rstrip("/")

    def _auth_headers(self, endpoint: str, payload: str | None = None) -> dict[str, str]:
        nonce = str(int(time.time() * 1_000_000))
        message = f"/api/v2/{endpoint}{nonce}{payload or ''}"
        signature = hmac.new(
            self.api_secret.encode("utf8"),
            message.encode("utf8"),
            hashlib.sha384,
        ).hexdigest()
        return {
            "bfx-nonce": nonce,
            "bfx-signature": signature,
            "bfx-apikey": self.api_key,
        }

    def post_auth(self, endpoint: str, body: dict[str, Any] | None = None) -> Any:
        payload = json.dumps(body or {})
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            **self._auth_headers(endpoint, payload),
        }
        response = requests.post(
            f"{self.rest_host}/{endpoint}",
            data=payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_wallets(self) -> Any:
        return self.post_auth("auth/r/wallets")

    def get_positions(self) -> Any:
        return self.post_auth("auth/r/positions")

    def submit_order(self, **params: Any) -> Any:
        return self.post_auth("auth/w/order/submit", body=params)
