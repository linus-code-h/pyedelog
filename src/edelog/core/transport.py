import time
from types import TracebackType
from typing import Any, Protocol, TypeVar

import httpx

from ..exceptions import ApiError, TransportError


class TransportConfig(Protocol):
    @property
    def base_url(self) -> str: ...

    @property
    def timeout(self) -> float: ...

    @property
    def max_retries(self) -> int: ...

    @property
    def retry_backoff(self) -> float: ...


TransportT = TypeVar("TransportT", bound="Transport")


class Transport:
    """Owns only clients it creates; injected clients remain caller-owned."""

    def __init__(self, config: TransportConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self._owns_client = client is None
        self.client = (
            client
            if client is not None
            else httpx.Client(
                base_url=config.base_url.rstrip("/"),
                timeout=config.timeout,
            )
        )
        self._closed = False

    def close(self) -> None:
        if not self._closed:
            if self._owns_client:
                self.client.close()
            self._closed = True

    def __enter__(self: TransportT) -> TransportT:
        if self._closed:
            raise RuntimeError("Client is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._closed:
            raise RuntimeError("Client is closed")
        method = method.upper()
        # Only reads are replayed automatically. A lost write response is ambiguous.
        retries = self.config.max_retries if method in {"GET", "HEAD", "OPTIONS"} else 0
        for attempt in range(retries + 1):
            try:
                response = self.client.request(method, path, **kwargs)
            except httpx.RequestError:
                if attempt == retries:
                    raise TransportError(
                        f"{method} request failed; write outcome may be unknown"
                        if retries == 0 and method not in {"GET", "HEAD", "OPTIONS"}
                        else f"{method} request failed after {attempt + 1} attempt(s)"
                    ) from None
            else:
                if not (response.status_code >= 500 and attempt < retries):
                    return response
                response.close()
            delay = min(self.config.retry_backoff * (2.0 ** min(attempt, 30)), 60.0)
            if delay:
                time.sleep(delay)
        raise RuntimeError("Unexpected retry state")

    @staticmethod
    def check(response: httpx.Response) -> httpx.Response:
        if not response.is_success:
            raise ApiError(response.status_code, response.text)
        return response
