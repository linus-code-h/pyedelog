import pytest

from edelog.sync import SyncRequest


def test_sync_upsert():
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

    payload = request.to_dict()

    assert payload["version"] == 1

    collection = payload["updateCollections"][0]

    assert collection["databaseName"] == "customers"
    assert collection["performOnNotMatchedRecords"] == "skip"

    task = collection["tasks"][0]

    assert task["type"] == "update-data"
    assert task["ifNotFound"] == "create-new"
    assert task["where"]["external_id"] == "CRM-4711"

    assert task["update"] == {
        "external_id": "CRM-4711",
        "name": "Example Customer",
    }


def test_sync_update():
    request = SyncRequest()

    request.database("customers").update(
        where={
            "external_id": "CRM-4711",
        },
        values={
            "name": "Updated",
        },
    )

    payload = request.to_dict()

    collection = payload["updateCollections"][0]
    task = collection["tasks"][0]

    assert collection["databaseName"] == "customers"
    assert collection["performOnNotMatchedRecords"] == "skip"

    assert task["type"] == "update-data"
    assert task["ifNotFound"] == "skip"

    assert task["where"] == {
        "external_id": "CRM-4711",
    }

    assert task["update"] == {
        "name": "Updated",
    }


def test_sync_delete():
    request = SyncRequest()

    request.database("customers").delete(
        where={
            "external_id": "CRM-4711",
        },
    )

    payload = request.to_dict()

    collection = payload["updateCollections"][0]
    task = collection["tasks"][0]

    assert collection["databaseName"] == "customers"
    assert collection["performOnNotMatchedRecords"] == "skip"

    assert task["type"] == "delete-data"
    assert task["ifNotFound"] == "skip"

    assert task["where"] == {
        "external_id": "CRM-4711",
    }


def test_sync_rejects_empty_where():
    request = SyncRequest()

    collection = request.database("customers")

    with pytest.raises(ValueError):
        collection.delete(
            where={},
        )


def test_select_statement():
    from edelog.sync import select

    statement = select(
        database_name="countries",
        field="id",
        where={
            "iso_code": "DE",
        },
        first=True,
    )

    assert statement == {
        "databaseName": "countries",
        "select": "id",
        "where": {
            "iso_code": "DE",
        },
        "returnFirstRecord": True,
    }


def test_select_statement_without_first():
    from edelog.sync import select

    statement = select(
        database_name="countries",
        field="id",
        where={
            "region": "EU",
        },
    )

    assert statement == {
        "databaseName": "countries",
        "select": "id",
        "where": {
            "region": "EU",
        },
    }


def test_select_rejects_empty_where():
    from edelog.sync import select

    with pytest.raises(ValueError):
        select(
            database_name="countries",
            field="id",
            where={},
        )


def test_upsert_with_relation():
    from edelog.sync import select

    request = SyncRequest()

    request.database("customers").upsert(
        where={
            "external_id": "CRM-4711",
        },
        values={
            "external_id": "CRM-4711",
            "name": "Example Customer",
            "country": select(
                database_name="countries",
                field="id",
                where={
                    "iso_code": "DE",
                },
                first=True,
            ),
        },
    )

    payload = request.to_dict()

    task = payload["updateCollections"][0]["tasks"][0]

    assert task["update"]["country"] == {
        "databaseName": "countries",
        "select": "id",
        "where": {
            "iso_code": "DE",
        },
        "returnFirstRecord": True,
    }


def test_not_matched_throw_error():
    request = SyncRequest()

    collection = request.database(
        "customers",
        perform_on_not_matched_records="throw-error",
    )

    collection.update(
        where={
            "external_id": "CRM-4711",
        },
        values={
            "name": "Updated",
        },
    )

    payload = request.to_dict()

    assert payload["updateCollections"][0]["performOnNotMatchedRecords"] == "throw-error"


def test_invalid_not_matched_action():
    request = SyncRequest()

    with pytest.raises(ValueError):
        request.database(
            "customers",
            perform_on_not_matched_records="invalid",
        )


def test_empty_full_snapshot_delete_is_rejected():
    request = SyncRequest()

    request.database(
        "customers",
        perform_on_not_matched_records="delete",
    )

    with pytest.raises(ValueError):
        request.to_dict()


def test_full_snapshot_delete_with_tasks():
    request = SyncRequest()

    collection = request.database(
        "customers",
        perform_on_not_matched_records="delete",
    )

    collection.upsert(
        where={
            "external_id": "CRM-4711",
        },
        values={
            "external_id": "CRM-4711",
            "name": "Customer",
        },
    )

    payload = request.to_dict()

    assert payload["updateCollections"][0]["performOnNotMatchedRecords"] == "delete"


def test_empty_sync_request_is_rejected():
    request = SyncRequest()

    with pytest.raises(ValueError):
        request.to_dict()


def test_sync_config_from_env(monkeypatch):
    from edelog.sync import DataSyncConfig

    monkeypatch.setenv(
        "EDELOG_BASE_URL",
        "https://example.edelog.com",
    )
    monkeypatch.setenv(
        "EDELOG_SYNC_SERVICE_ID",
        "service-id",
    )
    monkeypatch.setenv(
        "EDELOG_SYNC_ACCESS_KEY",
        "access-key",
    )

    config = DataSyncConfig.from_env()

    assert config.base_url == "https://example.edelog.com"
    assert config.service_id == "service-id"
    assert config.access_key == "access-key"
