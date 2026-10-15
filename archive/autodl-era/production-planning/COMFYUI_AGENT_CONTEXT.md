# ComfyUI × AutoDL Agent 运行上下文

更新：2026-10-12

这是新对话处理本项目 ComfyUI/AutoDL 任务时的唯一入口。它记录当前有效决策与运行状态，不替代代码注册表。

## 读取与验证顺序

1. 完整读取本文件；
2. 完整读取 `.agents/skills/comfyui/SKILL.md`；
3. 从代码注册表读取当前活动模板：
   - `tools/_comfyui/first_batch.py`
   - `tools/_comfyui/production.py`
   - `tools/_comfyui/tts.py`
4. 根据任务读取 `production-planning/PRODUCTION_API_TEMPLATES.md` 或 `GPU_ACCEPTANCE_CASES.json`；
5. **按需路由，不得常规加载**：只有用户明确选择Z-Image、SeedVR2、Wan Animate或SCAIL，准备恢复这些冷模型，或正在排查这4条模板的缺模型问题时，才完整读取`production-planning/AUTODL_MODEL_SLIMMING_2026-08-07.md`；普通Krea生图、Qwen3-TTS、Flux人物一致性、Wan 2.2 I2V和InfiniteTalk任务不得加载该文档；
6. 只有实例重建、存储规划、模型迁移或缺模型恢复任务才读取`production-planning/AUTODL_REBUILD_STORAGE_PLAN_2026-08-13.md`；普通生成任务不得加载；
7. 若上述重建/迁移任务仍在进行，再读取`production-planning/AUTODL_REBUILD_LIVE_STATE_2026-08-13.json`，先接管既有PID和状态文件，禁止重复启动传输；普通生成任务不得加载；
8. 对远端执行只读实时检查，不能把本文的时间点状态当成永久在线状态。

若本文与代码注册表在“模板是否活动”上冲突，以代码注册表为准，并更新本文。若本文与远端实时状态冲突，以实时状态为准，并记录变化。

## 新对话执行速查

新Agent不得依赖历史聊天，按以下顺序恢复工作：

> **⚠️ 平台状态（2026-10-15）：用户已放弃 AutoDL。** 下方第 2-9 条的开机/隧道/关机流程全部转为历史参考——不要再连 `autodl-comfyui`、不要规划 AutoDL 开机或删除。生产将来转本地或新平台（待定）；本文的模板路由、模型账本、工作流清单继续有效。模型底座 = duolaiduo 权威备份。

1. 读取本文件和`.agents/skills/comfyui/SKILL.md`，再读取三个Python注册表；
2. 通过只读SSH检查实例是否在线；当前普通实例不能用Pro API开机，离线时请用户在AutoDL控制台选择GPU模式开机；
3. 从项目根目录运行`production-planning/scripts/start-autodl-comfyui-session.sh`；脚本会拒绝无GPU环境、以远端 detached 日志方式启动 ComfyUI、建立本地18188隧道并做连续健康检查；自动化生成优先使用`production-planning/scripts/with-autodl-comfyui-tunnel.sh -- <command>`，让隧道与生成命令共享同一生命周期；
4. 设置`COMFYUI_SERVER_URL=http://127.0.0.1:18188`，确认`/system_stats`可用且`/queue`为空；
5. 运行`.venv/bin/python scripts/comfyui_workflow_preflight.py`，19 条模板通过后才开始项目生成（无卡 CPU 模式下 FastH3 三条会因 GPU attention 后端缺枚举显示 WAIT，属环境差异，以 GPU 模式验收为准）；
6. 按本文默认路由选择模板，读取工具`input_schema`，所有成品显式写入`projects/<项目>/assets/`；视频优先传`duration_seconds`；
7. 整个批次期间不删除远端输入、输出或临时资产，相同输入依SHA-256缓存复用；
8. 批次结束前从模板创建并人工审阅该项目专属retention JSON，先用收尾脚本`--dry-run`查看精确清单；
9. 清单确认后使用`--yes --shutdown`校验项目 `assets/` 清单、精确清理和Linux关机；不创建独立 `remote-final-backup`，任一门禁失败都不得删除或关机。
10. 问"某产线/模板组合要多少 G 模型"时，用账本速算：`python3 tools/_comfyui/model_footprint.py <预设或模板key>`（预设含 dance-step1/drama-step1/h3-family 等，`--list` 查全部；数据源 `production-planning/COMFYUI_MODEL_INVENTORY.tsv`，共享件自动去重、备选件不计入；开机会话后用实例 ls 校准账本的 unknown/alt 行）。

默认选择速记（2026-10-12 换代落地完成）：普通生图用`krea2_low_vram`；重点封面才用`krea2_extra_pass`；文生视频用`minimax_fasth3_t2v`；静帧动态化用`minimax_fasth3_i2v`（原生音频）；首尾帧转场用`minimax_fasth3_fflf`；短口型（≤15s）用`minimax_h3_audio_sync`；画幅扩图用`flux2_klein_outpaint`；人物一致性用`flux2_klein_4ref`；图像编辑/修复用`krea2_edit_lora`；同角色换装用`krea2_outfit_transfer`（2026-10-12 晚落地，preflight OK，GPU smoke 留待下次开机）。`wan22_i2v_q6`、`wan_infinitetalk_short`、`flux2_klein_inpaint` 三条旧链路已于 2026-10-12 从代码注册表删除，不得再引用。冷模型模板（z_image/scail/infinitetalk_extend）提交前仍必须先恢复；Nunchaku不得恢复，InfiniteTalk延长版不得由时长随机逻辑自动选中。

## 已批准的生产决策

- **平台：AutoDL 已放弃（2026-10-15 用户决定，原话"我已经放弃autoDL了"）**——不再租用 AutoDL GPU 生产，将来转本地或其它平台（待定）。下列路由决策在**工作流层面**继续有效（模板、模型清单、管线分工不变），但所有"实例在位 / 下次开机"表述转为历史。模型底座 = duolaiduo 权威备份（`AUTODL_DUOLAIDUO_MODEL_BACKUP_2026-10-14.tsv` + 暖库 153 文件）；三产线工作流清单见 `docs/pixaroma-comfyui-course-workflows.md` 尾部。2026-10-15 批准的约 100G 删除任务随之取消（整平台弃用后逐件删除无意义）；
- 默认生图：`krea2_low_vram`（2026-10-09 课程 Ep24/36 复核：文生图 Krea 2 仍是首选，不变）；
- 封面、Hero Frame 和少量重点图：显式选择 `krea2_extra_pass`；
- 生图备用：`z_image_turbo_gguf`，不由默认路由调用；模型当前冷迁在duolaiduo；
- Nunchaku：已撤销，模型、节点、缓存与活动模板均已清理，不得自动恢复或重新下载；
- 无 LoRA 人物一致性：`flux2_klein_4ref`（不变；Qwen Image 2.1 多图参考更强但许可证受阻，见下）；
- 图像编辑/修复：`krea2_edit_lora`（Krea 2 Edit LoRA + identity/enhancer 节点方案，2026-10-09 起替代 `flux2_klein_inpaint`，旧链路废弃；2026-10-12 晚完成落地，依赖 comfyui-krea2edit 自定义节点包，用户已批准安装）；
- 画幅扩图（9:16↔16:9 改版）：`flux2_klein_outpaint`（新增，外绘 LoRA + Outpaint Stitch，原图像素级不变）；
- 封面文字/排版：由 Remotion 承担（`ming_image` 已于 2026-10-09 撤销——文字直出与本项目"图/文分离"架构错位、课程作者自评不如在线工具、26GB 空间机会成本高；MIT 模型在 Comfy-Org/Ming-Image 官方仓，真需要时可随时补下）；
- 静帧动态化：`minimax_fasth3_i2v`（FastH3 首帧生视频、8 步、原生音频输出，2026-10-09 起替代 `wan22_i2v_q6`，旧链路废弃）；
- 文生视频、首尾帧转场（新增能力）：`minimax_fasth3_t2v` / `minimax_fasth3_fflf`；
- 人物口型（音频 ≤15 秒）：`minimax_h3_audio_sync`（2026-10-09 起替代 `wan_infinitetalk_short`，旧链路废弃）；
- 人物口型（长旁白 >15 秒）：`wan_infinitetalk_extend` 保留（H3 Audio Sync 上限 15 秒）；
- 写实人物动作/舞蹈：**Wan-Animate-2（B 方案，2026-10-14 用户直接选定，不做 A/B 对比测试——理由：官方新一代）**；生产模板待建（官方蓝图 "Motion Transfer (Wan Animate 2).json"），权重四件已在实例且 SHA-256 全通过，下次 GPU 会话建模板 + smoke 后投产。`wan22_animate_character`（A 方案）降为回退备选，其独占模型（基座 `Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2` 16.1G + `loras/wan2.2/` 五件 7.3G + `umt5-xxl-enc-fp8_e4m3fn` 6.3G + `wan_2.1_vae.safetensors` 243M ≈ **30G**）转为删除候选——duolaiduo 7 月权威备份全含（.verified 标记），**下次开机会话顺带删除，删前逐件对照备份哈希**。MiniMax H3 的 ref2va 是参考图不是驱动视频，无动作迁移能力（分工不变）；`wan_infinitetalk_extend` 与 B 方案共享 `umt5_xxl_fp8_e4m3fn_scaled`/`Wan2_1_VAE_bf16`/`lightx2v` LoRA 三件（2026-10-14 核实模板引用），删 A 链路不影响它；
- 卡通/非写实人物动作：`wan_scail_character`（保留）；模型当前冷迁在duolaiduo；
- 重点图片放大：`seedvr2_upscale`；模型当前冷迁在duolaiduo；
- 正式配音：Qwen3-TTS；Edge-TTS 只作应急兜底；
- 音乐：ACE-Step 为主；MiniMax Music 3（本地免费、上限 300 秒、课程自评不如 Suno）只在用户显式要求时试点；
- Qwen Image 2.1：编辑/多图参考/Inpaint 能力强（课程评测编辑超过 Krea、多图优于 FLUX.1 Kontext），但默认 non-commercial 许可证，商用授权获批前**不进入生产路由**；
- Krea LoRA 4条属于后续阶段，固定角色参考包和无 LoRA 基线通过后再讨论，不得自动发起 FAL 付费训练。

