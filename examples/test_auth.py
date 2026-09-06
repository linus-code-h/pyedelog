"""Manual, read-only OAuth smoke test using environment configuration."""

from edelog import EdelogAuth, EdelogConfig


def main() -> None:
    with EdelogAuth(EdelogConfig.from_env()) as auth:
        auth.get_token()
        print("Authentication successful")


if __name__ == "__main__":
    main()
