class EdelogError(Exception):
    """Base exception for pyedelog."""


class AuthenticationError(EdelogError):
    """Raised when authentication fails."""


class ApiError(EdelogError):
    """Raised when an EDELOG API request fails."""

    def __init__(
        self,
        status_code: int,
        message: str,
    ) -> None:
        self.status_code = status_code
        self.message = message

        super().__init__(f"EDELOG API error {status_code}: {message}")


class DatabaseNotFoundError(EdelogError):
    """Raised when a database cannot be resolved."""

    def __init__(
        self,
        database_name: str,
    ) -> None:
        self.database_name = database_name

        super().__init__(f'Database "{database_name}" not found')


class TransportError(EdelogError):
    """Network failure; a write may already have reached the server."""


class ResponseError(EdelogError):
    """The server returned an unexpected response shape or invalid JSON."""