任何模型家族、付费训练、默认路由或人物表演方案的改变，都必须先获得用户批准。

## 19条活动 workflow

> 2026-10-12 换代落地完成：`wan22_i2v_q6`、`wan_infinitetalk_short`、`flux2_klein_inpaint` 已从 Python 注册表删除；`minimax_fasth3_t2v`、`minimax_fasth3_i2v`、`minimax_fasth3_fflf`、`minimax_h3_audio_sync`、`flux2_klein_outpaint` 五条新模板已通过 GPU smoke test 并注册。`krea2_edit_lora` / `krea2_outfit_transfer` 已于 2026-10-12 晚落地（comfyui-krea2edit 节点包经用户批准安装，无卡 preflight 19 条中 16 OK；这两条的 GPU smoke 留待下次 GPU 开机顺带跑，约 5 分钟）。

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
| `z_image_turbo_gguf` | Krea 不可用时显式备用（模型冷存 duolaiduo） | prompt、seed、steps、aspect_preset | 171 |
| `flux2_klein_4ref` | 四参考图无 LoRA 人物一致性 | prompt、reference_image_paths（恰好4张）、aspect_preset、megapixels | 203 |
| `flux2_klein_outpaint` | 画幅扩图（9:16↔16:9 改版，原图像素不变） | prompt、reference_image_path、outpaint_ratio、seed | 226 |
| `krea2_edit_lora` | 图像编辑/修复（改服装、改背景、修漂移） | prompt、reference_image_path、reference_boost（0–10）、seed、steps | 199 |
| `krea2_outfit_transfer` | 同角色换装（单服装图+角色描述，保持身份） | prompt（角色描述）、reference_image_path（服装图）、aspect_preset、seed、steps | 199 |
| `seedvr2_upscale` | 重点素材放大（模型冷存 duolaiduo） | reference_image_path、resolution、seed | 6 |

### 视频与人物表演

| 模板 | 用途 | 关键输入 | 输出节点 |
|---|---|---|---:|
| `minimax_fasth3_t2v` | 文生视频 4–15 秒（原生音频） | prompt、duration_seconds、aspect_preset、seed、steps | 228 |
| `minimax_fasth3_i2v` | 静帧动态化 4–15 秒（原生音频） | prompt、reference_image_path、duration_seconds、longest_side、seed | 228 |
| `minimax_fasth3_fflf` | 首尾帧转场 4–15 秒 | prompt、reference_image_path（首帧）、last_image_path（尾帧）、duration_seconds、seed | 228 |
| `minimax_h3_audio_sync` | 图+音频口型（≤15 秒，保留原声） | prompt、reference_image_path、reference_audio_path、duration_seconds（匹配音频长）、seed | 228 |
| `wan_infinitetalk_extend` | 显式调用的延长口型链路（模型冷存 duolaiduo） | prompt、reference_image_path、reference_audio_path、duration_seconds | 240 |
| `wan22_animate_character` | 写实人物动作迁移 | prompt、reference_image_path、driving_video_path、width、height | 56 |
| `wan_scail_character` | 卡通/非写实人物动作迁移（模型冷存 duolaiduo） | prompt、reference_image_path、driving_video_path、width、height | 139 |

图片模板通过 `aspect_preset=portrait_9_16|landscape_16_9` 选择比例，不复制两套 workflow。FastH3 t2v 的横竖版由 SizesState 的 orientation + 档位（864–1920 长边，32 倍数圆整）控制；i2v/fflf/audio_sync 跟随输入图比例，长边用 `longest_side` 控制。

TreeElf 寓言角色包约束：四参考图必须来自同一身份的一张四视图转面表裁切，或来自真正维持身份的参考工作流；四次独立文生图和同图复制四份均不合格。场景提交前必须检查最终编译提示词，环境、物件、微距画面不能被自动拼入主角身份或人物镜头语言。封面绘图 prompt 只描述可见画面，标题、品牌与编辑排版由 Remotion 处理。

## 19条 workflow 使用与参数替换契约

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
| `flux2_klein_outpaint` | 画幅扩图（9:16↔16:9 改版）；原图像素不变，只生成周围环境 | `prompt`、`reference_image_path`、`output_path` | `outpaint_ratio`（16:9/9:16/3:2/2:3/4:3/3:4/1:1）、`seed` | pixaoutpaint LoRA + Outpaint Stitch 固定；1–1.5MP 最佳 | PNG，节点`226` |
| `krea2_edit_lora` | 图像编辑/修复：改服装、改背景、修人物漂移 | `prompt`、`reference_image_path`、`output_path` | `reference_boost`（0–10，默认4，甜点区1–4）、`seed`、`steps`（默认10） | 输出尺寸跟随源图；identity edit LoRA strength 1 固定；编辑指令写"改成什么+keep everything else the same" | PNG，节点`199` |
| `krea2_outfit_transfer` | 同角色换装（舞蹈 B/C 造型首选）：单服装图迁移到角色 | `prompt`（角色外貌+场景描述）、`reference_image_path`（服装参考图）、`output_path` | `aspect_preset`或`width/height`（720×1280/1280×720，16倍数圆整）、`seed`、`steps` | 换装触发词指令为固定 text_2（不复制衣架/模特等道具）；身份、姿势、场景保持 | PNG，节点`199` |
| `seedvr2_upscale` | 最终重点图放大/修复，不用于所有中间图 | `reference_image_path`、`resolution`、`output_path` | `seed` | 保留源图宽高比；SeedVR2 7B模型固定 | PNG，节点`6` |

`guidance` 已按真实图结构做防误用优化：Krea、Z-Image、Flux和Wan I2V等蒸馏/加速图的实际CFG固定为1，不开放替换。内置模板调用若传入`guidance`会明确失败，不再静默忽略；只有自定义API-format workflow显式映射自己的guidance节点时才可调整。

### 视频与人物表演 workflow

| workflow | 功能与使用时机 | 必填参数 | 可替换参数 | 固定参数/限制 | 输出 |
|---|---|---|---|---|---|
| `minimax_fasth3_t2v` | 文生视频（4–15 秒，原生音频输出） | `prompt`、`output_path` | `duration_seconds`（4–15，默认5）、`aspect_preset`、`width`（映射 864–1920 档位）、`seed`、`steps`（默认8） | FastH3 8步蒸馏链固定；星标小尺寸选种子、入选镜头再升档 | MP4+AAC，节点`228` |
| `minimax_fasth3_i2v` | 把关键静帧转成短动态镜头（原生音频白送环境音） | `prompt`、`reference_image_path`、`output_path` | `duration_seconds`（4–15）、`longest_side`（默认864）、`seed` | 输出跟随输入图比例；1–3 秒镜头出 4–5 秒后剪辑截取 | MP4+AAC，节点`228` |
| `minimax_fasth3_fflf` | 首尾帧转场 | `prompt`、`reference_image_path`（首帧）、`last_image_path`（尾帧）、`output_path` | `duration_seconds`（4–15）、`longest_side`、`seed` | 尾帧自动对齐首帧尺寸；两图须同场景连贯 | MP4+AAC，节点`228` |
| `minimax_h3_audio_sync` | 图+音频口型（音频 ≤15 秒，保留原声） | `prompt`、`reference_image_path`、`reference_audio_path`、`output_path` | `duration_seconds`（1–15，应等于音频长）、`longest_side`、`seed`、`steps`（默认4，音质平衡点） | ref2va 模型 + Speed LoRA 固定；提示遵循弱，否定指令不听 | MP4+AAC，节点`228` |
| `wan_infinitetalk_extend` | 明确需要较长旁白时显式调用（连续 >15 秒独白） | `prompt`、`reference_image_path`、`reference_audio_path`、`output_path` | `duration_seconds`或兼容字段`num_frames` | 12段、25fps；可选约4.20/11.88/19.56/27.24/34.92秒；默认路由绝不自动选中 | MP4，节点`240` |
| `wan22_animate_character` | 写实人物动作迁移 | `prompt`、`reference_image_path`、`driving_video_path`、`output_path` | `aspect_preset`或`width/height`、`seed`、`duration_seconds` | 16fps；未传秒数时跟随完整驱动视频；传入时只截短，超过源时长会失败，绝不自动循环；`num_frames`禁止 | MP4，节点`56` |
| `wan_scail_character` | 卡通/非写实角色动作迁移 | `prompt`、`reference_image_path`、`driving_video_path`、`output_path` | `aspect_preset`或`width/height`、`seed`、`duration_seconds` | 24fps；未传秒数时跟随完整驱动视频；传入时只截短，超过源时长会失败，绝不自动循环；`num_frames`禁止 | MP4，节点`139` |

