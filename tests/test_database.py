import httpx

from edelog import EdelogAuth, EdelogConfig
from edelog.core.http import EdelogHttpClient
from edelog.data import Database, DataClient


def create_data_client(
    handler,
) -> DataClient:
    transport = httpx.MockTransport(handler)

    client = httpx.Client(
        base_url="https://example.edelog.com",
        transport=transport,
    )

    config = EdelogConfig(
        base_url="https://example.edelog.com",
        client_id="client-id",
        client_secret="client-secret",
        organization_id="organization-id",
    )

    auth = EdelogAuth(
        config=config,
        client=client,
    )

    auth.get_token = lambda: "test-token"

    http = EdelogHttpClient(
        config=config,
        auth=auth,
        client=client,
    )

    return DataClient(http)


def test_database_object():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v4/data_types":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "database-id",
                            "name": "customers",
                        }
                    ]
                },
            )

        if request.url.path == ("/api/v4/data_types/database-id/data"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "1",
                            "name": "Customer",
                        }
                    ]
                },
            )

        raise AssertionError(f"Unexpected path: {request.url.path}")

    data = create_data_client(handler)

    customers = data.database("customers")

    assert isinstance(customers, Database)
    assert customers.technical_name == "customers"

    records = customers.list()

    assert len(records) == 1
    assert records[0]["name"] == "Customer"


def test_database_id_is_cached():
    resolve_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal resolve_count

        if request.url.path == "/api/v4/data_types":
            resolve_count += 1

            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "database-id",
                            "name": "customers",
                        }
                    ]
                },
            )

        if request.url.path == ("/api/v4/data_types/database-id/data"):
            return httpx.Response(
                200,
                json={"data": []},
            )

        raise AssertionError(f"Unexpected path: {request.url.path}")

    data = create_data_client(handler)

    customers = data.database("customers")

    customers.list()
    customers.list()

    assert resolve_count == 1
