import json
from typing import Any

import httpx

from .._validation import nonempty
from ..core.response import json_object
from ..core.transport import Transport
from ..exceptions import ResponseError
from .config import DataSyncConfig
from .request import SyncRequest


class DataSyncClient(Transport):
    """Submit asynchronous jobs using DataSyncConfig, independently of OAuth."""

    config: DataSyncConfig

    def __init__(self, config: DataSyncConfig, client: httpx.Client | None = None) -> None:
        super().__init__(config, client)

    def submit(self, request: SyncRequest) -> dict[str, Any]:
        payload = json.dumps(request.to_dict(), allow_nan=False)
        return self._post(
            f"/api/v4/sync_services/{self.config.service_id}/jobs",
            {"requestPayload": payload},
        )

    def report_error(self, message: str) -> dict[str, Any]:
        nonempty(message, "message")
        return self._post(
            f"/api/v4/sync_services/{self.config.service_id}/jobs/error",
            {"errorMessage": message},
        )

    def _post(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        response = self.check(
            self.send(
                "POST",
                path,
                headers={
                    "Authorization": f"Bearer {self.config.access_key}",
                },
                data=data,
            )
        )
        result = json_object(response)
        assert result is not None
        job = result.get("data")
        if (
            not isinstance(job, dict)
            or not isinstance(job.get("id"), str)
            or not job["id"]
            or job.get("status") not in {"enqueued", "processing", "completed", "failed"}
        ):
            raise ResponseError("Expected a sync job with id and status")
        return result