视频模板传本地路径时，工具先按SHA-256查询服务器输入缓存；哈希一致即复用，缺失才上传。`reference_image_url`只作为图生视频的可选下载入口，生产项目优先使用已审核的本地素材。

`duration_seconds` 是正式 API 时长入口。MiniMax FastH3/H3 模板直接接受连续秒数（FastH3 4–15、audio_sync 1–15，超出范围明确报错）；Wan/InfiniteTalk 模板由工具选择最近的合法模型档位，并在 provenance 中同时记录请求秒数、选中秒数和帧数。不得为了“随机”自动切换到 `wan_infinitetalk_extend`。

### API 调用规则

1. 图片入口：`ComfyUIImage` / `tools/graphics/comfyui_image.py`；视频入口：`ComfyUIVideo` / `tools/video/comfyui_video.py`；配音入口：`ComfyUITTS` / `tools/audio/comfyui_tts.py`。
2. 调用前先读工具 `input_schema`，选择 `workflow_template` 并传入上述参数；不要直接修改模型节点。
3. 工具将参数写入 API-format JSON 后调用 `POST /prompt`，轮询 `GET /history/{prompt_id}`，再通过 `GET /view` 把最终节点产物下载到Mac。
4. `output_node` 对19条内置模板是固定值，只有外部 `workflow_json/workflow_path` 才由调用者显式提供。
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

目标实例ID：`1vgexf3kfe-d6a65c1f`（普通容器实例，2026-10-08 起用）。历史实例均不得继续引用：`916b4d8f93-484e4934`与`601e43a60f-5b558258`已释放，Art实例`pro-7884ef011fc5`与`pro-791462c29633`亦已释放。普通容器实例不在 Pro/Art API 管控范围，开机/关机均需SSH或控制台操作。

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

该脚本先通过`ensure-autodl-comfyui-remote.sh`让远端 ComfyUI 独立于 SSH 会话运行，stdout/stderr 固定写入远端 detached 日志；随后建立`18188 -> 8188`隧道，并要求连续健康检查通过。自动化生产不依赖跨命令保存的后台隧道，而使用`with-autodl-comfyui-tunnel.sh -- <command>`包装预检或生成命令。只想前台保持隧道时使用`open-autodl-comfyui-tunnel.sh`；停止本地隧道使用`stop-autodl-comfyui-session.sh`，不会停止远端 ComfyUI。

### 2026-07-26 连接稳定性补丁：避免 stdout BrokenPipe

本轮 fable 30 秒测试发现：`start-autodl-comfyui-session.sh` 曾短暂返回 healthy，但随后本地 `18188` 隧道断开；Qwen3-TTS `FB_Qwen3TTSLoadSpeaker` 在打印 metadata warning 时触发 `BrokenPipeError`，原因是 ComfyUI stdout/stderr 仍绑定到已经断开的 SSH/日志管道。下次开机如果遇到以下任一现象：

- `curl http://127.0.0.1:18188/system_stats` 刚通过又立刻 connection refused；
- Qwen3-TTS 报 `BrokenPipeError`，traceback 指向 `print(...)`、`comfyui-manager/prestartup_script.py` 或 `app/logger.py`;
- 远端 `pgrep` 显示 ComfyUI 仍在，但本地隧道断开；

不要反复提交任务，也不要靠多次重试撞运气。当前脚本已经把以下稳定方式固化为默认路径：

1. 保留模型、声包和已生成资产，不删除 runtime output/input/temp。
2. `ensure-autodl-comfyui-remote.sh`用远端 detached 日志重定向方式启动 ComfyUI，让 stdout/stderr 写入远端文件，而不是 SSH 会话管道。以下命令只保留为人工诊断参考：

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

3. 自动化任务使用 `production-planning/scripts/with-autodl-comfyui-tunnel.sh -- <command>`，确保本地 `18188 -> 8188` 隧道在整个生成命令期间存活；人工查看 UI 时才单独使用 `open-autodl-comfyui-tunnel.sh`。
4. 重新确认 `/system_stats`、`/queue` 为空和 `scripts/comfyui_workflow_preflight.py` 通过后再继续生成。

### 本机代理与 AutoDL SSH

如果 SSH 输出 `Connection closed by 127.0.0.1 port 7897`，说明本机代理/TUN 链路参与并关闭了长连接。项目脚本不会擅自修改系统代理；应在代理客户端把当前 AutoDL 主机 `connect.nmb1.seetacloud.com` 及控制台显示的 SSH 目标设为 DIRECT。若 `nc` 和 `ssh` 对控制台当前端口都返回 `Connection refused`，应立即停止生产并核对实例是否真正处于 GPU 运行状态以及 SSH 主机/端口是否变化，不得继续重试生成任务。

注意：不要用 `pkill -f "python.*main.py"` 这类宽匹配命令；它可能匹配并杀掉当前 SSH shell。若要停止 detached ComfyUI，优先读 `$runtime/logs/openmontage-comfyui-detached.pid` 后按 PID 精确 kill。

## AutoDL API 当前限制

2026-09-03 已解谜：实例 `pro-7884ef011fc5` 属于 **AutoDL.Art（www.autodl.art）应用实例产品线**，与 api.autodl.com 的容器 Pro API 是两套入口、共用同一个开发者 Token（`.env` 的 `AutoDL_token`）。此前查不到该实例不是账号问题，是敲错了门。

- `scripts/autodl_instance.py` 现已支持 `--platform art`（HOST `https://www.autodl.art`，路径前缀 `/api/v1/adl_dev/dev/instance/pro`）；
- 两平台网关都会丢弃 GET 请求体（官方文档的 GET+body 示例实际不可用），脚本对 GET 端点一律改用 query string 传参（2026-09-03 实测：GET+body 报 `RequestParameterIsWrong`，GET+query 正常）；
- 两平台均「暂不支持 API 无卡开机」；art 的 release 端点同样只应在控制台人工操作；
- 2026-09-03 API 开机实测：list/status/power_on/power_off 鉴权与参数全部正确，power_on 被平台以「当前算力规格暂无库存, 请修改配置或稍等再试」拒绝——是 4090D·北京B区 库存问题而非 API 问题；实例全程保持 shutdown，零计费。库存恢复后重试 `--platform art power-on-gpu` 即可。

历史注：2026-07-23 曾对已删除旧实例验证 com 平台 Token 可用（list 0 条、power_on 返回 `RecordNotFoundError`），当时「不得假定 Pro API 适用」的告诫即由此而来，现已由 art 平台实测取代。

## 目标实例切换：pro-7884ef011fc5（AutoDL.Art 应用实例）

时间点：2026-09-03，API 只读核验 + 开机尝试。

- 实例：`pro-7884ef011fc5`，4090D ×1，北京B区，按量计费，创建于 2026-09-03，来源为 autodl.art 应用部署页（用户指定为今后主力机）；
- 管理命令：`python3 scripts/autodl_instance.py --platform art <list|status|snapshot|power-on-gpu|power-off> pro-7884ef011fc5`（power-off 需 `--yes`）；
- 首次成功开机后：立即从 snapshot 记录新的 `ssh_command`/`proxy_host`/`ssh_port`，更新本机 `ssh autodl-comfyui` 别名并完成免密；**旧别名指向 916b4d8f93 的 connect.nmb1.seetacloud.com:16717，旧实例释放后失效**；
- 该实例为全新应用实例：ComfyUI 环境需重装（旧机环境在 916b4d8f93 的 73GB 数据盘上，不随释放保留；自定义节点清单与启动脚本见本文档其上章节）；模型仍在账号级文件存储 nm-B1（105.7GB / 81 文件，SHA-256 已校验），新机可通过 `/root/autodl-fs` 挂载 + extra_model_paths 直读，无需重新上传；
- 旧实例 `916b4d8f93-484e4934`：用户计划释放（仅控制台操作；释放前须关机，最近核验为关机状态）。

