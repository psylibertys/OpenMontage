# AutoDL ComfyUI 生产 API 模板

更新：2026-07-23

> 新对话与新 Agent 必须先读取 `COMFYUI_AGENT_CONTEXT.md`；本文保留详细模板参数和验收记录。

## 套件边界

- 核心能力共 15 条：原第一批 7 条、Flux 无 LoRA 一致性 2 条、VoiceClone 2 条、InfiniteTalk 2 条、人物动作 2 条。
- 默认生图模板统一为 `krea2_low_vram`；重要封面或 hero frame 可显式选择 `krea2_extra_pass`。
- `z_image_turbo_gguf` 只作为显式备用，不再由默认路由调用。
- Nunchaku 路线已于 2026-07-23 撤销：停止下载、移除活动模板和 GPU A/B 验收，不再占用 Mac 或 AutoDL 模型空间。
- Krea LoRA 4 条属于后续付费训练阶段，本轮不执行。

## OpenMontage 调用入口

| 模板 | 工具 | 主要参数 | 输出节点 |
|---|---|---|---:|
| `z_image_turbo_gguf` | `comfyui_image` | prompt、seed、steps、aspect_preset | 171 |
| `krea2_low_vram` | `comfyui_image` | prompt、seed、steps、aspect_preset | 199 |
| `krea2_extra_pass` | `comfyui_image` | prompt、seed、steps、aspect_preset | 199 |
| `wan22_i2v_q6` | `comfyui_video` | prompt、reference_image_path、duration_seconds、aspect_preset | 122 |
| `seedvr2_upscale` | `comfyui_image` | reference_image_path、resolution | 6 |
| `qwen3_tts_custom_voice` | `comfyui_tts` | text、instruct、speaker、language、seed | 8 |
| `qwen3_tts_voice_design` | `comfyui_tts` | text、instruct、language、seed | 8 |
| `flux2_klein_4ref` | `comfyui_image` | prompt、reference_image_paths（恰好4张）、aspect_preset、megapixels | 203 |
| `flux2_klein_inpaint` | `comfyui_image` | prompt、reference_image_path、mask_image_path（白色为重绘区）、width、height | 203 |
| `qwen3_tts_voice_clone_save` | `comfyui_tts` | text、reference_audio_path、reference_text、voice_name | 8 |
| `qwen3_tts_voice_clone_load` | `comfyui_tts` | text、voice_name、language、seed | 8 |
| `wan_infinitetalk_short` | `comfyui_video` | prompt、reference_image_path、reference_audio_path、duration_seconds | 182 |
| `wan_infinitetalk_extend` | `comfyui_video` | prompt、reference_image_path、reference_audio_path、duration_seconds（仅显式选择） | 240 |
| `wan22_animate_character` | `comfyui_video` | prompt、reference_image_path、driving_video_path、duration_seconds、width、height | 56 |
| `wan_scail_character` | `comfyui_video` | prompt、reference_image_path、driving_video_path、duration_seconds、width、height | 139 |

## 文件位置

- 第一批 API 图：`tools/_comfyui/workflows/first_batch/`
- 扩展 API 图：`tools/_comfyui/workflows/production/`
- 第一批参数映射：`tools/_comfyui/first_batch.py`
- 扩展图像/视频参数映射：`tools/_comfyui/production.py`
- Qwen3-TTS 参数映射：`tools/_comfyui/tts.py`
- 图片入口：`tools/graphics/comfyui_image.py`
- 视频入口：`tools/video/comfyui_video.py`
- 配音入口：`tools/audio/comfyui_tts.py`

## 远端资产生命周期

1. Mac 通过 SSH 隧道连接 `127.0.0.1:18188`；服务器 ComfyUI 仍只监听远端 `127.0.0.1:8188`，不监听公网。
2. 输入文件上传到数据盘 `comfyui-runtime/input/`。
3. 活跃批次期间不逐条删除输入、输出或临时文件；成品下载使用本地隐藏 `.part` 文件，完成后原子改名。
4. 批次结束使用项目专属保留策略，先预览待备份/清理清单。
5. 收尾脚本把非复用远端文件备份到Mac，逐文件核对大小和SHA-256后才精确删除。
6. 队列非空、传输失败、哈希不一致或清理异常时保留远端文件，不执行关机。
7. 全部门禁通过后执行 `sync; shutdown -h now` 并确认SSH断开。

VoiceClone Save 生成的 `.qvp`、`.wav`、`.json` 三件套属于可复用角色声线，不按临时资产删除；它们保存在数据盘 `comfyui-models/qwen-tts/voices/`。GPU 验收后需通过 SCP 同步到本地角色包，再决定服务器是否保留缓存。详细录音与验收规范见 `COMFYUI_PRODUCTION_PLAN.md` 的“固定声线与声音克隆”。

## 当前验收状态

- 15/15 API-format workflow已导出并完成输出节点、参数映射和模型结构预检。
- 最终20/20验收已关闭：13条GPU实跑成功、4条静态契约验收、3条既有GPU产物验收。
- `wan_infinitetalk_extend` 的34.92秒样例已实跑成功，但模板只允许显式选择，不进入短镜头默认路由。
- 验收配置中的所有案例已禁用，默认dry-run为0条，不再执行GPU回归。
- 最终报告见 `GPU_ACCEPTANCE_FINAL_2026-07-23.md` 和同名JSON；无卡预检明细见 `CPU_PREFLIGHT_2026-07-23.md`。
