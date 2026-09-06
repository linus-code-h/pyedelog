import json
from urllib.parse import parse_qs

import httpx
import pytest

from edelog import ApiError, TransportError
from edelog.sync import (
    DataSyncClient,
    DataSyncConfig,
    SyncRequest,
)


def test_submit_sync_request():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"

        assert request.url.path == ("/api/v4/sync_services/service-id/jobs")

        assert request.headers["Authorization"] == "Bearer access-key"

        form = parse_qs(request.content.decode())

        payload = json.loads(form["requestPayload"][0])

        assert payload["version"] == 1

        assert payload["updateCollections"][0]["databaseName"] == "customers"

        return httpx.Response(
            201,
            json={
                "success": True,
                "data": {
                    "id": "job-id",
                    "status": "enqueued",
                },
            },
        )

    transport = httpx.MockTransport(handler)

    http_client = httpx.Client(
        base_url="https://example.edelog.com",
        transport=transport,
    )

    config = DataSyncConfig(
        base_url="https://example.edelog.com",
        service_id="service-id",
        access_key="access-key",
    )

    sync = DataSyncClient(
        config=config,
        client=http_client,
    )

    request = SyncRequest()

    request.database("customers").upsert(
        where={
            "external_id": "CRM-4711",
        },
        values={
            "external_id": "CRM-4711",
            "name": "Example Customer",
        },
    )

    result = sync.submit(request)

    assert result["success"] is True
    assert result["data"]["id"] == "job-id"
    assert result["data"]["status"] == "enqueued"


def test_report_error():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"

        assert request.url.path == ("/api/v4/sync_services/service-id/jobs/error")

        assert request.headers["Authorization"] == "Bearer access-key"

        form = parse_qs(request.content.decode())

        assert form["errorMessage"][0] == "Source system unavailable"

        return httpx.Response(
            201,
            json={
                "success": True,
                "data": {
                    "id": "failed-job-id",
                    "status": "failed",
                },
            },
        )

    transport = httpx.MockTransport(handler)

    http_client = httpx.Client(
        base_url="https://example.edelog.com",
        transport=transport,
    )

    config = DataSyncConfig(
        base_url="https://example.edelog.com",
        service_id="service-id",
        access_key="access-key",
    )

    sync = DataSyncClient(
        config=config,
        client=http_client,
    )

    result = sync.report_error("Source system unavailable")

    assert result["success"] is True
    assert result["data"]["status"] == "failed"


def test_sync_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            text="Not found",
        )

    transport = httpx.MockTransport(handler)

    http_client = httpx.Client(
        base_url="https://example.edelog.com",
        transport=transport,
    )

    config = DataSyncConfig(
        base_url="https://example.edelog.com",
        service_id="service-id",
        access_key="access-key",
    )

    sync = DataSyncClient(
        config=config,
        client=http_client,
    )

    request = SyncRequest()

    request.database("customers").upsert(
        where={
            "external_id": "CRM-4711",
        },
        values={
            "external_id": "CRM-4711",
        },
    )

    with pytest.raises(ApiError) as error:
        sync.submit(request)

    assert error.value.status_code == 404
    assert error.value.message == "Not found"


def test_sync_no_retry_on_server_error():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count < 3:
            return httpx.Response(
                500,
                text="Internal server error",
            )

        return httpx.Response(
            201,
            json={
                "success": True,
                "data": {
                    "id": "job-id",
                    "status": "enqueued",
                },
            },
        )

    transport = httpx.MockTransport(handler)

    http_client = httpx.Client(
        base_url="https://example.edelog.com",
        transport=transport,
    )

    config = DataSyncConfig(
        base_url="https://example.edelog.com",
        service_id="service-id",
        access_key="access-key",
        max_retries=2,
        retry_backoff=0,
    )

    sync = DataSyncClient(
        config=config,
        client=http_client,
    )

    request = SyncRequest()

    request.database("customers").upsert(
        where={
            "external_id": "CRM-4711",
        },
        values={
            "external_id": "CRM-4711",
        },
    )

    with pytest.raises(ApiError):
        sync.submit(request)
    assert request_count == 1


def test_sync_no_retry_on_client_error():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return httpx.Response(
            400,
            text="Bad request",
        )

    transport = httpx.MockTransport(handler)

    http_client = httpx.Client(
        base_url="https://example.edelog.com",
        transport=transport,
    )

    config = DataSyncConfig(
        base_url="https://example.edelog.com",
        service_id="service-id",
        access_key="access-key",
        max_retries=2,
        retry_backoff=0,
    )

    sync = DataSyncClient(
        config=config,
        client=http_client,
    )

    request = SyncRequest()

    request.database("customers").upsert(
        where={
            "external_id": "CRM-4711",
        },
        values={
            "external_id": "CRM-4711",
        },
    )

    with pytest.raises(ApiError) as error:
        sync.submit(request)

    assert error.value.status_code == 400
    assert request_count == 1


def test_sync_no_retry_on_network_error():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        if request_count < 3:
            raise httpx.ConnectError(
                "Connection failed",
                request=request,
            )

        return httpx.Response(
            201,
            json={
                "success": True,
                "data": {
                    "id": "job-id",
                    "status": "enqueued",
                },
            },
        )

    transport = httpx.MockTransport(handler)

    http_client = httpx.Client(
        base_url="https://example.edelog.com",
        transport=transport,
    )

    config = DataSyncConfig(
        base_url="https://example.edelog.com",
        service_id="service-id",
        access_key="access-key",
        max_retries=2,
        retry_backoff=0,
    )

    sync = DataSyncClient(
        config=config,
        client=http_client,
    )

    request = SyncRequest()

    request.database("customers").upsert(
        where={
            "external_id": "CRM-4711",
        },
        values={
            "external_id": "CRM-4711",
        },
    )

    with pytest.raises(TransportError):
        sync.submit(request)
    assert request_count == 1