## 舞蹈最小集重建（2026-10-08，已完成并关机）

时间点：2026-10-08，HF 学术加速直下完成，20/20 SHA-256 校验通过，实例已自动关机。

- **最终状态**：舞蹈最小集 18 个文件（60,628,162,502 字节）+ 2 个 flux2 标记文件全部就位于 `/autodl-fs/data/comfyui-models/`，`sha256sum -c` 20/20 通过（对照 `AUTODL_DANCE_RESTORE_SHA256_2026-10-07.tsv`），收尾脚本自动 `sync; shutdown -h now`，一次性传输密钥实例/Mac/duolaiduo 三端全部撤销。下次 GPU 开机即可直接生产舞蹈视频（`flux2_klein_4ref` → `wan22_animate_character`）；
- **实际执行路径**：用户选定 HF 学术加速直下。17/18 文件由 aria2 `-j2 -x16 -s16 --all-proxy`（显式传 `$http_proxy`）从公开源批量下载（午间 8-23MiB/s，晚高峰回落 2MiB/s）；仅 `sam3/sam3.pt`（3,450,062,241 字节）因 facebook/sam3 gated 403 失败，最终从 ungated 搬运仓 `1038lab/sam3`（备用镜像 `Justin331/sam3`，两者均逐字节同大小）双 URL aria2 补下完成；
- **中途放弃的路径**：duolaiduo→北京B区 rsync 直传实测晚高峰仅 0.2MB/s（白天 0.59MB/s，4 并行流不叠加，路径瓶颈），3.45GB 需 5 小时；Ultralytics CDN 的 `releases/download/v0.0.0/sam3.pt` 实际 404（308 链指向不存在的资产）；GitHub 四个 SAM3 ComfyUI 仓库均无 release 资产；ModelScope 搜索 API 无视 Query 参数不可用；
- **实例关键事实**：`1vgexf3kfe-d6a65c1f`（北京B区，4090D×1，50G数据盘不扩容，按量计费）；文件存储挂载点 `/autodl-fs/data`（200G rw，bj-B1 专区）；SSH 网关 `connect.bjb2.seetacloud.com`，**端口每次开机变化**（2026-10-13 为 33100；Mac 别名 `autodl-comfyui` 固定网关 IP `106.38.204.136` + HostKeyAlias，端口变了改 `~/.ssh/config` 的 Port 与 HostKeyAlias 即可）；非交互 shell 无 python3，用 `/root/ComfyUI-Easy-Install/python_embeded/bin/python3`；
- **找源清单存档**：`production-planning/AUTODL_DANCE_RESTORE_HF_SOURCES_2026-10-08.tsv`（大小/相对路径/URL 三列，sam3 行的 URL 为 gated 源，应急时改用 1038lab/sam3）；
- **经验**：HF 学术加速代理会污染 search API 结果（需 Mac 正常网络直查 huggingface.co/api）；gated 仓的可靠替代是找逐字节同大小的社区搬运仓（用 `?blobs=true` 查 siblings size 精确比对）；aria2c 不读代理环境变量需显式 `--all-proxy`；aria2 多连接分片写使 `du -sb` 逻辑大小虚高（看 `du -sh` 块占用或 aria2 进度行）；TSV 转 sha256sum 清单时行尾残留空格会让 20/20 全部 `FAILED open or read`（用 `sed -i 's/[[:space:]]*$//'` 修复）；aria2 exit 24 = HTTP authorization failed（gated）；AutoDL 无卡实例重启后 ControlMaster socket 需先删除再重连；duolaiduo 公网 SSH 用 `~/.ssh/duolaiduo` 密钥 + 125.38.165.110:2222（DDNS IP，Tailscale 停机时备用路径）。

## 视频路由换代：MiniMax FastH3 / H3 时代（2026-10-09 用户批准）

时间点：2026-10-09，依据 Pixaroma 课程 Ep27–37（2026-10-08 导入，笔记在 `treeElfNotes/03资源/YouTube课程/pixaroma/.../课次/27–37`，原始 UI workflow 在 `/Users/treeelf/Desktop/other/pixaroma-comfyui-workflow/EP27–EP36 Workflows/`）。

**用户已批准的决策**：按上文"生产决策"新路由表执行，`wan22_i2v_q6`、`wan_infinitetalk_short`、`flux2_klein_inpaint` 三条旧链路**立即废弃，以后不得再走**；新模板落地前，静帧动态化、短口型、图像编辑三类任务**暂停等待，不得自动回退旧链路**。

**新模板与模型清单（待落地）**：

| 模板（拟名） | 功能 | 模型与关键资产 | 源工作流 |
|---|---|---|---|
| `minimax_fasth3_i2v` | 静帧→动态（原生音频） | FastH3 主模型（diffusion_models/h3/fastvideo_fasth3_8step_v2_pruned_int8_convrot，8 步）+ Qwen 32B 文本编码器（nvfp4_awq）+ 双 VAE（音频）+ Sage/Sparse Attention 工作流内节点 | EP35/2. FirstFrame to Video |
| `minimax_fasth3_t2v` | 文生视频（4–15 秒） | 同上 | EP35/1. Text to Video |
| `minimax_fasth3_fflf` | 首尾帧转场 | 同上 | EP35/3. First and Last Frame |
| `minimax_h3_audio_sync` | 图+音频→口型（≤15s） | H3 ref2va pruned INT8（diffusion_models/h3/minimax_h3_ref2va_pruned_int8_convrot）+ Speed LoRA（loras/h3/minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16，shift 6、8 步） | EP32/SPEAK + Speed Lora |
| `krea2_edit_lora` | 图像编辑/修复 | krea2_turbo_int8_convrot 主模型 + qwen3-vl-4b-heretic_int8 编码器 + qwen_image_vae + Edit LoRA（loras/krea2/krea2_identity_edit_v1_2，strength 1）+ Krea 2 identity/enhancer 节点；Reference Boost 1–4 | EP30/Krea2 Edit |
| `krea2_outfit_transfer`（换装舞蹈专用） | 同角色换服装，保持身份 | 同 krea2_edit_lora 主模型组 + 换装 LoRA（loras/krea2/krea_outfittransfer） | EP30/Krea 2 + Outfit Transfer |
| `flux2_klein_outpaint` | 画幅扩图（原图不变） | Flux Klein 9B（本实例已有 fp8 版）+ 外绘 LoRA（loras/klein9b/pixaoutpaint）+ Outpaint/Stitch 节点；1–1.5MP 最佳 | Ep27 Workflows |
| ~~`ming_image`~~ | ~~封面文字/海报/缩略图~~ | 已撤销（2026-10-09，理由见生产决策节）；Ep37 工作流已到位存档备用 | EP37 Workflows |

**落地步骤（1–3 已完成）**：
1. ~~无卡开机核对环境~~ ✅ 2026-10-09 完成：ComfyUI → a4b5a045（10-08）、ComfyUI-Pixaroma → v1.4.206（10-08）、ComfyUI-Krea2T-Enhancer → 958898e（10-06，旧功能补丁备份在实例 `/root/krea2t-local-patch-2026-10-09.diff`）；
2. ~~摸清模型体积与 HF 源并下载~~ ✅ 2026-10-09 完成：102.50GB / 49 文件学术加速直下到文件存储（清单见下方会话记录节）；
3. ~~GPU 会话模板落地~~ ✅ 2026-10-12 完成（详见下方"2026-10-12 GPU 验收会话"节）：5 条新模板 GPU smoke 5/5 通过并注册，3 条废弃模板从注册表删除；`krea2_edit_lora`/`krea2_outfit_transfer` 同日晚经用户批准安装 comfyui-krea2edit 后在无卡会话完成落地（见下方无卡补落地节），本文档更新为 19 条表；
4. 旧链路模型（wan22_i2v、infinitalk_short 相关）本实例从未有过，无需处理；duolaiduo 上的旧模型为权威备份，永不删；
5. H3 采样固定参数（API 模板固化）：无 LoRA 20 步 CFG 1 res_multistep+simple shift 12；Speed LoRA 8 步 Euler+simple/beta shift 6（音质平衡点；4 步音频会劣化，20 步最高质量）；FastH3 原生 8 步、正常模式启动（Sage/Sparse 在工作流内，勿用启动参数重复启用）；时长档 4–15 秒（1–3 秒镜头生成 4–5 秒后剪辑截取）、尺寸 32 倍数圆整、分辨率对速度影响最大而时长近似线性（先用星标小尺寸选种子，入选镜头才升 Full HD 重跑）。

