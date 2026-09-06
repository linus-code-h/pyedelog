import json
from email.parser import BytesParser
from email.policy import default
from urllib.parse import parse_qs

import httpx
import pytest

from edelog import (
    ApiError,
    AuthenticationError,
    DataSyncClient,
    DataSyncConfig,
    Edelog,
    EdelogAuth,
    EdelogConfig,
    ResponseError,
    SyncRequest,
    TransportError,
    select,
)


def config(**kwargs):
    return EdelogConfig(
        "https://example.test", "client", "secret", "org", retry_backoff=0, **kwargs
    )


@pytest.fixture
def make_client():
    clients = []

    def make(handler):
        raw = httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(handler))
        client = Edelog(config(), client=raw)
        client.auth._token = "test-token"
        client.auth._expires_at = float("inf")
        clients.append((client, raw))
        return client

    yield make
    for client, raw in clients:
        client.close()
        raw.close()


@pytest.mark.parametrize("method", ["post", "put"])
@pytest.mark.parametrize("failure", ["timeout", "server"])
def test_writes_are_not_replayed(make_client, method, failure):
    calls = []

    def handler(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("lost write response", request=request)
        return httpx.Response(503)

    client = make_client(handler)
    with pytest.raises(TransportError if failure == "timeout" else ApiError):
        getattr(client.http, method)("/api/v4/test")
    assert len(calls) == 1


def test_read_transport_failure_is_bounded(make_client):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("unreachable", request=request)

    with pytest.raises(TransportError):
        make_client(handler).http.get("/api/v4/test")
    assert len(calls) == 3


def test_repeated_401_stops_after_one_refresh():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "token"})
        return httpx.Response(401)

    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    ) as raw:
        with Edelog(config(), client=raw) as client:
            with pytest.raises(ApiError):
                client.http.get("/data")
    assert calls == ["/oauth/token", "/data", "/oauth/token", "/data"]


@pytest.mark.parametrize("method", ["create_record", "update_record"])
def test_write_multipart_and_empty_response(make_client, method):
    def handler(request):
        message = BytesParser(policy=default).parsebytes(
            b"Content-Type: "
            + request.headers["content-type"].encode()
            + b"\r\n\r\n"
            + request.content
        )
        parts = list(message.iter_parts())
        assert len(parts) == 1
        assert parts[0].get_param("name", header="content-disposition") == "data"
        assert json.loads(parts[0].get_payload(decode=True)) == {"title": "Grüße", "links": ["one"]}
        return httpx.Response(204)

    data = make_client(handler).data
    args = ("db",) if method == "create_record" else ("db", "record")
    assert getattr(data, method)(*args, {"title": "Grüße", "links": ["one"]}) is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"data": None}),
        httpx.Response(200, json={"data": [1]}),
        httpx.Response(200, json={"success": False, "data": []}),
    ],
)
def test_bad_list_response_is_library_error(make_client, response):
    with pytest.raises(ResponseError):
        make_client(lambda r: response).data.list_records("db")


def test_get_record_contract(make_client):
    def handler(request):
        assert request.url.path == "/api/v4/data_types/db/data/one/payload"
        assert request.url.params["select"] == "id,title"
        return httpx.Response(200, json={"data": {"id": "one"}})

    assert make_client(handler).data.get_record("db", "one", ["id", "title"]) == {"id": "one"}


def test_resolve_second_page(make_client):
    pages = []

    def handler(request):
        page = int(request.url.params["page"])
        pages.append(page)
        rows = (
            [{"id": str(i), "name": str(i)} for i in range(200)]
            if page == 1
            else [{"id": "target", "name": "customers"}]
        )
        return httpx.Response(200, json={"data": rows})

    assert make_client(handler).data.database("customers").id == "target"
    assert pages == [1, 2]


def test_iterator_is_lazy_and_preserves_query(make_client):
    pages = []

    def handler(request):
        page = int(request.url.params["page"])
        pages.append(page)
        assert request.url.params["select"] == "id"
        assert request.url.params["viewOption"] == "archive"
        assert request.url.params["filterStatement"] == "filter"
        return httpx.Response(
            200, json={"data": [{"id": str(i)} for i in range(200)] if page == 1 else []}
        )

    records = make_client(handler).data.iter_records("db", ["id"], "filter", "archive")
    assert pages == []
    assert next(records) == {"id": "0"}
    assert pages == [1]
    assert len(list(records)) == 199
    assert pages == [1, 2]


def test_sync_copies_input_and_output():
    request = SyncRequest()
    where = {"external_id": "one"}
    values = {"external_id": "one", "links": ["a"]}
    collection = request.database("customers").upsert(where, values)
    where.clear()
    values["links"].append("b")
    exported = request.to_dict()
    exported["updateCollections"][0]["tasks"][0]["where"].clear()
    task = collection.to_dict()["tasks"][0]
    assert task["where"] == {"external_id": "one"}
    assert task["update"]["links"] == ["a"]


def test_sync_revalidates_before_any_network_request():
    request = SyncRequest()
    collection = request.database("customers").delete({"external_id": "one"})
    collection.tasks[0]["where"].clear()

    def handler(r):
        pytest.fail("Invalid request reached the network")

    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    ) as raw:
        with DataSyncClient(
            DataSyncConfig("https://example.test", "service", "key"), client=raw
        ) as sync:
            with pytest.raises(ValueError):
                sync.submit(request)


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), [1], {"arbitrary": "object"}, object()]
)
def test_sync_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        SyncRequest().database("db").update({"id": "one"}, {"value": value})


