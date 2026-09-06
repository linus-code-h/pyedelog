from typing import Any

import httpx

from ..exceptions import ResponseError


def json_object(response: httpx.Response, *, allow_empty: bool = False) -> dict[str, Any] | None:
    if allow_empty and response.status_code == 204:
        return None
    try:
        result = response.json()
    except ValueError:
        raise ResponseError("Expected a JSON response") from None
    if not isinstance(result, dict):
        raise ResponseError("Expected a JSON object")
    if result.get("success") is False:
        raise ResponseError("API reported success=false in a successful HTTP response")
    return result


def record_list(response: httpx.Response) -> list[dict[str, Any]]:
    result = json_object(response)
    assert result is not None
    data = result.get("data")
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ResponseError("Expected data to contain a list of records")
    return data
