#!/usr/bin/env python3
"""Back up, verify, clean, and optionally shut down an AutoDL ComfyUI batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REMOTE_RUNTIME = Path("/root/autodl-tmp/comfyui-runtime")
REMOTE_PYTHON = "/root/ComfyUI-Easy-Install/python_embeded/bin/python3"

REMOTE_MANIFEST_CODE = r"""
import hashlib, json, sys
from pathlib import Path
config = json.loads(sys.argv[1])
retain = {str(Path(value)) for value in config["retain"]}
paths = []
for value in config["roots"]:
    root = Path(value)
    if root.exists():
        paths.extend(path for path in root.rglob("*") if path.is_file() or path.is_symlink())
for value in config["extra_files"]:
    path = Path(value)
    if path.is_file() or path.is_symlink():
        paths.append(path)
rows = []
for path in sorted(set(paths), key=str):
    if str(path) in retain:
        continue
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1048576), b""):
            digest.update(chunk)
    rows.append({"path": str(path), "size": path.stat().st_size, "sha256": digest.hexdigest()})
print(json.dumps(rows))
"""

REMOTE_DELETE_CODE = r"""
import json, sys
from pathlib import Path
config = json.loads(sys.argv[1])
allowed_roots = [Path(value).resolve() for value in config["roots"]]
allowed_files = {str(Path(value)) for value in config["extra_files"]}
deleted = []
for value in config["delete_paths"]:
    path = Path(value)
    resolved = path.resolve()
    in_root = any(resolved == root or root in resolved.parents for root in allowed_roots)
    if not in_root and str(path) not in allowed_files:
        raise SystemExit(f"unsafe cleanup target: {path}")
    if path.is_file() or path.is_symlink():
        path.unlink()
        deleted.append(str(path))