**许可证状态（2026-10-09 已核官方原文）**：
- MiniMax H3/FastH3：官方 LICENSE 定义 Excluded Territories = 欧盟、英国、韩国、美国；**Applicable Territory = 全球其余地区，中国大陆在内，直接可商用、免版税，无需申请**。仅当商业产品年收入超 2000 万美元才需邮件 `api@minimax.io`（标题 "MiniMax H3 licensing - authorization request"）另行授权；`platform.minimax.io/h3-license` 申请表是给排除区组织用的，本项目不用。注意条款 V.4：H3 产出（Outputs）不得在排除区使用/展示——国内平台发布无忧，YouTube 等全球分发属灰色地带（生成内容版权归用户，但展示地限制在条款内），用户已知悉；
- Qwen Image 2.1：Qwen Research License，Non-Commercial = "for research or evaluation purposes only"（比一般非商用更窄）；商用申请邮箱 `model-business@notice.qwencloud.com`（LICENSE 2.b 条）；课程作者发信多日未获回复，无公开批复先例，周期/费用未知。**获批前不进路由**，编辑需求由 `krea2_edit_lora` 承接；
- Ming Image 0.1：MIT，可商用，无障碍。

**经验（课程要点，落地时参考）**：H3 两类模型不可混用（fl2va 走首/尾帧、ref2va 走参考图/音频）；ref2va 提示遵循弱且随尺寸增大而下降，否定指令不听；显存峰值实测约 22GB（4090D 24G 贴边，FastH3 更稳）；生成耗时分辨率非线性、时长近似线性（Full HD 5 秒约 10 分钟@20步；FastH3 小尺寸 5 秒约 1 分钟@8步）；Krea 2 Edit 的 Reference Boost 甜点区 1–4（0 丢身份、10 拒改）；Outpaint 2–3MP 慢且易对不齐，固定 1–1.5MP。

## 2026-10-09 无卡落地会话：环境升级 + 新模型下载（已完成）

实例 `1vgexf3kfe` 无卡模式执行，学术加速实测 28–29MiB/s。**本节是"模型在哪、怎么用"的权威状态，做视频前先读这里。**

### 已下载就位的模型（`/autodl-fs/data/comfyui-models/`，102.50GB / 49 文件，19 个 LFS 大文件已过 HF 官方 SHA-256 校验）

