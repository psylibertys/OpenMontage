# story-to-storyboard 进度一览

> 一眼看懂当前进度。详版见 [`STORY_TO_STORYBOARD_ROADMAP.md`](STORY_TO_STORYBOARD_ROADMAP.md)。
> 最后更新：2026-10-13（v1 成片否决 → v2 短剧返工，GPU 生产前准备就绪）

## 一句话状态

**v1 成片被用户否决（旁白+静帧形态），storyboard v2 短剧返工完成、GPU 生产前准备全部就绪**：25 镜 106s、无旁白、全中国人物、H3 公式提示词、单镜 ≥4s；对白 TTS 5/5 已产出；批次 3 剩余组 + 批次 4 视频批等 GPU 会话执行。剩余：验收③反向对标视频。

## 三期 Checklist

### 一期：双向闭环 MVP（正向为主 + 反向本地版）— 🔄 进行中

- [x] 详版路线图落库（`STORY_TO_STORYBOARD_ROADMAP.md`）
- [x] 简版进度一览落库（本文件）
- [x] `script.schema.json` 加性扩展（beat_map / visual_intent / emotion / character_dialogue）
- [x] `story_brief.schema.json`（故事输入契约）
- [x] `storyboard_export.schema.json`（导出契约）
- [x] `schemas/artifacts/__init__.py` 注册两个新 artifact
- [x] `lib/storyboard_export.py`（t2i/i2v/voice 规则校验库，移植自四件套）
- [x] `pipeline_defs/story-to-storyboard.yaml`（4 阶段全人审门）
- [x] `config/studiobinder-stage-routing.yaml` 追加路由段
- [x] `scripts/export_storyboard_json.py`（导出 CLI）
- [x] EP + 4 个 stage director skills
- [x] references 规则吸收 4 件（prompt-rules / i2v-prompt-rules / voice-rules / consistency-checklist）
- [x] `skills/meta/brief-to-beat-bridge.md`（反向确定性映射）
- [x] `docs/treeelf-knowledge-sources.md` 登记
- [x] `tests/contracts/test_story_to_storyboard_pipeline.py` 契约测试
- [x] 契约测试全绿（35 项）+ tests/contracts 全量回归零新增失败（15 项失败为预先存在的环境问题：缺 google.genai 依赖、registry provider 集合与未提交环境不一致，均与本管线无关）
- [x] 端到端验收①（管线级）：「记忆修理店」（较陈美珍更简单的短篇，用户选定）跑通 4 阶段、4 道门逐门批准；script 经 rev1→rev4 三轮人工反馈修订，教训已固化为 script-director 协议（重述法 HARD RULE + 首听四查）
- [ ] 端到端验收①（最终）：**真实成片逻辑验证**——v1 静帧 animatic 已被用户否决（2026-10-13 四要求：无旁白/人物开口/画面动态/全中国人物）；v2 短剧返工就绪（storyboard v2 + 批次 3/4），等 GPU 生产出视频镜成片后关门
- [x] 端到端验收②：四 artifact 全过 schema + 25 镜全 lint + 双向溯源 + narration_all=script 全文逐字（v1 时 ≤3s 收紧；v2 起短剧产线改为单镜 ≥4s=H3 最短档，静帧图解类仍 ≤3s，两规则按产线并存）
- [ ] 端到端验收③：任一对标视频（本地栈）反推出剧本骨架 + structure_template
- [x] Backlot 看板正确显示（4 阶段全 completed）
- [ ] 结构模板库首批 2-3 个（可滑二期）

### 二期：外部 API 实验 + 导出打磨 — ⏸ 未启动

- [ ] TwelveLabs Pegasus / Gemini video understanding 接入为 EXPERIMENTAL 工具（无 key 自动降级本地）
- [ ] 精度对比：3-5 个对标视频，本地版 vs API 版对照，结论写回路线图
- [ ] 自动拆长镜（>5s 按停顿/句读切分）+ golden 测试
- [ ] **script 门 TTS 旁白预览**（验收①教训：听觉媒体用听觉校验，script 批准前机器念一遍给用户听）
- [ ] storyboard_json → scene_plan 宽松导入（可选）
- [ ] structure_template 模板库扩充

### 三期：生态整合 — ⏸ 未启动

- [ ] scene_plan 续跑 animation / character-animation 出成片（successor_pipelines 续传）——即验收①最终成片验证的承载路径
- [ ] treeelf-story-creator 可选接入（显式登记）
- [ ] pixaroma H3 三字段契约加性扩展
- [ ] video_understand 逐镜回验（成片逻辑验证的自动化承载）
- [ ] 寓言双角色文案 → 分镜 → 成片一条龙演示

## 下一步

1. **批次 3 剩余组（GPU 会话）**：character_pack 2（中国面孔角色包）→ 人审 cut-refs/approve → krea 9 + flux 7 人物首帧重生成（dialogue_tts 组 5/5 已于 2026-10-13 完成，音频就位）；配置 `workflow_configs/memory-repair-shop/batch-3.json`
2. **批次 4（视频批）**：22 镜 FastH3 两段式（seed 480 选种人审星标 → HD 1920 同 seed）+ 3 口型镜 audio_sync 单轮 HD + s21→22 fflf 转场；配置 `workflow_configs/memory-repair-shop/batch-4.json`；批次 2 旧断点 manifest 已作废，不要续跑
3. **Remotion 短剧组件（新写，不复用 TeachersDayClayBouquet）**：视频镜拼接 + 对白字幕 + 3 角标 + 店招/结尾文字层 + H3 环境音与对白混音 → 用户看成片 → 验收①关门
4. 验收③：选一个对标分析库视频走反向分支验证 brief-to-beat-bridge
5. 按需跑「来电人陈美珍」蓝图作为复杂案例回归（多角色、长弧线）
