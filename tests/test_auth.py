import httpx

from edelog import EdelogAuth, EdelogConfig


def test_get_token():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/token"
        assert request.method == "POST"

        return httpx.Response(
            200,
            json={
                "access_token": "test-token",
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

    token = auth.get_token()

    assert token == "test-token"


def test_token_is_cached():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return httpx.Response(
            200,
            json={
                "access_token": "test-token",
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

    first_token = auth.get_token()
    second_token = auth.get_token()

    assert first_token == "test-token"
    assert second_token == "test-token"
    assert request_count == 1


def test_clear_token():
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1

        return httpx.Response(
            200,
            json={
                "access_token": f"token-{request_count}",
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

    first_token = auth.get_token()

    auth.clear_token()

    second_token = auth.get_token()

    assert first_token == "token-1"
    assert second_token == "token-2"
    assert request_count == 2
