---
name: comfyui
description: Use when working with ComfyUI workflows in OpenMontage, including comfyui_image/comfyui_video, custom workflow_json/workflow_path inputs, output_node selection, missing model setup, LoRAs, low-VRAM workflow choices, and community workflow imports.
---

# ComfyUI Workflows in OpenMontage

Use this skill before calling `comfyui_image` or `comfyui_video`, and when converting a community ComfyUI workflow into an OpenMontage tool call.

## Project Deployment Context

**2026-10-15 路线变更**：AutoDL 租卡路线已废弃（资料归档于 `archive/autodl-era/`，原 `production-planning/COMFYUI_AGENT_CONTEXT.md` 已过时）。生成任务统一走 RunningHub 自定义工作流 API — 先读 `.agents/skills/runninghub/SKILL.md`。本 skill 保留的是通用 ComfyUI 规则：API 格式、节点选择、模型/LoRA、prompt 合同、provenance — 写 RunningHub `nodeInfoList`（本质就是 API 格式节点参数替换）时同样适用。

## Server Contract

- ComfyUI must be running before the tool can generate. The default server is `http://localhost:8188`; override it with `COMFYUI_SERVER_URL`.
- Health and hardware status come from `GET /system_stats`.
- Jobs are submitted to `POST /prompt`, completed outputs are read from `GET /history/{prompt_id}`, and artifact bytes are downloaded with `GET /view`.
- Export workflows with ComfyUI's API-format JSON, not the UI layout format. If a downloaded workflow will not submit, re-export it from ComfyUI with API format enabled.

## MCP Tools (comfy-mcp) Available in This Project

The `comfy` MCP server (official Comfy-Org/comfy-mcp, 39 tools) is registered in the project `.mcp.json` and targets the **local Mac ComfyUI at `127.0.0.1:8188`**（探索、一次性任务、小规模运行用）. Full access is granted (user-approved 2026-10-14): introspection (`server_info`, `nodes`, `search_models`), validation (`validate_workflow`, `node_dependencies`), AND generation (`run_workflow`, `generate_image`, `job`, `fetch_outputs`, `upload_file`) plus workflow editing (`set_workflow_slot`, `vary_workflow`).

Guardrails: paid cloud actions (`partner_generate`/`auth_login`) ask first; MCP lifecycle tools act on the local Mac only — no remote instance is managed anymore. Assets produced via MCP that a project uses must land in `projects/<id>/assets/` with a one-line provenance note in `decision_log`. 正式生产走 RunningHub（见 `.agents/skills/runninghub/SKILL.md`），MCP 不承担批次生产。

## Archived: AutoDL Era (2026-10-15)

原 "AutoDL SSH Reliability Contract" 与 "TreeElf fable continuous batch contract" 两节已随 AutoDL 路线整体归档至 `archive/autodl-era/`（README 有索引；`git log --follow` 可追溯）。SSH 隧道、18188 端口、GPU 开关机流程不再适用。

## Choosing a Workflow

- Use bundled workflows when the requested operation matches and the local machine has the required models and VRAM.
- Use a custom `workflow_json` or `workflow_path` when the user needs a community recipe, a lower-VRAM model, a different style family, or custom nodes.
- For 8GB-12GB GPUs, prefer lower-footprint workflows such as Wan 2.1 1.3B, LTXV FP8 or quantized workflows, or Wan 2.2 GGUF/quantized community workflows. The bundled Wan 2.2 14B FP8 video workflows are a 16GB-class path, not a provider-wide floor.
- Do not promise that arbitrary custom workflows will fit a machine. The workflow, quantization, resolution, frame count, and offload settings determine the real resource envelope.

## Output Node Contract

- Custom workflows must pass `output_node`.
- Pick the node that writes the artifact, usually `SaveImage`, `SaveVideo`, `VHS_VideoCombine`, or another terminal saver node.
- Pass the node ID as a string, for example `"108"`. Do not pass the class name.
- If a workflow has multiple savers, choose the final deliverable node, not previews or intermediates.

## Templated vs Fixed Nodes

- Identify templated nodes before execution: prompt text, seed, dimensions, frame count, source image, sampler settings, and output filename prefix.
- Fixed nodes are model loaders, VAEs, text encoders, LoRA loaders, schedulers, and graph wiring. Do not mutate those unless the workflow author intended that customization.
- For community workflows, inspect each loader node and note every required model or custom node before running. Missing models should be handled through the tool's structured `missing_models` payload when available.

## Prompt and Character Reference Contract

- Review the final compiled prompt sent to ComfyUI, not only the author's base prompt. A pipeline may append identity, camera or guardrail text that contradicts the intended scene. Persist a compiled-prompt report before paid generation when prompts are assembled by code.
- Declare whether a scene is human-led or human-free before compilation. Append protagonist identity and human camera language only to human-led scenes; environment, object and macro scenes must keep their own subject contract.
- Four independent text-to-image calls do not constitute a consistent four-reference character pack. Generate one coherent turnaround/contact sheet containing distinct views of the same identity, then crop those views, or use an actual identity-preserving reference workflow.
- Never duplicate one image into four files to satisfy a four-reference input. The four references must depict the same identity from genuinely different useful views.
- Prompts for generated artwork should describe visible content. Keep typography, titles, brand names and editorial-layout instructions out of the image-generation prompt when text will be added downstream; retain explicit technical text/logo/watermark guardrails and verify the downloaded image before packaging.

## Model and LoRA Setup

- Use ComfyUI Manager or the workflow author's model links when available, and respect model licenses.
- Place models in the folders expected by the loader nodes: diffusion models under `ComfyUI/models/diffusion_models/`, text encoders under `ComfyUI/models/text_encoders/`, VAEs under `ComfyUI/models/vae/`, and LoRAs under `ComfyUI/models/loras/`.
- For LoRA stacks, use `LoraLoader` or `LoraLoaderModelOnly` chains in the workflow. Record each LoRA name plus `strength_model` and `strength_clip` when applicable.
- The current ComfyUI tools do not inject LoRAs into arbitrary graphs. To use LoRAs, provide a workflow that already contains the LoRA loader chain and pass model-stack provenance.

## Provenance

- For custom workflows, provide `workflow_name` and `workflow_model` when known.
- Provide `workflow_model_stack` for reproducibility when the workflow is not bundled. Include base checkpoint or diffusion model, quantization, text encoder, VAE, LoRAs and strengths, sampler or scheduler, steps, and guidance if the workflow exposes them.
- The tools record the final workflow hash. Treat that hash plus the model stack, seed, dimensions, and prompt as the reproducibility contract.

## Failure Handling

- If the server is unavailable, surface the structured setup offer. Starting ComfyUI or setting `COMFYUI_SERVER_URL` is the first fix.
- If models are missing, read `data.missing_models[]`; each item should include the file name, role, destination hint, and download URL when OpenMontage knows it.
- If custom nodes are missing, ask the user to install them through ComfyUI Manager or the workflow author's documented install path, then restart ComfyUI.
- If a long render times out locally, check ComfyUI history before retrying from scratch; the server may still have completed the prompt.
