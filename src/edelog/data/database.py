import builtins
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import DataClient


class Database:
    def __init__(
        self,
        client: "DataClient",
        technical_name: str,
    ) -> None:
        self.client = client
        self.technical_name = technical_name
        self._database_id: str | None = None

    @property
    def id(self) -> str:
        if self._database_id is None:
            database = self.client.resolve_database(self.technical_name)

            self._database_id = database["id"]

        return self._database_id

    def get(
        self,
        record_id: str,
        fields: builtins.list[str] | None = None,
    ) -> dict[str, Any] | None:
        return self.client.get_record(
            database_id=self.id,
            record_id=record_id,
            fields=fields,
        )

    def list(
        self,
        fields: builtins.list[str] | None = None,
        filter_statement: str | None = None,
        view_option: str = "listable",
    ) -> builtins.list[dict[str, Any]]:
        return self.client.list_records(
            database_id=self.id,
            fields=fields,
            filter_statement=filter_statement,
            view_option=view_option,
        )

    def iter_records(
        self,
        fields: builtins.list[str] | None = None,
        filter_statement: str | None = None,
        view_option: str = "listable",
    ) -> Iterator[dict[str, Any]]:
        return self.client.iter_records(self.id, fields, filter_statement, view_option)

    def create(
        self,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        return self.client.create_record(
            database_id=self.id,
            values=values,
        )

    def update(
        self,
        record_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any] | None:
        return self.client.update_record(
            database_id=self.id,
            record_id=record_id,
            values=values,
        )
