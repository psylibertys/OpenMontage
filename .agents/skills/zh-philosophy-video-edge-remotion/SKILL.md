---
name: zh-philosophy-video-edge-remotion
description: Restore and run the preserved TreeElf Chinese philosophy/psychology video workflow that produced files such as fear-being-seen-20260718_youtube_landscape_edge-zh-cn-xiaoxiaoneural.mp4. Use for the legacy 16:9 landscape chain with Edge-TTS XiaoxiaoNeural, local/free stock footage, exact Chinese text cards, captions, local music, Remotion, and FFmpeg; use when the user asks to reproduce, maintain, audit, or resume that specific pre-ComfyUI workflow without replacing the current vertical ComfyUI zh-philosophy-video skill.
---

# 中文哲思横屏 Edge + Remotion 链路

恢复并维护 2026-07-16 至 2026-07-21 批量成片使用的固定横屏链路。把本技能视为现存实现的调用契约；不要复制、重写或覆盖当前 `zh-philosophy-video` ComfyUI 竖屏技能。

## 身份与边界

- 固定入口：`scripts/zh_philosophy_video_workflow.py`
- 历史配置：`workflow_configs/zh-philosophy-video/*.json`
- 项目目录：`projects/<project_id>/`
- 默认交付：`/Users/treeelf/Movies/zh-philosophy-video/`
- 可复现样本：`workflow_configs/zh-philosophy-video/fear-being-seen-20260718.json`
- 对应成片：`fear-being-seen-20260718_youtube_landscape_edge-zh-cn-xiaoxiaoneural.mp4`

只新增项目配置和项目产物。不得修改或删除 `.agents/skills/zh-philosophy-video/`、其他技能目录、已有历史配置或已有成片。默认保留本机成片和 `projects/<project_id>/`；只有用户明确指定精确目标并再次确认后，才执行清理。

## 固定制作规格

使用 `animated-explainer` pipeline 和以下已验证路径：

1. Edge-TTS `7.2.7` 单次合成整篇旁白。
2. 固定声线 `zh-CN-XiaoxiaoNeural`，默认 `rate=+0%`、`pitch=+0Hz`、`volume=+0%`。
3. 使用同一次合成的 WordBoundary 生成短语字幕、段落时间和场景时间。
4. 先查 `~/.openmontage/clips_cache/`，不足时使用 Pexels/Pixabay，仍不足才使用本地文字卡。
5. 中文概念卡、字幕和封面文字由 PIL/Remotion 准确渲染；不要让图像模型生成中文文字。
6. 使用本地纯音乐库、Remotion 主合成和 FFmpeg 媒体准备/单帧封面拼接。
7. 默认 `profile: youtube_landscape`，输出 1920×1080、30 fps、H.264/AAC；只有用户明确要求时才使用竖屏 profile。

这条链路以 Remotion 的成片外观为身份特征。仍须遵守 `AGENT_GUIDE.md` 的 proposal 决策规则：若 Remotion 与 HyperFrames 同时可用，展示两者并说明选择 HyperFrames 会离开本恢复链路；取得用户明确选择后再锁定 runtime。

## 执行流程

### 1. 读取规则与输入

完整读取仓库根目录 `AGENT_GUIDE.md`。若文案来自 `treeElfNotes/07产出/`，同时读取 `docs/treeelf-knowledge-sources.md`。保留用户文案原文，除非用户明确要求改稿。

### 2. 运行预检

先运行仓库规定的 `provider_menu_summary()` 预检，读取 `pipeline_defs/animated-explainer.yaml`，并按当前 manifest 执行 checkpoint、review 和 human approval。确认以下本地能力：

- 项目 `.venv` 可用，并包含 `edge-tts==7.2.7`；
- `ffmpeg`、`ffprobe` 和 Remotion 可用；
- 至少一个 stock provider 可用，或用户接受文字卡 fallback；
- 音乐目录可读。

不要因 Edge-TTS 失败自动切换 DashScope、Qwen 或其他付费 TTS；不要从本链路静默切换到 ComfyUI。任何 provider、模型或 runtime 变化都先报告并等待批准。

### 3. 新建配置

以 `workflow_configs/zh-philosophy-video/fear-being-seen-20260718.json` 或最接近的历史配置为只读模板，新建不同 `project_id` 的 JSON。至少核对：

- `title`、`cover_title` / `cover_lines`；
- `profile: youtube_landscape`；
- `sections[].text`、`queries[]`、`cards[]`；
- `tts` 固定参数；
- `style`、音乐目录和 `final_output_dir`；
- `retention.cleanup_remotion_public: true`；
- `retention.cleanup_intermediate_renders: false`；
- `stock_library.enabled: true`、`min_match_score: 0.3`。

不得覆盖同名配置。目标路径已存在时停止，报告冲突并改用新的 project id 或等待用户决定。

### 4. 校验与试音

使用项目环境运行：

```bash
.venv/bin/python scripts/zh_philosophy_video_workflow.py \
  --config workflow_configs/zh-philosophy-video/<project-id>.json \
  --validate-config
```

新声线或标点敏感文案先运行：

```bash
.venv/bin/python scripts/zh_philosophy_video_workflow.py \
  --config workflow_configs/zh-philosophy-video/<project-id>.json \
  --sample-only
```

试音通过且 proposal checkpoint 获批后，才进入完整生成。

### 5. 生成与恢复

完整生成：

```bash
.venv/bin/python scripts/zh_philosophy_video_workflow.py \
  --config workflow_configs/zh-philosophy-video/<project-id>.json
```

只构建 artifacts 和资产时增加 `--no-render`。复跑时优先复用缓存与 `projects/<project_id>/artifacts/`，不要删除已有资产后从头开始。

### 6. 验收

确认以下文件及其 provenance：

```text
projects/<project_id>/artifacts/script.json
projects/<project_id>/artifacts/scene_plan.json
projects/<project_id>/artifacts/asset_manifest.json
projects/<project_id>/artifacts/edit_decisions.json
projects/<project_id>/artifacts/render_report.json
projects/<project_id>/renders/final_<profile>_<voice>_cover_music.mp4
/Users/treeelf/Movies/zh-philosophy-video/<project_id>_<profile>_<voice>.mp4
```

使用 `ffprobe` 验证视频流、音频流、1920×1080、30 fps、H.264/AAC 和合理时长；抽帧检查字幕、概念卡、封面与素材相关性；检查旁白首尾完整、背景音乐可听且不压旁白。报告最终绝对路径、TTS 参数、素材来源、fallback 数量和任何警告。

## 恢复证据

不要凭记忆改写链路。需要审计时按以下优先级取证：

1. 目标 `projects/<project_id>/artifacts/`、checkpoints、`events.jsonl`；
2. 对应 `workflow_configs/zh-philosophy-video/<project_id>.json`；
3. `scripts/zh_philosophy_video_workflow.py` 与测试 `tests/scripts/test_zh_philosophy_video_workflow.py`；
4. Git 历史和 Codex 2026-07-21 运行记录。

`fear-being-seen-20260718` 的现存 artifacts 证明该链路使用 `animated-explainer`、Remotion、templated composition、Edge-TTS XiaoxiaoNeural、stock footage、本地文字卡、字幕、音乐与单帧封面。若任何新说明与这些一手产物冲突，以一手产物和可执行实现为准，并记录差异。
