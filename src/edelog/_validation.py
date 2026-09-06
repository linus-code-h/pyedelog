import math
from urllib.parse import urlsplit


def nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def validate_config(base_url: str, timeout: float, max_retries: int, retry_backoff: float) -> None:
    nonempty(base_url, "base_url")
    try:
        url = urlsplit(base_url)
        port = url.port
    except ValueError:
        raise ValueError("base_url must be a valid HTTP(S) URL") from None
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username is not None
        or url.password is not None
        or url.query
        or url.fragment
        or any(c.isspace() for c in base_url)
    ):
        raise ValueError("base_url must be an HTTP(S) URL without credentials, query or fragment")
    if port == 0:
        raise ValueError("base_url port must be greater than zero")
    for name, value, minimum in (("timeout", timeout, 0), ("retry_backoff", retry_backoff, 0)):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < minimum
            or (name == "timeout" and value == 0)
        ):
            raise ValueError(
                f"{name} must be finite and {'positive' if name == 'timeout' else 'non-negative'}"
            )
    if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
        raise ValueError("max_retries must be a non-negative integer")