| 组 | 文件（相对路径） | 体积 | HF 源 |
|---|---|---|---|
| H3 视频 | `diffusion_models/h3/fastvideo_fasth3_8step_v2_pruned_int8_convrot.safetensors` | 22.13GB | FastVideo/FastVideo-FastH3-Comfy |
| H3 视频 | `diffusion_models/h3/minimax_h3_ref2va_pruned_int8_convrot.safetensors`（口型必须） | 20.97GB | Comfy-Org/MiniMax-H3 |
| H3 视频 | `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 15.69GB | FastVideo/FastVideo-FastH3-Comfy |
| H3 视频 | `vae/minimax_h3_video_vae_fp16.safetensors` + `vae/minimax_h3_audio_vae_fp32.safetensors` | 5.82GB | 同上 |
| H3 视频 | `loras/h3/minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16.safetensors`（Speed LoRA） | 1.96GB | lightx2v/Minimax-h3-Turbo |
| Krea2 编辑 | `diffusion_models/krea2/krea2_turbo_int8_convrot.safetensors` | 13.49GB | Comfy-Org/Krea-2 |
| Krea2 编辑 | `text_encoders/qwen3-vl-4b-heretic_int8.safetensors` | 4.84GB | DreamFast/Qwen3-VL-4b-Heretic-ComfyUI |
| Krea2 编辑 | `vae/qwen_image_vae.safetensors` | 0.25GB | Comfy-Org/Krea-2 |
| Krea2 编辑 | `loras/krea2/krea2_identity_edit_v1_2.safetensors`（原名带中文"编辑模型"后缀，已重命名） | 1.83GB | RunningHubAI/rh-krea2-identity-edit-v1-2-lora |
| 换装 | `loras/krea2/krea_outfittransfer.safetensors` | 1.14GB | AliveAi/Krea-2-Edit-Outfit-Transfer |
| 外绘 | `loras/klein9b/pixaoutpaint.safetensors` | 0.13GB | Pixaroma/experimental_loras |
| 配音恢复 | `qwen-tts/`（1.7B Base/CustomVoice/VoiceDesign + Tokenizer 全套） | ~14GB | Qwen 官方四仓 |

**有意未下载**：fl2va 完整版（20.97GB，FastH3 覆盖其全部场景）、Ming Image（~26GB，已撤销）、Qwen Image 2.1（许可证）、3D/Music 3/风格 LoRA（不在路由）。下载清单与校验文件存档在实例 `/root/h3-upgrade/`（aria2-input.txt / sha256.txt / aria.log / verify.log）。

### 实例当前状态与注意点

- 文件存储用量 57 → 154G / 200G（df 块口径，47G 余量）；数据盘 50G 空；本实例独有舞蹈最小集 + 本次新增组，**duolaiduo 上的其余冷模型（SeedVR2/Z-Image/SCAIL 等）仍只在 duolaiduo**；
- 备份快速通道经验（2026-10-09 实测）：duolaiduo 直连 HF 被墙，但 **hf-mirror.com 可达且 21–49MiB/s**——以后大模型备份/恢复首选"duolaiduo 走 hf-mirror 按 HF 官方 LFS sha256 清单直拉"，不要再试国内 rsync 中转；Mac 直连 HF API 也会失败，可用 duolaiduo 的 hf-mirror API 查 tree/哈希；
- 环境已升级：ComfyUI a4b5a045（10-08）、ComfyUI-Pixaroma v1.4.206、Krea2T-Enhancer 958898e（旧补丁备份 `/root/krea2t-local-patch-2026-10-09.diff`）；
- ~~老 krea2 模板文件名映射待改~~ ✅ 2026-10-12 完成（两个 JSON 已引用 int8_convrot + heretic_int8）；**2026-10-13 补修第三处**：`tools/graphics/comfyui_image.py` `_REQUIRED_MODELS` 与 `tools/_comfyui/metadata.py` `BUNDLED_MODEL_STACKS` 的 Python 声明当时仍是旧文件名，导致工具运行时被拦（preflight 走模板 JSON 不报此问题）——改声明后契约测试 96/96；
- ~~qwen-tts 的 voices 声线包不在本实例~~ ✅ 权威备份在 Mac `projects/cherry-voice-restore-20261012/assets/server-voice-backup/`；文件存储 `/autodl-fs/data/comfyui-models/qwen-tts/voices/` 为长期在位副本，数据盘经软链接过去（见下方 models 断链记录，2026-10-13）；
- 删除记录：远端 UI workflow `Wan 2.2 Image to Video.json`（废弃链路）；`loras/wan2.2/` 下 Pusa/Lightning/FastWan/Fun-InP 四个 LoRA 经核对是 `wan22_animate_character` 模板依赖，**保留不删**；
- duolaiduo 备份 **2026-10-09 完成**：12 个 LFS 大文件（约 88.25GB，H3 换代组）由 duolaiduo 经 hf-mirror.com 直拉（实测 21–49MiB/s，rsync 国内中转 0.2–0.6MB/s 已绕开），sha256sum -c 12/12 OK（对齐 HF 官方 LFS oid）；qwen-tts 四仓 duolaiduo 本有同构全套未重复拉取，speech_tokenizer 三件旧库顺手校验 3/3 OK。manifest 在 duolaiduo `/media/data/ai-models/comfyui/manifests/h3-upgrade-2026-10-09.{sha256,status}`，实例侧状态文件 `/root/h3-upgrade/BACKUP_STATUS`；
- 校验补丁记录：首轮流校验 16/19 OK、3 FAILED 的根因是**清单生成 bug**——qwen-tts 三仓 `speech_tokenizer/model.safetensors`（682MB，三仓同内容同哈希）的哈希被错写到主模型路径，导致 aria2 下载时两 URL 写同一路径互相覆盖（主模型 3.86GB 胜出且完好），speech_tokenizer 三件实际从未落盘。已学术加速补下并 3/3 OK；实例主清单 `/root/h3-upgrade/sha256.txt` 已修正为 19 行唯一路径。**下次生成多文件下载清单时，out= 必须带子目录路径并对唯一性做断言**；
- 文件存储实测 154G / 200G（df 块口径，47G 余量）；新增文件 49 个（aria2 46 落盘 + 补下 3），加舞蹈集 20 共 69 文件。

## 2026-10-12 GPU 验收会话：H3 换代模板落地（已完成）

实例 `1vgexf3kfe` GPU 模式执行，17 条注册模板 13 OK + 3 WAIT（冷存模型，合理放行）。

### 环境修复与升级（本次会话完成）

- **extra_model_paths.yaml 挂载落地**（方案 A）：`/root/ComfyUI-Easy-Install/ComfyUI/extra_model_paths.yaml` 映射文件存储 `/autodl-fs/data/comfyui-models` 的 10 个键（diffusion_models/text_encoders/vae/loras/clip_vision/controlnet/detection/nlf/qwen-tts/sam3），ComfyUI 直读文件存储，数据盘零占用；krea2edit 所需的 detection/nlf 键已预先就位；
- **models 断软链修复**：`models → /root/autodl-tmp/comfyui-models` 因数据盘目录不存在而断链，导致节点包 INPUT_TYPES 的 makedirs 全部 FileNotFoundError（qwen-tts voice_clone_load 曾因此缺节点）；`mkdir -p /root/autodl-tmp/comfyui-models/{qwen-tts/voices,rembg}` 修复，object_info 动态恢复无需重启；
  - **2026-10-13 复发与持久方案**：数据盘在实例重置后会清空（50G 盘全新），断链坑每次复发；本次改用软链 `models/qwen-tts/voices → /autodl-fs/data/comfyui-models/qwen-tts/voices`（声包权威在文件存储，不再依赖数据盘），并补齐 rembg 等空目录防注册失败；**LoadSpeaker 节点注册失败必须精确 kill + 冷启动才能恢复**（object_info 不会动态恢复已失败的节点注册）；GPU 开机后若 preflight 报 voice_clone_load 缺节点，先查 `ls /root/autodl-tmp/comfyui-models/` 是否为空；
- **ComfyUI 核心升级**：947c2749 → e8665ca8（Comfy-Org/ComfyUI，remote 走 gh-proxy），0.39.0；MiniMax H3 全系节点（MiniMaxH3ImageToVideo/ReferenceToVideo、BlockSparseAttention、ModelAttentionBackend 等）是新核心内置节点（comfy_extras/nodes_minimax_h3.py），无需自定义包；新依赖 7 个已随升级安装；
- **ComfyUI-Pixaroma 升级**：v1.4.52 → v1.4.209，注册节点 0 → 129 个；H3 课程节点（node_duration/node_h3_audio_sync/node_longest_side 等）就位；新依赖 imageio-ffmpeg；
- **krea2 老模板文件名映射完成**：`first_batch/krea2-low-vram.json` 与 `krea2-extra-pass.json` 的 `krea2_turbo_fp8_scaled`→`krea2_turbo_int8_convrot`、`qwen3vl_4b_fp8_scaled`→`qwen3-vl-4b-heretic_int8`（各 2 处），preflight 转 OK；
- **cherry 声包重克隆闭环**：旧声包随实例重建丢失；Mac whisper（Homebrew，Azure CDN 模型源不经 HF）转写参考音频 → qwen3_tts_voice_clone_save 重克隆 → 三件套（qvp/wav/json）duolaiduo 备份 SHA-256 双端一致 → 实例 voices/ 就位；Mac 试听件 `projects/cherry-voice-restore-20261012/assets/treeelf_cherry_smoke.mp3`；qwen-tts speech_tokenizer 三仓补齐 3×3 小文件（config/configuration/preprocessor，hf-mirror 源）。

### 模板落地（5/5 GPU smoke 通过）

UI→API 无头转换管线：UI JSON scp 到实例 input → 浏览器 `fetch('/view?filename=X.json&type=input')` → `app.loadGraphData(wf)` → `app.graphToPrompt()` → 取 `result.output` 落盘 Mac（100% 保真，中间产物在 `tools/_comfyui/workflows/_ui2api_draft/`）。

| 模板 | smoke 结果 | 产物规格 |
|---|---|---|
| `minimax_fasth3_t2v` | ✅ 429s（含首次 22GB 模型加载） | 480×864、5.18s、124帧、AAC 原生音频 |
| `minimax_fasth3_i2v` | ✅ 326s | 480×864、5.18s、AAC |
| `minimax_fasth3_fflf` | ✅ 424s | 480×864、4.46s、AAC |
| `minimax_h3_audio_sync` | ✅ 308s（ref2va 二次加载模型） | 480×864、9.43s、cherry 原声口型 |
| `flux2_klein_outpaint` | ✅ 268s | 683×384（竖图 9:16 扩为 16:9） |

smoke 产物与报告：`projects/comfyui-h3-templates-20261012/assets/`、`smoke_results.json`；脚本 `run_smoke.py`。Pixaroma 节点参数藏在状态 JSON 串（PromptState.text、SeedState.runSeed、DurationState.seconds、SizesState、LongestSideState、LoadAudioState、OutpaintState、DropdownState），`production.py` 已实现 `_patch_state` 机制统一注入；`_prune_to_output` 自动剪掉 Label/Note 等 UI 装饰节点（23→18 节点）。

### 注册表换代（代码侧完成）

- 删除：`wan22_i2v_q6`（first_batch）、`wan_infinitetalk_short`、`flux2_klein_inpaint`（production）及 3 个 JSON；
- 新增：5 条新模板 spec + `tools/_comfyui/workflows/production/` 5 个 API JSON（课程 Windows 路径反斜杠已修正；outpaint 主模型对齐实例实际文件 `flux2/flux-2-klein-9b-kv-fp8.safetensors`）；
- 工具层：`comfyui_video.py`（新 enum、last_image_path、longest_side、source_image 按 spec 条件化——t2v 不再强制参考图）、`comfyui_image.py`（outpaint_ratio、inpaint mask 机制移除）；
- `treeelf_philosophy_batch.py` model_group_order 跟随新路由（wan22_i2v_q6 → minimax_fasth3_i2v）；`comfyui_workflow_preflight.py` 补 last_image/source_audio_state 占位；
- ComfyUI 相关测试 156/156 通过；teachers_day_clay 系列 10 项失败为既有问题（`projects/teachers-day-clay-bouquet/assets/window2_manifest.json` 从未入库且不在磁盘，与本次改动无关）。

### 待用户决定

- cherry 声线试听确认（`projects/cherry-voice-restore-20261012/assets/treeelf_cherry_smoke.mp3`）。

## 2026-10-12 晚无卡会话：krea2_edit_lora / krea2_outfit_transfer 落地（已完成）

实例 `1vgexf3kfe` 无卡模式执行，用户批准安装 comfyui-krea2edit 后完成。

- **comfyui-krea2edit 安装**：`lbouaraba/comfyui-krea2edit` v1.2.5 经 gh-proxy 克隆到 custom_nodes；纯 `__init__.py` 节点实现、无额外依赖（einops 0.8.2 已有）；核心节点 `Krea2EditModelPatch`（in-context edit forward：序列重建为 [text | source | target]，3-axis RoPE 区分）+ `Krea2EditGroundedEncode`；
- **UI→API 转换**：ComfyUI 以 `--cpu` detached 启动（无卡模式必须带 `--cpu`，start 脚本会拒绝无 GPU 环境）；EP30 两 UI workflow（Krea 2 + Edit Lora / Krea 2 + One Image Outfit Lora）走浏览器 fetch→loadGraphData→graphToPrompt 管线转换，bad 节点 0/0；中间产物在 `tools/_comfyui/workflows/_ui2api_draft/`；
- **production JSON 预处理**：Windows 反斜杠路径修正（unet `krea2/krea2_turbo_int8_convrot.safetensors`、LoraLoaderState 内嵌 `krea2/krea2_identity_edit_v1_2` / `krea2/krea_outfittransfer`）；`krea2-edit-lora.json`（20 节点）与 `krea2-outfit-transfer.json`（19 节点）落 `production/`；
- **注册表**：`production.py` 新增 2 spec + `ref_boost_state`（SlidersState 注入，0–10 校验）与 `resolution_state`（PixaromaResolution 注入，预设 720×1280/1280×720，显式 width/height 时 16 倍数 snap 到 64–16384）两分支；`comfyui_image.py` enum +2、`reference_boost` schema 参数；outfit 的换装触发词指令固定在 text_2 不开放，prompt 只写角色描述；
- **验证**：ComfyUI 相关测试全过（含 2 个新契约用例）；handoff 契约 count 19；无卡 preflight 19 条 = 16 OK + 3 WAIT（z_image/scail 冷存 + FastH3 三条因无卡 CPU 模式 attention 枚举只有 `pytorch attention` 显示 WAIT——GPU 后端枚举差异，GPU 模式已验收过，非模板缺陷）；
- **GPU smoke 未跑**：留待下次 GPU 开机做视频批次开头顺带跑两条（约 5 分钟），跑通前这两条模板的生产调用视为待验收状态；
- 实例 UI workflow 输入已清理，会话结束即无卡关机。

### 无卡模式注意事项（本次实测补充）

- `start-autodl-comfyui-session.sh` 拒绝无 GPU 环境是设计行为；无卡需手动 detached 启动：`nohup python_embeded main.py --cpu --listen 127.0.0.1 --port 8188 --input/output/temp-directory …`（pidfile 在 `$runtime/logs/openmontage-comfyui-detached.pid`）；
- `ModelAttentionBackend.attention` 在 CPU 模式枚举只有 `pytorch attention`，GPU 专用后端（comfy kitchen attention 等）不出现——preflight 的 FastH3 WAIT 判读要区分"冷存模型"与"无卡枚举差异"两类。

## 生产场景管线（2026-10-09 与用户确认，做视频按此路由）

### 场景一：换装舞蹈视频（模型全就位，随时可生产）

角色基准定妆 `flux2_klein_4ref`（四参考）→ 换装出 B/C 造型：首选 `krea2_outfit_transfer`（换装 LoRA，2026-10-12 已落地）→ 舞蹈动作 **Wan-Animate-2（B 方案，2026-10-14 选定，模板待建）**，回退备选 `wan22_animate_character`（A 方案，模型已转删除候选）→ 可选 `seedvr2_upscale`（冷存需恢复）→ Remotion 剪辑 + ACE-Step 配乐（关机后离线）。

### 场景二：15 秒短剧（模板已就位）

剧本分镜（每镜头标注说话/动作/空镜）→ 人物 `flux2_klein_4ref` / 空镜场景 `krea2_low_vram` → **先配音** `qwen3_tts_voice_clone_load`（treeelf_cherry）→ 说话镜头 `minimax_h3_audio_sync`（图+音频→口型，保留原声，音频 ≤15 秒）→ 动作/空镜 `minimax_fasth3_i2v`（原生音频白送环境音）→ 转场 `minimax_fasth3_fflf` → Remotion 拼接。1–3 秒镜头的生成策略：出 4–5 秒后剪辑截取。

### 场景三：3 分钟短剧（模板已就位，管线同 15 秒版 + 规模管理）

180 秒 ≈ 40–70 个 2–5 秒镜头；口型逐镜头 `minimax_h3_audio_sync`（天然分段），连续 >15 秒独白才用 `wan_infinitetalk_extend`（单条 ≤35 秒）；一致性靠每角色一套 4ref 参考包全片复用 + `krea2_edit_lora` 修漂移；同场景复用同一张场景基图；生产拆 2–3 个 GPU 批次（批次1 图片+配音 → 关机离线审核 → 批次2 全部视频镜头 → 关机 → 离线 Remotion）。GPU 时长量级约 4–5 小时。

## 下次 GPU 会话 SOP（做视频前置）

1. 控制台 GPU 开机 → `production-planning/scripts/start-autodl-comfyui-session.sh` → `COMFYUI_SERVER_URL=http://127.0.0.1:18188` → `scripts/comfyui_workflow_preflight.py`（预期 16 OK + 3 WAIT 冷存）；
2. ~~上传 `treeelf_cherry` 声包~~ ✅ 2026-10-12 已就位（重克隆版）；
3. ~~模板落地（换代步骤 3）~~ ✅ 2026-10-12 完成（5 新模板注册 + 3 废弃删除 + krea2_edit/outfit 无卡落地，共 19 条）；GPU 开机后先顺带跑 `krea2_edit_lora`/`krea2_outfit_transfer` 两条 smoke（约 5 分钟）再进入生产批次；
4. ~~修 krea2 老模板文件名映射~~ ✅ 2026-10-12 完成；
5. 之后按"生产场景管线"开工做视频；批次结束走 `finalize_autodl_comfyui_batch.py --yes --shutdown` 门禁关机。

