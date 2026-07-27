# ComfyUI × AutoDL Agent 运行上下文

更新：2026-07-23

这是新对话处理本项目 ComfyUI/AutoDL 任务时的唯一入口。它记录当前有效决策与运行状态，不替代代码注册表。

## 读取与验证顺序

1. 完整读取本文件；
2. 完整读取 `.agents/skills/comfyui/SKILL.md`；
3. 从代码注册表读取当前活动模板：
   - `tools/_comfyui/first_batch.py`
   - `tools/_comfyui/production.py`
   - `tools/_comfyui/tts.py`
4. 根据任务读取 `production-planning/PRODUCTION_API_TEMPLATES.md` 或 `GPU_ACCEPTANCE_CASES.json`；
5. 对远端执行只读实时检查，不能把本文的时间点状态当成永久在线状态。

若本文与代码注册表在“模板是否活动”上冲突，以代码注册表为准，并更新本文。若本文与远端实时状态冲突，以实时状态为准，并记录变化。

## 新对话执行速查

新Agent不得依赖历史聊天，按以下顺序恢复工作：

1. 读取本文件和`.agents/skills/comfyui/SKILL.md`，再读取三个Python注册表；
2. 通过只读SSH检查实例是否在线；当前普通实例不能用Pro API开机，离线时请用户在AutoDL控制台选择GPU模式开机；
3. 从项目根目录运行`production-planning/scripts/start-autodl-comfyui-session.sh`；脚本会拒绝无GPU环境、建立本地18188隧道并等待健康检查；
4. 设置`COMFYUI_SERVER_URL=http://127.0.0.1:18188`，确认`/system_stats`可用且`/queue`为空；
5. 运行`.venv/bin/python scripts/comfyui_workflow_preflight.py`，15/15通过后才开始项目生成；
6. 按本文默认路由选择模板，读取工具`input_schema`，所有成品显式写入`projects/<项目>/assets/`；视频优先传`duration_seconds`；
7. 整个批次期间不删除远端输入、输出或临时资产，相同输入依SHA-256缓存复用；
8. 批次结束前从模板创建并人工审阅该项目专属retention JSON，先用收尾脚本`--dry-run`查看精确清单；
9. 清单确认后使用`--yes --shutdown`完成Mac备份、双端哈希、精确清理和Linux关机；任一门禁失败都不得删除或关机。

默认选择速记：普通生图用`krea2_low_vram`；重点封面才用`krea2_extra_pass`；静帧动态化用`wan22_i2v_q6`；短口型用`wan_infinitetalk_short`；人物一致性先`flux2_klein_4ref`再按需`flux2_klein_inpaint`；重点图最后才用`seedvr2_upscale`。Z-Image只作显式备用，Nunchaku不得恢复，InfiniteTalk延长版不得由时长随机逻辑自动选中。

## 已批准的生产决策

- 默认生图：`krea2_low_vram`；
- 封面、Hero Frame 和少量重点图：显式选择 `krea2_extra_pass`；
- 生图备用：`z_image_turbo_gguf`，不由默认路由调用；
- Nunchaku：已撤销，模型、节点、缓存与活动模板均已清理，不得自动恢复或重新下载；
- 无 LoRA 人物一致性：`flux2_klein_4ref` 后接 `flux2_klein_inpaint`；
- 关键静帧动态化：`wan22_i2v_q6`；
- 人物口型：默认使用 `wan_infinitetalk_short`；只有明确需要长旁白并显式选择时才使用 `wan_infinitetalk_extend`；
- 写实人物动作：`wan22_animate_character`；
- 卡通/非写实人物动作：`wan_scail_character`；
- 重点图片放大：`seedvr2_upscale`；
- 正式配音：Qwen3-TTS；Edge-TTS 只作应急兜底；
- Krea LoRA 4条属于后续阶段，固定角色参考包和无 LoRA 基线通过后再讨论，不得自动发起 FAL 付费训练。