@pytest.mark.parametrize("action", ["delete", "throw-error"])
def test_duplicate_reconciliation_rejected(action):
    request = SyncRequest()
    request.database("db", action).upsert({"id": "a"}, {"id": "a"})
    request.database("db").upsert({"id": "b"}, {"id": "b"})
    with pytest.raises(ValueError):
        request.to_dict()


def test_missing_record_policy_and_select_validation():
    collection = SyncRequest().database("db")
    collection.update({"id": "one"}, {}, if_not_found="throw-error")
    collection.delete({"id": "two"}, if_not_found="throw-error")
    assert all(t["ifNotFound"] == "throw-error" for t in collection.to_dict()["tasks"])
    with pytest.raises(ValueError):
        select("", "id", {"code": "DE"})
    with pytest.raises(ValueError):
        select("countries", "", {"code": "DE"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("base_url", "ftp://example.test"),
        ("base_url", "https://user:secret@example.test"),
        ("base_url", "https://example.test?token=secret"),
        ("base_url", " "),
        ("client_id", " "),
        ("timeout", float("nan")),
        ("timeout", 0),
        ("retry_backoff", float("inf")),
        ("max_retries", 1.5),
        ("max_retries", True),
    ],
)
def test_config_rejects_invalid_values(field, value):
    args = dict(
        base_url="https://example.test",
        client_id="client",
        client_secret="secret",
        organization_id="org",
    )
    args[field] = value
    with pytest.raises(ValueError):
        EdelogConfig(**args)


def test_config_repr_hides_secrets():
    assert "client_secret=" not in repr(config())
    assert "access_key=" not in repr(DataSyncConfig("https://example.test", "service", "key"))


def test_owned_clients_close_and_injected_client_stays_open():
    with Edelog(config(), DataSyncConfig("https://example.test", "service", "key")) as owned:
        assert owned.auth.client is owned.http.client
        sync_raw = owned.sync.client
    assert owned.http.client.is_closed
    assert sync_raw.is_closed
    owned.close()
    with pytest.raises(RuntimeError):
        owned.auth.get_token()
    with httpx.Client(base_url="https://example.test") as raw:
        with Edelog(config(), client=raw) as borrowed:
            pass
        assert not raw.is_closed
        with pytest.raises(RuntimeError):
            borrowed.http.get("/data")


def test_auth_form_cache_and_expiry(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("edelog.auth.time.monotonic", lambda: now[0])
    calls = []

    def handler(request):
        calls.append(request)
        assert parse_qs(request.content.decode()) == {
            "grant_type": ["client_credentials"],
            "client_id": ["client"],
            "client_secret": ["secret"],
            "organization_id": ["org"],
        }
        return httpx.Response(200, json={"access_token": f"token-{len(calls)}", "expires_in": 100})

    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    ) as raw:
        with EdelogAuth(config(), client=raw) as auth:
            assert auth.get_token() == "token-1"
            now[0] = 150
            assert auth.get_token() == "token-1"
            now[0] = 191
            assert auth.get_token() == "token-2"
        assert not raw.is_closed


def test_auth_failure_does_not_echo_secret():
    with httpx.Client(
        base_url="https://example.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(403, text="secret")),
    ) as raw:
        with EdelogAuth(config(), client=raw) as auth:
            with pytest.raises(AuthenticationError) as error:
                auth.get_token()
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "payload,error_type",
    [
        ({}, AuthenticationError),
        ({"access_token": 123}, AuthenticationError),
        ({"access_token": "token", "expires_in": 0}, AuthenticationError),
        ({"access_token": "token", "expires_in": True}, AuthenticationError),
        ([], ResponseError),
    ],
)
def test_invalid_auth_responses(payload, error_type):
    with httpx.Client(
        base_url="https://example.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)),
    ) as raw:
        with EdelogAuth(config(), client=raw) as auth:
            with pytest.raises(error_type):
                auth.get_token()


@pytest.mark.parametrize(
    "payload", [{}, {"data": {}}, {"data": {"id": "job", "status": "unknown"}}]
)
def test_invalid_sync_job_response(payload):
    with httpx.Client(
        base_url="https://example.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(201, json=payload)),
    ) as raw:
        with DataSyncClient(
            DataSyncConfig("https://example.test", "service", "key"), client=raw
        ) as sync:
            with pytest.raises(ResponseError):
                sync.report_error("source unavailable")


def test_standalone_clients_close_on_exception():
    for client in [
        EdelogAuth(config()),
        DataSyncClient(DataSyncConfig("https://example.test", "service", "key")),
    ]:
        with pytest.raises(ValueError):
            with client:
                raise ValueError("application failure")
        assert client.client.is_closed
        client.close()


def test_sync_error_reporting_does_not_retry_timeout():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("response lost", request=request)

    with httpx.Client(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    ) as raw:
        with DataSyncClient(
            DataSyncConfig("https://example.test", "service", "key"), client=raw
        ) as sync:
            with pytest.raises(TransportError):
                sync.report_error("source unavailable")
    assert len(calls) == 1
