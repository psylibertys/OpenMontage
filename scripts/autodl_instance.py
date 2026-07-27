#!/usr/bin/env python3
"""Small, guarded client for the official AutoDL Container Instance Pro API.

The script intentionally omits the irreversible release endpoint.  Power-off
requires --yes so an agent cannot stop a paid job because of a typo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


HOST = "https://api.autodl.com"
ENDPOINTS = {
    "list": ("POST", "/api/v1/dev/instance/pro/list"),
    "status": ("GET", "/api/v1/dev/instance/pro/status"),
    "snapshot": ("GET", "/api/v1/dev/instance/pro/snapshot"),
    "power-on-gpu": ("POST", "/api/v1/dev/instance/pro/power_on"),
    "power-off": ("POST", "/api/v1/dev/instance/pro/power_off"),
}


def _load_project_env() -> None:
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    try:
        lines = open(path, encoding="utf-8")
    except OSError:
        return
    with lines:
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def call(command: str, body: dict) -> dict:
    _load_project_env()
    token = os.environ.get("AutoDL_token") or os.environ.get("AUTODL_TOKEN")
    if not token:
        raise SystemExit("Missing AutoDL_token (or AUTODL_TOKEN) in environment/.env")
    method, path = ENDPOINTS[command]
    request = urllib.request.Request(
        HOST + path,
        data=json.dumps(body).encode(),
        method=method,
        headers={"Authorization": token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise SystemExit(f"AutoDL HTTP {exc.code}: {detail}") from exc
    if payload.get("code") != "Success":
        raise SystemExit(f"AutoDL API failed: {json.dumps(payload, ensure_ascii=False)}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=ENDPOINTS)
    parser.add_argument("instance_uuid", nargs="?")
    parser.add_argument("--yes", action="store_true", help="confirm power-off")
    parser.add_argument("--page-size", type=int, default=20)
    args = parser.parse_args()

    if args.command == "list":
        body = {"page_index": 1, "page_size": args.page_size}
    else:
        if not args.instance_uuid:
            parser.error(f"{args.command} requires instance_uuid")
        body = {"instance_uuid": args.instance_uuid}
        if args.command == "power-on-gpu":
            body["payload"] = "gpu"
        if args.command == "power-off" and not args.yes:
            parser.error("power-off requires --yes")
    payload = call(args.command, body)
    print(json.dumps(payload["data"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