任何模型家族、付费训练、默认路由或人物表演方案的改变，都必须先获得用户批准。

## 15条活动 workflow

### 配音

| 模板 | 用途 | 关键输入 | 输出节点 |
|---|---|---|---:|
| `qwen3_tts_custom_voice` | 使用预设音色，不需要参考录音 | text、speaker、language、instruct、seed | 8 |
| `qwen3_tts_voice_design` | 用自然语言设计栏目声线，不需要参考录音 | text、language、instruct、seed | 8 |
| `qwen3_tts_voice_clone_save` | 从已授权参考录音克隆并保存声音包 | text、reference_audio_path、reference_text、voice_name | 8 |
| `qwen3_tts_voice_clone_load` | 复用已保存的固定角色声线 | text、voice_name、language、seed | 8 |

### 生图与图片处理

| 模板 | 用途 | 关键输入 | 输出节点 |
|---|---|---|---:|
| `krea2_low_vram` | 默认分镜、配图、常规主视觉 | prompt、seed、steps、aspect_preset | 199 |
| `krea2_extra_pass` | 封面和重点图增强 | prompt、seed、steps、aspect_preset | 199 |
| `z_image_turbo_gguf` | Krea 不可用时显式备用 | prompt、seed、steps、aspect_preset | 171 |
| `flux2_klein_4ref` | 四参考图无 LoRA 人物一致性 | prompt、reference_image_paths（恰好4张）、aspect_preset、megapixels | 203 |
| `flux2_klein_inpaint` | 修复脸、手、服装和身份漂移 | prompt、reference_image_path、mask_image_path、width、height | 203 |
| `seedvr2_upscale` | 重点素材放大 | reference_image_path、resolution、seed | 6 |

### 视频与人物表演

| 模板 | 用途 | 关键输入 | 输出节点 |
|---|---|---|---:|
| `wan22_i2v_q6` | 静态分镜转短动态镜头 | prompt、reference_image_path、duration_seconds、aspect_preset | 122 |
| `wan_infinitetalk_short` | 短版中文口型 | prompt、reference_image_path、reference_audio_path、duration_seconds | 182 |
| `wan_infinitetalk_extend` | 显式调用的延长口型链路 | prompt、reference_image_path、reference_audio_path、duration_seconds | 240 |
| `wan22_animate_character` | 写实人物动作迁移 | prompt、reference_image_path、driving_video_path、width、height | 56 |
| `wan_scail_character` | 卡通/非写实人物动作迁移 | prompt、reference_image_path、driving_video_path、width、height | 139 |

图片模板通过 `aspect_preset=portrait_9_16|landscape_16_9` 选择比例，不复制两套 workflow。视频横竖版按模板暴露的尺寸或比例参数调用。

## 15条 workflow 使用与参数替换契约

OpenMontage 只调用 ComfyUI HTTP API，不依赖浏览器点击。工具加载已导出的 API-format JSON，按下表替换明确开放的字段；模型加载器、VAE、文本编码器、采样器/调度器、图连接和未列出的节点参数保持固定。所有正式调用都必须显式提供 `output_path`，并写入 `projects/<项目>/assets/`。

### 配音 workflow

