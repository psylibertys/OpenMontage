# AI 短剧技术方案调研报告(2026-10-13)

> 调研方式:4 个并行调研 Agent 网络检索(前沿视频模型 / 国内短剧生态 / 工作流编排 / 数字人表演与音频),官方页面直抓 + 中英文交叉验证,共 100+ 次检索。
> 对照基线:本项目现行栈 = ComfyUI(AutoDL 4090D 24G)+ MiniMax FastH3/H3(2026-10-12 换代)+ Krea 2 + Flux2 Klein 4ref + Qwen3-TTS + InfiniteTalk/Wan-Animate/SCAIL + SeedVR2 + Remotion + ACE-Step。

## 一、总体结论

**你们的主线已经站在 2026 年 10 月的正确位置上。** 调研独立得出的"自建最优解"——开源 MiniMax H3 + ComfyUI 官方支持 + 原生音画——正是你们 10 月 12 日刚落地的架构。不存在"放弃自建、全面转云"的理由;"更先进的方式"体现在**管线内模型换代、编排层升级、混合云 API** 三个方向,而非推倒重来。

**Sora 之死是最强佐证**:OpenAI Sora 2 产品 2026-04-26 关停、API 2026-09-24 移除且无替代。押注单一闭源产品的流水线会一夜归零;自建 + 按需混合才是抗风险结构。

## 二、行业格局:三条路线与你们的定位

| 路线 | 代表 | 优势 | 劣势 |
|---|---|---|---|
| 平台一体化(业界主流) | 即梦 Seedance 2.5、可灵、Vidu、剪映 | 零运维、模型永远最新、直连平台扶持 | 按条计费、深度受控、无法沉淀资产 |
| 云 API 按需采购 | Kling 4.0 / Seedance 2.5 / Veo 3.1 API | 画质天花板、单段 30s、4K | 成本随量线性涨、角色库/分镜控制弱 |
| ComfyUI 自建(进阶量产) | 你们 + 社区 FLUX+Wan/H3 组合 | 单条边际成本最低、无水印、工作流/LoRA/角色包全自有 | 需自行跟进模型迭代 |

爆款实证:《山海奇镜》《新世界加载中》等全生成动画爆款全部用可灵官方模型——**开源与闭源旗舰在画质/物理合理性上仍有差距**;但量产团队遇积分贵、水印、一致性失控时会回落到 ComfyUI 自建。隐性主流是**混合**:正片产能走自建,重镜头/宣传物料按需买 API。

## 三、前沿模型横向对比(2026-10 现役)

| 模型 | 最新版 | 多镜头/一致性 | 原生音频/口型 | 时长/分辨率 | 价格要点 | 开源? |
|---|---|---|---|---|---|---|
| ~~Sora 2~~ | 已关停(App 2026-04 / API 2026-09) | — | — | — | — | 已死 |
| Veo 3.1(Google) | 2025-10 | Flow Ingredients 参考图 | 对白+音效+BGM | 8s、1080p | Vertex $0.15-0.40/条 | 闭源 |
| **Kling 4.0**(快手) | 2026-10 | **10 关键帧 + 15 参考素材** | 音画同生、中英口型 | **单次 3-30s**、4K+10bit HDR | 国内铂金 266 元/月≈300 条;API ~$0.10-0.2/s | 闭源,**官方 MCP/CLI** |
| **Seedance 2.5**(字节) | 2026-07-31 | 一镜成片+分层引用 | 音画同生 | **30s+两次续写** | ~1.5-2.1 元/s(720P) | 闭源(即梦/火山) |
| **海螺 H3**(MiniMax) | 2026-07-31 | 多模态参考 | 立体声+口型 | 15s、**2K 直出** | API 2K $0.13/s;**本地自建近零边际** | **开源 + ComfyUI 官方支持** |
| Wan 3.0(阿里) | 2026-08 | 全模态输入 | 音画同生 | 30s 1080p | 未公布 | **开源止步 2.2** |
| Vidu Q3/Q4(生数) | Q4 已上官网 | 多主体参考 | 四音轨直出 | 16s | 未核实 | 闭源 |
| LTX-2.5(Lightricks) | 2026-01 | 可微调 | 音视频一体(14B+5B) | ~20s、4K@50fps | 本地免费 | **开源** |
| Gen-4.5(Runway) | 2025-11 | — | 无原生音频 | 2-10s | 12 credits/s(上代 2.4 倍) | 闭源 |

