#!/usr/bin/env python3
"""Small, guarded client for the official AutoDL Container Instance Pro API.

Supports two product lines that share one developer token:
  com  api.autodl.com   container Pro instances (/api/v1/dev/instance/pro/*)
  art  www.autodl.art   app instances deployed from the AutoDL.Art community
                        (/api/v1/adl_dev/dev/instance/pro/*)

Both gateways silently drop GET request bodies (the docs' GET-with-body
examples do not work), so GET endpoints pass parameters via query string
(verified 2026-09-03 against the art platform).  Neither platform supports
API power-on without GPU.

The script intentionally omits the irreversible release endpoint.  Power-off
requires --yes so an agent cannot stop a paid job because of a typo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


PLATFORMS = {
    "com": {
        "host": "https://api.autodl.com",
        "prefix": "/api/v1/dev/instance/pro",
    },
    "art": {
        "host": "https://www.autodl.art",
        "prefix": "/api/v1/adl_dev/dev/instance/pro",
    },
}
ENDPOINTS = {
    "list": ("POST", "/list"),
    "status": ("GET", "/status"),
    "snapshot": ("GET", "/snapshot"),
    "power-on-gpu": ("POST", "/power_on"),
    "power-off": ("POST", "/power_off"),
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


def call(command: str, body: dict, platform: str = "com") -> dict:
    _load_project_env()
    token = os.environ.get("AutoDL_token") or os.environ.get("AUTODL_TOKEN")
    if not token:
        raise SystemExit("Missing AutoDL_token (or AUTODL_TOKEN) in environment/.env")
    if platform not in PLATFORMS:
        raise SystemExit(f"Unknown platform: {platform} (choose from {', '.join(PLATFORMS)})")
    spec = PLATFORMS[platform]
    method, suffix = ENDPOINTS[command]
    url = spec["host"] + spec["prefix"] + suffix
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(body)
    else:
        data = json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=data,
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
    parser.add_argument("--platform", choices=PLATFORMS, default="com",
                        help="com=api.autodl.com Pro instances, art=www.autodl.art app instances")
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
    payload = call(args.command, body, platform=args.platform)
    print(json.dumps(payload["data"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
