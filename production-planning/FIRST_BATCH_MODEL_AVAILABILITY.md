# 第一批 ComfyUI Workflow 模型可用性核验

> 核验日期：2026-07-22
> 核验范围：AutoDL.Art 公共模型库只读搜索、家庭服务器模型主库准备；未创建 AutoDL 实例、未映射模型或安装 ComfyUI
> 当前结论：公共库对第一批 workflow 的有效覆盖接近 0，不足以作为选择 AutoDL.Art 的理由

## 1. 判定口径

- **有效命中**：文件名或官方仓库一致，文件体积与模型规模合理，可放入 workflow loader 预期目录。
- **伪命中**：名称相似，但实际是训练适配器、脚本、索引、小型 ZIP 或其他非完整权重。
- **未命中**：精确文件名搜索没有结果。
- **待补查**：本轮没有取得明确搜索结果；不计入有效命中。

## 2. 核验结果

| Workflow | 所需模型或仓库 | 预期角色/目录 | 公共库结果 | 判定与理由 |
|---|---|---|---|---|
| Qwen3-TTS | `Qwen/Qwen3-TTS-Tokenizer-12Hz` | tokenizer，`models/qwen-tts/` | `Qwen3-TTS-Tokenizer-12Hz.zip`，4.10KB | **伪命中**：体积不可能包含 tokenizer 权重 |
| Qwen3-TTS | `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` | CustomVoice，`models/qwen-tts/` | 两个同名 ZIP，1.59MB / 1.73MB | **伪命中**：1.7B 模型至少是数 GB 级，MB 级 ZIP 不是完整权重 |
| Qwen3-TTS | `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` | VoiceDesign，`models/qwen-tts/` | 同名 ZIP，1.72MB | **伪命中**：不是完整 1.7B 权重 |
| Z-Image Turbo | `z-image-turbo-q4_k_s.gguf` | diffusion model | 无精确匹配 | **未命中** |
| Z-Image Turbo | `qwen-4b-zimage-heretic-q8.gguf` | text encoder | 无精确匹配 | **未命中** |
| Z-Image Turbo | `ae.safetensors` | VAE | 未取得明确结果 | **待补查**；同名很多，必须核对是否来自 `Comfy-Org/z_image_turbo` |
| Krea 2 | `krea2_turbo_fp8_scaled.safetensors` | diffusion model，约 12.2GB | 仅出现 `krea2_turbo_training_adapter_v1.safetensors`，218MB | **伪命中**：这是 training adapter，不是 Krea 2 base model |
| Krea 2 | `qwen3vl_4b_fp8_scaled.safetensors` | text encoder，约 4.8GB | 无精确匹配 | **未命中** |
| Krea 2 | `qwen_image_vae.safetensors` | VAE，约 242MB | 无精确匹配 | **未命中** |
| Wan 2.2 I2V | `wan2.2_i2v_A14b_high_noise_lightx2v_4step-Q6_K.gguf` | high-noise diffusion model | 无精确匹配 | **未命中** |
| Wan 2.2 I2V | `wan2.2_i2v_A14b_low_noise_lightx2v_4step-Q6_K.gguf` | low-noise diffusion model | 无精确匹配 | **未命中** |
| Wan 2.2 I2V | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` | text encoder | 无精确匹配 | **未命中** |
| Wan 2.2 I2V | `wan_2.1_vae.safetensors` | VAE | 无精确匹配 | **未命中** |
| SeedVR2 | `seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors` | upscale model | 无精确匹配 | **未命中** |
| SeedVR2 | `ema_vae_fp16.safetensors` | VAE | 无精确匹配 | **未命中** |

## 3. 覆盖率

- 第一批共计 15 项模型/仓库要求。
- 已明确核验 14 项：**0 项有效命中**，4 项伪命中，10 项未命中。
- 另有 `ae.safetensors` 1 项待补查。
- 即使 `ae.safetensors` 最终有效命中，覆盖率也只有 `1/15`，不改变平台选择。

## 4. 渠道决策

### 当前推荐：AutoDL.com + 课程作者的 Easy Install 路线

理由：

1. AutoDL.Art 公共模型映射是其主要便利点之一，但本批核心模型没有获得有效覆盖。
2. 选择 AutoDL.Art 后仍需自行下载或上传几乎全部大模型，公共库没有实质节省数据盘和部署时间。
3. 课程作者使用 `ComfyUI-Easy-Install`，在标准 AutoDL 实例上复现同一套目录、节点和依赖更容易排查课程 workflow 问题。
4. 第一批涉及 Qwen3-TTS、GGUF、Krea 2、Wan 2.2 和 SeedVR2，多种自定义节点与版本约束；自行控制 ComfyUI 版本、Python 环境和数据盘比依赖现成 Art 镜像更重要。
5. AutoDL.com 的公共数据目录可以作为偶发辅助来源，但不能当作本批精确模型清单的可靠替代品；正式生产仍应把已验证模型保存到自己的数据盘。

### AutoDL.Art 仍可保留的用途

- 临时测试它已有的、能够精确命中的其他 workflow；
- 后续公共库新增本批模型时重新评估；
- 若现成 ComfyUI 镜像能显著缩短一次性试验，可作为实验环境，但不作为第一批正式生产环境。

## 5. 下一步边界

在用户批准前，继续保持只规划、不创建实例、不安装。下一步应先形成：

1. 每个模型的官方来源 URL、许可证、文件体积和目标目录；
2. 第一批模型总存储量与 300GB/500GB 数据盘预算；
3. AutoDL.com 实例镜像、GPU、系统盘和数据盘的最终配置单；
4. Easy Install、ComfyUI CLI、自定义节点和 workflow 的分阶段安装顺序；
5. 下载失败与模型源不可用时的镜像/缓存兜底方案。

## 6. 第一批数据盘容量计算

以下体积来自课程 workflow 指定文件及对应 Hugging Face 仓库的文件元数据。`GB` 为十进制容量，云平台磁盘界面通常使用该口径；括号中给出操作系统常见的 `GiB` 口径。

| 模型组 | 文件构成 | 精确合计 |
|---|---|---:|
| Qwen3-TTS | Tokenizer + 1.7B CustomVoice + 1.7B VoiceDesign | 9.72GB（9.05GiB） |
| Z-Image Turbo | Q4_K_S diffusion + Q8 text encoder + VAE | 8.95GB（8.34GiB） |
| Krea 2 | FP8 diffusion + Qwen3-VL 4B FP8 + VAE | 18.64GB（17.36GiB） |
| Wan 2.2 I2V | high-noise Q6_K + low-noise Q6_K + UMT5 FP8 + VAE | 31.02GB（28.89GiB） |
| SeedVR2 | 7B mixed FP8/FP16 + VAE | 8.97GB（8.35GiB） |
| **第一批模型总计** | 15 项模型/仓库要求 | **77.30GB（71.99GiB）** |

Qwen3-TTS 的 9.72GB 按自定义节点默认下载三个完整仓库计算。CustomVoice 和 VoiceDesign 仓库各自包含 speech tokenizer，独立 Tokenizer 仓库又包含一份，因此这里保留重复占用，不把尚未验证可否安全去重的空间提前扣除。

### 非模型空间预算

| 用途 | 建议预留 |
|---|---:|
| ComfyUI、Python 环境、PyTorch、自定义节点 | 20GB |
| Hugging Face、pip、Git 与下载临时缓存 | 35GB |
| 输入图片、配音、workflow、日志 | 10GB |
| 视频生成中间帧、临时视频和放大结果 | 80GB |
| 已完成素材与近期项目产出 | 40GB |
| 文件系统与故障重试安全余量 | 35GB |
| **非模型空间合计** | **220GB** |

模型 77.30GB 加非模型预算 220GB，得到约 **297GB**。

### 容量档位结论

| 数据盘 | 结论 |
|---|---|
| 200GB | 不推荐；能放模型和环境，但 Wan/SeedVR2 中间帧与缓存很容易把盘写满 |
| **300GB** | **第一阶段推荐起步容量**；覆盖第一批全部模型和少量短视频并行制作，但需要定期清理缓存与中间帧 |
| **500GB** | **长期生产推荐**；适合保留多个项目、第二套量化模型和逐步进入第二批人物/口型能力 |

上述结论适用于“全部模型长期保存在实例本地盘”的独立部署。采用下节的家庭主库与 AutoDL 文件存储分层后，本地盘可以进一步缩减。

## 7. 家庭服务器与云存储分层方案

### 家庭服务器条件

`duolaiduo` 的 `/media/data` 约有 13TiB，当前占用很低，并已有公网域名、SSH、DDNS 和 Tailscale，因此完全可以保存 ComfyUI 模型的权威副本。建议未来使用独立目录：

```text
/media/data/ai-models/comfyui/
├── qwen-tts/
├── diffusion_models/
├── text_encoders/
├── vae/
├── seedvr2/
├── manifests/
└── checksums/
```

家庭服务器适合作为长期主库和备份源，但**不建议让 ComfyUI 通过家庭公网直接挂载并读取模型**。Safetensors/GGUF 文件为 4–13GB，公网延迟、断线和家庭上行带宽会拖慢加载，SSHFS/FUSE 在容器实例中也可能受限。正确方式是先按需同步到 AutoDL 本地 SSD，再由 ComfyUI 本地加载。

### 四类存储比较

以第一批 77.30GB 模型、每月完整拉取一次为基准，以下不含 GPU 实例费：

| 方案 | 保存 77.30GB 的成本 | 完整拉取一次 | 优点 | 主要问题 |
|---|---:|---:|---|---|
| 家庭服务器 | 边际存储费约 0 | 家庭宽带通常无按量流量费 | 已有 13TiB、容量最大、完全可控 | 取决于家庭上行速度；慢速同步会浪费 GPU 开机时间 |
| AutoDL 文件存储 | 约 17.19元/月：`(77.3-20)×0.01×30` | 同地区复制，无对象存储外网流出费 | 自动挂载、实例间共享、多副本、模型一次上传长期使用 | 网络盘 IO 一般，运行前仍应复制到本地 SSD；默认总容量 200GB |
| 阿里云 OSS 标准存储 | 约 9.28元/月 | 约 19.33元（闲时）或 38.65元（忙时） | 工具成熟、稳定，AutoDL 官方上传文档直接推荐 OSS | AutoDL 通常通过公网 Endpoint 拉取，外网流出按量收费；重复拉取成本高 |
| 百度智能云 BOS 标准存储 | 约 9.20元/月 | 约 19.33元（闲时）或 37.88元（忙时） | 兼容 S3，适合 rclone/SDK 自动化 | 与 OSS 类似，需要支付公网流出；成本优势很小 |

费用按公开按量价格估算：OSS 标准本地冗余约 0.12元/GB/月、外网流出示例为闲时 0.25元/GB/忙时 0.50元/GB；BOS 标准存储约 0.119元/GB/月、外网流出闲时 0.25元/GB/忙时 0.49元/GB。实际地域、资源包和活动价格可能变化，以购买页面为准。

个人版百度网盘/阿里云盘可用于人工搬运，AutoDL 官方也将其列为上传方式，但不建议作为正式自动化模型仓库：它们不是面向服务器工作负载的对象存储，命令行/API、限速、断点续传和权限控制不如 OSS/BOS/SSH 稳定。

### 当前推荐架构

```text
duolaiduo 13TiB 家庭服务器
  └─ 权威模型库、SHA256、manifest、灾备
          ↓ 首次或版本更新同步
