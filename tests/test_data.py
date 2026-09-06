import httpx
import pytest

from edelog import (
    DatabaseNotFoundError,
    EdelogAuth,
    EdelogConfig,
)
from edelog.core.http import EdelogHttpClient
from edelog.data import DataClient


def test_list_records():

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == ("/api/v4/data_types/database-id/data")

        assert request.url.params["page"] == "1"
        assert request.url.params["limit"] == "200"
        assert request.url.params["viewOption"] == "listable"
        assert request.url.params["select"] == "id,name"

        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "1",
                        "name": "First",
                    },
                    {
                        "id": "2",
                        "name": "Second",
                    },
                ]
            },
        )

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

    data = DataClient(http)

    records = data.list_records(
        database_id="database-id",
        fields=["id", "name"],
    )

    assert len(records) == 2
    assert records[0]["name"] == "First"
    assert records[1]["name"] == "Second"


def test_list_records_with_filter():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["filterStatement"] == "status:eq:open"

        return httpx.Response(
            200,
            json={"data": []},
        )

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

    data = DataClient(http)

    records = data.list_records(
        database_id="database-id",
        filter_statement="status:eq:open",
    )

    assert records == []


def test_list_records_pagination():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        page = int(request.url.params["page"])

        if page == 1:
            return httpx.Response(
                200,
                json={"data": [{"id": str(i)} for i in range(200)]},
            )

        return httpx.Response(
            200,
            json={"data": [{"id": "200"}]},
        )

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

    data = DataClient(http)

    records = data.list_records(
        database_id="database-id",
    )

    assert len(records) == 201
    assert request_count == 2


def test_create_record():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == ("/api/v4/data_types/database-id/data")

        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "new-record-id",
                    "name": "Test",
                }
            },
        )

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

    data = DataClient(http)

    result = data.create_record(
        database_id="database-id",
        values={
            "name": "Test",
        },
    )

    assert result["data"]["id"] == "new-record-id"


def test_update_record():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == ("/api/v4/data_types/database-id/data/record-id")

        return httpx.Response(
            200,
            json={
                "data": {
                    "id": "record-id",
                    "name": "Updated",
                }
            },
        )

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

    data = DataClient(http)

    result = data.update_record(
        database_id="database-id",
        record_id="record-id",
        values={
            "name": "Updated",
        },
    )

    assert result["data"]["name"] == "Updated"


def test_resolve_database():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v4/data_types"
        assert request.url.params["includeHidden"] == "1"
        assert request.url.params["limit"] == "200"

        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "database-1",
                        "name": "customers",
                    },
                    {
                        "id": "database-2",
                        "name": "employees",
                    },
                ]
            },
        )

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

    data = DataClient(http)

    database = data.resolve_database("employees")

    assert database["id"] == "database-2"
    assert database["name"] == "employees"


def test_resolve_database_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": []},
        )

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

    data = DataClient(http)

    with pytest.raises(DatabaseNotFoundError):
        data.resolve_database("unknown")
