# AutoDL 实例模型清单

> 生成:2026-10-14(无卡模式 SSH 实测,实例 `1vgexf3kfe`)· 后续模型增删后请同步更新本页
>
> 路径根:`/autodl-fs/data/comfyui-models/`(网络文件存储,经 `extra_model_paths.yaml` 的 `openmontage_filestore` 十键挂给 ComfyUI:diffusion_models / text_encoders / vae / loras / clip_vision / controlnet / detection / nlf / qwen-tts / sam3)
>
> **再生成方法**(开机后任一时可跑,刷新本页数据):
> ```bash
> ssh autodl-comfyui 'find /autodl-fs/data/comfyui-models -type f -printf "%s\t%p\n" | sort -k2'
> # 引用关系对照(本地):
> grep -rhoE '"[^"]*\.(safetensors|gguf|onnx|bin|pt)"' tools/_comfyui/workflows/ | sort -u
> ```

状态标记:🟢 在用(有 API 模板引用 + 已 GPU 验收)/ 🟡 在用待验收 / 🆕 已下载、模板未建 / 🔵 冷存(API 模板在,模型只在 duolaiduo 备份盘,实例上没有)

## 一、总览

| 目录 | 体积 | 主要内容 |
|---|---|---|
| diffusion_models | 93.5G | H3×2、Krea2、Flux2 Klein、Wan2.2 Animate、Wan-Animate-2 |
| text_encoders | 39.7G | H3 用 Qwen3-VL-32B、Krea2 用 heretic、Klein 用 Qwen3-8B、UMT5×2 |
| qwen-tts | ~16.1G | Qwen3-TTS 三变体 + 声音库 |
| loras | 12.5G | 各视频/图像模型的加速与功能 LoRA |
| vae | 6.4G | H3 视频/音频 VAE、flux2-vae、Wan 系 VAE×2、qwen_image_vae |
| sam3 | 3.2G | SAM3 语义抠图 |
| detection | 2.4G | VitPose 姿态 + YOLO 人体检测(Animate 预处理) |
| controlnet | 1.9G | Uni3C(Animate 相机控制) |
| clip_vision | 1.2G | CLIP Vision-H(Animate 参考图编码) |
| nlf | 0.5G | 辅助模型(节点包用) |
| **合计** | **≈177.4G** | 按配额 200G 计,余量约 22.6G ⚠️(见第四节) |

## 二、按功能组明细

### H3 视频组(EP29/32/35,合计 ~62.0G)

| 文件 | 大小 | 用途 | 引用模板 | 状态 |
|---|---|---|---|---|
| diffusion_models/h3/fastvideo_fasth3_8step_v2_pruned_int8_convrot | 20.61G | FastH3 快速视频主模型 | `minimax_fasth3_t2v` / `i2v` / `fflf` | 🟢 |
| diffusion_models/h3/minimax_h3_ref2va_pruned_int8_convrot | 19.53G | H3 标准版(口型/多参考) | `minimax_h3_audio_sync` 等 | 🟢 |
| text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq | 14.61G | H3 专用文本编码器 | H3 全系 | 🟢 |
| vae/minimax_h3_video_vae_fp16 | 4.85G | H3 视频 VAE | H3 全系 | 🟢 |
| vae/minimax_h3_audio_vae_fp32 | 0.56G | H3 音频 VAE | H3 含音频输出 | 🟢 |
| loras/h3_turbo_4step(名称含 turbo 4step) | 1.82G | H3 提速 LoRA | EP32 系 | 🟢 |

### Flux2 Klein 组(EP09/27,合计 ~17.6G)

| 文件 | 大小 | 用途 | 引用模板 | 状态 |
|---|---|---|---|---|
| diffusion_models/flux2/flux-2-klein-9b-kv-fp8 | 9.14G | Klein 9B KV 主模型(多图合成/编辑主力) | `flux2_klein_4ref` / `flux2_klein_outpaint` | 🟢 |
| text_encoders/qwen_3_8b_fp8mixed | 8.07G | Klein 专用文本编码器 | 同上 | 🟢 |
| vae/flux2-vae | 0.31G | Flux2 VAE | 同上 | 🟢 |
| loras/pixaoutpaint(klein9b 外绘 LoRA) | 0.12G | EP27 外绘专用 | `flux2_klein_outpaint` | 🟢 |

