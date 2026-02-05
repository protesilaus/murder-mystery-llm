"""HTTP client utilities."""

from __future__ import annotations

import json
from typing import Any, Dict
from urllib.error import URLError
from urllib.request import Request, urlopen


def post_json(
    url: str, payload: Dict[str, Any], *, timeout: int = 30
) -> Dict[str, Any]:
    """POST JSON data to a URL and return the JSON response.

    Args:
        url: The URL to POST to.
        payload: The JSON-serializable payload.
        timeout: Request timeout in seconds.

    Returns:
        The parsed JSON response.

    Raises:
        RuntimeError: If the request fails.
    """
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"HTTP request failed: {exc}") from exc