| workflow | 功能与使用时机 | 必填参数 | 可替换参数 | 固定/长期资产 | 输出 |
|---|---|---|---|---|---|
| `qwen3_tts_custom_voice` | 使用内置说话人快速生成正式旁白；不需要参考录音 | `text`、`workflow_template`、`output_path` | `speaker`、`language`、`instruct`、`seed`、`temperature`、`top_p`、`top_k`、`max_new_tokens` | Qwen CustomVoice模型与图连接固定 | MP3，节点`8` |
| `qwen3_tts_voice_design` | 用自然语言描述栏目声线；适合先设计主/备用声音 | `text`、`workflow_template`、`output_path` | `language`、`instruct`、`seed`、`temperature`、`top_p`、`top_k`、`max_new_tokens` | Qwen VoiceDesign模型与图连接固定 | MP3，节点`8` |
| `qwen3_tts_voice_clone_save` | 用授权参考音频克隆声线，并保存可复用声音包 | `text`、`reference_audio_path`、`reference_text`、`voice_name`、`output_path` | `language`、`seed`、`temperature`、`top_p`、`top_k`、`max_new_tokens` | `voice_name`生成的`.qvp/.wav/.json`是服务器长期资产 | MP3，节点`8`；同时保存声音包 |
| `qwen3_tts_voice_clone_load` | 后续直接复用已保存声线，不再传参考音频 | `text`、`voice_name`、`output_path` | `language`、`seed`、`temperature`、`top_p`、`top_k`、`max_new_tokens` | 对应声音包必须已在服务器`models/qwen-tts/voices/` | MP3，节点`8` |

Voice Clone 的参考音频应为10–20秒、单人、干净、无音乐/混响，`reference_text`必须与录音逐字一致。相同参考音频以SHA-256缓存名复用。

### 生图与图片处理 workflow

| workflow | 功能与使用时机 | 必填参数 | 可替换参数 | 固定参数/限制 | 输出 |
|---|---|---|---|---|---|
| `krea2_low_vram` | 默认分镜、公众号配图、普通主视觉 | `prompt`、`output_path` | `aspect_preset`或`width/height`、`seed`、`steps` | Krea模型、VAE、采样链固定；默认路由 | PNG，节点`199` |
| `krea2_extra_pass` | 封面、Hero Frame和少量重点图二次增强 | `prompt`、`output_path` | `aspect_preset`或`width/height`、`seed`、`steps` | 增强链固定；只显式选用，不作为批量默认 | PNG，节点`199` |
| `z_image_turbo_gguf` | Krea不可用时的显式备用，不自动路由 | `prompt`、`output_path` | `aspect_preset`或`width/height`、`seed`、`steps` | Z-Image Q4_K_S GGUF及采样链固定 | PNG，节点`171` |
| `flux2_klein_4ref` | 用恰好4张参考图维持无LoRA人物一致性 | `prompt`、`reference_image_paths`（恰好4张）、`output_path` | `aspect_preset`、`megapixels`、`seed`、`steps` | FLUX.2 Klein 9B KV FP8模型和四参考图接线固定 | PNG，节点`203` |
| `flux2_klein_inpaint` | 修复脸、手、服装或身份漂移 | `prompt`、`reference_image_path`、`output_path` | `mask_image_path`、`aspect_preset`或`width/height`、`seed`、`steps` | 有mask时工具先合成alpha输入；Inpaint图结构固定 | PNG，节点`203` |
| `seedvr2_upscale` | 最终重点图放大/修复，不用于所有中间图 | `reference_image_path`、`resolution`、`output_path` | `seed` | 保留源图宽高比；SeedVR2 7B模型固定 | PNG，节点`6` |

`guidance` 已按真实图结构做防误用优化：Krea、Z-Image、Flux和Wan I2V等蒸馏/加速图的实际CFG固定为1，不开放替换。内置模板调用若传入`guidance`会明确失败，不再静默忽略；只有自定义API-format workflow显式映射自己的guidance节点时才可调整。

### 视频与人物表演 workflow

