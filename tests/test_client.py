from edelog import (
    DataSyncConfig,
    Edelog,
    EdelogConfig,
)
from edelog.auth import EdelogAuth
from edelog.core.http import EdelogHttpClient
from edelog.data import DataClient
from edelog.sync import DataSyncClient


def create_config() -> EdelogConfig:
    return EdelogConfig(
        base_url="https://example.edelog.com",
        client_id="client-id",
        client_secret="client-secret",
        organization_id="organization-id",
    )


def test_edelog_client():
    config = create_config()

    edelog = Edelog(config)

    assert edelog.config is config

    assert isinstance(
        edelog.auth,
        EdelogAuth,
    )

    assert isinstance(
        edelog.http,
        EdelogHttpClient,
    )

    assert isinstance(
        edelog.data,
        DataClient,
    )

    assert edelog.sync is None


def test_edelog_client_with_sync():
    config = create_config()

    sync_config = DataSyncConfig(
        base_url="https://example.edelog.com",
        service_id="service-id",
        access_key="access-key",
    )

    edelog = Edelog(
        config=config,
        sync_config=sync_config,
    )

    assert isinstance(
        edelog.data,
        DataClient,
    )

    assert isinstance(
        edelog.sync,
        DataSyncClient,
    )

    assert edelog.sync_config is sync_config


def test_edelog_from_env(monkeypatch):
    monkeypatch.setenv(
        "EDELOG_BASE_URL",
        "https://example.edelog.com",
    )
    monkeypatch.setenv(
        "EDELOG_CLIENT_ID",
        "client-id",
    )
    monkeypatch.setenv(
        "EDELOG_CLIENT_SECRET",
        "client-secret",
    )
    monkeypatch.setenv(
        "EDELOG_ORGANIZATION_ID",
        "organization-id",
    )

    edelog = Edelog.from_env()

    assert isinstance(edelog.data, DataClient)
    assert edelog.sync is None


def test_edelog_from_env_with_sync(monkeypatch):
    monkeypatch.setenv(
        "EDELOG_BASE_URL",
        "https://example.edelog.com",
    )
    monkeypatch.setenv(
        "EDELOG_CLIENT_ID",
        "client-id",
    )
    monkeypatch.setenv(
        "EDELOG_CLIENT_SECRET",
        "client-secret",
    )
    monkeypatch.setenv(
        "EDELOG_ORGANIZATION_ID",
        "organization-id",
    )

    monkeypatch.setenv(
        "EDELOG_SYNC_SERVICE_ID",
        "service-id",
    )
    monkeypatch.setenv(
        "EDELOG_SYNC_ACCESS_KEY",
        "access-key",
    )

    edelog = Edelog.from_env(
        with_sync=True,
    )

    assert isinstance(edelog.data, DataClient)
    assert isinstance(edelog.sync, DataSyncClient)