### 批次 1 已执行（2026-10-13，记忆修理店成片验证）

- 53/53 产物（26 TTS + 2 转面表 + 18 krea + 7 flux）落地本地、SHA-256 复核通过；角色 2/2 人审批准；finalize 未带 --shutdown（用户留用 GPU）；4 条 TTS 语速超计划 35%（总量 64.4s vs 66s 持平，Remotion 以逐镜音频轨为锚消化）；
- 本会话三修：models 断链软链方案（见实例状态记录）、TTS language 枚举要 `Chinese` 全称、工具 `_REQUIRED_MODELS` 旧文件名声明；规划与实录见 `projects/memory-repair-shop/production/gpu-batch-plan.md`；preflight 实测 15 OK + 4 WAIT（WAIT 全为废弃 Wan 链路冷模型，无需处理）。

### 批次 1 成片被否决 → v2 短剧返工（2026-10-13）

- 用户四要求：**无旁白、人物开口说话、画面动态（视频镜）、全中国人物**。v1 是旁白驱动静帧有声书形态（复用了粘土手工线路），全部作废：26 条 cherry 旁白 TTS 弃用、v1 人物首帧作废、批次 2 断点 manifest（b2，seed 3/25）作废不要续跑。
- 复盘结论：剧本旁白驱动 + 声音契约断裂（character_dialogue 从未进音频）+ i2v_prompt 用反 pixaroma 公式（"the same X remain consistent" 正是 EP35 头号错误 preservation wall，画面冻结主因）。
- v2 已落地：storyboard v2（`build-storyboard-v2.py` 可重跑，25 镜 106s，全镜 4-6s 设计时长=生成时长，i2v 全按 EP35 H3 公式：对齐行+三字段+指向锚+四拍动作+独立镜头句）；9 空镜复用 v1 首帧，16 人物镜中国面孔重写。
- 声音 v2：5 镜对白 Qwen3-TTS 按人物特征 voice_design 直出（4 角色 seed 2026101301-04），old_man 第二句 clone_save 保同声线（old_man_v2 已入远端 voices）；成品存档 `~/Desktop/psynautCode/treeelfVoice/音色/`；3 角标字幕 + 店招/结尾大字走 Remotion 文字层。
- 批次 3（b3）dialogue_tts 组 **5/5 已执行完成**（首跑 s21 因依赖 s9 同轮 blocked，重跑同组补齐）；剩余组 character_pack 2 + krea 9 + flux 7 待 GPU 会话；批次 4（b4）视频批已配好（22 镜两段式 + 3 口型单轮 HD audio_sync + s21→22 fflf）。
- 镜头时长规则更新：H3 短剧单镜 ≥4s（H3 最短档），与静帧图解类 ≤3s 规则按产线区分。
- 详见 `projects/memory-repair-shop/production/gpu-batch-plan.md`（v2 返工版）。

### 2026-10-14 无卡会话：模型空间核查 + Wan-Animate-2 权重补齐（已完成，已关机）

- **核查结论：`/autodl-fs/data/comfyui-models` 共 177G 全员有主，无多余模型**（diffusion 94G + text_encoders 40G + qwen-tts 16G + loras 13G + vae 6.5G + 辅助件 9.4G；无 .part 残留，data 下无其他目录）。疑似多余项逐一核实有主：`qwen_image_vae`(243M) 是 `krea2_edit_lora`/`krea2_outfit_transfer` 模板的 VAE；Qwen3-TTS `1.7B-Base`(4.9G) 是 VoiceClone 节点运行时模型（节点源码 3 处 `load_qwen_model("Base",…)`，映射表 miss 时也 fallback 到 Base）；两份 umt5 各 6.3G 为不同打包（SHA 不同），A 组用 `umt5-xxl-enc-fp8_e4m3fn`、B 方案用 `umt5_xxl_fp8_e4m3fn_scaled`，不可互删；`minimax_h3_ref2va`(20G) 归 `minimax_h3_audio_sync`；`loras/wan2.2/` 五件 7.3G 归 `wan22_animate_character`。
- **Wan-Animate-2（B 方案）权重四件全部在位、SHA-256 全通过**（对照 `download_wananimate2.sh` 期望值）：`wan_animate_2_int8_convrot` 16G + `umt5_xxl_fp8_e4m3fn_scaled` 6.3G + `Wan2_1_VAE_bf16` 243M 三件此前已在，本次无卡补下 `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16` 704M（hf-mirror）。B 方案与 A 组同批对比测试的前置条件已齐，无需再下载。
- **仍欠两件（用户明确暂不下）**：SeedVR2 两件 9G（短剧 68 图放大用；duolaiduo 未挂载，用前 HF 直下或挂盘上传）与 IndexTTS-2.5 全包 7.7G（升级计划 #4 表演轨，HF 源清单 `AUTODL_UPGRADE_1_2_4_HF_SOURCES_2026-10-13.tsv`）。
- 会话结束执行实例内 `shutdown` 关机，端口拒连验证通过；本节记录于关机后离线补写。

### 2026-10-14 第二次无卡会话：H3 组 + B 方案四件备份至 duolaiduo（已完成，已关机）

