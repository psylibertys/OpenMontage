# 树精灵视频制作知识来源地图

本文件告诉 OpenMontage 项目下的所有 Agent：跨 Psynaut 与 OpenMontage 的资料分别是什么、什么时候读取、如何保持来源可追溯。这里不复制课程正文，也不替代课程检索权限。

课程访问使用项目级检索身份 `openmontage-project-agent`。默认 Agent、阶段 Agent 和 `treeelf-video-producer` 都可以直接查询，不需要先调用另一个 Agent。`treeelf-video-producer` 只是可选的用户界面角色，不是知识网关。

## 1. 创作输入：07产出

```text
/Users/treeelf/Desktop/Psynaut/treeElfNotes/07产出/
```

- 这里是已经形成的文章、短视频文案和准发布内容，是视频生产的内容源。
- 默认优先检索 `心哲灵/短视频文案/`。
- 只读使用；原文案不因生产而改写。采用的版本应快照到 OpenMontage 项目工作区。

## 2. StudioBinder：电影制作、导演与故事方法库

Obsidian 根目录：

```text
/Users/treeelf/Desktop/Psynaut/treeElfNotes/03资源/YouTube课程/StudioBinder/
```

它是人类可读的课程学习区，包含课程档案、中文课名、学习顺序、逐课方法、案例、练习和来源定位。当前课程分成两类路由：摄影/导演/制作方法使用 `cinematography`，故事/编剧/剧本方法使用 `storytelling`。

### Skill Hub 与课程检索的分工

OpenMontage 通过用户级 MCP 连接 `treeelf-skill-hub`，使用其中治理的
26 个 StudioBinder 技能。Skill Hub 提供**方法与决策框架**；下面的
Qdrant 检索提供**案例、证据和时间码**。两者不能互相冒充：

- 先读 `skills/meta/studiobinder-skill-hub.md`，按
  `config/studiobinder-stage-routing.yaml` 的 explicit stage mapping 显式选择 slug；
- 默认调用 `skills_invoke(..., compose=false)`，不让 `skills_route` 自动决定生产方法；
- 需要课程依据时，再用 `openmontage-project-agent` 查询对应课程领域；
- 在 artifact/checkpoint metadata 中记录 skill slug、catalog generation、
  content hash 和实际采用的决策；
- 不复制 Skill Hub 技能正文到 OpenMontage，也不修改 Psynaut 中的源技能。

当前自动路由的无泄漏质量门禁尚未通过，因此只能用于探索，不得作为
cinematic pipeline 的自动生产决策器。MCP 不可用时，继续遵守现有阶段
director 和审批门禁，并明确记录降级状态。

| 课程 | 课程 ID | 主要用途 |
|---|---|---|
| 摄影机运动终极指南 | `ytpl_PLEzQZpmbzckWUQALEX8UlbyH2GtRLMrSd` | 固定机位、推拉变焦、跟拍、横摇/俯仰、边走边谈等运镜选择，以及运动的叙事动机。 |
| 电影制作终极指南 | `ytpl_PLEzQZpmbzckVQL5QNLv1XaJW4slV0CMZO` | 特写、全景、慢动作、延时、摄影机支撑、字幕和电影格式等制作语言。 |
| 电影摄影技法 | `ytpl_PLEzQZpmbzckX3A_SopJ-krGsV6BERxdwb` | 灯光、镜头、构图、调度、景别、视觉叙事、摄影风格、镜头清单和现场制作方法。 |
| 影视叙事与故事创作 | `ytpl_PLEzQZpmbzckX-T0iZDy0ZaZLGHbYpeJph` | 故事结构、人物、主题、叙事机制与案例。 |
| 编剧软件操作教程 | `ytpl_PLEzQZpmbzckWlSyAbPoFVFq_nTlURCcq1` | 编剧软件、剧本格式和写作流程。 |
| 导演风格解析 | `ytpl_PLEzQZpmbzckUl3P1gqpM5Awa9U-CxdhVy` | 导演美学、镜头、调度、声音、剪辑与风格迁移。 |
| 影视制作剧本拆解教程 | `ytpl_PLEzQZpmbzckUSHM-c3bSmMpXSONweaneO` | 从剧本拆出场景、元素与制作需求。 |
| 分镜设计精通课 | `ytpl_PLEzQZpmbzckVaRg_LDLTISRBF9qM5aaHZ` | 分镜构图、镜头连续性和视觉规划。 |
| 电影剧本写作精通课 | `ytpl_PLEzQZpmbzckUKajpmx78kS66ipD6_4UfX` | 电影剧本写作与故事设计。 |
| 成片之路：从剧本到银幕 | `ytpl_PLEzQZpmbzckX9umb1yTf-KGNT92u3W66I` | 从剧本、筹备、拍摄到成片的制作链路。 |
| 镜头表：影视镜头制作全指南 | `ytpl_PLEzQZpmbzckV0_a2QCO2qF9Yfe-LKSDha` | 镜头表、景别、机位、覆盖与现场执行。 |
| 剧本构成解析 | `ytpl_PLEzQZpmbzckVYZJOjysgVG6vqBcB7hX_I` | 剧本格式、构成元素和可制作表达。 |
| 你最喜爱的电影人，他们最爱的电影 | `ytpl_PLEzQZpmbzckVCXIZSFl_Na8TA3Ov5tjaY` | 经典影片的导演方法、摄影、剪辑与声音案例。 |