print(json.dumps(deleted))
"""


def _run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, check=True, **kwargs)


def _ssh_json(host: str, code: str, payload: dict[str, Any]) -> Any:
    command = shlex.join([REMOTE_PYTHON, "-c", code, json.dumps(payload)])
    proc = _run(["ssh", host, command], capture_output=True)
    return json.loads(proc.stdout)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _backup_path(backup_root: Path, remote_path: str) -> Path:
    path = Path(remote_path)
    runtime_prefix = str(REMOTE_RUNTIME) + "/"
    if remote_path.startswith(runtime_prefix):
        return backup_root / "runtime" / remote_path.removeprefix(runtime_prefix)
    return backup_root / "extra" / path.name


def _queue(host: str) -> dict[str, Any]:
    proc = _run(
        ["ssh", host, "curl -fsS http://127.0.0.1:8188/queue"],
        capture_output=True,
    )
    return json.loads(proc.stdout)


def _require_empty_queue(host: str) -> None:
    queue = _queue(host)
    if queue.get("queue_running") or queue.get("queue_pending"):
        raise SystemExit("ComfyUI queue is not empty; refusing cleanup and shutdown")


def remote_runtime_manifest(host: str) -> list[dict[str, Any]]:
    """Return the current runtime-file manifest for an exact batch baseline."""

    return _ssh_json(
        host,
        REMOTE_MANIFEST_CODE,
        {
            "roots": [
                str(REMOTE_RUNTIME / runtime_type)
                for runtime_type in ("input", "output", "temp")
            ],
            "extra_files": [],
            "retain": [],
        },
    )


def _retention_payload(policy: dict[str, Any]) -> dict[str, Any]:
    runtime_types = policy.get("backup_then_delete_runtime_types", [])
    allowed_runtime_types = {"input", "output", "temp"}
    unknown = set(runtime_types) - allowed_runtime_types
    if unknown:
        raise ValueError(
            f"Unsupported runtime cleanup type(s): {', '.join(sorted(unknown))}"
        )
    extra_files = policy.get("backup_then_delete_voice_files", [])
    voice_root = Path("/root/autodl-tmp/comfyui-models/qwen-tts/voices")
    for value in extra_files:
        path = Path(value)
        if path.parent != voice_root or path.suffix not in {".qvp", ".wav", ".json"}:
            raise ValueError(f"Unsafe voice cleanup target: {path}")
    roots = [
        str(REMOTE_RUNTIME / value)
        for value in runtime_types
    ]
    return {
        "roots": roots,
        "extra_files": extra_files,
        "retain": policy.get("retain_project_assets", []),
    }


def _verify_local_backup(
    backup_root: Path,
    remote_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    verified = []
    for row in remote_rows:
        local = _backup_path(backup_root, row["path"])
        if not local.is_file():
            raise SystemExit(f"Missing local backup: {local}")
        local_size = local.stat().st_size
        local_sha = _sha256(local)
        if local_size != row["size"] or local_sha != row["sha256"]:
            raise SystemExit(f"Backup verification failed: {row['path']}")
        verified.append({
            **row,
            "local_path": str(local),
            "verified": True,
        })
    return verified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument(
        "--policy",
        type=Path,
        required=True,
        help="Reviewed batch-specific retention policy JSON",
    )
    parser.add_argument("--ssh-host", default="autodl-comfyui")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--shutdown", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    project_dir = args.project_dir.expanduser().resolve()
    projects_root = (PROJECT_ROOT / "projects").resolve()
    if projects_root not in project_dir.parents:
        raise SystemExit(f"Project directory must be inside {projects_root}")
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    if not (project_dir / "assets").is_dir():
        raise SystemExit(f"Project assets directory does not exist: {project_dir / 'assets'}")

    _require_empty_queue(args.ssh_host)
    payload = _retention_payload(policy)
    remote_rows = _ssh_json(args.ssh_host, REMOTE_MANIFEST_CODE, payload)
    if args.dry_run:
        print(json.dumps(remote_rows, ensure_ascii=False, indent=2))
        return 0
    if not args.yes:
        raise SystemExit("Cleanup requires --yes after reviewing --dry-run")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = project_dir / "assets" / "remote-final-backup" / stamp
    (backup_root / "runtime").mkdir(parents=True, exist_ok=True)
    (backup_root / "extra").mkdir(parents=True, exist_ok=True)

    for root in payload["roots"]:
        destination = backup_root / "runtime" / Path(root).name
        destination.mkdir(parents=True, exist_ok=True)
        _run([
            "rsync", "-a", "-e", "ssh",
            f"{args.ssh_host}:{root}/",
            f"{destination}/",
        ])
    runtime_prefix = str(REMOTE_RUNTIME) + "/"
    existing_extra_files = [
        row["path"]
        for row in remote_rows
        if not row["path"].startswith(runtime_prefix)
    ]
    for remote in existing_extra_files:
        _run([
            "rsync", "-a", "-e", "ssh",
            f"{args.ssh_host}:{remote}",
            f"{backup_root / 'extra'}/",
        ])

    verified = _verify_local_backup(backup_root, remote_rows)
    _require_empty_queue(args.ssh_host)
    delete_payload = {
        **payload,
        "delete_paths": [row["path"] for row in verified],
    }
    deleted = _ssh_json(args.ssh_host, REMOTE_DELETE_CODE, delete_payload)
    if set(deleted) != {row["path"] for row in verified}:
        raise SystemExit("Remote cleanup did not delete exactly the verified file set")
    remaining = _ssh_json(args.ssh_host, REMOTE_MANIFEST_CODE, payload)
    if remaining:
        raise SystemExit(f"Remote cleanup left {len(remaining)} non-retained file(s)")
    _require_empty_queue(args.ssh_host)

    audit = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "project_dir": str(project_dir),
        "policy": str(args.policy),
        "backup_root": str(backup_root),
        "files_verified_and_deleted": len(verified),
        "bytes_verified_and_deleted": sum(row["size"] for row in verified),
        "files": verified,
        "queue_empty": True,
        "shutdown_requested": args.shutdown,
    }
    audit_path = project_dir / "artifacts" / f"autodl-batch-finalize-{stamp}.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.shutdown:
        subprocess.run(
            ["ssh", args.ssh_host, "sync; shutdown -h now"],
            text=True,
            timeout=20,
            check=False,
        )
        for _ in range(10):
            probe = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=3", args.ssh_host, "true"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if probe.returncode != 0:
                audit["ssh_down"] = True
                audit_path.write_text(
                    json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                break
            time.sleep(2)
        else:
            raise SystemExit("Shutdown command sent, but SSH is still reachable")

    print(json.dumps({
        "audit": str(audit_path),
        "files": len(verified),
        "shutdown": bool(audit.get("ssh_down")),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
