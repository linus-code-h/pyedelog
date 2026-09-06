import os
from dataclasses import dataclass, field

from ._validation import nonempty, validate_config


@dataclass(frozen=True, slots=True)
class EdelogConfig:
    base_url: str
    client_id: str
    client_secret: str = field(repr=False)
    organization_id: str

    timeout: float = 30.0
    max_retries: int = 2
    retry_backoff: float = 0.5

    def __post_init__(self) -> None:
        validate_config(self.base_url, self.timeout, self.max_retries, self.retry_backoff)
        nonempty(self.client_id, "client_id")
        nonempty(self.client_secret, "client_secret")
        nonempty(self.organization_id, "organization_id")

    @classmethod
    def from_env(cls) -> "EdelogConfig":
        return cls(
            base_url=cls._get_env("EDELOG_BASE_URL"),
            client_id=cls._get_env("EDELOG_CLIENT_ID"),
            client_secret=cls._get_env("EDELOG_CLIENT_SECRET"),
            organization_id=cls._get_env("EDELOG_ORGANIZATION_ID"),
        )

    @staticmethod
    def _get_env(name: str) -> str:
        value = os.getenv(name)

        if not value:
            raise ValueError(f"Environment variable {name} is not set")

        return value