| workflow | 功能与使用时机 | 必填参数 | 可替换参数 | 固定参数/限制 | 输出 |
|---|---|---|---|---|---|
| `wan22_i2v_q6` | 把关键静帧转成短动态镜头 | `prompt`、`reference_image_path`、`output_path` | `aspect_preset`或`width/height`、`seed`、`duration_seconds`或兼容字段`num_frames` | 秒数映射到1/2/3/4/5秒档；帧数档为17/33/49/65/81，两字段不得同时传 | MP4，节点`122` |
| `wan_infinitetalk_short` | 短中文口型/说话镜头 | `prompt`、`reference_image_path`、`reference_audio_path`、`output_path` | `aspect_preset`或`width/height`、`seed`、`duration_seconds`或兼容字段`num_frames` | 2段、25fps；可选约1.00/2.28/3.56/4.84/6.12秒，默认约3.56秒 | MP4，节点`182` |
| `wan_infinitetalk_extend` | 明确需要较长旁白时显式调用 | 同上 | 同上 | 12段、25fps；可选约4.20/11.88/19.56/27.24/34.92秒；默认路由绝不自动选中 | MP4，节点`240` |
| `wan22_animate_character` | 写实人物动作迁移 | `prompt`、`reference_image_path`、`driving_video_path`、`output_path` | `aspect_preset`或`width/height`、`seed`、`duration_seconds` | 16fps；未传秒数时跟随完整驱动视频；传入时只截短，超过源时长会失败，绝不自动循环；`num_frames`禁止 | MP4，节点`56` |
| `wan_scail_character` | 卡通/非写实角色动作迁移 | `prompt`、`reference_image_path`、`driving_video_path`、`output_path` | `aspect_preset`或`width/height`、`seed`、`duration_seconds` | 24fps；未传秒数时跟随完整驱动视频；传入时只截短，超过源时长会失败，绝不自动循环；`num_frames`禁止 | MP4，节点`139` |

视频模板传本地路径时，工具先按SHA-256查询服务器输入缓存；哈希一致即复用，缺失才上传。`reference_image_url`只作为图生视频的可选下载入口，生产项目优先使用已审核的本地素材。

`duration_seconds` 是正式 API 时长入口。上游可按分镜节奏随机或显式选择秒数后传入；工具负责选择最近的合法模型档位，并在 provenance 中同时记录请求秒数、选中秒数和帧数。不得为了“随机”自动切换到 `wan_infinitetalk_extend`。

### API 调用规则

1. 图片入口：`ComfyUIImage` / `tools/graphics/comfyui_image.py`；视频入口：`ComfyUIVideo` / `tools/video/comfyui_video.py`；配音入口：`ComfyUITTS` / `tools/audio/comfyui_tts.py`。
2. 调用前先读工具 `input_schema`，选择 `workflow_template` 并传入上述参数；不要直接修改模型节点。
3. 工具将参数写入 API-format JSON 后调用 `POST /prompt`，轮询 `GET /history/{prompt_id}`，再通过 `GET /view` 把最终节点产物下载到Mac。
4. `output_node` 对15条内置模板是固定值，只有外部 `workflow_json/workflow_path` 才由调用者显式提供。
5. API调用通过Mac到AutoDL的SSH隧道 `127.0.0.1:18188 -> 127.0.0.1:8188`；不得开放公网8188。
6. 活跃批次使用 `COMFYUI_REMOTE_ASSET_POLICY=retain_until_batch_end`，不逐条删除；关机前按本文件的批次资产规则备份、校验和清理。

## OpenMontage 调用入口

- 图片：`tools/graphics/comfyui_image.py`；
- 视频：`tools/video/comfyui_video.py`；
- 配音：`tools/audio/comfyui_tts.py`；
- API workflow JSON：
  - `tools/_comfyui/workflows/first_batch/`
  - `tools/_comfyui/workflows/production/`
- 参数映射：`tools/_comfyui/first_batch.py`、`production.py`、`tts.py`。

调用前必须使用工具 Schema，而不是凭记忆拼参数。自定义 workflow 必须使用 API-format JSON 并提供最终成品 `output_node`。

## AutoDL 连接

目标实例 UUID：`601e43a60f-5b558258`。

Mac 已配置专用 Ed25519 密钥和 SSH 别名：

```bash
ssh autodl-comfyui
```

不得在文档、日志或回复中输出私钥、SSH 密码或 `.env` Token。

