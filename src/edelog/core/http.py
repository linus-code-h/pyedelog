from typing import Any

import httpx

from ..auth import EdelogAuth
from ..config import EdelogConfig
from .transport import Transport


class EdelogHttpClient(Transport):
    def __init__(
        self, config: EdelogConfig, auth: EdelogAuth, client: httpx.Client | None = None
    ) -> None:
        super().__init__(config, client)
        self.auth = auth

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._closed:
            raise RuntimeError("Client is closed")
        headers = httpx.Headers(kwargs.pop("headers", {}) or {})
        for attempt in range(2):
            headers["Authorization"] = f"Bearer {self.auth.get_token()}"
            response = self.send(method, path, headers=headers, **kwargs)
            if response.status_code != 401 or attempt == 1:
                return self.check(response)
            response.close()
            self.auth.clear_token()
        raise RuntimeError("Unexpected authentication state")

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", path, **kwargs)
