# 「故事→剧本→分镜」+「参考视频→剧本」全链路路线图

> 状态：一期实施中 · 管线 `story-to-storyboard`（beta）
> 简版进度一览见 [`story-to-storyboard-status.md`](story-to-storyboard-status.md)（一眼看进度，随实施更新）。
> 本文档为详版路线图：调查结论、架构决策、三期划分、实施清单、风险与缓解。

---

## 1. 目标

1. **正向链路**：故事（故事蓝图/寓言文案/自由文本）→ 剧本 → 分镜，一步到位产出可直接喂生成链的分镜资产。
2. **反向链路（本地版）**：参考视频 → 本地分析（video_analyzer 栈）→ 剧本骨架 + 结构模板，可回用为正向输入。
3. 双产物契约：**scene_plan 是分镜唯一权威（canonical）**，storyboard.json 是单向下变换导出格式（t2i/i2v 提示词，直接喂 ComfyUI 生成链）。
4. 深度嵌入 OpenMontage：全治理体系（manifest 自动发现、checkpoint 4 道人审门、Backlot 看板、decision_log、StudioBinder 路由）。

## 2. 调查结论（摘要）

### 2.1 外部工具

| 类别 | 代表 | 结论 |
|---|---|---|
| 反向视频理解 API | [TwelveLabs Pegasus](https://www.twelvelabs.io/pricing)（输入 $1.75/小时 + 输出 $7.50/1M tokens，送 600 分钟免费额度）；[Gemini video understanding](https://ai.google.dev/gemini-api/docs/pricing)（视频 ~66 tokens/帧 @1fps，混合约 $0.009/分钟） | 单视频成本几美分级，成本不是障碍；放二期的真正理由是**范围控制**（一期不翻倍）+ **先验证本地版精度是否够用** |
| 正向 SaaS | Storyflow / Drawstory / Katalist / LTX Studio / 知剧AI / LibTV | 订阅黑盒；本地方法论（StudioBinder 13 门课 + Qdrant 检索）不输且可追溯 → 不采用 |
| GitHub | [zenstory-ai/drama-skills](https://github.com/zenstory-ai/drama-skills)（流程设计已吸收）；BrightWayAI/video-analyzer 等 | 与本地 video_analyzer 同构，砖块已有 |

### 2.2 本地资产（直接复用）

| 资产 | 位置 | 链路角色 |
|---|---|---|
| StudioBinder 13 门课 | Qdrant 三域，受控检索器 `course_agent_retrieve.py --domain storytelling/cinematography`，身份 `openmontage-project-agent` | Dan Harmon 故事环、Master Scene 六元素、镜头表字段全集（方法与证据分离：Skill Hub 出方法，Qdrant 出证据） |
| pixaroma 提示词公式包 | `03资源/YouTube课程/pixaroma/.../提示词公式/` | H3 EP35 三字段契约（三期采用） |
| SC 故事卡 + 故事蓝图模板 | `03资源/故事创作/故事卡片/`、`07产出/小故事/来电人陈美珍/故事蓝图.md` | 故事输入与 story_brief 模板（一期验收用例） |
| video_analyzer + video-reference-analyst | `tools/analysis/`、`skills/meta/video-reference-analyst.md` | 反向链路的分析引擎（已存在，零新增） |
| 用户级四件套 | `~/.claude/skills/{copy-to-storyboard-json, script-blueprint-writer, script-team-orchestrator, image-prompt-writer}` | 规则吸收源（blueprint 八字段、t2i/i2v lint、voice 规则、跨场景一致性）。**本体保留独立可用，OpenMontage 吸收版为生产权威** |
| 对标文案分析库 | `03资源/对标文案分析/`（11 博主） | 一期结构模板（structure_template）提炼范本 |

> 附注：Pinecone MCP 插件 key 已失效（401），与本链路无关——向量库即 Qdrant 检索体系。如需修 Pinecone 到 app.pinecone.io 重新生成 key。

## 3. 架构总览

```
新管线 story-to-storyboard（beta，规划终点管线）
  story_intake → script → scene_plan → storyboard_export   [human gate ×4]
   ├─ story 模式：故事蓝图/寓言文案/自由文本 → story_brief
   └─ reference 模式（一期即含，本地版）：video_analyzer → video_analysis_brief
        → brief-to-beat-bridge（确定性映射）→ beat/骨架 → 复用 script/scene_plan 阶段填充
  终态双产物：① scene_plan（canonical，checkpoint/Backlot 治理）
             ② storyboard.json（t2i/i2v 提示词，喂 ComfyUI 生成链）

制作交接（三期）：scene_plan 续跑 animation / character-animation 出成片
```

### 核心原则

1. **scene_plan 为分镜唯一权威，storyboard.json 是单向下变换导出格式**——创作 truth 与渲染约束分离：渲染约束（单镜头 ≤5s、7 情绪枚举、t2i 单句英文无禁字符、i2v 四类锚点）只存在于导出层，不绑架创作层的 shot_language/narrative_role 词表。
2. **复用在组件层，manifest 层新建**——director 方法/Skill Hub/Qdrant/checkpoint 基建全部复用；pipeline manifest 新建，不动 cinematic；`pipeline_loader` 按 glob 自动发现，零代码注册。
3. **四件套规则吸收 + 校验移植**（`lib/storyboard_export.py`），运行时不依赖 `~/.claude`；来源标注 `absorbed_from` + 快照日期。
4. **全本地优先**；外部付费 API 为二期实验位（无 key 自动降级本地栈）。

## 4. 三期划分

### 一期：双向闭环 MVP（正向为主 + 反向本地版）

**目标**：故事进来出分镜双产物；参考视频进来（本地分析）也能出剧本骨架与分镜。

**范围**：
- 正向：4 阶段管线 + script schema 加性扩展 + story_brief / storyboard_export 两 schema + `lib/storyboard_export.py` 校验库 + EP/4 director + references 规则吸收 + StudioBinder 路由 + 知识源登记 + `scripts/export_storyboard_json.py`
- 反向本地版（+3 文件）：`skills/meta/brief-to-beat-bridge.md`（确定性映射）+ story-intake-director 反向分支 + manifest 激活 `reference_reverse` 条件子阶段
- 结构模板库首批：从对标文案分析库提炼 2-3 个 structure_template（若超时可滑到二期）

**出口标准**：
1. 「来电人陈美珍/故事蓝图.md」端到端跑通 4 阶段，4 checkpoint 全部 awaiting_human 并逐门批准
2. 四个 artifact 全过 schema 校验；导出 storyboard.json 过全部吸收规则（emotion∈7 枚举、停顿标记、≤5s、t2i 单句无禁字符、i2v 四类锚点）；scene_plan 与 storyboard.json 一一溯源
3. 任一对标分析库视频（本地栈）反推出剧本骨架 + structure_template，模板可回用为正向 blueprint 输入
4. Backlot 看板正确显示；既有 tests/contracts 全量回归无失败
5. 两份文档落库（本文档 + 简版进度一览）

### 二期：外部 API 实验 + 导出打磨（按需启动）

**目标**：量化外部 API 相对本地版的精度增量，值得才付费；补齐机械打磨。

**范围**：
- TwelveLabs Pegasus / Gemini video understanding 接入为 EXPERIMENTAL 工具（TwelveLabs 送 600 分钟免费额度，实验基本零成本；Gemini 单视频几美分）——无 key 自动降级本地栈 + 成本记录进 decision_log
- 精度对比：取 3-5 个对标视频，本地版 vs API 版的镜头切分/时间戳/语义描述对照，结论写入本文档
- 自动拆长镜（>5s 按停顿标记/句读切分，子镜重编号）；storyboard_json → scene_plan 宽松导入（可选）
- structure_template 模板库扩充

**出口标准**：精度对比结论落文档；API 采用/弃用决策记 decision_log；自动拆镜过 golden 测试。

### 三期：生态整合（长期）

**范围**：
- scene_plan 续跑 animation / character-animation 出成片（successor_pipelines 续传约定）
- treeelf-story-creator 可选接入（显式登记，不做自动路由）
- pixaroma H3 三字段契约加性扩展（integrated_multimodal_description / overall_soundscape / non_diegetic_music）
- video_understand 逐镜回验

**出口标准**：寓言双角色文案 → 分镜 → 成片一条龙演示。

## 5. 关键决策（已批准）

| # | 决策 | 理由 |
|---|---|---|
| 1 | **加性扩展现有 `script.schema.json`**：顶层可选 `beat_map[]`；section 可选 `visual_intent` / `emotion` / `character_dialogue[]`；version 保持 "1.0" | 剧本是中间产物，消费方要旁白+画面意图+情绪+节拍而非 Master Scene 交付；对既有 12 条管线零影响（纯可选字段） |
| 2 | **scene_plan canonical + 单向下变换导出**；反向转换器（storyboard→scene_plan 伪造字段）否决 | 渲染约束不绑架创作层；反向转换必然伪造 shot_language 等创作字段 |
| 3 | **新建管线不动 cinematic** | pipeline_loader 按 glob 自动发现，零代码注册；制作端三期续跑现有管线 |
| 4 | **四件套规则吸收 + 校验移植**（`lib/storyboard_export.py`），本体保留 | OpenMontage 运行时不依赖 `~/.claude`；用户级本体独立可用不受影响 |
| 5 | **付费 API 进二期且先本地后付费** | 成本非障碍（单视频<$1），真正理由是范围控制 + 本地版精度需求验证 |

## 6. 一期实施清单

**修改文件**

| 路径 | 改动 |
|---|---|
| `schemas/artifacts/script.schema.json` | 加性扩展（决策 1） |
| `schemas/artifacts/__init__.py` | ARTIFACT_NAMES 追加 `story_brief`、`storyboard_export` |
| `config/studiobinder-stage-routing.yaml` | 新增 `pipelines.story-to-storyboard` 段（script/scene_plan 复用 cinematic 已验证 slug） |
| `docs/treeelf-knowledge-sources.md` | 登记 07产出消费方式、四件套吸收来源与权威声明、storytelling 域检索指引 |

**新增文件**

| 路径 | 内容 |
|---|---|
| `production-planning/STORY_TO_STORYBOARD_ROADMAP.md` | 本文档 |
| `production-planning/story-to-storyboard-status.md` | 简版进度一览 |
| `pipeline_defs/story-to-storyboard.yaml` | 4 stages 全 gate；reference_reverse 条件子阶段 |
| `schemas/artifacts/story_brief.schema.json` | source/SC卡引用、premise、characters、emotional_arc、hook/turn/landing、target_duration、tone、寓言扩展字段 |
| `schemas/artifacts/storyboard_export.schema.json` | scenes[{scene_id、scene_plan_scene_id、emotion、narration、t2i_prompt、i2v_prompt、duration_seconds}]、metadata |
| `skills/pipelines/story-to-storyboard/executive-producer.md` | EP 编排 |
| `skills/pipelines/story-to-storyboard/{story-intake,script,scene,storyboard-export}-director.md` | 4 阶段 director（story-intake 含反向分支协议） |
| `skills/pipelines/story-to-storyboard/references/{prompt-rules,i2v-prompt-rules,voice-rules,consistency-checklist}.md` | 四件套规则吸收（标注 absorbed_from + 快照日期 2026-10） |
| `skills/meta/brief-to-beat-bridge.md` | 反向确定性映射协议（shot_language 子集映射表等） |
| `lib/storyboard_export.py` | 校验/合并纯库（移植 build_storyboard_json.py 规则） |
| `scripts/export_storyboard_json.py` | CLI：读 scene_plan+storyboard_export → 校验 → 写 `projects/<name>/exports/storyboard/{theme}/{theme}.json` |
| `tests/contracts/test_story_to_storyboard_pipeline.py` | manifest 校验、fixture 过 schema、导出 golden 测试、规则校验器单测、brief-to-beat 映射测试 |

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| script schema 扩展波及既有管线 | 纯加性可选字段 + version 不变；全量契约回归 |
| 规则双源漂移（四件套 vs OpenMontage 吸收版） | absorbed_from + 快照日期；OpenMontage 版为生产权威 |
| ≤5s 约束 vs 长镜头 | 创作约定 + 转换器硬校验；`--max-shot-seconds` 参数化；二期自动拆镜 |
| 7 情绪枚举过窄 | narrative_role→7类映射表 + director 覆盖 + decision_log |
| 反向桥接的视觉富化质量不稳 | 失败 → 用户口述参考 → 标准 creative-intake 兜底 |
| Skill Hub MCP 不可用 | 沿用 studiobinder-skill-hub.md Step7 降级路径 |
| 一期范围含反向后膨胀 | 反向仅 3 文件且出口标准只有 1 条（验收 3）；若实施中超时，反向模板库可滑到二期 |
