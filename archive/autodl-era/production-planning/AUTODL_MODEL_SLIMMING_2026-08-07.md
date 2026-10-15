# AutoDL ComfyUI 冷模型精简与恢复说明

日期：2026-08-07（Asia/Shanghai）

> 路由限制：本文不是ComfyUI任务的常规必读文档。只有明确使用或恢复Z-Image、SeedVR2、Wan Animate、SCAIL，或排查这4条模板缺模型时才读取；普通Krea、Qwen3-TTS、Flux、Wan 2.2 I2V和InfiniteTalk任务不要加载本文。

## 结果

- 精简前模型：153个文件，181,569,648,075字节；
- 精简后模型：117个文件，105,695,194,684字节；
- 删除的20个主体模型：75,874,452,210字节；
- 数据盘：从约95%占用、10GiB可用，降至约53%占用、92GiB可用；
- 同时删除数据盘内不再使用的旧`ComfyUI-Easy-Install`副本（约10.88GB）和`downloads`安装缓存（约336MB）；
- 系统盘正式ComfyUI、`wheelhouse`、运行时目录和所有保留模型均未删除。

删除前已再次通过只读SSH核对duolaiduo：以下20个主体文件全部存在，合计字节数与AutoDL源文件完全一致。完整备份曾于2026-07-29完成153/153 SHA-256校验，详见`AUTODL_MODEL_BACKUP_2026-07-29.md`。

## 长期恢复源

新Agent需要恢复冷模型时，不要默认重新从Hugging Face下载，先从duolaiduo权威备份恢复：

- 管理端真实目录：`/media/data/ai-models/comfyui/models/`；
- Mac管理SSH别名：`duolaiduo-qdrant`；
- 只读SFTP账号：`model-sync@duolaiduo.psynaut.cn:2222`；
- Mac只读私钥：`/Users/treeelf/.ssh/id_ed25519_autodl_model_sync`；
- SFTP chroot中的模型目录：`/models/models/`；
- AutoDL目标目录：`/root/autodl-tmp/comfyui-models/`；
- SHA-256总清单：`/media/data/ai-models/comfyui/checksums/autodl-models-sha256-20260729.tsv`；
- 路径与大小清单：`/media/data/ai-models/comfyui/manifests/autodl-model-files-20260729.tsv`。

恢复必须保持相对路径，使用支持断点续传的传输方式；传输后先按清单核对大小和SHA-256，再启动ComfyUI做对应workflow预检。不要通过SSHFS让ComfyUI跨公网直接加载模型，也不要把家庭服务器长期私钥复制到AutoDL。若需要duolaiduo主动推送到AutoDL，应使用一次性密钥并在完成后双端撤销。

## 已冷迁模型

### Z-Image：8.951GB

影响：`z_image_turbo_gguf`保持注册但当前不可运行。默认生图继续使用Krea；只有用户明确要求恢复Z-Image时才同步以下文件：

```text
diffusion_models/z-image/z-image-turbo-q4_k_s.gguf
text_encoders/qwen-4b-zimage-heretic-q8.gguf
vae/ae.safetensors
```

### SeedVR2：8.968GB

影响：`seedvr2_upscale`保持注册但当前不可运行。重点图确需SeedVR2放大时同步：

```text
SEEDVR2/ema_vae_fp16.safetensors
SEEDVR2/seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors
```

`.validation_cache.json`是可重建缓存，不需要恢复。

### Wan Animate与SCAIL：57.956GB

影响：`wan22_animate_character`和`wan_scail_character`保持注册但当前不可运行。普通静帧动态化继续使用`wan22_i2v_q6`。需要精确动作迁移时，按所选workflow恢复对应主体模型及共享姿态组件。

```text
diffusion_models/wan2.2/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors
diffusion_models/scail/Wan21-14B-SCAIL-preview_fp8_e4m3fn_scaled_KJ.safetensors
text_encoders/umt5-xxl-enc-fp8_e4m3fn.safetensors
clip_vision/clip_vision_h.safetensors
controlnet/Wan21_Uni3C_controlnet_fp16.safetensors
detection/vitpose_h_wholebody_data.bin
detection/vitpose_h_wholebody_model.onnx
detection/yolov10m.onnx
sam3/sam3.pt
nlf/nlf_l_multi_0.3.2.torchscript
loras/wan2.2/FastWan_T2V_14B_480p_lora_rank_64_bf16.safetensors
loras/wan2.2/Wan2.2-Fun-A14B-InP-LOW-HPS2.1_resized_dynamic_avg_rank_15_bf16.safetensors
loras/wan2.2/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors
loras/wan2.2/Wan21_PusaV1_LoRA_14B_rank512_bf16.safetensors
loras/wan2.2/WanAnimate_relight_lora_fp16.safetensors
```

`loras/wan2.2/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors`仍在AutoDL，因为InfiniteTalk也使用它，不得重复恢复或误删。`vae/wan_2.1_vae.safetensors`同样作为Wan 2.2 I2V共享资产保留。

## 当前常驻生产模型

以下能力仍可直接使用：

- Krea 2默认生图与重点图增强；
- Qwen3-TTS四条配音/声音克隆流程及两个正式声音包；
- Flux 2 Klein四参考图人物一致性与局部重绘；
- Wan 2.2 I2V短视频；
- InfiniteTalk短版和显式延长版；
- LightX2V共享LoRA。

任何Agent在提交任务前仍应根据所选workflow做模型存在性预检。不要因为模板仍注册就假定冷模型已驻留。
