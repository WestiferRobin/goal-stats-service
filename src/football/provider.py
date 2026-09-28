"""Optional API-Football access; secrets stay on the server."""

import json
import os
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def api_get(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    key = os.environ.get("API_FOOTBALL_KEY")
    if not key:
        return None
    request = Request(
        "https://v3.football.api-sports.io" + endpoint + "?" + urlencode(params or {}),
        headers={"x-apisports-key": key},
    )
    try:
        with urlopen(request, timeout=5) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            return None
        data = json.loads(raw)
        if (
            not isinstance(data, dict)
            or data.get("errors")
            or not isinstance(data.get("response"), list)
        ):
            return None
        return data
    except (URLError, TimeoutError, OSError, ValueError):
        return None