Qdrant 保存中文知识块与中文字幕段，并保留英文证据、时间码和视觉资产引用。摄影类稳定 alias 为 `course_cinematography_active`，故事类稳定 alias 为 `course_storytelling_active`。Agent 不直接访问物理 collection，必须使用受控检索器：

```bash
conda run -n cyber_factory python \
  /Users/treeelf/Desktop/Psynaut/.claude/skills/treeelf-youtube-course-harvest/scripts/course_agent_retrieve.py \
 "QUERY" --agent openmontage-project-agent --domain cinematography \
  --intent knowledge
```

故事或编剧问题把领域改为 `--domain storytelling`。只需要某一套课程时增加 `--course-id COURSE_ID`，避免其他课程干扰。

## 3. Pixaroma：ComfyUI 方法与 workflow 知识库

Obsidian 课程目录：

```text
/Users/treeelf/Desktop/Psynaut/treeElfNotes/03资源/YouTube课程/pixaroma/ComfyUI_Course_-_Learn_ComfyUI_From_Scratch_Pixaroma/
```

Qdrant 领域为 `ai_visual_tools`，用于查询模型、节点、依赖、参数、输入输出、工作流方法和故障排查。原始 UI workflow 位于：

项目 Agent 查询时使用相同的 `openmontage-project-agent` 身份，并将领域改为 `--domain ai_visual_tools`。

```text
/Users/treeelf/Desktop/pixaroma-comfyui-workflow/
```

原始文件用于查看和导入 ComfyUI，不是可直接调用的 API workflow。必须在目标 ComfyUI 中补齐模型和自定义节点、成功运行、导出 API 格式并通过 smoke test，才能标记为 `ready`。

## 4. 如何选择知识来源

- 先看 Obsidian：了解课程覆盖范围、浏览课次、建立连续上下文。
- 再查 Qdrant：回答具体问题、寻找技法、取得中英文证据和 YouTube 时间码。
- 再开视觉资产：判断构图、光线、空间关系、运镜方向、速度、轨迹和剪辑节奏。
- 只有实际打开图片、三联帧或短片段后，才能声称本次视觉证据已核验。
- 课程提炼状态为 `proposed` 时，把它当作有来源的参考，不冒充用户已经确认的规则。

## 5. Agent 何时应主动查询

在以下情况下，不要只凭通用模型记忆决定：

- 不确定某种镜头、运镜、构图、灯光或剪辑方式是否适合当前文案。
- 要把抽象文案拆成分镜、提示词变量、镜头节奏或视觉叙事方案。
- 要解释为什么选择某个 ComfyUI workflow、模型、节点组合或参数。
- 用户要求课程依据、案例、原话、时间码或画面证明。
- 生成结果出现视觉、运动或工作流问题，需要用课程方法诊断。

如果课程没有足够证据，应明确说明；可以提出实机测试，但不能虚构课程结论。

## 6. story-to-storyboard 管线的知识入口

「故事→剧本→分镜」管线（`pipeline_defs/story-to-storyboard.yaml`）按阶段消费知识：

- **story_intake**：故事蓝图来自 `07产出/`（默认优先 `心哲灵/短视频文案/`，小故事系列在 `小故事/`）；故事方法问题查 `--domain storytelling`（故事环、Master Scene 元素、故事结构）。
- **script**：节拍与可观察化方法走 Skill Hub slug（见 `config/studiobinder-stage-routing.yaml` 的 `story-to-storyboard` 段）；案例证据查 `--domain storytelling`。
- **scene_plan**：镜头设计方法走 Skill Hub slug；景别/运镜/灯光依据查 `--domain cinematography`。
- **storyboard_export**：提示词与语音规则已内化为 `skills/pipelines/story-to-storyboard/references/`（不查课程）。
- **reference 反向模式**：先跑 `skills/meta/video-reference-analyst.md` 本地分析栈，再按 `skills/meta/brief-to-beat-bridge.md` 确定性映射。

### 用户级四件套吸收声明

`t2i/i2v/voice` 生成规则与跨场景一致性规则吸收自用户级 skill：

| 吸收源（`~/.claude/skills/`） | 吸收目标 | 权威性 |
|---|---|---|
| `copy-to-storyboard-json`（SKILL.md + references + 校验脚本） | `skills/pipelines/story-to-storyboard/references/{prompt-rules,i2v-prompt-rules,voice-rules,consistency-checklist}.md` + `lib/storyboard_export.py` | **OpenMontage 版为生产权威**（改动先进 OpenMontage，再选择性回移）；用户级本体保留独立可用 |
| `script-blueprint-writer` | story-intake-director 的蓝图八字段映射表 | 同上 |
| `script-team-orchestrator` | references/consistency-checklist.md 的跨场景一致性、局部重试策略 | 同上 |

快照日期 2026-10；各吸收文件头部标注 `absorbed_from`。OpenMontage 运行时不依赖 `~/.claude/skills/`。

### 对标文案分析库

```text
/Users/treeelf/Desktop/Psynaut/treeElfNotes/03资源/对标文案分析/
```

11 位博主的对标拆解，是 structure_template（结构模板）的提炼范本：反向模式产出的模板与正向创作采用的模板都应有可追溯来源；本库只读，提炼结果快照到项目工作区 `artifacts/structure_templates/`。

