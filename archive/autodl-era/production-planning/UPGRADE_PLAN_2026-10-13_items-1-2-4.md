# 升级计划:音效 / 长口型 / 配音表演轨(条目 1、2、4)

日期:2026-10-13 · 状态:**待用户确认**(确认后按 Phase B → Phase C 执行)
前置文档:`RESEARCH_2026-10-13_ai-short-drama-tech.md`(调研)、`COMFYUI_AGENT_CONTEXT.md`(现行状态)
下载清单:`AUTODL_UPGRADE_1_2_4_HF_SOURCES_2026-10-13.tsv`(54 文件,含 HF LFS sha256)

## 一、三项最终方案

| 条目 | 现状 | 升级方案 | 下载量 | 许可证 | 风险 |
|---|---|---|---|---|---|
| 1 音效 | 无音效能力(ACE-Step 只做 BGM;MMAudio 从未用过但商用禁用,永久挡在门外) | **Stable Audio 3 Medium**,走课程 EP19 `txt2audio` 工作流 | 9.7GB | Community License,年收入 <$1M 免费商用,产出归用户 | gated 仓,下载需 HF token |
| 2 长口型 | InfiniteTalk(>15s 独白唯一选项,Wan2.1 时代,分钟级会色漂) | **LongCat-Video-Avatar-1.5 INT8**(美团,MIT;社区节点 rookiestar28/ComfyUI-LongCat-Avatar) | 20.6GB(+UMT5 6.3 条件项) | MIT 无障碍 | **24G 单卡未验证**,GPU smoke 门禁 |
| 4 配音表演 | Qwen3-TTS 单轨(情感控制有限) | **IndexTTS-2.5** 表演轨(节点 chenpipi0807/ComfyUI-Index-TTS 763★;模型包 t8star/IndexTTS-2.5-Comfy) | 7.7GB | bilibili 许可证:MAU<1亿且年收入<10亿 **无需申请**,保留版权声明即可 | 低 |

关键取舍:
- **LTX-2 否决**(原条目 2 候选):官方 ComfyUI 支持要求 32GB+ VRAM,现行 LTX-2.5 22B 全家约 66GB;课程里的 19b-fp8 是社区重封装非官方。4090D 24G 跑不动,挂起至 5090 时代再评。
- **SA3 不下 Gemma4**(省 8GB):Gemma4 在课程工作流里只做"短提示词→丰富音频描述"的扩写,这活由 Agent 直接写好提示词替代。基础 `txt2audio.json` 只需 2 个模型文件,引用名已从工作流 JSON 核实:`stableaudio3\stable_audio_3_medium.safetensors` + `t5gemma_b_b_ul2.safetensors`。
- **IndexTTS 不替换 Qwen3-TTS**:Qwen3 仍是旁白/主力声线;IndexTTS 定位"人物对白表演轨"(情感参考音频 + emo_alpha 强度 + 台词自动情感推断),以 A/B 盲测决定转正。
- **ACE-Step 1.5 升级本轮不做**:SA3 先补音效短板,音乐升级留下一轮,避免摊子过大。

## 二、存储预算(文件存储 200G,现用 154G,余 47G)

| 组 | 体积 |
|---|---|
| Stable Audio 3(checkpoint 8.59 + t5gemma 1.10) | 9.73GB |
| LongCat INT8(基座 14.79 + dmd_lora 2.35 + whisper 2.88 + VAE 0.47 + 人声分离 0.06) | 20.60GB |
| IndexTTS-2.5 全包 | 7.72GB |
| 小计(固定) | **38.05GB → 余 ~8.9G** |
| UMT5-XXL fp8(备选项) | +6.27GB → 最坏余 ~2.7G |

**UMT5 复用已核实(2026-10-13 本地确认)**:舞蹈最小集已含 Kijai 版 `text_encoders/umt5-xxl-enc-fp8_e4m3fn.safetensors`(6.73G,`wan22_animate_character`/`wan_scail_character` 模板在用)。LongCat 节点大概率可直接复用;仅当节点只认 Comfy-Org scaled 版(`umt5_xxl_fp8_e4m3fn_scaled`)时才补下 6.27G。**预算按 38.05G 锁定,本次升级不需要删除实例上任何现有模型。**

