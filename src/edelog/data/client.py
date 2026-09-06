import json
from collections.abc import Iterator
from typing import Any

from ..core.http import EdelogHttpClient
from ..core.response import json_object, record_list
from ..exceptions import DatabaseNotFoundError, ResponseError
from .database import Database


class DataClient:
    def __init__(self, http: EdelogHttpClient) -> None:
        self.http = http

    def database(
        self,
        technical_name: str,
    ) -> Database:
        return Database(
            client=self,
            technical_name=technical_name,
        )

    def get_record(
        self,
        database_id: str,
        record_id: str,
        fields: list[str] | None = None,
    ) -> dict[str, Any] | None:
        params: dict[str, Any] = {}

        if fields:
            params["select"] = ",".join(fields)

        response = self.http.get(
            f"/api/v4/data_types/{database_id}/data/{record_id}/payload",
            params=params,
        )

        result = json_object(response)
        assert result is not None
        if "data" not in result:
            raise ResponseError("Expected data in record response")
        record = result["data"]
        if record is not None and not isinstance(record, dict):
            raise ResponseError("Expected a record or null")
        return record

    def list_records(
        self,
        database_id: str,
        fields: list[str] | None = None,
        filter_statement: str | None = None,
        view_option: str = "listable",
    ) -> list[dict[str, Any]]:
        return list(self.iter_records(database_id, fields, filter_statement, view_option))

    def iter_records(
        self,
        database_id: str,
        fields: list[str] | None = None,
        filter_statement: str | None = None,
        view_option: str = "listable",
    ) -> Iterator[dict[str, Any]]:
        page = 1
        limit = 200

        while True:
            params: dict[str, Any] = {
                "page": page,
                "limit": limit,
                "viewOption": view_option,
            }

            if fields:
                params["select"] = ",".join(fields)

            if filter_statement:
                params["filterStatement"] = filter_statement

            response = self.http.get(
                f"/api/v4/data_types/{database_id}/data",
                params=params,
            )

            page_records = record_list(response)
            yield from page_records

            if len(page_records) < limit:
                break

            page += 1

    def create_record(
        self,
        database_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        response = self.http.post(
            f"/api/v4/data_types/{database_id}/data",
            files={
                "data": (
                    None,
                    json.dumps(values, allow_nan=False),
                )
            },
        )

        return json_object(response, allow_empty=True)

    def update_record(
        self,
        database_id: str,
        record_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        response = self.http.put(
            f"/api/v4/data_types/{database_id}/data/{record_id}",
            files={
                "data": (
                    None,
                    json.dumps(values, allow_nan=False),
                )
            },
        )

        return json_object(response, allow_empty=True)

    def resolve_database(
        self,
        technical_name: str,
    ) -> dict[str, Any]:
        page = 1
        while True:
            response = self.http.get(
                "/api/v4/data_types",
                params={"includeHidden": 1, "limit": 200, "page": page},
            )
            databases = record_list(response)
            for database in databases:
                if database.get("name") == technical_name:
                    if not isinstance(database.get("id"), str) or not database["id"]:
                        raise ResponseError("Database response lacks a valid id")
                    return database
            if len(databases) < 200:
                break
            page += 1
        raise DatabaseNotFoundError(technical_name)