### Krea 2 组(EP24/30,合计 ~20.1G)

| 文件 | 大小 | 用途 | 引用模板 | 状态 |
|---|---|---|---|---|
| diffusion_models/krea2/krea2_turbo_int8_convrot | 12.57G | Krea 2 文生图主模型(INT8) | `krea2_low_vram` / `krea2_extra_pass` | 🟢 |
| text_encoders/qwen3-vl-4b-heretic_int8 | 4.50G | Krea2 组文本编码器(heretic 社区封装) | krea2 全系 | 🟢 |
| vae/qwen_image_vae | 0.24G | Krea2 组 VAE | krea2 全系 | 🟢 |
| loras/krea2_identity_edit_v1_2 | 1.70G | 编辑 LoRA | `krea2_edit_lora` | 🟡 |
| loras/krea_outfittransfer | 1.06G | 服装迁移 LoRA | `krea2_outfit_transfer` | 🟡 |

### Wan 2.2 Animate 组(EP06,动作迁移主力,合计 ~36.0G)

| 文件 | 大小 | 用途 | 引用模板 | 状态 |
|---|---|---|---|---|
| diffusion_models/wan2.2/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2 | 16.13G | Animate 主模型(KJ v2 封装) | `wan22_animate_character` | 🟢 |
| text_encoders/umt5-xxl-enc-fp8_e4m3fn | 6.27G | Wan2.2 文本编码器(Kijai 版) | `wan22_animate_character` / `wan_scail_character` | 🟢 |
| loras/Wan21_PusaV1 | 4.57G | Pusa 动作增强 | 同上 | 🟢 |
| detection/vitpose_h_wholebody(data.bin + onnx) | 2.37G | 姿态预处理 | Animate 预处理链 | 🟢 |
| controlnet/Wan21_Uni3C_controlnet_fp16 | 1.86G | 相机控制 | Animate 可选 | 🟢 |
| loras/WanAnimate_relight | 1.34G | 重打光 | Animate 后处理 | 🟢 |
| clip_vision/clip_vision_h | 1.18G | 参考图外观编码 | Animate 预处理链 | 🟢 |
| loras/lightx2v distill | 0.69G | 蒸馏提速 | Animate 可选 | 🟢 |
| loras/FastWan | 0.59G | 提速 | Animate 可选 | 🟢 |
| loras/Lightning | 0.57G | 提速 | Animate 可选 | 🟢 |
| loras/Fun-InP | 0.09G | 局部重绘 | Animate 可选 | 🟢 |
| detection/yolov10m.onnx | 0.06G | 人体检测 | Animate 预处理链 | 🟢 |
| vae/wan_2.1_vae | 0.24G | Wan 系 VAE(小写名版) | animate / scail / wan22 i2v / t2v | 🟢 |

### Qwen3-TTS 组(EP07,合计 ~16.1G)

| 文件 | 大小 | 用途 | 引用模板 | 状态 |
|---|---|---|---|---|
| qwen-tts/Base(变体目录,内含 model.safetensors ~3.59G + model.1 0.64G + speech_tokenizer 0.64G) | ~4.9G | 基础合成 | `qwen3_tts_custom_voice` 等 4 条 | 🟢 |
| qwen-tts/CustomVoice(同构三件) | ~4.9G | 预设说话人 | 同上 | 🟢 |
| qwen-tts/VoiceDesign(同构三件) | ~4.9G | 声线设计 | `qwen3_tts_voice_design` | 🟢 |
| qwen-tts/Tokenizer-12Hz | 0.64G | 音频 tokenizer | 全系 | 🟢 |
| qwen-tts/voices/old_man_v2.json / treeelf_cherry.json | 极小 | 已克隆声线库(项目自有) | `qwen3_tts_clone_load` | 🟢 |