另核实:文件存储 154G 全部为在用资产(H3/Krea/TTS 组 102.5G + 舞蹈集 60.6G),无可删项;已废弃链路(wan22_i2v_q6、infinitetalk_short、klein_inpaint)的模型只存在于 duolaiduo 权威备份,不占实例空间。

## 三、执行分阶段

### Phase B:无卡会话(白天跑,学术加速满速 21-29MiB/s;约 2-4 小时,~¥0.3)

1. **用户控制台开无卡机**;SSH 端口每次开机变化,先对齐 `~/.ssh/config`;
2. ComfyUI `--cpu` detached 启动(无卡模式必须带 `--cpu`,start 脚本会拒绝无 GPU);
3. LongCat 节点装好后先试复用实例已有 Kijai 版 umt5-xxl-enc-fp8;不认再补 Comfy-Org scaled 版 → 生成 aria2 输入(out= 带子目录路径并对唯一性断言,吸取 2026-10-09 清单 bug 教训);
4. 下载三组:LongCat/IndexTTS/UMT5 走学术加速或 hf-mirror;**SA3 需 HF token**(gated=auto,aria2 `--header` 带 Bearer);
5. `sha256sum -c` 全量校验(对 HF LFS oid);
6. 装节点:`ComfyUI-Index-TTS`、`ComfyUI-LongCat-Avatar`(gh-proxy 克隆);SA3 用核心内置节点(CheckpointLoaderSimple + CLIPLoader type=stable_audio + EmptyLatentAudio + VAEDecodeAudio,核对核心 e8665ca8/0.39.0 是否已含,缺则升级核心);Pixaroma 包 v1.4.206 已含 SaveAudioMP3;
7. `extra_model_paths.yaml` 增 `checkpoints`、`clip` 两键映射到文件存储;
8. UI→API 模板转换(浏览器 fetch→loadGraphData→graphToPrompt 管线,--cpu 可用):
   - EP19 `txt2audio.json` → `stableaudio3_sfx`
   - LongCat 节点仓示例 workflow → `longcat_avatar_extend`(目录对齐节点 README)
   - IndexTTS 节点示例 → `indextts25_emotion`(t8star 包落节点指定目录)
9. 无卡 preflight(新增模板的 CPU 枚举差异按 FastH3 先例判读);
10. duolaiduo 经 hf-mirror 备份 manifest;无卡关机。

### Phase C:GPU 会话(与记忆修理店 b3 剩余 + b4 合并开机,预计 4-6 小时,~¥8-16)

1. 开机 → start 脚本 → 隧道 → preflight;
2. 欠账先还:`krea2_edit_lora` / `krea2_outfit_transfer` 两条 smoke(约 5 分钟);
3. b3 剩余组:character_pack 2 + krea 9 + flux 7 → 角色人审门禁;
4. 新模板 GPU smoke:
   - SA3:音效 2 条(如关门闷响、雨夜环境底)+ 环境底 1 条;
   - IndexTTS:对白 1 条(情感参考模式);
   - **LongCat:30 秒长口型 1 条(显存判定时刻)**;
5. b4 视频批照计划执行(22 镜两段式 + 3 口型单轮 + s21→22 fflf);
6. IndexTTS vs Qwen3-TTS 同台词 A/B 素材 5 组(素材在会话内生成,盲听在关机后离线做);
7. `finalize_autodl_comfyui_batch.py` 门禁 → `sync; shutdown -h now`。

## 四、验收与回退

| 项 | 转正标准 | 回退方案 |
|---|---|---|
| LongCat | 30s 视频不 OOM(INT8+offload);口型稳定性/色漂显著优于 InfiniteTalk 同素材 | 保留 InfiniteTalk,LongCat 标注"5090 复测";wan_infinitetalk_extend 路由不动 |
| SA3 | 音效进入 Remotion 混音链可用;与 ACE-Step 分工明确(SA3=音效/环境声,ACE-Step=BGM) | 不涉及回退,能力新增 |
| IndexTTS | 用户盲听 5 组对白,情感表现 ≥3 组胜出 → 转正"对白表演轨" | 不转正则保留为实验模板,对白继续 Qwen3 |

