from types import TracebackType

import httpx

from .auth import EdelogAuth
from .config import EdelogConfig
from .core.http import EdelogHttpClient
from .data import DataClient
from .sync import DataSyncClient, DataSyncConfig


class Edelog:
    def __init__(
        self,
        config: EdelogConfig,
        sync_config: DataSyncConfig | None = None,
        *,
        client: httpx.Client | None = None,
        sync_client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = (
            client
            if client is not None
            else httpx.Client(
                base_url=config.base_url.rstrip("/"),
                timeout=config.timeout,
            )
        )
        self.config = config
        self.sync_config = sync_config

        self.auth = EdelogAuth(
            config=config,
            client=self._client,
        )

        self.http = EdelogHttpClient(
            config=config,
            client=self._client,
            auth=self.auth,
        )

        self.data = DataClient(
            http=self.http,
        )

        self.sync = (
            DataSyncClient(
                config=sync_config,
                client=sync_client,
            )
            if sync_config is not None
            else None
        )

    @classmethod
    def from_env(
        cls,
        with_sync: bool = False,
    ) -> "Edelog":
        config = EdelogConfig.from_env()

        sync_config = DataSyncConfig.from_env() if with_sync else None

        return cls(
            config=config,
            sync_config=sync_config,
        )

    def close(self) -> None:
        self.http.close()
        self.auth.close()
        if self.sync is not None:
            self.sync.close()
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "Edelog":
        if self.http._closed:
            raise RuntimeError("Client is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