ComfyUI 只允许监听远端回环地址：

```bash
ssh -N -L 18188:127.0.0.1:8188 autodl-comfyui
export COMFYUI_SERVER_URL=http://127.0.0.1:18188
```

不得把远端 8188 绑定到公网地址。

远端路径：

- ComfyUI：`/root/ComfyUI-Easy-Install/ComfyUI`；
- Python：`/root/ComfyUI-Easy-Install/python_embeded/bin/python3`；
- 模型：`/root/autodl-tmp/comfyui-models`；
- 输入：`/root/autodl-tmp/comfyui-runtime/input`；
- 输出：`/root/autodl-tmp/comfyui-runtime/output`；
- 临时文件：`/root/autodl-tmp/comfyui-runtime/temp`。

无卡模式启动命令带 `--cpu`；GPU 模式不带 `--cpu`。在一次 Agent 任务内应以前台、可监控的 SSH 会话承载 ComfyUI，AutoDL 可能清理普通 SSH 会话派生的后台进程。不要为了预检随意安装进程管理器。

### 下次开机与健康检查

用户先在AutoDL控制台选择GPU模式开机，随后在Mac项目根目录运行：

```bash
production-planning/scripts/start-autodl-comfyui-session.sh
export COMFYUI_SERVER_URL=http://127.0.0.1:18188
```

该脚本让远端ComfyUI作为SSH会话的前台进程运行，同时建立`18188 -> 8188`隧道并等待`/system_stats`健康检查通过。只想建立隧道时使用`open-autodl-comfyui-tunnel.sh`；停止本地会话使用`stop-autodl-comfyui-session.sh`。

### 2026-07-26 连接稳定性补丁：避免 stdout BrokenPipe

本轮 fable 30 秒测试发现：`start-autodl-comfyui-session.sh` 曾短暂返回 healthy，但随后本地 `18188` 隧道断开；Qwen3-TTS `FB_Qwen3TTSLoadSpeaker` 在打印 metadata warning 时触发 `BrokenPipeError`，原因是 ComfyUI stdout/stderr 仍绑定到已经断开的 SSH/日志管道。下次开机如果遇到以下任一现象：

- `curl http://127.0.0.1:18188/system_stats` 刚通过又立刻 connection refused；
- Qwen3-TTS 报 `BrokenPipeError`，traceback 指向 `print(...)`、`comfyui-manager/prestartup_script.py` 或 `app/logger.py`;
- 远端 `pgrep` 显示 ComfyUI 仍在，但本地隧道断开；

不要反复提交任务，也不要靠多次重试撞运气。优先按以下稳定方式处理：

1. 保留模型、声包和已生成资产，不删除 runtime output/input/temp。
2. 用远端 detached 日志重定向方式启动 ComfyUI，让 stdout/stderr 写入远端文件，而不是 SSH 会话管道：

```bash
ssh autodl-comfyui 'set -Eeuo pipefail
runtime=/root/autodl-tmp/comfyui-runtime
install=/root/ComfyUI-Easy-Install
pidfile="$runtime/logs/openmontage-comfyui-detached.pid"
mkdir -p "$runtime/input" "$runtime/output" "$runtime/temp" "$runtime/logs"
if [[ -s "$pidfile" ]]; then old=$(cat "$pidfile"); if kill -0 "$old" 2>/dev/null; then kill "$old" || true; fi; fi
cd "$install/ComfyUI"
if [[ -s "$runtime/openmontage.env" ]]; then set -a; source "$runtime/openmontage.env"; set +a; fi
nohup "$install/python_embeded/bin/python3" main.py \
  --listen 127.0.0.1 --port 8188 \
  --input-directory "$runtime/input" \
  --output-directory "$runtime/output" \
  --temp-directory "$runtime/temp" \
  > "$runtime/logs/openmontage-comfyui-detached.log" 2>&1 &
echo $! > "$pidfile"
sleep 10
tail -30 "$runtime/logs/openmontage-comfyui-detached.log"'
```

