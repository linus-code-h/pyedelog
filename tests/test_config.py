import pytest

from edelog import EdelogConfig


def test_config():
    config = EdelogConfig(
        base_url="https://example.edelog.com",
        client_id="client-id",
        client_secret="client-secret",
        organization_id="organization-id",
    )

    assert config.base_url == "https://example.edelog.com"
    assert config.timeout == 30.0


def test_config_from_env(monkeypatch):
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

    config = EdelogConfig.from_env()

    assert config.base_url == "https://example.edelog.com"
    assert config.client_id == "client-id"
    assert config.client_secret == "client-secret"
    assert config.organization_id == "organization-id"


def test_config_from_env_missing(monkeypatch):
    monkeypatch.delenv(
        "EDELOG_BASE_URL",
        raising=False,
    )

    with pytest.raises(ValueError):
        EdelogConfig.from_env()
