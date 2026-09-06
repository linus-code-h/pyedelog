import math
import time
from threading import RLock

import httpx

from .config import EdelogConfig
from .core.response import json_object
from .core.transport import Transport
from .exceptions import AuthenticationError


class EdelogAuth(Transport):
    config: EdelogConfig

    def __init__(self, config: EdelogConfig, client: httpx.Client | None = None) -> None:
        super().__init__(config, client)
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = RLock()

    def get_token(self) -> str:
        with self._lock:
            if self._closed:
                raise RuntimeError("Client is closed")
            if self._token is not None and time.monotonic() < self._expires_at:
                return self._token
            response = self.send(
                "POST",
                "/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "organization_id": self.config.organization_id,
                },
            )
            if not response.is_success:
                # OAuth responses may echo credentials; never include their body.
                raise AuthenticationError(f"Authentication failed: {response.status_code}")
            data = json_object(response)
            assert data is not None
            token = data.get("access_token")
            if not isinstance(token, str) or not token.strip():
                raise AuthenticationError(
                    "Authentication response does not contain a valid access_token"
                )
            expires_in = data.get("expires_in")
            if expires_in is None:
                expires_at = math.inf
            elif (
                isinstance(expires_in, bool)
                or not isinstance(expires_in, (int, float))
                or not math.isfinite(expires_in)
                or expires_in <= 0
            ):
                raise AuthenticationError("Authentication response contains invalid expires_in")
            else:
                expires_at = time.monotonic() + expires_in - min(30.0, expires_in * 0.1)
            self._token = token
            self._expires_at = expires_at
            return token

    def clear_token(self) -> None:
        with self._lock:
            self._token = None
            self._expires_at = 0.0

    def close(self) -> None:
        with self._lock:
            self.clear_token()
            super().close()