### InfiniteTalk 组(EP06 长口型,合计 ~6.5G,主模型冷存)

| 文件 | 大小 | 用途 | 引用模板 | 状态 |
|---|---|---|---|---|
| text_encoders/umt5_xxl_fp8_e4m3fn_scaled | 6.27G | UMT5(Comfy-Org scaled 版) | `wan_infinitetalk_extend` / wan22 i2v / t2v(后两者整条冷存) | 🟢(文件在盘;LongCat 升级可直接复用两版之一) |
| vae/Wan2_1_VAE_bf16 | 0.24G | InfiniteTalk 用 VAE | `wan_infinitetalk_extend` | 🟢 |
| (主模型 wan2.1_infiniteTalk_single_fp16) | — | 长口型主模型 | 同上 | 🔵 仅 duolaiduo |

### SAM3 抠图组(EP08,合计 ~3.7G)

| 文件 | 大小 | 用途 | 引用模板 | 状态 |
|---|---|---|---|---|
| sam3/sam3.pt | 3.21G | SAM3 语义抠图 | 抠像链路(EP08-02) | 🟢 |
| nlf/ | 0.47G | 节点包辅助模型 | 节点内部 | 🟢 |

### Wan-Animate-2(🆕 未验收,15.51G)

| 文件 | 大小 | 用途 | 引用模板 | 状态 |
|---|---|---|---|---|
| diffusion_models/wan_animate_2_int8_convrot.safetensors(根目录) | 15.51G | Wan-Animate-2 INT8 主模型(backlog 储备项:写实动作换代) | **无**(模板未建) | 🆕 2026-10-13 下载完成(日志 FAILED=0);预处理模型(vitpose/yolo/clip_vision)可复用 Animate 组,文本编码器可复用 UMT5 |

## 三、模板引用但实例没有的模型(🔵 冷存,均在 duolaiduo 权威备份)

| 模型 | 所属链路 | 说明 |
|---|---|---|
| wan2.1_infiniteTalk_single_fp16 | `wan_infinitetalk_extend` | 长口型主模型;LongCat 转正后整条退役 |
| wan2.2 i2v/t2v 全家(high/low noise + lightx2v loras,~31G) | `wan22_i2v_4step` / `wan22_t2v_4step` | 通用文/图生视频,已由 H3 取代 |
| scail/Wan21-14B-SCAIL-preview | `wan_scail_character` | SCAIL 1 代;2 代见 EP23 |
| z-image/z-image-turbo-q4_k_s.gguf | `z_image_turbo_gguf` | Krea 故障备用 |
| seedvr2_ema_7b_fp8 | `seedvr2_upscale` | 超分备用 |
| sd_xl_base、ae、clip_l、ema_vae、my_lora | Getting Started 系(UI 演示) | 课程入门件,生产不用 |
| flux2-dev-nvfp4、flux2 klein int8、mistral_3_small | flux2-dev 链路(draft) | 被 KV fp8 版取代 |
| qwen-4b-zimage-heretic-q8、wav2vec2-chinese | z-image / infiniteTalk 配套 | 随主模型冷存 |

## 四、存储余量(⚠️ 与升级计划冲突,需拍板)

- 2026-10-13 升级计划的口径:已用 154G、余 47G、计划下载 38.05G(SA3 9.73 + LongCat 20.60 + IndexTTS 7.72)。
- 本轮实测:≈177.4G。差额 ≈23G 正好对上 10-13 新下的 **wan_animate_2(15.51G)+ umt5 scaled 版(6.27G)+ 零头**。
- 即:若配额确为 200G,余量约 22.6G,**装不下 38.05G 的下载计划**。取舍见仓库整理方案(wan_animate_2 是头号回收候选);也请顺手在 AutoDL 控制台核实文件存储配额口径。

## 五、变更记录

| 日期 | 变更 | 备注 |
|---|---|---|
| 2026-10-13 | +wan_animate_2_int8_convrot 15.51G(根目录) | 下载日志 FAILED=0,模板未建 |
| 2026-10-14 | 本清单建立 | 无卡模式实测 78 个文件 |
