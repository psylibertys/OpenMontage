# 心哲灵 12 篇 GPU 连续生产运行单

状态：两个 6 篇批次均已 `validate`、`gpu-plan`、`prepare`。原文已快照，原文完成状态未修改。

## 开机后第一步

用户在 AutoDL 控制台选择 GPU 模式开机后，从 OpenMontage 根目录执行：

```bash
production-planning/scripts/ensure-autodl-comfyui-remote.sh
```

随后用一个受控隧道连续执行两个批次，避免批次之间等待人工核验：

```bash
production-planning/scripts/with-autodl-comfyui-tunnel.sh -- \
  zsh -lc '.venv/bin/python scripts/treeelf_philosophy_batch.py generate-gpu --config workflow_configs/zh-philosophy-video/batches/20260728-twelve/batch-a.json && .venv/bin/python scripts/treeelf_philosophy_batch.py generate-gpu --config workflow_configs/zh-philosophy-video/batches/20260728-twelve/batch-b.json'
```

脚本会在每个批次开始时要求 GPU 存在、`/system_stats` 连续健康、队列为空、15/15 工作流通过，并冻结该批次远端基线。模型组顺序固定为：

1. Qwen3-TTS VoiceClone Load；
2. Krea 2 Low VRAM；
3. Wan 2.2 I2V Q6。

## GPU 资产生成完成后

先对 B 批次执行 dry-run 和无关机收尾，再对 A 批次执行 dry-run，并在最终门禁通过后关机。这样 B 的基线会保留 A 已生成的远端文件，最后由 A 的收尾统一处理剩余文件。

```bash
.venv/bin/python scripts/treeelf_philosophy_batch.py finalize-gpu \
  --config workflow_configs/zh-philosophy-video/batches/20260728-twelve/batch-b.json --dry-run

.venv/bin/python scripts/treeelf_philosophy_batch.py finalize-gpu \
  --config workflow_configs/zh-philosophy-video/batches/20260728-twelve/batch-b.json --yes

.venv/bin/python scripts/treeelf_philosophy_batch.py finalize-gpu \
  --config workflow_configs/zh-philosophy-video/batches/20260728-twelve/batch-a.json --dry-run

.venv/bin/python scripts/treeelf_philosophy_batch.py finalize-gpu \
  --config workflow_configs/zh-philosophy-video/batches/20260728-twelve/batch-a.json --yes --shutdown
```

任何队列非空、下载失败、大小或 SHA-256 不一致、清理失败都会阻止关机。模型、自定义节点、验证工作流和 `treeelf_voice02_v1` 声音包必须保留。

## 关机后

按批次运行 `stage-local`，完成 Whisper、精确字幕、音乐选择、Remotion 合成、联系表与音频 QC。只有最终成片复制到 Movies 且 SHA-256 一致后，才由 `deliver` 更新源 Markdown 的 `production_status: completed`。
