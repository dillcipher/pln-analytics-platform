from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def get(path: str, params: dict[str, object] | None = None):
    query = urllib.parse.urlencode(params or {})
    url = f"{BASE}{path}" + (f"?{query}" if query else "")
    with urllib.request.urlopen(url, timeout=120) as response:
        body = response.read().decode("utf-8")
        return response.status, json.loads(body)


def main() -> int:
    checks = [
        ("suspect months", "/suspect/months", {}),
        ("suspect analytics", "/suspect/analytics", {"month": "202606"}),
        ("suspect map", "/suspect/map", {"month": "202606", "limit": 100000}),
        ("dlpd prabayar months", "/dlpd/months", {"customer_type": "prabayar"}),
        ("dlpd prabayar dashboard", "/dlpd/dashboard", {"customer_type": "prabayar", "month": "202606"}),
        ("dlpd prabayar map", "/dlpd/map", {"customer_type": "prabayar", "month": "202606", "limit": 100000}),
        ("executive kpis", "/executive/kpis", {"month": "202606"}),
        ("executive charts", "/executive/charts", {"month": "202606"}),
    ]

    failed = 0
    for name, path, params in checks:
        try:
            status, payload = get(path, params)
            print(f"[OK]   {name:<28} HTTP {status}")
        except urllib.error.HTTPError as exc:
            failed += 1
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"[FAIL] {name:<28} HTTP {exc.code}: {detail[:500]}")
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {name:<28} {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
