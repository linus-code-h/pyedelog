import os
from dataclasses import dataclass, field

from .._validation import nonempty, validate_config


@dataclass(frozen=True, slots=True)
class DataSyncConfig:
    base_url: str
    service_id: str
    access_key: str = field(repr=False)

    timeout: float = 30.0
    max_retries: int = 2
    retry_backoff: float = 0.5

    def __post_init__(self) -> None:
        validate_config(self.base_url, self.timeout, self.max_retries, self.retry_backoff)
        nonempty(self.service_id, "service_id")
        nonempty(self.access_key, "access_key")

    @classmethod
    def from_env(cls) -> "DataSyncConfig":
        return cls(
            base_url=cls._get_env("EDELOG_BASE_URL"),
            service_id=cls._get_env("EDELOG_SYNC_SERVICE_ID"),
            access_key=cls._get_env("EDELOG_SYNC_ACCESS_KEY"),
        )

    @staticmethod
    def _get_env(name: str) -> str:
        value = os.getenv(name)

        if not value:
            raise ValueError(f"Environment variable {name} is not set")

        return value