3. 再用 `production-planning/scripts/open-autodl-comfyui-tunnel.sh` 单独保持本地 `18188 -> 8188` 隧道。
4. 重新确认 `/system_stats`、`/queue` 为空和 `scripts/comfyui_workflow_preflight.py` 通过后再继续生成。

注意：不要用 `pkill -f "python.*main.py"` 这类宽匹配命令；它可能匹配并杀掉当前 SSH shell。若要停止 detached ComfyUI，优先读 `$runtime/logs/openmontage-comfyui-detached.pid` 后按 PID 精确 kill。

## AutoDL API 当前限制

2026-07-23 已验证：`.env` 中的 Token 可以访问官方 API，但 `/api/v1/dev/instance/pro/list` 返回0条，使用上述 UUID 调用 `/instance/pro/power_on` 返回 `RecordNotFoundError`。该实例当前无法通过现有 Pro API 脚本开机。

在核对实例类型、开发者 Token 所属账号或普通实例的官方开机端点之前：

- 不要反复调用 Pro 开机接口；
- 不要自行给 UUID 添加 `pro-` 前缀；
- 需要开机时请用户先在控制台操作，或者明确提供与该实例匹配的官方 API 信息。

`scripts/autodl_instance.py` 当前只实现 Pro API，不代表适用于该实例。

## 最近验证状态

时间点：2026-07-23，GPU验收与批次清理已完成，实例已关机。

- ComfyUI、Comfy CLI 和所需自定义节点已安装；
- 15/15 活动模板通过节点类型、模型枚举与输出节点结构预检；
- GPU、SeedVR2 两个加载节点和15/15活动模板已通过 GPU 预检；
- Nunchaku 节点和文件为0；
- 主要模型已在位：Krea、Z-Image GGUF、Flux 2 Klein、InfiniteTalk、Wan Animate、SCAIL；
- Qwen3-TTS 1.7B Base 已通过 Mac 代理下载并传到服务器，13/13文件远端SHA-256校验通过；数据盘剩余约70GB；
- 15/15 API-format workflow已在本地导出、可解析且输出节点存在；
- GPU验收已关闭为20/20：13条GPU实跑成功、4条Animate/SCAIL静态契约验收、3条使用既有GPU产物验收；
- 验收配置中全部案例均已显式禁用，默认dry-run活动任务为0，不会因遗漏`--resume`而误跑；
- `duration_seconds`已映射到Wan I2V、InfiniteTalk及Animate/SCAIL的真实时长机制；
- 本次ComfyUI范围的工具、参数、验收、交接与收尾脚本测试104/104通过；
- 全项目契约测试另有4项既有非ComfyUI失败（HyperFrames渲染1项、DashScope状态2项、Edge-TTS注册表预期1项），未在本任务中越界修改；
- 输入缓存已改为SHA-256稳定命名，并通过受认证的服务器端哈希接口判断复用，避免同一素材重复上传。
- 本批次远端input/output/temp已完成Mac备份和SHA-256校验后清空；模型、节点、ComfyUI和validation workflow均保留；
- `openmontage_acceptance_voice`测试声音包经试听后按用户决定只从服务器删除，Mac试听与备份保留；
- Linux `shutdown -h now`已执行，SSH断开，用户确认AutoDL控制台显示已关机。

机器可读报告：

- `projects/comfyui-gpu-acceptance-20260723/artifacts/cpu-preflight.json`；
- `projects/comfyui-gpu-acceptance-20260723/artifacts/gpu-acceptance-dry-run.json`；
- 验收配置：`production-planning/GPU_ACCEPTANCE_CASES.json`；
- 最终验收：`production-planning/GPU_ACCEPTANCE_FINAL_2026-07-23.md`及同名JSON；
- 详细无卡报告：`production-planning/CPU_PREFLIGHT_2026-07-23.md`。

