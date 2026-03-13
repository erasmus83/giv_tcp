#!/usr/bin/env python3
"""Container healthcheck for GivTCP.

Checks:
- REST endpoint responds with HTTP 200 and valid JSON.
- Payload contains Stats.status == "online".
- Stats.Last_Updated_Time is not older than the allowed threshold.

Configuration via environment variables:
- HEALTHCHECK_URL: endpoint to call (default: http://127.0.0.1:6345/readData)
- HEALTHCHECK_MAX_AGE_SECONDS: max age for Last_Updated_Time (default: 300)
"""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import urlopen


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def main() -> int:
    url = os.getenv("HEALTHCHECK_URL", "http://127.0.0.1:6345/readData")
    max_age_seconds = _env_int("HEALTHCHECK_MAX_AGE_SECONDS", 300)

    try:
        with urlopen(url, timeout=8) as response:
            if response.status != 200:
                print(f"unhealthy: HTTP status {response.status}")
                return 1
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except URLError as exc:
        print(f"unhealthy: request failed: {exc}")
        return 1
    except Exception as exc:
        print(f"unhealthy: invalid response: {exc}")
        return 1

    stats = payload.get("Stats")
    if not isinstance(stats, dict):
        print("unhealthy: missing Stats object")
        return 1

    status = str(stats.get("status", "")).lower()
    if status != "online":
        print(f"unhealthy: unexpected status '{status}'")
        return 1

    last_updated = stats.get("Last_Updated_Time")
    if not isinstance(last_updated, str) or not last_updated:
        print("unhealthy: missing Stats.Last_Updated_Time")
        return 1

    try:
        # Python handles timezone offsets in ISO8601 strings from GivTCP.
        updated_at = datetime.fromisoformat(last_updated)
    except ValueError as exc:
        print(f"unhealthy: invalid Last_Updated_Time '{last_updated}': {exc}")
        return 1

    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_seconds = (now - updated_at.astimezone(timezone.utc)).total_seconds()

    if age_seconds > max_age_seconds:
        print(
            "unhealthy: stale data "
            f"(age={age_seconds:.1f}s, max={max_age_seconds}s, last={last_updated})"
        )
        return 1

    print(f"healthy: status=online age={age_seconds:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
