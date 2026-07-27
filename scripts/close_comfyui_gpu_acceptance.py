#!/usr/bin/env python3
"""Close the July 2026 ComfyUI acceptance matrix without further GPU calls."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = PROJECT_ROOT / "projects" / "comfyui-gpu-acceptance-20260723"
RESULTS_PATH = PROJECT_DIR / "artifacts" / "gpu_acceptance_results.json"
CONFIG_PATH = PROJECT_ROOT / "production-planning" / "GPU_ACCEPTANCE_CASES.json"
REPORT_JSON = PROJECT_ROOT / "production-planning" / "GPU_ACCEPTANCE_FINAL_2026-07-23.json"
REPORT_MD = PROJECT_ROOT / "production-planning" / "GPU_ACCEPTANCE_FINAL_2026-07-23.md"

STATIC_CASES = {
    "animate-realistic": "wan22_animate_character",
    "scail-stylized": "wan_scail_character",
    "animate-realistic-landscape": "wan22_animate_character",
    "scail-stylized-landscape": "wan_scail_character",
}
ARCHIVED_CASES = {
    "regression-krea-low": [
        PROJECT_DIR / "assets" / "images" / "krea-default-portrait.png",
        PROJECT_DIR / "assets" / "images" / "krea-default-landscape.png",
    ],
    "regression-wan22-i2v": [
        PROJECT_DIR / "assets" / "remote-preflight-archive" / "output" / "wan-portrait_00001.mp4",
        PROJECT_DIR / "assets" / "remote-preflight-archive" / "output" / "wan-landscape_00001.mp4",
    ],
    "regression-seedvr2": [
        PROJECT_DIR / "assets" / "remote-preflight-archive" / "output" / "seed-landscape_00001_.png",
    ],
}
WORKFLOW_FILES = {
    "wan22_animate_character": (
        PROJECT_ROOT / "tools" / "_comfyui" / "workflows" / "production"
        / "wan22-animate-character.json"
    ),
    "wan_scail_character": (
        PROJECT_ROOT / "tools" / "_comfyui" / "workflows" / "production"
        / "wan-scail-character.json"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"Missing acceptance artifact: {path}")
    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    if not isinstance(results, list):
        raise SystemExit("GPU acceptance results must be a list")
    executed = []
    for record in results:
        if record.get("success") is not True:
            raise SystemExit(f"Unsuccessful GPU record cannot be closed: {record.get('id')}")
        artifacts = [artifact_record(PROJECT_ROOT / path) for path in record.get("artifacts", [])]
        if not artifacts:
            raise SystemExit(f"GPU record has no local artifact: {record.get('id')}")
        executed.append({
            "id": record["id"],
            "workflow_template": record["workflow_template"],
            "validation_mode": "gpu_executed",
            "artifacts": artifacts,
        })

    static = []
    for case_id, template in STATIC_CASES.items():
        workflow_path = WORKFLOW_FILES[template]
        static.append({
            "id": case_id,
            "workflow_template": template,
            "validation_mode": "static_contract_review",
            "workflow": artifact_record(workflow_path),
            "evidence": [
                "API-format graph parses and contains the declared output node",
                "reference image and driving video mappings are covered by contract tests",
                "prompt, seed, portrait/landscape size and driver-derived frame count are covered",
                "user explicitly waived GPU generation",
            ],
        })

    archived = []
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cases_by_id = {case["id"]: case for case in config["cases"]}
    for case_id, paths in ARCHIVED_CASES.items():
        archived.append({
            "id": case_id,
            "workflow_template": cases_by_id[case_id]["workflow_template"],
            "validation_mode": "existing_gpu_artifacts",
            "artifacts": [artifact_record(path) for path in paths],
        })

    report = {
        "project_id": config["project_id"],
        "closed_at": datetime.now(timezone.utc).isoformat(),
        "status": "closed",
        "no_further_gpu_runs_required": True,
        "counts": {
            "gpu_executed_success": len(executed),
            "static_contract_review": len(static),
            "existing_gpu_artifacts": len(archived),
            "total": len(executed) + len(static) + len(archived),
        },
        "gpu_executed": executed,
        "static_contract_review": static,
        "existing_gpu_artifacts": archived,
    }
    if report["counts"] != {
        "gpu_executed_success": 13,
        "static_contract_review": 4,
        "existing_gpu_artifacts": 3,
        "total": 20,
    }:
        raise SystemExit(f"Unexpected acceptance counts: {report['counts']}")

    REPORT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# ComfyUI GPU 验收最终报告",
        "",
        f"- 状态：已关闭",
        f"- GPU 实跑成功：{len(executed)}",
        f"- 静态契约验收：{len(static)}",
        f"- 既有 GPU 产物验收：{len(archived)}",
        f"- 合计：{report['counts']['total']}/20",
        "- 后续恢复验收不会再次提交已关闭条目。",
        "",
        "## 静态验收（用户免除 GPU 实跑）",
        "",
    ]
    lines.extend(f"- `{item['id']}`：`{item['workflow_template']}`" for item in static)
    lines.extend([
        "",
        "## 使用既有产物验收",
        "",
    ])
    lines.extend(f"- `{item['id']}`：{len(item['artifacts'])} 个本地校验产物" for item in archived)
    lines.extend([
        "",
        "完整文件大小、SHA-256 和逐条记录见 "
        "`production-planning/GPU_ACCEPTANCE_FINAL_2026-07-23.json`。",
        "",
    ])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