## 下一步

基础设施阶段没有待跑GPU任务。下一次开机应直接进入真实项目的小批量生产；先复制并审核`AUTODL_BATCH_RETENTION_TEMPLATE.json`形成该项目专属保留策略，不得沿用其他批次的删除决定。

批次结束先预览：

```bash
.venv/bin/python scripts/finalize_autodl_comfyui_batch.py \
  --project-dir projects/<项目> \
  --policy production-planning/<项目>-retention.json \
  --dry-run
```

确认保留清单后，由Agent执行同一命令并增加`--yes --shutdown`，自动完成空队列检查、Mac备份、逐文件SHA-256校验、精确清理、审计记录和Linux关机。任何门禁失败都不会删除或关机。

## 远端资产生命周期

这是硬规则，任何工作流和新对话都不得覆盖：

1. 活跃批次期间不删除任何服务器输入、输出或临时资产；不得生一条删一次；
2. 模型、自定义节点、Qwen声音包、已批准的固定人物/参考素材包和后续会复用的输入缓存属于服务器长期资产，跨批次保留；
3. 相同输入使用内容SHA-256稳定命名，服务器已有且哈希一致时直接复用，不重复上传；
4. 每次批量任务结束后，把项目需要的非复用成品下载到 `projects/<项目>/assets/` 的隐藏 `.part` 文件，完成大小与SHA-256校验后原子改名；
5. 只有本地备份及双端哈希验证成功后，才在关机前批量删除不会复用的远端输入、输出和temp；不得删除长期资产；
6. 哈希不一致、传输失败、清理失败或队列非空时保留文件并写入待处理清单，不得关机；
7. 批次备份、校验、清理和空队列审计全部通过后，Agent主动执行 `ssh autodl-comfyui 'sync; shutdown -h now'`，以SSH断开作为Linux关机验证；任一前置门禁失败时不得关机。

### 当前实例的关机方式

当前实例 UUID `601e43a60f-5b558258` 使用以下方式关机：

```bash
ssh autodl-comfyui 'sync; shutdown -h now'
```

2026-07-23 已实测：命令执行后SSH立即断开，用户随后确认AutoDL控制台显示已关机。用户已授权后续批次在全部关机门禁通过后由Agent主动采用这一方式，不必再次要求用户点击控制台。不得用普通SSH退出、仅停止ComfyUI进程或不适用的Pro API冒充实例关机。

VoiceClone 保存的 `.qvp`、`.wav`、`.json` 默认属于服务器长期资产，不进入批量清理清单。

### 当前GPU验收批次的分类决定

当前 `comfyui-gpu-acceptance-20260723` 批次的普通测试输入、测试输出和temp不复用，完成Mac备份与SHA-256校验后删除。用户试听后确认不保留服务器端 `models/qwen-tts/voices/openmontage_acceptance_voice.{qvp,wav,json}`；3个文件已从服务器删除。Mac项目备份、生成音频和桌面试听副本仍保留。ComfyUI本体、自定义节点、模型文件和`comfyui-runtime/validation/`中的UI/API workflow属于服务器运行基础设施，必须保留。机器可读规则见 `production-planning/GPU_ACCEPTANCE_REMOTE_RETENTION.json`。

## 声音与 LoRA 阶段

- `CustomVoice`、`VoiceDesign` 不需要提前准备声音样本；
- `VoiceClone Save` 需要10–20秒干净、单人、无音乐、无混响的参考 WAV，以及逐字一致的参考文本；
- 只使用本人、明确授权或许可证允许的声音；
- 每个栏目最终批准一个主声线和一个备用声线；
- 固定人物先用四参考图与 Inpaint；只有跨大量作品仍明显漂移时才考虑 Krea LoRA。

更详细的声音录制与授权规范见 `production-planning/COMFYUI_PRODUCTION_PLAN.md`。
