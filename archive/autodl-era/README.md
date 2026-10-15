# AutoDL 时代归档（2026-10-15）

本目录归档 OpenMontage 的 **AutoDL ComfyUI 租卡生产路线** 全部资料。该路线已于 2026-10 放弃，生产转 RunningHub（币多多，自定义工作流 API）。见 `.agents/skills/runninghub/SKILL.md`。

## 内容

- `production-planning/` — AutoDL 生产规划大本营：
  - `AUTODL_*.md/.tsv/.json` — 实例运维、模型瘦身、热集验证、多来多备份、批次留存模板
  - `COMFYUI_AGENT_CONTEXT.md` — 原"source of truth"（AutoDL 连接与部署状态，已过时）
  - `COMFYUI_MODEL_INVENTORY.tsv` — AutoDL 实例模型账本
  - `GPU_ACCEPTANCE_*`、`FIRST_BATCH_*`、`REBUILD_*` — GPU 验收与首批生产记录
  - `treeelf-*-retention.json`、`treeelf-fable-series-status.json` — 批次留存决策与状态台账（生成内容）
  - `scripts/` — 11 个 autodl 实例/隧道/会话管理脚本
  - `server/openmontage_cleanup.py` — AutoDL 远端清理工具
  - `workflow-sources/`、`PRODUCTION_API_TEMPLATES.md` — 工作流来源与 19 个 API 模板说明
  - `RESEARCH_2026-10-13`、`UPGRADE_*`、`三类视频制作方法.md`、`动作素材获取与素材库建设.md` — 路线研究与方法论
- `scripts/` — GPU 验收脚本（close/run_comfyui_gpu_acceptance.py）

## 仍具参考价值（勿随路线遗忘）

- **19 个 API 格式工作流模板**（`tools/_comfyui/workflows/`，代码未归档）：上传 RunningHub 平台注册为自有工作流的核心素材；模板要点见 `docs/pixaroma-comfyui-course-workflows.md`。
- **三类视频产线设计**（产线一 舞蹈 / 产线二 图+TTS / 产线三 H3）：方法论在 `production-planning/三类视频制作方法.md`，迁移 RunningHub 后继续适用。

历史可追溯：`git log --follow archive/autodl-era/production-planning/<file>`。