- **用户决策：备份到 duolaiduo，先不删**（目的是将来省 H3 组约 35-40 元/月存储费；删除动作延后到记忆修理店批次 3/4 GPU 任务跑完的那次开机会话顺带做）。
- **H3 六件无需传输**：duolaiduo `/media/data/ai-models/comfyui/models/` 早已全有（7 月备份），本次仅三方核验。
- **B 方案补齐两件**：`wan_animate_2_int8_convrot` 16G 与 `lightx2v_I2V_14B_480p…rank64_bf16` 704M 由 duolaiduo 用 aria2c 从 hf-mirror 直下（85-96 MiB/s，远快于 rsync 跨端传输；注意 aria2 外层单引号内的 `\$R` 会被再转义吃掉，URL 必须写死）；另两件（umt5_scaled、Wan2_1_VAE）duolaiduo 7 月已有，本次补算哈希。
- **三方对照全部一致（期望 = duolaiduo 实算 = AutoDL 实例实算，共 10 件 / 84.7 GiB）**：H3 六件（62.0 GiB）+ B 方案四件（22.7 GiB）。实例端哈希在无卡 CPU 上算约 50 分钟（63G），SSH 连接稳定未断。
- **权威清单**：`production-planning/AUTODL_DUOLAIDUO_MODEL_BACKUP_2026-10-14.tsv`（含逐件字节数与 SHA-256，删除后恢复的唯一依据）。duolaiduo 端校验记录：`~/h3-backup/sha256.txt` + `~/h3-backup/wananimate2_backup.sha256`。
- 会话结束执行实例内 `shutdown` 关机，端口拒连验证通过。

### 2026-10-15 用户放弃 AutoDL 平台（决策记录）

- **用户原话**："帮我把跳舞，短剧第一步，短剧第二步，需要的工作流，写到文档中吧。我已经放弃autoDL了。你先把这个记录一下。"
- **含义**：不再租用 AutoDL GPU 生产；将来视频生产转本地或其它平台（替代方案待定，用户未指定）。工作流 JSON 与 Python 注册表全在本地 repo，零成本保留；模型底座 = duolaiduo 权威备份（2026-10-14 清单 + 7 月暖库 153 文件 181.6G）。
- **删除任务取消**：2026-10-15 批准的"帮我删吧"（A 链路 8 件 29.8G + H3 六件 62.0G + 账外件 8.2G ≈ 100G）**不再执行**——平台整体弃用后逐件删除无意义，用户将来在控制台直接释放实例即全清。已完成的删前哈希门禁（第三批 6/6 两端一致；A 链路 duolaiduo 端 8 件哈希在档）留作恢复参考，不追加进权威 tsv。
- **实例状态**：本决策记录时 SSH 拒连（关机特征）。数据盘/文件存储内容仍在（模型 177G 等），除非用户在控制台释放。**放弃后无必须抢救的实例独有资产**：模型全在 duolaiduo；自定义声线 `treeelf_cherry` 三件套与 `cat_machine_*` 六件历史声线均有本地备份；历批次 outputs 均已拉回。可放心释放。
- **三产线工作流清单**（跳舞 59.8 GiB / 短剧第一步 74.7 GiB / 短剧第二步 62.0 GiB，共享件去重口径）已写入 `docs/pixaroma-comfyui-course-workflows.md` 尾部。
- 遗留小项：duolaiduo 当日 SSH 超时不可达，qwen-tts/voices 的 duolaiduo 端核对未做（本地有备份，不影响）；B 方案 `wan_animate2` 模板待建 + smoke 转为"新平台落地时"事项。

## 当前重建实例状态

时间点：2026-08-13，无卡模式只读核验。

- 当前实例ID为`916b4d8f93-484e4934`，`ssh autodl-comfyui`已更新到新端口并完成专用公钥免密验证；
- 系统盘镜像中的ComfyUI约15GB、26个自定义节点和控制脚本在位；
- 数据盘为全新50GB空盘，`/root/autodl-tmp/comfyui-models`为0个文件；
- 200GB文件存储已挂载到`/root/autodl-fs`，当前为0个文件；
- 旧实例数据盘中的模型、runtime validation和workflow没有随镜像恢复；本地OpenMontage仍保存15条API workflow；
- duolaiduo权威备份可访问，153个文件、181,569,648,075字节、SHA-256清单153行；
- 重建后的三层存储和模型分组方案见`production-planning/AUTODL_REBUILD_STORAGE_PLAN_2026-08-13.md`；用户批准迁移前不得上传模型、扩容或运行GPU验收。

## 旧实例历史验收（只作兼容性证据）

以下状态属于已删除旧实例在2026-07-23的验收记录，只证明镜像中的软件栈及workflow曾经可用，**不代表新实例模型已在位或已完成重建验收**。

- ComfyUI、Comfy CLI 和所需自定义节点已安装；
- 15/15 活动模板通过节点类型、模型枚举与输出节点结构预检；
- GPU、SeedVR2 两个加载节点和15/15活动模板已通过 GPU 预检；
- Nunchaku 节点和文件为0；
- 当时主要模型已在位：Krea、Z-Image GGUF、Flux 2 Klein、InfiniteTalk、Wan Animate、SCAIL；
- 当时Qwen3-TTS 1.7B Base的13/13文件远端SHA-256校验通过；新实例当前没有这些数据盘模型；
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

2026-08-13重建恢复已完成：73GB数据盘生效，15条API workflow已恢复，文件存储暖库81个普通文件＋1个符号链接、105,695,171,441字节通过逐文件SHA-256，双端一次性密钥已撤销，实例已Linux关机。下次开无卡模式后先从`AUTODL_HOT_MODEL_PROFILES_73GB.json`选择一个热集复制到数据盘并校验；不得把105.70GB全套复制进73GB数据盘，也不得在热集预检前切GPU生产。

**2026-09-03实测修正（见`AUTODL_HOTSET_VERIFY_2026-09-03.json`）**：`/root/autodl-tmp`实际为50G项目配额（XFS prjquota），并非73GB；热盘并非空盘——krea2组+qwen-tts（即窗口1热集）已于2026-08-14被恢复且经SHA-256逐文件验证与暖库一致（qwen-tts多出的6个`cat_machine_*`声线文件为需保留的历史资产，已另存本地备份）。窗口1可直接GPU开机生产。窗口2（wan22_i2v 31GB）在50G配额下无法满足20GB最低剩余规则（31+20>50），需用户决定扩容数据盘或对该窗口放宽规则。GPU生命周期铁律（2026-09-03用户重申）：开机即生产、生产完即关机、素材质检在关机后离线进行。

**2026-09-03晚二次修正（用户口述）**：模型暖库在AutoDL**文件存储**（console → 文件存储，disk `nm-B1`），并不占用实例数据盘的50G配额——"扩容数据盘 vs 放宽20GB规则"的抉择作废。窗口2修订方案：下次开机（可无卡）先`mount`/`df -h`确认文件存储在实例内的挂载点并SHA抽验`wan22_i2v`，然后二选一：A) ComfyUI `extra_model_paths.yaml` 直接加挂载点路径读模型（数据盘零占用，推荐先试）；B) 从文件存储复制`wan22_i2v`到热盘（删krea2腾位，窗口结束即删，原件始终在文件存储）。另：声线已于当日定版——`treeelf_cherry`（dashscope Cherry走神样本本地克隆，v4），三件套在`projects/teachers-day-clay-bouquet/assets/server-voice-backup/`，后续视频直接`voice_clone_load`复用，无需发布署名（合成音色）。

TreeElf fable 批次不再手动逐组运行。完成 `prepare` 与 `capture-gpu-baseline` 后，通过持续隧道执行：

```bash
production-planning/scripts/with-autodl-comfyui-tunnel.sh -- \
  .venv/bin/python scripts/treeelf_fable_batch.py run-gpu-batch \
  --config workflow_configs/treeelf-fable/<batch>/batch.json
```

该命令自动推进旁白、角色转面表、Krea正文、封面、已通过角色门禁的Flux和可选Wan。角色未审核只阻断对应Flux任务，Krea与封面继续生产；返回`waiting_character_review`时审核联系表后原样重跑，已完成任务自动跳过。Wan失败或运动审核未通过时，本地Remotion使用相应静帧，不启动强制补生循环。

批次结束先预览：

```bash
.venv/bin/python scripts/finalize_autodl_comfyui_batch.py \
  --project-dir projects/<项目> \
  --policy production-planning/<项目>-retention.json \
  --dry-run
```

确认保留清单后，由Agent执行同一命令并增加`--yes --shutdown`，自动完成空队列检查、项目主素材SHA-256校验、精确清理、审计记录和Linux关机；不创建独立批次灾备。任何门禁失败都不会删除或关机。

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

当前实例ID `916b4d8f93-484e4934` 在批次关机门禁全部通过后使用以下方式关机：

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
