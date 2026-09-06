import httpx
import pytest

from edelog import (
    ApiError,
    EdelogAuth,
    EdelogConfig,
)
from edelog.core.http import EdelogHttpClient


def test_get_request():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v4/test"
        assert request.headers["Authorization"] == "Bearer test-token"

        return httpx.Response(
            200,
            json={
                "success": True,
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

    response = http.get("/api/v4/test")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
    }


def test_reauthenticate_on_401():
    api_request_count = 0
    token_request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal api_request_count
        nonlocal token_request_count

        if request.url.path == "/oauth/token":
            token_request_count += 1

            return httpx.Response(
                200,
                json={
                    "access_token": f"token-{token_request_count}",
                },
            )

        if request.url.path == "/api/v4/test":
            api_request_count += 1

            if api_request_count == 1:
                assert request.headers["Authorization"] == "Bearer token-1"

                return httpx.Response(
                    401,
                    json={
                        "error": "unauthorized",
                    },
                )

            assert request.headers["Authorization"] == "Bearer token-2"

            return httpx.Response(
                200,
                json={
                    "success": True,
                },
            )

        raise AssertionError(f"Unexpected path: {request.url.path}")

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

    http = EdelogHttpClient(
        config=config,
        auth=auth,
        client=client,
    )

    response = http.get("/api/v4/test")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
    }

    assert token_request_count == 2
    assert api_request_count == 2


def test_api_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            text="Not found",
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

    with pytest.raises(ApiError) as error:
        http.get("/api/v4/test")

    assert error.value.status_code == 404
    assert error.value.message == "Not found"


def test_retry_on_server_error():
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
            200,
            json={
                "success": True,
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
        max_retries=2,
        retry_backoff=0,
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

    response = http.get("/api/v4/test")

    assert response.status_code == 200
    assert request_count == 3


def test_no_retry_on_client_error():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return httpx.Response(
            400,
            text="Bad request",
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
        max_retries=2,
        retry_backoff=0,
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

    with pytest.raises(ApiError) as error:
        http.get("/api/v4/test")

    assert error.value.status_code == 400
    assert request_count == 1


def test_retry_on_network_error():
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
            200,
            json={
                "success": True,
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
        max_retries=2,
        retry_backoff=0,
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

    response = http.get("/api/v4/test")

    assert response.status_code == 200
    assert request_count == 3