全部转正后另行提交:注册表 19→22 条、`COMFYUI_AGENT_CONTEXT.md` 路由表更新、`wan_infinitetalk_extend` 冷存迁移评估。

## 五、风险与未定项

1. **SA3 gated**:唯一需要用户动作的下载项。途径 A:用户 HF 账号同意条款后提供 token(aria2 --header 注入);途径 B:授权找社区搬运仓(按 2026-10-08 sam3 先例,逐字节比对 size/sha256)。
2. **LongCat 24G 单卡**:官方示例为双卡;INT8 + 文本编码器 offload 后社区有零星单卡成功报告但未系统验证。smoke 失败即走回退,不恋战。
3. 存储最坏 44.3/47G,贴极限;UMT5 复用则 38.1G 安全。
4. ComfyUI 核心 0.39.0 若缺 SA3 节点类型,现场升级核心(低风险,10-12 刚升过)。
5. whisper-large-v3 只下 `model.safetensors`(fp16,2.88G),不下 fp32 分片/flax/pytorch_model.bin 重复件;LongCat 基座只下 INT8 分片,不下 bf16 全量(29.5G,不装)。

## 六、需要用户确认/操作的事

1. **方案确认**:回"同意"或指出调整(尤其:LTX-2 挂起、SA3 不下 Gemma4、IndexTTS 定位表演轨而非替换);
2. **无卡开机时机**:确认后白天开无卡机(学术加速白天 8-29MiB/s,晚高峰跌到 2MiB/s),开好说一声即可;
3. **SA3 的 HF token**(途径 A)或授权走镜像(途径 B)。

## 七、本轮未选的储备项(backlog,按触发条件排)

> 来源:调研报告第四节分级建议 + 2026-10-13 Pixaroma 课程盘点(EP01-37 中项目未消费课次)。此处集中存档,防对话丢失。

| 储备项 | 内容 | 触发条件 | 依赖 |
|---|---|---|---|
| SCAIL-2(原条目 3) | 卡通动作换代,端到端免姿态预处理,已并入 ComfyUI 官方主仓库;课程 EP23 在库 | 下一轮升级窗口 | Apache 2.0 ✓ |
| ACE-Step 1.5 | 音乐生成升级(本轮明确延后,SA3 先补音效) | SA3 验收转正后 | 本地,无许可障碍 |
| Wan-Animate-2 | 写实动作换代(14B,Lite 实时流式,官方 ComfyUI 集成已完成) | wan22_animate 出现质量瓶颈时 | Apache 2.0 ✓ |
| SeedVR2.5 | 重点图修复放大升级 | 现用 SeedVR2 不够用时 | 待核实 |
| Nano Banana 2.1 试点 | Google 付费 API(~$0.045-0.24/张),14 参考图混融,分镜一致性新主流 | 有关键角色一致性项目 + 接受按张付费 | 付费 API + 网络代理 |
| Kling 4.0 / Seedance 2.5 混合云 | 重镜头按需外包(开场钩子/高潮),Kling 官方 MCP/CLI 可编排 | 重点短剧预算允许时 | 付费 API(30-60 元/条量级) |
| Comfy 官方 MCP / Router | 编排层试点,让 director 体系直连 ComfyUI(零成本,不动模型) | 随时 | 官方 2026 Q3-Q4 新品,先小规模试用 |
| 5090 32G 切换 | 下次扩产/换代时;同时重评 LTX-2(官方门槛 32GB+ 压线) | 文件存储腾挪空间不足或 H3 再换代时 | ¥2.88/时 |
| EP29.4 H3 生图 | 课程工作流在库(Minimax H3 Text to image / Image Edit / Low VRAM t2v) | 需要文生图新选项时 | 模型已大概率复用现有 H3 组 |
| EP33/34 多视角 3D | Trellis2 / Pixal3D 多视角生成,四视图转面表质量提升 | flux4ref 角色包质量瓶颈时 | 待核实许可证 |
| 发布合规 | 2025-09-01 起 AI 内容双标识;2026-07-01 微短剧分类分层(投资 <30 万走"其他微短剧"平台播前审核) | 首次平台发布前 | 政策,详见调研报告 E 节 |
