import math
from copy import deepcopy
from typing import Any, Literal

from .._validation import nonempty

NotMatchedAction = Literal["skip", "throw-error", "delete"]
MissingAction = Literal["skip", "throw-error"]
VALID_NOT_MATCHED_ACTIONS = {"skip", "throw-error", "delete"}


def _value(value: Any, *, allow_select: bool) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return
    if allow_select and isinstance(value, dict):
        required = {"databaseName", "select", "where"}
        if not required <= value.keys() or value.keys() - required - {"returnFirstRecord"}:
            raise ValueError("Invalid select statement properties")
        nonempty(value["databaseName"], "databaseName")
        nonempty(value["select"], "select")
        _mapping(value["where"], allow_select=False, require_values=True)
        if "returnFirstRecord" in value and not isinstance(value["returnFirstRecord"], bool):
            raise ValueError("returnFirstRecord must be boolean")
        return
    raise ValueError(
        "Expected null, string, finite number, boolean, string array or select statement"
    )


def _mapping(values: Any, *, allow_select: bool = True, require_values: bool = False) -> None:
    if not isinstance(values, dict) or (require_values and not values):
        raise ValueError("Expected a non-empty mapping" if require_values else "Expected a mapping")
    for key, value in values.items():
        nonempty(key, "field name")
        _value(value, allow_select=allow_select)


def select(
    database_name: str, field: str, where: dict[str, Any], first: bool = False
) -> dict[str, Any]:
    statement: dict[str, Any] = {
        "databaseName": database_name,
        "select": field,
        "where": deepcopy(where),
    }
    if not isinstance(first, bool):
        raise ValueError("first must be boolean")
    if first:
        statement["returnFirstRecord"] = True
    _value(statement, allow_select=True)
    return statement


class SyncCollection:
    def __init__(
        self, database_name: str, perform_on_not_matched_records: NotMatchedAction = "skip"
    ) -> None:
        nonempty(database_name, "database_name")
        if perform_on_not_matched_records not in VALID_NOT_MATCHED_ACTIONS:
            raise ValueError("Invalid perform_on_not_matched_records action")
        self.database_name = database_name
        self.perform_on_not_matched_records = perform_on_not_matched_records
        self.tasks: list[dict[str, Any]] = []

    def _add(self, task: dict[str, Any]) -> "SyncCollection":
        self._validate_task(task)
        self.tasks.append(deepcopy(task))
        return self

    @staticmethod
    def _validate_task(task: Any) -> None:
        if not isinstance(task, dict):
            raise ValueError("Task must be a mapping")
        kind = task.get("type")
        if kind not in {"update-data", "delete-data"}:
            raise ValueError("Unsupported task type")
        keys = {"type", "where", "ifNotFound"}
        if kind == "update-data":
            keys.add("update")
        if task.keys() != keys:
            raise ValueError("Invalid task properties")
        _mapping(task["where"], require_values=True)
        allowed = {"skip", "throw-error"}
        if kind == "update-data":
            allowed.add("create-new")
            _mapping(task["update"])
        if task["ifNotFound"] not in allowed:
            raise ValueError("Invalid ifNotFound action")

    def upsert(self, where: dict[str, Any], values: dict[str, Any]) -> "SyncCollection":
        return self._add(
            {"type": "update-data", "where": where, "update": values, "ifNotFound": "create-new"}
        )

    def update(
        self, where: dict[str, Any], values: dict[str, Any], *, if_not_found: MissingAction = "skip"
    ) -> "SyncCollection":
        if if_not_found not in {"skip", "throw-error"}:
            raise ValueError("Update supports skip or throw-error; use upsert to create")
        return self._add(
            {"type": "update-data", "where": where, "update": values, "ifNotFound": if_not_found}
        )

    def delete(
        self, where: dict[str, Any], *, if_not_found: MissingAction = "skip"
    ) -> "SyncCollection":
        if if_not_found not in {"skip", "throw-error"}:
            raise ValueError("Delete supports skip or throw-error")
        return self._add({"type": "delete-data", "where": where, "ifNotFound": if_not_found})

    def to_dict(self) -> dict[str, Any]:
        nonempty(self.database_name, "database_name")
        if self.perform_on_not_matched_records not in VALID_NOT_MATCHED_ACTIONS:
            raise ValueError("Invalid perform_on_not_matched_records action")
        if not isinstance(self.tasks, list):
            raise ValueError("tasks must be a list")
        if self.perform_on_not_matched_records == "delete" and not self.tasks:
            raise ValueError("Refusing full snapshot delete with an empty task list")
        for task in self.tasks:
            self._validate_task(task)
        return deepcopy(
            {
                "databaseName": self.database_name,
                "tasks": self.tasks,
                "performOnNotMatchedRecords": self.perform_on_not_matched_records,
            }
        )


class SyncRequest:
    def __init__(self) -> None:
        self.collections: list[SyncCollection] = []

    def database(
        self, database_name: str, perform_on_not_matched_records: NotMatchedAction = "skip"
    ) -> SyncCollection:
        collection = SyncCollection(database_name, perform_on_not_matched_records)
        self.collections.append(collection)
        return collection

    def to_dict(self) -> dict[str, Any]:
        if not self.collections:
            raise ValueError("SyncRequest must contain at least one collection")
        if any(not isinstance(c, SyncCollection) for c in self.collections):
            raise ValueError("Expected SyncCollection instances")
        collections = [collection.to_dict() for collection in self.collections]
        for collection in collections:
            if collection["performOnNotMatchedRecords"] != "skip":
                if sum(c["databaseName"] == collection["databaseName"] for c in collections) > 1:
                    raise ValueError("Reconciliation requires exactly one collection per database")
        return {"version": 1, "updateCollections": collections}
