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

## 2. StudioBinder：电影制作与摄影方法库

Obsidian 根目录：

```text
/Users/treeelf/Desktop/Psynaut/treeElfNotes/03资源/YouTube课程/StudioBinder/
```

它是人类可读的课程学习区，包含课程档案、中文课名、学习顺序、逐课方法、案例、练习和来源定位。当前有三套课程：

| 课程 | 课程 ID | 主要用途 |
|---|---|---|
| 摄影机运动终极指南 | `ytpl_PLEzQZpmbzckWUQALEX8UlbyH2GtRLMrSd` | 固定机位、推拉变焦、跟拍、横摇/俯仰、边走边谈等运镜选择，以及运动的叙事动机。 |
| 电影制作终极指南 | `ytpl_PLEzQZpmbzckVQL5QNLv1XaJW4slV0CMZO` | 特写、全景、慢动作、延时、摄影机支撑、字幕和电影格式等制作语言。 |
| 电影摄影技法 | `ytpl_PLEzQZpmbzckX3A_SopJ-krGsV6BERxdwb` | 灯光、镜头、构图、调度、景别、视觉叙事、摄影风格、镜头清单和现场制作方法。 |

Qdrant 领域为 `cinematography`。它把三套课程的中文知识块、英文证据、时间码和视觉证据索引放在稳定 alias `course_cinematography_active` 下。Agent 不直接访问物理 collection，必须使用受控检索器：

```bash
conda run -n cyber_factory python \
  /Users/treeelf/Desktop/Psynaut/.claude/skills/treeelf-youtube-course-harvest/scripts/course_agent_retrieve.py \
  "QUERY" --agent openmontage-project-agent --domain cinematography \
  --intent knowledge
```

只需要某一套课程时增加 `--course-id COURSE_ID`，避免其他课程干扰。

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
