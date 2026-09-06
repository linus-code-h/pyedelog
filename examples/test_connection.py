"""Manual, read-only connection check using environment configuration."""

from edelog import Edelog


def main() -> None:
    with Edelog.from_env() as edelog:
        page = 1
        count = 0
        while True:
            response = edelog.http.get(
                "/api/v4/data_types",
                params={"includeHidden": 1, "limit": 200, "page": page},
            )
            databases = response.json()["data"]
            count += len(databases)
            if len(databases) < 200:
                break
            page += 1
        print(f"Connection successful; databases found: {count}")


if __name__ == "__main__":
    main()
