#!/usr/bin/env python3
"""模型↔工作流占用计算器：任意模板组合 / 产线预设，秒算实例模型体积。

用法（在 OpenMontage 根目录）:
  python3 tools/_comfyui/model_footprint.py dance-step1        # 产线预设
  python3 tools/_comfyui/model_footprint.py flux2-klein-4ref wan_animate2   # 任意模板组合
  python3 tools/_comfyui/model_footprint.py --list             # 列全部预设与可用模板

数据源：production-planning/COMFYUI_MODEL_INVENTORY.tsv（账本，开机会话后校准字节数）
模板源：tools/_comfyui/workflows/production/*.json + projects/dance-video-20261013/wan_animate2_template.json
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "archive" / "autodl-era" / "production-planning" / "COMFYUI_MODEL_INVENTORY.tsv"
TEMPLATE_DIRS = [ROOT / "tools/_comfyui/workflows/production", ROOT / "projects/dance-video-20261013"]

# 产线预设（模板 key 的并集）
PRESETS = {
    "dance-step1": ["flux2-klein-4ref", "krea2-outfit-transfer", "wan_animate2"],
    "dance-full": ["flux2-klein-4ref", "flux2-klein-outpaint", "krea2-outfit-transfer", "wan_animate2"],
    "drama-step1": ["flux2-klein-4ref", "krea2-low-vram", "qwen3-tts-custom-voice"],
    "dance-plus-drama1": ["flux2-klein-4ref", "krea2-low-vram", "qwen3-tts-custom-voice", "wan_animate2"],
    "drama-full": ["flux2-klein-4ref", "krea2-low-vram", "qwen3-tts-custom-voice", "minimax-fasth3-i2v", "minimax-h3-audio-sync"],
    "drama-step2-h3": ["minimax-fasth3-i2v", "minimax-h3-audio-sync"],
    "h3-family": ["minimax-fasth3-t2v", "minimax-fasth3-i2v", "minimax-fasth3-fflf", "minimax-h3-audio-sync"],
    "fallback-a": ["wan22-animate-character"],
    "scail": ["wan-scail-character"],
    "infinitetalk": ["wan-infinitetalk-extend"],
}

GIB = 1024 ** 3


def load_inventory():
    """返回 {文件名: (bytes, duolaiduo_path, instance_status, [模板])}。"""
    inv = {}
    for line in INVENTORY.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        name, size, path, status, templates = parts[:5]
        inv[name] = (int(size), path, status, [t for t in templates.split(",") if t])
    return inv


def discover_templates():
    """扫描模板 json，返回 {模板key: 引用文件名集合}。"""
    found = {}
    for d in TEMPLATE_DIRS:
        if not d.is_dir():
            continue
        for fp in sorted(d.glob("*.json")):
            if fp.name == "wan_animate2_template.json":
                key = "wan_animate2"
            else:
                key = fp.stem
            try:
                data = json.loads(fp.read_text())
            except json.JSONDecodeError:
                continue
            refs = set()

            def walk(o):
                if isinstance(o, dict):
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for i in o:
                        walk(i)
                elif isinstance(o, str):
                    for m in re.findall(r"[\w\-./\\]+\.(?:safetensors|gguf|pth)\b", o, re.I):
                        refs.add(m.replace("\\", "/").split("/")[-1])

            walk(data)
            found[key] = refs
    return found


def main(argv):
    inv = load_inventory()
    templates = discover_templates()

    if not argv or argv[0] == "--list":
        print("产线预设:")
        for k, v in PRESETS.items():
            print(f"  {k:16s} = {'+'.join(v)}")
        print("\n可用模板 key:", ", ".join(sorted(templates)))
        return

    keys = []
    for a in argv:  # 每个参数都先查预设再当模板 key，预设与模板可混用组合
        keys.extend(PRESETS.get(a, [a]))
    # 有效 key = json 发现的模板 ∪ 账本模板列声明（覆盖无静态引用的 TTS/注册表内生成模板）
    declared = {t for _, (_, _, _, ts) in inv.items() for t in ts}
    wanted, unknown_keys, unbilled = set(), [], set()
    for k in keys:
        if k in templates:
            wanted |= templates[k]
            unbilled |= {r for r in templates[k] if r not in inv}
        elif k not in declared:
            unknown_keys.append(k)
    for name, (_, _, _, ts) in inv.items():  # 账本反向声明（TTS 包、krea2-low-vram 等）
        if set(ts) & set(keys):
            wanted.add(name)

    # on=在实例 / off=冷存（启用需下回）→ 计入合计；unknown/alt → 不计入，单列待核
    counted, parked, total, unknown_bytes = [], [], 0, False
    for name in sorted(wanted):
        if name not in inv:
            continue
        size, path, status, _ = inv[name]
        (counted if status in ("on", "off") else parked).append((name, size, status))
        if size == 0:
            unknown_bytes = True
        elif status in ("on", "off"):
            total += size

    print(f"组合: {' + '.join(keys)}")
    print(f"{'文件':<64s} {'GiB':>7s}  实例")
    for name, size, status in counted:
        sz = f"{size / GIB:.2f}" if size else "?"
        print(f"{name:<64s} {sz:>7s}  {status}")
    tag = "≥" if unknown_bytes else ""
    print(f"\n合计: {tag}{total / GIB:.1f} GiB（{len(counted)} 件，共享件已去重）")
    if parked:
        print(f"未计入（备选/待核件）: {', '.join(n for n, _, _ in parked)}")
    if unbilled:
        print(f"警告: 模板引用但账本缺行: {', '.join(sorted(unbilled))} —— 请补 COMFYUI_MODEL_INVENTORY.tsv")
    if unknown_keys:
        print(f"警告: 未知模板 key: {', '.join(unknown_keys)}（--list 查看可用项）")


if __name__ == "__main__":
    main(sys.argv[1:])
