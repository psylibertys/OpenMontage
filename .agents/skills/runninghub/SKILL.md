---
name: runninghub
description: Use when generating video/images/audio via RunningHub (币多多) custom ComfyUI workflow API — workflowId/nodeInfoList task creation, asset upload, polling, output download, 三条产线（舞蹈 wan_animate、图+TTS flux/krea/qwen3、H3 minimax）routing, RH币 cost gates, and API key setup.
---

# RunningHub 生产路线（币多多 · 自定义工作流 API）

OpenMontage 自 2026-10-15 起的视频/图像生产通道。AutoDL 租卡路线已退役（资料在 `archive/autodl-era/`）。通用 ComfyUI 规则（API 格式、节点选择、模型/LoRA、prompt 合同、provenance）见 `.agents/skills/comfyui/SKILL.md`，写 `nodeInfoList` 时同样适用。

## 硬规则（先于一切）

1. **付费即询问**：任务按运行时长扣 RH 币 —— 模型加载计入、排队不计、**扣费金额事后才显示**。创建任何真实任务前，向用户报预计成本并获批准；单批生产同样先批后跑。CLI 的 `check` 是唯一不花钱的调用。
2. **API key** 从 `.env` 的 `RUNNINGHUB_API_KEY` 读取（runninghub.cn → 账号设置 → API Key）。绝不写入代码、日志或提交。
3. **工作流注册只能在网页端完成**：ComfyUI 导出 API 格式 JSON → 平台粘贴 → 映射可编辑节点 → 得 `workflowId`。本仓库 `tools/_comfyui/workflows/` 的 19 个 API 模板是上传素材（要点见 `docs/pixaroma-comfyui-course-workflows.md`）。workflowId 登记后记录到下方「已注册工作流」清单。
4. **产物落地**：下载的资产放对应 `projects/<id>/assets/`，并在 run 的 `decision_log` 记一行 provenance（workflowId、nodeInfoList 摘要、taskId）。

## CLI（唯一调用通道）

```
.venv/bin/python scripts/runninghub_cli.py check                          # 鉴权（免费）
.venv/bin/python scripts/runninghub_cli.py upload <文件>                   # → fileName 填节点
.venv/bin/python scripts/runninghub_cli.py run <workflowId> \
    --node 125.text=提示词 --node 31.image=上传返回的fileName \
    --wait --out-dir <项目assets目录>                                      # 创建+轮询+下载（计费！）
.venv/bin/python scripts/runninghub_cli.py status <taskId>
.venv/bin/python scripts/runninghub_cli.py download <taskId> --out-dir DIR
```

端点：`POST /task/openapi/create`、`POST /task/openapi/outputs`、`POST /task/openapi/upload`（默认 `https://www.runninghub.cn`，可用 `RUNNINGHUB_BASE_URL` 覆盖）。

## 任务全流程

1. **准备**：确认 workflowId 已注册；把 prompt/参数整理成 `nodeId.fieldName=value` 列表。
2. **素材上传**（需要参考图/音频/视频输入时）：`upload` 拿 `fileName`（如 `xxx.png`），填进 LoadImage/LoadAudio 类节点的 `fieldValue`。若节点映射的是 string 型输入则可能要 `fileUrl` —— 以平台注册时的节点映射为准。
3. **创建**：`run` + `--node` 条目。**先报成本再执行**（见硬规则 1）。
4. **轮询**：`--wait`（默认 5s 间隔）或事后 `status`。taskState：排队/运行中→4 成功；失败时 CLI 会打印 failedReason 与完整响应。
5. **下载**：输出到项目 assets 目录；多输出（video+封面）会全部落盘。

## 三条产线路由（工作流注册清单待补）

| 产线 | 内容 | 计划工作流（tools/_comfyui/workflows/ 对应模板） | workflowId |
|------|------|----------------------------------|-----------|
| 一 · 舞蹈 | 参考图→wan_animate2 驱动人物 | wan22-i2v / wan animate 模板 | 待注册 |
| 二 · 图+TTS | flux2_klein_4ref / krea2 角色与场景 + qwen3_tts 配音 | flux2-txt2img 等 | 待注册 |
| 三 · H3 短剧 | minimax_fasth3_i2v / minimax_h3_audio_sync（自有模板上传） | 产线三自备 | 待注册 |

注册后把 workflowId 补进此表 —— 这是本路线的台账。

## 故障处理

- `803` 队列已满 → 稍后重试（排队不计时，不扣费）。
- `805` 任务失败 → 看 failedReason；修复 nodeInfoList 后重跑，不要盲重试。
- 余额不足错误码 → 提醒用户充值，不要反复尝试。
- HTTP 4xx/网络错误 → CLI 直接退出并带响应体；先 `check` 再排查。
- 扣费事后显示 → 每批结束后建议用户在网页端核对账单；对账差异即停止后续批次并报告。

## 成本纪律（与全局规则一致）

小金额试跑先行：任何新注册工作流，先用最短时长/最小分辨率参数跑 1 次验证连通与单价，拿到实际扣费后再谈批量。批量执行按批次预算走，超预算即停。
