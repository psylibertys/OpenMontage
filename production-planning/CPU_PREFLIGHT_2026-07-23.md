# AutoDL ComfyUI 无卡最终预检

日期：2026-07-23

## 结论

无卡阶段已完成，可以切换 GPU 模式进行串行验收。当前不需要继续下载模型，也不需要安装新的自定义节点。

## 连接与安全

- AutoDL 专用 Ed25519 密钥免密登录验证通过；
- Mac SSH 别名：`autodl-comfyui`；
- ComfyUI 仅监听远端 `127.0.0.1:8188`，Mac 通过 SSH 本地端口转发访问；
- 无卡检查时设备类型为 `cpu`，队列运行中 0、等待中 0；
- `/object_info` 共返回 1924 个节点类型，Nunchaku 节点为 0。

## 模型与磁盘

- Krea 2 diffusion、Qwen3-VL text encoder 和 Qwen Image VAE 在位；
- Z-Image GGUF 备用模型在位；
- Flux 2 Klein diffusion、Qwen 8B text encoder 和 Flux VAE 在位；
- InfiniteTalk、Wan Animate、SCAIL 所需主体模型在位；
- 数据盘 250GB，已用约 176GB，剩余约 75GB；
- 没有模型下载进程，没有待清理清单。

## Workflow 预检

- 活动 API 模板：15；
- 节点、模型枚举、输出节点全部通过：15/15；
- SeedVR2 的 `SeedVR2LoadDiTModel` 与 `SeedVR2LoadVAEModel` 在无卡模式无法完成 GPU 初始化，已明确延后到 GPU 阶段验证；这不是模型缺失。

机器可读报告：

- `projects/comfyui-gpu-acceptance-20260723/artifacts/cpu-preflight.json`
- `projects/comfyui-gpu-acceptance-20260723/artifacts/gpu-acceptance-dry-run.json`

## 验收夹具

夹具统一保存于：

`projects/comfyui-gpu-acceptance-20260723/assets/`

已准备：

- 人物主参考图与四张一致性参考图；
- 4096×4096 人脸 Inpaint 遮罩；
- 8.832 秒基础配音；
- 34.992 秒 InfiniteTalk 延长版配音；
- Wan Animate/SCAIL 驱动视频。

17 组验收配置会展开为 20 次串行运行。第一项是 Krea 默认竖版，最后一项是 SeedVR2 回归。

## 远端资产清理

无卡预检前发现远端历史运行目录有 26 个输入、输出和临时文件，约 98MB。已经：

1. 完整同步到本地 `assets/remote-preflight-archive/`；
2. 本地与远端逐文件核对 SHA-256；
3. 校验一致后清空远端 `input/`、`output/`、`temp/`。

## GPU 阶段操作

1. 结束无卡实例并切换 GPU 模式；
2. 启动 ComfyUI，仍只监听 `127.0.0.1:8188`；
3. 重新建立 SSH 隧道；
4. 再跑一次 `/object_info`，确认 SeedVR2 节点加载；
5. 确认 GPU 设备、空队列与至少 50GB 剩余空间；
6. 使用 `scripts/run_comfyui_gpu_acceptance.py --yes` 串行执行；
7. 每个成品完成本地下载、大小与 SHA-256 校验后，再删除服务器输入、输出和临时文件；
8. 任何失败立即停止，不自动关机。