AutoDL 文件存储 /root/autodl-fs（约 80GB）
  └─ 第一批模型的云端运行镜像
          ↓ 每次只复制当前 workflow 所需模型
AutoDL 本地 SSD /root/autodl-tmp（150GB）
  └─ ComfyUI 热模型、输入、中间帧和当前产出
```

推荐理由：

1. 家里服务器承担长期低成本存储，AutoDL 本地盘故障或释放实例后仍可恢复。
2. AutoDL 文件存储解决家庭上行速度不确定、每次启动 GPU 等待几十 GB 下载的问题。
3. 本地 SSD 只保存当前 workflow：单组最大是 Wan 2.2 的 31.02GB，不必同时保留全部 77.30GB。
4. ComfyUI 不直接读取网络盘，避免模型加载和视频处理中断。
5. OSS/BOS 暂不作为必需层；只有家庭上行过慢、AutoDL 文件存储不可用或需要异地第三份灾备时再开通。

### 修订后的本地数据盘建议

- 不使用任何远程/共享模型仓库：本地数据盘仍建议 300GB。
- 使用“家庭服务器 + AutoDL 文件存储 + 本地热缓存”：本地数据盘建议 **150GB**。
- 极限节省可尝试 100GB，但 Wan 2.2 加视频中间帧时较紧，不作为默认配置。

家庭上行带宽会影响是否可以省略 AutoDL 文件存储。传输完整 77.30GB 的理论时间约为：20Mbps 需 8.6小时、50Mbps 需 3.4小时、100Mbps 需 1.7小时、200Mbps 需 52分钟，实际还要考虑协议损耗和公网波动。

#### 2026-07-22 家庭服务器实测

通过 SSH 在 `duolaiduo` 上使用内存零数据流访问 Cloudflare 测速端点；未安装软件、未写入磁盘。本次合计产生约 225MiB 上行测试流量。

| 测试 | 结果 |
|---|---:|
| 单连接上传 25MiB | 22.11秒，约 9.5Mbps |
| 四连接并发上传 4×25MiB，第1轮 | 24秒，聚合约 35.0Mbps |
| 四连接并发上传 4×25MiB，第2轮 | 23秒，聚合约 36.5Mbps |

结论：家庭公网总上行可按 **35–36Mbps 实效、40Mbps 标称**规划，但单连接吞吐明显较低。完整传输 77.30GB 的理论时间约 4.8小时，实际建议按 5.5–6.5小时估算。后续同步应使用多文件并发、断点续传和 SHA256 校验，避免单路 SCP/SFTP 长时间占用；首次部署仍优先让家庭服务器与 AutoDL 分别从官方模型源下载，家庭上行只承担私有模型和灾备恢复。

### 安全边界

- 不使用现有日常 SSH 账号作为 AutoDL 自动同步账号；后续应建立只读、限定模型目录的专用账号和独立密钥。
- 不公开目录浏览，不把模型做成无认证公网直链。
- 当前服务器 UFW 为 inactive，实施前必须先核对路由器 NAT 与公网暴露面。
- 推荐优先测试 Tailscale；若 AutoDL 容器不支持所需网络模式，再使用密钥认证的受限 SFTP/rsync。
- 同步后校验 SHA256，只有校验通过的文件才进入 ComfyUI 模型目录。

## 8. 家庭服务器只读模型账号（已配置）

> 配置日期：2026-07-22
> 状态：读取、拒绝写入、拒绝 Shell 三项验收通过

| 项目 | 配置 |
|---|---|
| SSH/SFTP 用户 | `model-sync` |
| 公网入口 | `duolaiduo.psynaut.cn:2222` |
| 登录方式 | 仅 Ed25519 公钥；密码与交互式认证关闭 |
| 客户端私钥 | `/Users/treeelf/.ssh/id_ed25519_autodl_model_sync`，权限应保持 `0600` |
| 公钥指纹 | `SHA256:UzPUClSQWr6hZBLnG2YXps0DzUQDCH+KkJgCOwaZN50` |
| SFTP 初始目录 | `/models` |
| 服务器真实目录 | `/media/data/ai-models/comfyui` |
| 隔离方式 | `/srv/model-sync` Chroot + `/models` 只读 bind mount |
| SSH 限制 | 强制 `internal-sftp -R`；无 Shell、TTY、端口转发、Agent 转发、Tunnel 或 X11 |

服务器已创建与 ComfyUI 对齐的空目录：

```text
/media/data/ai-models/comfyui/
├── models/
│   ├── qwen-tts/
│   ├── diffusion_models/{z-image,krea2,wan2.2}/
│   ├── text_encoders/
│   ├── vae/
│   ├── SEEDVR2/
│   └── loras/
├── manifests/
└── checksums/
```

验收结果：

- 使用专用密钥通过 SFTP 登录后，默认位于 `/models`；
- 能读取上述目录；
- 上传测试返回 `Permission denied`，未生成测试文件；
- 尝试通过 SSH 执行 `id` 返回 `This service allows sftp connections only.`；
- 只读挂载由 systemd 持久化，当前状态为 active，挂载参数包含 `ro`。

注意：当前密钥无口令，目的是供 AutoDL 自动化读取；风险通过服务端只读 Chroot 和禁用 Shell 限制。私钥不得放入 Git、公开文档或家庭服务器。AutoDL 实例创建后，仅复制到实例的 root 私有目录并保持 `0600`。

## 9. AutoDL 150GB 本地数据盘用途

实际安装核验后，课程 Easy Install、独立 Python/PyTorch、24 个自定义节点、ComfyUI CLI 和 7 个首批 workflow 合计约 11GB，可放入 30GB 系统盘且仍保留约 20GB。最终采用“程序进镜像、模型留数据盘”的分层结构：

- 系统盘：`/root/ComfyUI-Easy-Install`，保存 ComfyUI 本体、Python 环境、节点、CLI 和 workflow；
- 数据盘模型：`/root/autodl-tmp/comfyui-models`，由系统盘 `ComfyUI/models` 软链接接入；
- 数据盘运行目录：`/root/autodl-tmp/comfyui-runtime/{input,output,temp,logs}`，避免生成物撑大镜像；
- 保存私有镜像时仅包含系统盘，约 77.30GB 的第一批模型不会进入镜像。

| 用途 | 预算 |
|---|---:|
| 第一批全部模型 | 77.30GB |
| 当前短视频的输入、音频、参考图和 workflow | 5GB |
| Wan/SeedVR2 中间帧、临时视频和放大结果 | 30GB |
| 当前成片、封面、字幕和待回传素材 | 12GB |
| 断点下载临时文件与安全余量 | 25GB |
| **合计** | **150GB** |

运行规则：

1. 家庭服务器保存长期权威副本，AutoDL 本地盘保存运行副本；
2. 首次部署优先从官方模型源直接下载到 AutoDL，并在家庭服务器独立下载相同文件；
3. 产出完成后回传家庭服务器/OpenMontage，再清理中间帧和下载缓存；
4. 本地盘使用率达到 80% 时停止新任务并清理，不等磁盘写满；
5. 若需要同时保留第二批 LoRA、InfiniteTalk 和人物模型，或长期保留多个项目中间素材，则扩容到 200–300GB。

## 10. 家庭服务器第一批模型下载状态

> 状态时间：2026-07-22
> 当前状态：**后台任务已恢复；小型仓库文件已开始完成，大模型正在通过镜像重试**

已准备服务器端可重入下载任务，目标是让 `duolaiduo` 直接从模型源拉取第一批 77.30GB，避免先下载到 Mac 再上传。任务具备断点续传、完整文件按预期字节数跳过、官方源失败后切换 `hf-mirror`、完成后生成 SHA-256 的设计。

第一次任务曾以 PID `2313638` 启动。发现服务器直连 `huggingface.co:443` 超时后，为避免每个文件重复等待，下载代理无损停止旧进程并生成优化版脚本。审批通道一度因 `stream disconnected` 阻止恢复；用户再次明确授权后，2026-07-22 已成功部署最新版并以新 PID `2319882` 恢复后台任务。

最新版脚本增加了：官方源首次失败后整批记住 `hf-mirror`、`.part` 断点续传、完整文件字节数跳过、SHA-256、收到信号时写入 `interrupted`，以及在状态文件中记录当前来源、当前已下载字节和当前文件期望字节。这样可避免“进程已停但状态仍显示 running”的误判。

当前留存内容：

| 项目 | 路径 / 状态 |
|---|---|
| 服务器当前脚本 | `/media/data/ai-models/comfyui/manifests/first-batch-server-download.sh` |
| 本地优化版脚本 | `production-planning/scripts/first-batch-server-download.sh` |
| 服务器日志 | `/media/data/ai-models/comfyui/manifests/first-batch-download.log` |
| 服务器状态文件 | `/media/data/ai-models/comfyui/manifests/first-batch-download.status` |
| 精确文件清单 | `/media/data/ai-models/comfyui/manifests/first-batch-model-files.tsv` |
| 原进程 | PID `2313638`，已停止 |
| 当前进程 | PID `2319882`，恢复检查时存活 |
| 脚本备份 | `first-batch-server-download.sh.bak.20260722T062903` |
| 已完成 | Qwen Tokenizer 前 4 个小文件，共 7,413 字节；`completed=4`、`failed=0` |
| 当前文件 | `Qwen3-TTS-Tokenizer-12Hz/model.safetensors`，期望 682,293,092 字节 |
| 当前来源 | `hf-mirror.com`；大文件连接曾被对端 reset，curl 正按策略自动重试 |

恢复原则：

1. 通过状态文件和日志观察大模型 `.part` 是否持续增长；
2. 逐文件核对预期字节数和 SHA-256；失败文件保留 `.part` 以便续传；
3. 若 `hf-mirror` 大文件重试全部耗尽，优先更换服务器可达的传输端点或今晚通过局域网管理连接处理，不把 77.30GB 全量先落到 Mac；
4. 只有状态为 `complete` 且 44 个文件全部通过大小/SHA-256 校验，才视为第一批下载完成；
5. 状态为 `running_with_errors` 或 `complete_with_errors` 时，根据失败清单重跑同一可重入脚本，不删除有效断点。

## 11. AutoDL 无卡部署与首批模型验收

> 完成时间：2026-07-22 22:18（Asia/Shanghai）
> 实例模式：无卡模式，0.5 CPU / 2GB RAM
> 结果：**ComfyUI 已迁入系统盘，首批模型 44/44 下载并验收通过**

### 系统盘镜像内容

| 项目 | 验收结果 |
|---|---|
| ComfyUI 安装目录 | `/root/ComfyUI-Easy-Install`，约 11GB |
| 系统盘占用 | 约 11GB / 30GB，剩余约 20GB |
| ComfyUI CLI | 1.12.0 |
| 自定义节点仓库 | 24 个 |
| 首批 workflow | 7 个 |
| Python 入口迁移 | 112 个旧 shebang 已改写为系统盘路径，残留 0 |
| 启停脚本 | `/root/autodl-comfyui-ctl.sh`，自动检测 GPU；新实例可用 `prepare` 创建数据盘目录 |

### 数据盘内容

| 项目 | 路径 / 结果 |
|---|---|
| 模型根目录 | `/root/autodl-tmp/comfyui-models` |
| 运行目录 | `/root/autodl-tmp/comfyui-runtime` |
| manifest 文件数 | 44 |
| 精确验收字节数 | 77,295,972,275 |
| 大小不一致 | 0 |
| SHA-256 记录 | 44 |
| `.part` / `.aria2` 残留 | 0 |
| 数据盘占用 | 约 83GB / 150GB，剩余约 68GB；其中还保留迁移前的 11GB ComfyUI 数据盘副本，GPU 验收前不删除 |

无卡模式使用 `--cpu` 能启动 ComfyUI 并通过 `/system_stats` 健康检查；SeedVR2 节点在完全没有 GPU 后端时会拒绝导入，但它在迁移前的 RTX 4080 SUPER GPU 模式已经成功加载。因此最终仍需以 GPU 模式重启，逐个实跑 7 个 workflow，完成模型加载、显存和实际输出验收后再处理旧数据盘副本。