关键事实:
- **原生音画(对白+口型+音效)已是 2026 旗舰标配**——"TTS→生成→对口型"三步正在被一步生成替代,但仅闭源 API 侧完整;开源侧 H3/LTX-2 跟进。
- **Wan 开源线已分叉**:GitHub 官方组织核验,开源止于 2.1/2.2(2025-07),2.5/2.6/3.0 全部 API-only。你们已切 H3,判断正确。
- Kling 4.0 官方提供 **MCP + CLI**,可被 Agent 批量驱动——与自动化流水线最契合的云 API。

## 四、对你们管线的分级升级建议

### A. 管线内模型换代(全部开源,多数已进 ComfyUI,不换架构)

| 现用 | 升级目标 | 增量 | 依据 |
|---|---|---|---|
| InfiniteTalk(长口型) | **LongCat-Video-Avatar-1.5**(美团,MIT) | 同团队换代:Whisper-Large 口型编码、分钟级无色漂、8 步蒸馏+INT8 降本 | github.com/meituan-longcat/LongCat-Video |
| SCAIL(卡通动作) | **SCAIL-2**(智谱,Apache 2.0) | 端到端免姿态预处理、多参考角色一致、**已并入 ComfyUI 官方主仓库**(PR #14373/#14509);长片用社区 auto-extend/infinity 节点 | github.com/zai-org/SCAIL-2 |
| Wan-Animate(写实动作) | **Wan-Animate-2**(阿里,Apache 2.0) | 端到端直接消费驱动视频、14B、Lite 实时流式;官方 ComfyUI 集成已完成 | github.com/Wan-Video/Wan-Animate-2 |
| Qwen3-TTS(主力,保留) | **补 IndexTTS-2.5**(B 站,0.8B) | 情感表演级控制:情感参考音频+强度 emo_alpha+台词自动情感推断;4090 RTF 0.2;商用需邮件 bilibili 确认 | github.com/index-tts/index-tts |
| SeedVR2 | **SeedVR2.5** | Topaz 社区评"当前世界第一"视频修复 | HF Demo 720p/121 帧 |
| ACE-Step | **ACE-Step 1.5** | 开源最强本地音乐,社区评"超几乎所有商业方案" | 13472 星 |
| (音效若用 MMAudio) | **HunyuanVideo-Foley** | ⚠️ MMAudio 权重 CC-BY-NC **非商用**,商用必须换 | github.com/Tencent-Hunyuan/HunyuanVideo-Foley |
| Flux2 Klein 4ref(保留) | **并行试点 Nano Banana 2.1**(Google,ComfyUI Partner Nodes 直连) | 14 张参考图混融保角色、4K、免训练、指令式编辑;2026 分镜一致性新主流,比训 LoRA 低一个数量级成本 | blog.comfy.org 2026-10-06 |

### B. 编排层升级(官方 2026 年 8-10 月新能力)

- **官方 Comfy MCP**(comfy.org/mcp):让外部 Agent(Claude/director 体系)直接生成图/视频/音频、搜索节点模板、运行工作流——补齐你们 director 体系与 ComfyUI 之间的执行层缺口;
- **Comfy Router**(2026-09-23):一个 API 接入全部前沿模型,本地/云按任务自选——"开源权重 + 闭源 API 混编"的官方通道;
- **Comfy Agent**(2026-10-01)/ **Comfy API**(2026-09-30):对话式建工作流、工作流一键生产化。
- ⚠️ 四项均为 2026 Q3-Q4 刚发布,**生产采用前先小规模试用**。第三方 ComfyDeploy 已于 2026-01 关闭,生态向官方收敛,长期维护风险在下降。

你们的"多导演 Agent + YAML 流水线"与国际 2026 共识架构(剧本 Agent → 镜头分解 → ComfyUI 执行(MCP)→ 资产组装 → 审片队列)同构,属先进形态。

### C. 混合云 API(重镜头按需外包,不迁主管线)

- **Kling 4.0**:10 关键帧+15 参考素材+单次 30s+4K,官方 MCP/CLI 可编排——多镜头连贯叙事最强云选项;
- **Seedance 2.5**:30s+两次续写+分层引用;绑定即梦/抖音 AIGC 短剧扶持(单部投资 50-70%);
- **Veo 3.1**:画质/物理标杆,首尾帧+延展,$0.15-0.40/条,适合封面级物料;
- **海螺 H3 API**:与本地同一模型,本地排队溢出时弹性上云,风格零差异。

### D. 硬件

AutoDL **5090 32GB ¥2.88/时**(会员 ¥2.74)vs 现用 4090D 24G(~¥1.88-2.68/时):H3 显存峰值实测 ~22GB 贴边,5090 跨过 24GB 门槛且时租仅贵约 1 元——建议下次换代/扩产时切 5090,继续"开机即生产、生产完即关机"。AutoDL 价格仍是全球洼地(海外 H100 ~$2/时 vs 国内 ¥12),无需换平台。

### E. 分发变现与合规(发布侧)

- 2025-09-01 起 AI 生成内容**强制显式+隐式双标识**;
- 2026-07-01 起 AI 微短剧专项分类分层:**投资 <30 万一般题材走"其他微短剧"平台播前审核**,小成本负担较轻;
- 变现主渠道是平台投资/流量分成而非付费点播:《兴安岭诡事》抖音付费收入仅 ~30 万;抖音辰星最高投资 70%、即梦+抖音 AIGC 招募 50-70%、红果果燃 5 亿(主推真人,**严打 AI 肖像侵权**——AI 真人风在红果有合规风险)。

## 五、不要动的部分

- **Remotion 合成、director 体系、AutoDL 成本模型**:2026 年仍是正确选择;
- **Qwen3-TTS 主力声线**:开源第一梯队(生态 13757 星),无需更换;
- **Flux2 Klein 4ref 角色包资产**:H3 多模态参考时代,首图质量更关键,Flux 管线价值反而上升。

## 六、许可证雷区清单

| 模型 | 许可证 | 状态 |
|---|---|---|
| MiniMax H3 | 排除区=欧盟/英/韩/美,中国大陆免版税商用;年收入 >$2000 万需邮件授权;产出不得在排除区展示 | 已知悉 |
| MMAudio | 权重 CC-BY-NC | **商用禁用** |
| Qwen Image 2.1 | Qwen Research License(非商用) | 已在挡门外 |
| IndexTTS-2.5 | bilibili Model Use License | 商用前邮件确认 |
| Fish Audio S2 Pro | Research License | 不建议引入 |
| LongCat / SCAIL-2 / Wan-Animate-2 / LTX-2 | MIT / Apache 2.0 / Apache 2.0 / 开放 | 无障碍 |

## 七、未核实事项(诚实边界)

- Kling 4.0 各档精确积分表;国内版 3.0/4.0 功能口径差异(官网栏目 vs 发布页);
- Wan 3.0、Vidu Q4 官方单价与规格;
- Seedance 2.5 的 1.5-2.1 元/秒为第三方 token 折算,非官方直接标价;
- Artificial Analysis 2026-10 Elo 榜单快照多次抓取失败,本报告不含第三方排名;
- 《兴安岭诡事》制作方身份;快手星芒 AI 专项扶持细则。

## 八、建议的下一步(最小验证顺序)

1. **零成本立即可做**:在 ComfyUI 接入官方 MCP,让现有 director 体系直连(纯编排层,不动模型);
2. **下次 GPU 会话顺带 smoke**:IndexTTS-2.5 情感表演轨 A/B(对照 Qwen3-TTS 同台词盲测)、ACE-Step 1.5;
3. **下一个换代窗口**:InfiniteTalk → LongCat-Video-Avatar-1.5、SCAIL → SCAIL-2(同场景长口型/动作戏质量天花板);
4. **按项目选配**:重点短剧的关键镜头(开场钩子/高潮)用 Kling 4.0 或 Seedance 2.5 API 外包,成本 30-60 元/条量级;
5. **硬件**:扩产时切 5090。

## 附:主要信源

- blog.comfy.org(Comfy Agent/API/Router/MCP,2026-08~10)/ comfy.org/mcp
- openai.com/index/sora-2(Sora 关停声明,2026-04-26)
- blog.google(Veo 3.1,2025-10-15)/ aistudio.google.com/models/veo-3
- kling.ai/release-note/release-notes/Kling_4(2026-10)
- seed.bytedance.com/zh/seedance_2_5(2026-07-31)/ platform.minimax.io/docs/guides/pricing-paygo
- github.com/Wan-Video(组织 API 核验)、github.com/meituan-longcat/LongCat-Video、github.com/zai-org/SCAIL-2、github.com/Wan-Video/Wan-Animate-2、github.com/index-tts/index-tts
- cac.gov.cn(标识办法,2025-09-01 施行)/ nrta.gov.cn(分类分层)/ news.cctv.com(2026-06-26 AI 微短剧标准)
- tidenews.com.cn(山海奇镜)、ebrun.com(2025-10-27 AI 真人短剧)、tvoao.com(2025-05-20 辰星/即梦招募)
- autodl.com + 知乎/SegmentFault(GPU 价格,2026-03~07)/ runpod.io/pricing
