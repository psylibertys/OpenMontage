"""Authenticated, hash-verified cleanup endpoint for remote ComfyUI assets.

Deploy this file as a ComfyUI custom node. It deliberately exposes no graph
nodes. The authenticated loopback-only endpoints verify cached assets and
delete runtime assets by exact hash.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

from aiohttp import web
import folder_paths
from server import PromptServer


def _root(folder_type: str) -> Path:
    roots = {
        "input": Path(folder_paths.get_input_directory()),
        "output": Path(folder_paths.get_output_directory()),
        "temp": Path(folder_paths.get_temp_directory()),
    }
    if folder_type not in roots:
        raise ValueError("type must be input, output, or temp")
    return roots[folder_type].resolve()


def _authorize(request: web.Request) -> None:
    configured = os.environ.get("OPENMONTAGE_CLEANUP_TOKEN", "")
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not configured or not hmac.compare_digest(configured, supplied):
        raise web.HTTPUnauthorized(text="invalid cleanup token")


def _target(body: dict) -> Path:
    filename = str(body.get("filename", ""))
    subfolder = str(body.get("subfolder", ""))
    if not filename or Path(filename).name != filename:
        raise web.HTTPBadRequest(text="invalid filename")
    root = _root(str(body.get("type", "output")))
    target = (root / subfolder / filename).resolve()
    if target == root or root not in target.parents:
        raise web.HTTPBadRequest(text="path escapes managed ComfyUI root")
    return target


def _sha256(target: Path) -> str:
    digest = hashlib.sha256()
    with open(target, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@PromptServer.instance.routes.post("/openmontage/asset-status")
async def asset_status(request: web.Request) -> web.Response:
    _authorize(request)
    body = await request.json()
    target = _target(body)
    if not target.is_file():
        raise web.HTTPNotFound(text="asset does not exist")
    actual = _sha256(target)
    expected = str(body.get("sha256", "")).lower()
    return web.json_response({
        "exists": True,
        "bytes": target.stat().st_size,
        "sha256": actual,
        "matches": len(expected) == 64 and hmac.compare_digest(actual, expected),
    })


@PromptServer.instance.routes.post("/openmontage/cleanup")
async def cleanup(request: web.Request) -> web.Response:
    _authorize(request)
    body = await request.json()
    expected = str(body.get("sha256", "")).lower()
    if len(expected) != 64:
        raise web.HTTPBadRequest(text="invalid sha256")
    target = _target(body)
    if not target.is_file():
        raise web.HTTPNotFound(text="asset does not exist")
    actual = _sha256(target)
    if not hmac.compare_digest(actual, expected):
        raise web.HTTPConflict(text="sha256 mismatch; asset retained")

    size = target.stat().st_size
    target.unlink()
    return web.json_response({"deleted": True, "bytes": size, "sha256": actual})


NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
