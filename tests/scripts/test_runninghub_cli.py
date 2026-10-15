"""RunningHub 路线合约：CLI 存在、解析正确、文档路由到位（2026-10-15 转线交付）。"""

import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CLI = os.path.join(ROOT, "scripts", "runninghub_cli.py")
SKILL = os.path.join(ROOT, ".agents", "skills", "runninghub", "SKILL.md")
GUIDE = os.path.join(ROOT, "AGENT_GUIDE.md")


def test_cli_help_runs():
    result = subprocess.run([sys.executable, CLI, "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "runninghub" in result.stdout.lower()


def test_parse_nodes_handles_cjk_and_spaces():
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from runninghub_cli import parse_nodes

    infos = parse_nodes(["125.text=你好世界", "31.image=a b c.png"])
    assert infos[0] == {"nodeId": "125", "fieldName": "text", "fieldValue": "你好世界"}
    assert infos[1]["fieldValue"] == "a b c.png"
    with pytest.raises(SystemExit):
        parse_nodes(["badformat"])


def test_skill_doc_contract():
    with open(SKILL, encoding="utf-8") as fh:
        body = fh.read()
    assert "RUNNINGHUB_API_KEY" in body
    assert "workflowId" in body
    assert "付费即询问" in body


def test_guide_routes_to_runninghub_not_autodl():
    with open(GUIDE, encoding="utf-8") as fh:
        body = fh.read()
    assert ".agents/skills/runninghub/SKILL.md" in body
    assert "archive/autodl-era" in body
    # production-planning 只允许出现在归档说明行里，不得作为活跃入口
    for line in body.splitlines():
        if "production-planning" in line:
            assert "archive/autodl-era" in line, f"活跃引用残留: {line}"


def test_env_example_has_runninghub_key():
    with open(os.path.join(ROOT, ".env.example"), encoding="utf-8") as fh:
        body = fh.read()
    assert "RUNNINGHUB_API_KEY=" in body
    assert "AutoDL" not in body
