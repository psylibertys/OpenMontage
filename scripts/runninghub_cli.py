#!/usr/bin/env python3
"""RunningHub 自定义工作流 API CLI（币多多路线，2026-10 起 OpenMontage 生产通道）.

用法（详见 .agents/skills/runninghub/SKILL.md）:
  .venv/bin/python scripts/runninghub_cli.py check
  .venv/bin/python scripts/runninghub_cli.py upload <本地文件>
  .venv/bin/python scripts/runninghub_cli.py run <workflowId> --node 125.text=提示词 [--wait --out-dir DIR]
  .venv/bin/python scripts/runninghub_cli.py status <taskId>
  .venv/bin/python scripts/runninghub_cli.py download <taskId> --out-dir DIR

端点（官方文档 doc-8287469/425761093/425749004）:
  POST /task/openapi/create    {apiKey, workflowId, nodeInfoList}
  POST /task/openapi/outputs   {apiKey, taskId}
  POST /task/openapi/upload    multipart(apiKey, file)

计费警告: 真实任务按运行时长扣 RH 币（模型加载计时、排队不计时、扣费事后显示）。
本 CLI 不做成本预判 —— 创建任务前的成本确认是调用方（agent/人）的责任。
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BASE = os.environ.get("RUNNINGHUB_BASE_URL", "https://www.runninghub.cn")

# 已知 taskState 取值（不同文档版本有出入，未知值一律原样透传）:
#   常见映射 1=QUEUED 2=RUNNING 4=SUCCESS 5=FAILED; outputs 非空亦可佐证完成。
STATE_DONE = {4}
STATE_FAILED = {5, 6, 7, 8}


def load_env() -> str:
    """从项目 .env 读取 RUNNINGHUB_API_KEY（不存在时回退环境变量）。"""
    key = os.environ.get("RUNNINGHUB_API_KEY", "")
    if key:
        return key.strip()
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("RUNNINGHUB_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    if key:
                        return key
    sys.exit("错误: 未找到 RUNNINGHUB_API_KEY（.env 或环境变量）。到 runninghub.cn 账号设置生成后填入 .env。")


def _post(url: str, payload: dict, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        sys.exit(f"HTTP {exc.code} from {url}\n{body[:2000]}")
    except urllib.error.URLError as exc:
        sys.exit(f"网络错误（{url}）: {exc.reason}")


def _post_multipart(url: str, api_key: str, file_path: str, timeout: int = 300) -> dict:
    boundary = uuid.uuid4().hex
    filename = os.path.basename(file_path)
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(file_path, "rb") as fh:
        blob = fh.read()
    parts = []
    for name, value in (("apiKey", api_key),):
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
        )
    parts.append(
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode("utf-8")
        + blob
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        sys.exit(f"HTTP {exc.code} from {url}\n{exc.read().decode('utf-8', 'replace')[:2000]}")
    except urllib.error.URLError as exc:
        sys.exit(f"网络错误（{url}）: {exc.reason}")


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_nodes(node_args: list[str]) -> list[dict]:
    """把 ['125.text=你好', '31.image=a.png'] 解析为 nodeInfoList。"""
    infos = []
    for raw in node_args:
        target, _, value = raw.partition("=")
        node_id, sep, field = target.partition(".")
        if not sep or not field:
            sys.exit(f"错误: --node 格式应为 nodeId.fieldName=value，收到 {raw!r}")
        infos.append({"nodeId": node_id, "fieldName": field, "fieldValue": value})
    return infos


def task_state(resp: dict) -> int | None:
    data = resp.get("data") or {}
    state = data.get("taskState")
    return state if isinstance(state, int) else None


def fetch_outputs(api_key: str, task_id: str, base: str) -> dict:
    return _post(f"{base}/task/openapi/outputs", {"apiKey": api_key, "taskId": task_id})


def output_files(resp: dict) -> list[dict]:
    data = resp.get("data") or {}
    outs = data.get("taskOutputs")
    if isinstance(outs, list):
        return [o for o in outs if isinstance(o, dict) and o.get("fileUrl")]
    return []


def cmd_check(args: argparse.Namespace) -> None:
    """鉴权连通性检查（不创建真实任务、不花钱）: 用无效 workflowId 试探，看错误类别。"""
    api_key = load_env()
    resp = _post(
        f"{DEFAULT_BASE}/task/openapi/create",
        {"apiKey": api_key, "workflowId": "0", "nodeInfoList": []},
    )
    code = resp.get("code")
    msg = resp.get("errorMsg") or resp.get("msg") or ""
    if code == 0:
        print("异常: 无效 workflowId 竟然创建成功，请人工核对。")
        _emit(resp)
        return
    lowered = str(msg).lower()
    if "api" in lowered and ("key" in lowered or "错误" in msg or "无效" in msg):
        sys.exit(f"API key 无效: code={code} msg={msg}")
    print(f"连通 OK，API key 有效（探测响应 code={code} msg={msg} —— workflowId=0 的业务报错属预期）。")
    _emit(resp)


def cmd_upload(args: argparse.Namespace) -> None:
    api_key = load_env()
    path = args.file
    if not os.path.isfile(path):
        sys.exit(f"错误: 文件不存在 {path}")
    resp = _post_multipart(f"{DEFAULT_BASE}/task/openapi/upload", api_key, path)
    _emit(resp)
    data = resp.get("data") or {}
    if resp.get("code") == 0 and data.get("fileName"):
        print(f"\n上传成功: fileType={data.get('fileType')} fileName={data.get('fileName')}", file=sys.stderr)
        print("把上面的 fileName 填进对应 --node 的 fieldValue（LoadImage/LoadAudio 类节点）。", file=sys.stderr)


def cmd_run(args: argparse.Namespace) -> None:
    api_key = load_env()
    infos = parse_nodes(args.node or [])
    resp = _post(
        f"{DEFAULT_BASE}/task/openapi/create",
        {"apiKey": api_key, "workflowId": args.workflow_id, "nodeInfoList": infos},
    )
    _emit(resp)
    data = resp.get("data") or {}
    if resp.get("code") != 0 or not data.get("taskId"):
        sys.exit(f"\n任务创建失败: code={resp.get('code')} msg={resp.get('errorMsg') or resp.get('msg')}")
    task_id = data["taskId"]
    print(f"\ntaskId: {task_id}", file=sys.stderr)
    if not args.wait:
        print("（未 --wait；稍后用: runninghub_cli.py status/download <taskId>）", file=sys.stderr)
        return
    final = wait_task(api_key, task_id, poll=args.poll)
    files = output_files(final)
    if not files:
        sys.exit("\n任务结束但无输出文件。")
    dest = args.out_dir or os.path.join(ROOT, "outputs", "runninghub", task_id)
    download_files(files, dest)


def wait_task(api_key: str, task_id: str, poll: float = 5.0) -> dict:
    print(f"轮询中（每 {poll}s）...", file=sys.stderr)
    while True:
        resp = fetch_outputs(api_key, task_id, DEFAULT_BASE)
        state = task_state(resp)
        files = output_files(resp)
        marker = "?" if state is None else str(state)
        print(f"  taskState={marker} outputs={len(files)}", file=sys.stderr)
        if state in STATE_FAILED:
            data = resp.get("data") or {}
            reason = data.get("failedReason") or data.get("taskErrorMsg") or resp.get("errorMsg") or "未知原因"
            sys.exit(f"\n任务失败: {reason}\n完整响应:\n{json.dumps(resp, ensure_ascii=False, indent=2)}")
        if state in STATE_DONE or (files and state is not None and state >= 4):
            return resp
        time.sleep(poll)


def download_files(files: list[dict], dest: str) -> None:
    os.makedirs(dest, exist_ok=True)
    for item in files:
        url = item["fileUrl"]
        name = item.get("fileName") or os.path.basename(urllib.parse.urlparse(url).path) or "output.bin"
        target = os.path.join(dest, name)
        print(f"下载 {name} ...", file=sys.stderr)
        req = urllib.request.Request(url, headers={"User-Agent": "OpenMontage-RunningHub-CLI/1.0"})
        with urllib.request.urlopen(req, timeout=600) as resp, open(target, "wb") as fh:
            fh.write(resp.read())
        size = os.path.getsize(target)
        print(f"  -> {target} ({size} bytes) [{item.get('fileType', '?')}]", file=sys.stderr)
    print(f"\n全部输出已保存到 {dest}", file=sys.stderr)


def cmd_status(args: argparse.Namespace) -> None:
    api_key = load_env()
    resp = fetch_outputs(api_key, args.task_id, DEFAULT_BASE)
    _emit(resp)
    files = output_files(resp)
    if files:
        print(f"\n{len(files)} 个输出文件就绪（taskState={task_state(resp)}），可 download。", file=sys.stderr)


def cmd_download(args: argparse.Namespace) -> None:
    api_key = load_env()
    resp = fetch_outputs(api_key, args.task_id, DEFAULT_BASE)
    files = output_files(resp)
    if not files:
        sys.exit("当前无输出文件（任务可能仍在排队/运行，或已失败）。先 status 查看。")
    download_files(files, args.out_dir or os.path.join(ROOT, "outputs", "runninghub", args.task_id))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="鉴权连通性检查（不花钱）")

    up = sub.add_parser("upload", help="上传素材文件，返回 fileName 供 nodeInfoList 使用")
    up.add_argument("file")

    run = sub.add_parser("run", help="创建任务（真实计费！）")
    run.add_argument("workflow_id")
    run.add_argument("--node", action="append", default=[], metavar="NODEID.FIELD=VALUE",
                     help="nodeInfoList 条目，可重复，如 --node 125.text=你好")
    run.add_argument("--wait", action="store_true", help="轮询至完成并下载输出")
    run.add_argument("--poll", type=float, default=5.0, help="轮询间隔秒数（默认 5）")
    run.add_argument("--out-dir", default=None, help="输出目录（默认 outputs/runninghub/<taskId>/）")

    st = sub.add_parser("status", help="查询任务状态与输出列表")
    st.add_argument("task_id")

    dl = sub.add_parser("download", help="下载已完成任务的全部输出")
    dl.add_argument("task_id")
    dl.add_argument("--out-dir", default=None)

    args = parser.parse_args(argv)
    {"check": cmd_check, "upload": cmd_upload, "run": cmd_run,
     "status": cmd_status, "download": cmd_download}[args.cmd](args)


if __name__ == "__main__":
    main()
