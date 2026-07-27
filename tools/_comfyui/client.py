"""Thin REST client for a running ComfyUI server.

Handles the full generation cycle: submit workflow, poll for completion,
download artifacts.  Used by comfyui_image, comfyui_video, and comfyui_music.
"""

from __future__ import annotations

import copy
import hashlib
import json
import mimetypes
import os
import random
import time
from pathlib import Path
from typing import Any

import requests


class ComfyUIError(Exception):
    """Raised when ComfyUI returns an error or times out."""


class ComfyUIClient:
    """Client for the ComfyUI REST API.

    The protocol is simple and battle-tested:
      1. POST /prompt           → queue a workflow, get a prompt_id
      2. GET  /history/{id}     → poll until outputs appear
      3. GET  /view?filename=…  → download the generated artifact
      4. POST /upload/image     → stage a local image for I2V workflows
    """

    def __init__(self, server_url: str | None = None) -> None:
        self.server_url = (
            server_url
            or os.environ.get("COMFYUI_SERVER_URL", "http://localhost:8188")
        ).rstrip("/")
        self.cleanup_failures: list[dict[str, Any]] = []
        self._uploaded_assets: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @property
    def is_default_url(self) -> bool:
        """True if using the fallback URL (user didn't set COMFYUI_SERVER_URL)."""
        return not os.environ.get("COMFYUI_SERVER_URL")

    def is_available(self) -> bool:
        """Return True if the ComfyUI server is reachable."""
        try:
            resp = requests.get(
                f"{self.server_url}/system_stats", timeout=5
            )
            return resp.status_code == 200
        except Exception:
            return False

    def unavailable_reason(self) -> str:
        """Human-readable explanation of why the server can't be reached."""
        if self.is_default_url:
            return (
                f"No ComfyUI server found at {self.server_url} "
                f"(default — no COMFYUI_SERVER_URL configured).\n"
                f"Set COMFYUI_SERVER_URL in your .env file to the address of "
                f"your ComfyUI server (e.g. http://localhost:8188)."
            )
        return (
            f"ComfyUI server not reachable at {self.server_url}.\n"
            f"Check that ComfyUI is running and the URL is correct."
        )

    # ------------------------------------------------------------------
    # Model discovery
    # ------------------------------------------------------------------

    def list_models(self) -> dict[str, list[str]]:
        """Query ComfyUI for available models, grouped by type.

        Returns a dict like::

            {
                "checkpoints": ["sd_xl_base.safetensors", ...],
                "diffusion_models": ["flux2-dev-nvfp4.safetensors", ...],
                "vae": ["ae.safetensors", ...],
                "clip": ["clip_l.safetensors", ...],
                "loras": ["my_lora.safetensors", ...],
            }
        """
        node_to_key = {
            "CheckpointLoaderSimple": ("ckpt_name", "checkpoints"),
            "UNETLoader": ("unet_name", "diffusion_models"),
            "VAELoader": ("vae_name", "vae"),
            "CLIPLoader": ("clip_name", "clip"),
            "LoraLoaderModelOnly": ("lora_name", "loras"),
        }
        result: dict[str, list[str]] = {}
        for node_class, (field, group) in node_to_key.items():
            try:
                resp = requests.get(
                    f"{self.server_url}/object_info/{node_class}", timeout=10
                )
                resp.raise_for_status()
                data = resp.json()
                options = (
                    data.get(node_class, {})
                    .get("input", {})
                    .get("required", {})
                    .get(field, [[]])[0]
                )
                if isinstance(options, list):
                    result[group] = options
            except Exception:
                result[group] = []
        return result

    def check_models(
        self, required: list[str]
    ) -> tuple[list[str], list[str]]:
        """Check which of *required* model filenames are available.

        ComfyUI reports models relative to their loader roots, so a model in a
        subdirectory may be returned as ``krea2/model.safetensors`` while the
        tool contract only requires ``model.safetensors``. Match either the
        normalized relative path or its basename and return the caller's
        original names in ``(found, missing)``.
        """
        all_models: set[str] = set()
        for names in self.list_models().values():
            all_models.update(str(name).replace("\\", "/") for name in names)

        basenames = {name.rsplit("/", 1)[-1] for name in all_models}

        def available(model: str) -> bool:
            normalized = model.replace("\\", "/")
            return normalized in all_models or normalized.rsplit("/", 1)[-1] in basenames

        found = [model for model in required if available(model)]
        missing = [model for model in required if not available(model)]
        return found, missing

    # ------------------------------------------------------------------
    # Core cycle
    # ------------------------------------------------------------------

    def begin_job(self) -> None:
        """Reset per-job cleanup bookkeeping on reusable tool instances."""
        self.cleanup_failures.clear()
        self._uploaded_assets.clear()

    def submit(self, workflow: dict) -> str:
        """Queue a workflow for execution.  Returns the ``prompt_id``."""
        resp = requests.post(
            f"{self.server_url}/prompt",
            json={"prompt": workflow},
            timeout=30,
        )
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if data.get("node_errors"):
            raise ComfyUIError(f"Node errors: {json.dumps(data['node_errors'])}")
        if data.get("error"):
            raise ComfyUIError(f"Prompt error: {json.dumps(data['error'])}")
        resp.raise_for_status()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"No prompt_id in response: {data}")
        return prompt_id

    def poll(
        self,
        prompt_id: str,
        *,
        timeout: int = 600,
        interval: int = 5,
    ) -> dict:
        """Block until *prompt_id* finishes.  Returns the history entry."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                resp = requests.get(
                    f"{self.server_url}/history/{prompt_id}", timeout=10
                )
            except (requests.Timeout, requests.ConnectionError):
                # A generation can temporarily saturate the same ComfyUI process
                # that serves /history.  The prompt is still running remotely, so
                # keep polling until the overall job deadline instead of causing
                # a duplicate submission on retry.
                time.sleep(interval)
                continue
            resp.raise_for_status()
            history = resp.json()
            if prompt_id in history:
                entry = history[prompt_id]
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    msgs = status.get("messages", [])
                    raise ComfyUIError(f"Execution error: {msgs}")
                return entry
            time.sleep(interval)
        raise ComfyUIError(
            f"Prompt {prompt_id} did not complete within {timeout}s"
        )

    def download(
        self,
        filename: str,
        subfolder: str,
        dest: Path,
        folder_type: str = "output",
    ) -> Path:
        """Download an output artifact from the ComfyUI server."""
        resp = requests.get(
            f"{self.server_url}/view",
            params={
                "filename": filename,
                "subfolder": subfolder,
                "type": folder_type,
            },
            timeout=120,
            stream=True,
        )
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(f".{dest.name}.part")
        digest = hashlib.sha256()
        with open(partial, "wb") as handle:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
                    digest.update(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        partial.replace(dest)
        if self._cleanup_enabled:
            self._cleanup_or_record(
                filename=filename,
                subfolder=subfolder,
                folder_type=folder_type,
                sha256=digest.hexdigest(),
                manifest_dir=dest.parent,
            )
        elif self._batch_cleanup_enabled:
            self._record_batch_cleanup(
                filename=filename,
                subfolder=subfolder,
                folder_type=folder_type,
                sha256=digest.hexdigest(),
                manifest_dir=dest.parent,
            )
        return dest

    def upload_image(self, local_path: Path, name: str) -> str:
        """Upload a local image so it can be referenced by LoadImage nodes.

        Returns the server-side filename.
        """
        return self.upload_file(local_path, name)

    def upload_file(self, local_path: Path, name: str) -> str:
        """Upload any ComfyUI input asset and track it for verified cleanup."""
        digest_obj = hashlib.sha256()
        with open(local_path, "rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest_obj.update(chunk)
        digest = digest_obj.hexdigest()
        suffix = Path(name).suffix or local_path.suffix
        server_name = f"openmontage-cache-{digest}{suffix.lower()}"
        payload = {"name": server_name, "subfolder": "", "type": "input"}
        if not self._remote_asset_matches(server_name, digest):
            mime = mimetypes.guess_type(server_name)[0] or "application/octet-stream"
            with open(local_path, "rb") as f:
                resp = requests.post(
                    f"{self.server_url}/upload/image",
                    files={"image": (server_name, f, mime)},
                    data={"type": "input", "overwrite": "true"},
                    timeout=120,
                )
            resp.raise_for_status()
            payload = resp.json()
        server_name = payload["name"]
        self._uploaded_assets.append(
            {
                "filename": server_name,
                "subfolder": payload.get("subfolder", ""),
                "folder_type": payload.get("type", "input"),
                "sha256": digest,
            }
        )
        return server_name

    def _remote_asset_matches(self, filename: str, digest: str) -> bool:
        """Return true when the authenticated remote input cache matches."""
        token = os.environ.get("COMFYUI_CLEANUP_TOKEN", "")
        if not token:
            return False
        resp = requests.post(
            f"{self.server_url}/openmontage/asset-status",
            json={
                "filename": filename,
                "subfolder": "",
                "type": "input",
                "sha256": digest,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return bool(resp.json().get("matches"))

    @property
    def _cleanup_enabled(self) -> bool:
        return os.environ.get("COMFYUI_REMOTE_ASSET_POLICY", "").lower() == (
            "delete_after_verified_download"
        )

    @property
    def _batch_cleanup_enabled(self) -> bool:
        return os.environ.get("COMFYUI_REMOTE_ASSET_POLICY", "").lower() == (
            "retain_until_batch_end"
        )

    def _record_batch_cleanup(
        self,
        *,
        filename: str,
        subfolder: str,
        folder_type: str,
        sha256: str,
        manifest_dir: Path,
        reason: str | None = None,
    ) -> None:
        """Record a verified remote runtime asset for cleanup before shutdown."""
        record = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type,
            "sha256": sha256,
            "server_url": self.server_url,
        }
        if reason:
            record["reason"] = reason
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest = manifest_dir / ".comfyui-cleanup-retained.jsonl"
        with open(manifest, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _cleanup_or_record(
        self,
        *,
        filename: str,
        subfolder: str,
        folder_type: str,
        sha256: str,
        manifest_dir: Path,
    ) -> bool:
        payload = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type,
            "sha256": sha256,
        }
        token = os.environ.get("COMFYUI_CLEANUP_TOKEN", "")
        try:
            if not token:
                raise ComfyUIError("COMFYUI_CLEANUP_TOKEN is not configured")
            resp = requests.post(
                f"{self.server_url}/openmontage/cleanup",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            failure = {**payload, "error": str(exc), "server_url": self.server_url}
            self.cleanup_failures.append(failure)
            manifest_dir.mkdir(parents=True, exist_ok=True)
            with open(manifest_dir / ".comfyui-cleanup-pending.jsonl", "a", encoding="utf-8") as handle:
                handle.write(json.dumps(failure, ensure_ascii=False) + "\n")
            return False

    def cleanup_uploaded_assets(self, manifest_dir: Path) -> None:
        """Delete inputs only after their bytes were accepted by a completed job."""
        if self._batch_cleanup_enabled:
            pending, self._uploaded_assets = self._uploaded_assets, []
            for item in pending:
                self._record_batch_cleanup(manifest_dir=manifest_dir, **item)
            return
        if not self._cleanup_enabled:
            self._uploaded_assets.clear()
            return
        pending, self._uploaded_assets = self._uploaded_assets, []
        for item in pending:
            self._cleanup_or_record(manifest_dir=manifest_dir, **item)

    def record_pending_upload_cleanup(self, manifest_dir: Path, reason: str) -> None:
        """Record uploaded inputs after a failed/uncertain job without deleting them."""
        if not self._uploaded_assets:
            return
        if self._batch_cleanup_enabled:
            pending, self._uploaded_assets = self._uploaded_assets, []
            for item in pending:
                self._record_batch_cleanup(
                    manifest_dir=manifest_dir, reason=reason, **item
                )
            return
        manifest_dir.mkdir(parents=True, exist_ok=True)
        with open(manifest_dir / ".comfyui-cleanup-pending.jsonl", "a", encoding="utf-8") as handle:
            for item in self._uploaded_assets:
                failure = {
                    **item,
                    "error": reason,
                    "server_url": self.server_url,
                    "retained_intentionally": True,
                }
                self.cleanup_failures.append(failure)
                handle.write(json.dumps(failure, ensure_ascii=False) + "\n")
        self._uploaded_assets.clear()

    # ------------------------------------------------------------------
    # High-level helper
    # ------------------------------------------------------------------

    def generate(
        self,
        workflow: dict,
        output_node: str,
        dest: Path,
        *,
        timeout: int = 600,
        interval: int = 5,
    ) -> list[Path]:
        """Submit → poll → download.  Returns list of artifact paths."""
        prompt_id = self.submit(workflow)
        entry = self.poll(prompt_id, timeout=timeout, interval=interval)

        outputs = entry.get("outputs", {})
        node_output = outputs.get(output_node, {})

        # ComfyUI stores images and videos under the "images" key
        items = (
            node_output.get("images", [])
            or node_output.get("gifs", [])
            or node_output.get("audio", [])
        )
        if not items:
            raise ComfyUIError(
                f"No output artifacts on node {output_node}. "
                f"Available nodes: {list(outputs.keys())}"
            )

        paths: list[Path] = []
        for i, item in enumerate(items):
            suffix = Path(item["filename"]).suffix
            if len(items) == 1:
                target = dest
            else:
                target = dest.with_stem(f"{dest.stem}_{i:03d}").with_suffix(suffix)
            self.download(
                item["filename"],
                item.get("subfolder", ""),
                target,
                item.get("type", "output"),
            )
            paths.append(target)
        self.cleanup_uploaded_assets(dest.parent)
        return paths

    # ------------------------------------------------------------------
    # Workflow helpers
    # ------------------------------------------------------------------

    @staticmethod
    def load_workflow(path: Path) -> dict:
        """Load a workflow JSON template from disk."""
        with open(path) as f:
            return json.load(f)

    @staticmethod
    def patch_workflow(
        workflow: dict, patches: dict[str, dict[str, Any]]
    ) -> dict:
        """Deep-copy *workflow* and apply *patches*.

        *patches* maps ``node_id`` → ``{input_name: value, ...}``.
        """
        w = copy.deepcopy(workflow)
        for node_id, values in patches.items():
            if node_id not in w:
                raise ComfyUIError(
                    f"Node {node_id!r} not found in workflow. "
                    f"Available: {list(w.keys())}"
                )
            for key, val in values.items():
                w[node_id]["inputs"][key] = val
        return w

    @staticmethod
    def random_seed() -> int:
        """Return a random seed suitable for ComfyUI noise nodes."""
        return random.randint(0, 2**32 - 1)
