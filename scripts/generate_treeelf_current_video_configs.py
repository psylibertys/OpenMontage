#!/usr/bin/env python3
"""Generate zh-philosophy-video configs for current TreeElf short scripts."""

from __future__ import annotations

import json
import re
from pathlib import Path


PSYNAUT = Path("/Users/treeelf/Desktop/Psynaut")
SCRIPT_DIR = PSYNAUT / "treeElfNotes/07产出/心哲灵/短视频文案"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "workflow_configs/zh-philosophy-video"
MUSIC_DIR = "/Users/treeelf/Desktop/crewai/music/music-sucai/纯音乐"


PROJECTS = {
    "2026-07-17_为什么一个陌生人的善意会被转交给下一个人.md": {
        "project_id": "kindness-relay-20260717",
        "core_message": "微小善意不必拯救社会，但有时会把合作基线带进下一轮互动。",
        "key_points": ["合作可能级联", "微善意不是道德奖章", "先守住一个日常接口"],
        "music": ["ambient", "calming", "piano", "纯音乐"],
        "queries": [
            ("strangers kindness coffee shop thank you", "陌生人之间短暂道谢"),
            ("person holding door for stranger city", "公共场景里的让行"),
            ("people cooperating in public space", "合作行为在人群中传递"),
            ("relay baton handoff close up", "善意接力棒隐喻"),
            ("cashier customer smiling thank you", "收银台明确道谢"),
            ("city commuters respectful interaction", "通勤里的微小善意"),
        ],
        "cards": [(["善意接力"], "合作有时会进入下一轮"), (["别让接力棒", "在你这里掉线"], "从一个日常接口开始")],
    },
    "2026-07-17_为什么下午有个安排上午就什么也做不了.md": {
        "project_id": "appointment-occupies-day-20260717",
        "core_message": "未来安排会占用内部报时和切换准备；用外部提醒接管报时，才能把现在还给现在。",
        "key_points": ["预约会触发查钟", "等待会预订整天", "提醒和小任务能释放当下"],
        "music": ["lo-fi", "ambient", "calming", "纯音乐"],
        "queries": [
            ("person checking clock waiting appointment", "反复看钟等待预约"),
            ("calendar appointment afternoon anxiety morning", "日历安排占住上午"),
            ("delivery waiting doorbell home", "等快递留半只耳朵"),
            ("phone reminder notification calendar", "提醒接管报时"),
            ("person doing small task before meeting", "安排前做可收尾小任务"),
            ("calm desk timer focus", "把现在还给现在"),
        ],
        "cards": [(["预约占台"], "日历只占一格，体感占全天"), (["两个提醒"], "准备 / 出发")],
    },
    "2026-07-17_为什么报复之后脑子反而更放不下.md": {
        "project_id": "revenge-keeps-rumination-20260717",
        "core_message": "惩罚可以处理规则，却未必负责情绪结案；回击后继续追踪可能给反刍续航。",
        "key_points": ["报复可能延长追踪", "边界账和恢复账不同", "该立边界也该结束重播"],
        "music": ["ambient", "dark piano", "calming", "纯音乐"],
        "queries": [
            ("angry person looking at phone message night", "狠话发出后反复看手机"),
            ("person replaying argument alone dark room", "争执后脑内重播"),
            ("courtroom justice boundary metaphor", "边界与正义账"),
            ("looping thoughts rumination anxiety", "反刍循环"),
            ("blocking contact on phone calm", "屏蔽和结束追踪"),
            ("person closing laptop relief night", "情绪结案的收束"),
        ],
        "cards": [(["复仇续航"], "回击可能让追踪继续"), (["两本账"], "边界与正义 / 情绪恢复")],
    },
    "2026-07-18_世界上最普通的人为什么不存在.md": {
        "project_id": "ordinary-coordinate-20260718",
        "core_message": "平均数可以描述人群，但不能替一个人做价值裁判；普通必须先说清坐标。",
        "key_points": ["平均人是拼出来的", "普通依赖维度、人群和时间", "统计师不能兼任价值裁判"],
        "music": ["ambient", "minimal", "piano", "纯音乐"],
        "queries": [
            ("crowd of people city diversity", "人群中的差异"),
            ("tailor measuring suit close up", "平均尺码穿到真人不合身"),
            ("statistics chart demographic data", "统计维度与人群画像"),
            ("person comparing self to others social media", "和同龄人比较"),
            ("map coordinates abstract data visualization", "普通坐标隐喻"),
            ("person walking confidently through crowd", "不让平均数裁判自我"),
        ],
        "cards": [(["普通坐标"], "哪个维度 / 哪群人 / 哪个时间"), (["平均数"], "描述人群，不决定你是谁")],
    },
    "2026-07-18_为什么不在乎真假的话反而更难防.md": {
        "project_id": "truth-indifferent-familiarity-20260718",
        "core_message": "重复会制造熟悉感，但熟悉不等于证据；越不在乎真假的话，越要把判断带回出处和范围。",
        "key_points": ["真假漠不关心不同于谎言", "重复会提高加工流畅性", "用出处、范围、可证伪来核验"],
        "music": ["ambient", "tension", "minimal", "纯音乐"],
        "queries": [
            ("person reading repeated fake news phone", "反复看到没有出处的话"),
            ("social media misinformation feed scrolling", "社交媒体里的熟悉感"),
            ("security guard checking id door metaphor", "大脑门卫查证件"),
            ("rumor spreading in crowd city", "大家都这么说的传播"),
            ("fact checking laptop source evidence", "核对可靠出处"),
            ("person pausing before sharing phone", "转发前暂停"),
        ],
        "cards": [(["真假免检"], "熟悉感不能替证据盖章"), (["出处", "范围", "可证伪"], "把判断换回核对")],
    },
    "2026-07-18_为什么团队越同步复杂任务反而可能做差.md": {
        "project_id": "sync-tax-teamwork-20260718",
        "core_message": "团队同步只能说明一起动，不说明方向正确；复杂协作需要对齐，也需要分工和不同信息。",
        "key_points": ["同步不等于绩效", "复杂任务需要认知分工", "用三问保留纠错入口"],
        "music": ["ambient", "focused", "minimal", "纯音乐"],
        "queries": [
            ("team meeting everyone nodding office", "顺滑会议里的点头"),
            ("two people playing tetris teamwork", "双人协作任务"),
            ("drivers steering car together metaphor", "双人驾驶隐喻"),
            ("team brainstorming different opinions", "不同信息上桌"),
            ("whiteboard decision making team", "复杂决策前的三问"),
            ("team aligned but checking direction", "该对齐时对齐，该不同处看路"),
        ],
        "cards": [(["同步之税"], "一起动，不等于方向对"), (["谁分工", "谁有不同信息", "什么会推翻"], "复杂决策三问")],
    },
    "2026-07-18_为什么我们害怕被看见.md": {
        "project_id": "fear-being-seen-20260718",
        "core_message": "完美人设能换来掌声，也会剪掉真实镜头；靠近是慢慢确认谁能看见一点花絮。",
        "key_points": ["怕被看见后离开", "成片会剪掉真实部分", "先给安全的人看十秒花絮"],
        "music": ["ambient", "calming", "piano", "纯音乐"],
        "queries": [
            ("person nervous backstage audition", "像不能NG的试镜"),
            ("perfect social mask portrait", "完美人设与面具"),
            ("film editing timeline deleted clips", "真实镜头被剪掉"),
            ("close friends quiet conversation vulnerability", "向安全的人露出一点真实"),
            ("person anxious but honest conversation", "我其实有点紧张"),
            ("two people sitting calmly together", "安全靠近的关系"),
        ],
        "cards": [(["害怕看见"], "怕的是看见后离开"), (["十秒花絮"], "先给安全的人看一点真实")],
    },
    "2026-07-18_为什么我们总被同一种角色吸引.md": {
        "project_id": "archetype-character-mirror-20260718",
        "core_message": "反复吸引你的角色像一面镜子，它不替你下结论，只提醒你正在寻找某种力量。",
        "key_points": ["角色模式会反复出现", "原型像共同的梦与期待", "用三问看见自己羡慕什么"],
        "music": ["cinematic", "ambient", "piano", "纯音乐"],
        "queries": [
            ("person watching movie theater face close up", "被同一种角色吸引"),
            ("hero mentor villain movie archetypes", "英雄导师反派的原型感"),
            ("mirror reflection mysterious person", "角色之镜"),
            ("person writing questions journal", "用三问理解吸引"),
            ("silhouette hero doorway cinematic", "想要的力量投射"),
            ("movie screen audience introspective", "故事像镜子"),
        ],
        "cards": [(["角色之镜"], "你到底在寻找什么"), (["我羡慕什么", "希望他替我做什么"], "从喜欢看见自己")],
    },
    "2026-07-18_为什么未来的自己总像个陌生人.md": {
        "project_id": "future-self-borrows-hand-20260718",
        "core_message": "未来自我不只是等待抵达的结果，也可以成为今天感受、选择和行动的出发点。",
        "key_points": ["按未来版本过今天", "纠缠不是许愿", "停掉一个旧习惯"],
        "music": ["ambient", "hopeful", "piano", "纯音乐"],
        "queries": [
            ("person looking at future self mirror", "未来自我像镜中人"),
            ("woman hospital window hopeful", "治疗中的希望和边界"),
            ("meditation event emotional love", "冥想和强烈情感体验"),
            ("person walking toward sunrise path", "已经在路上"),
            ("breaking old habit morning routine", "停掉一个旧习惯"),
            ("hands opening curtain morning light", "未来借你的手改写现在"),
        ],
        "cards": [(["未来借手"], "像那个未来版本一样活今天"), (["别先问拥有"], "问他今天会停掉什么旧习惯")],
    },
    "2026-07-19_你是否与过去纠缠不清.md": {
        "project_id": "past-self-old-script-20260719",
        "core_message": "过去不只在记忆里，也在熟练反应里；未来从第一次没有照旧开始。",
        "key_points": ["过去会借手重活", "旧剧本自动续播", "在熟悉反应里做一次不同选择"],
        "music": ["ambient", "calming", "piano", "纯音乐"],
        "queries": [
            ("person alone remembering past at night", "偶尔想起过去"),
            ("old film reel looping memory", "旧剧本自动续播"),
            ("person facing new opportunity hesitation", "新机会前播放旧失败"),
            ("person pausing before reacting conversation", "照旧反应前停十秒"),
            ("changing response in difficult conversation", "换一种回应"),
            ("calendar page turning new day", "未来不是换一本日历"),
        ],
        "cards": [(["旧剧续播"], "过去正在借你的手再活一遍"), (["多停十秒"], "第一次没有照旧")],
    },
    "2026-07-19_女性向男性调情的3种方式.md": {
        "project_id": "flirting-signals-three-ways-20260719",
        "core_message": "调情不是密码本，而是一段双方都愿意推进的互动；轻轻回应，看信号是否持续。",
        "key_points": ["女性可能先发出可接近信号", "眼神、轻松感和兴趣回流", "友好不等于同意"],
        "music": ["lo-fi", "light", "calming", "纯音乐"],
        "queries": [
            ("man woman eye contact cafe subtle", "短暂停留的眼神"),
            ("couple laughing casual conversation", "互动变得轻松"),
            ("two people talking smiling reciprocal interest", "注意力有来有回"),
            ("dance partners gentle steps metaphor", "双人舞隐喻"),
            ("respectful dating conversation cafe", "尊重边界的回应"),
            ("person walking away politely", "信号没有持续时尊重停下"),
        ],
        "cards": [(["调情信号"], "不是恋爱密码本"), (["轻轻回应"], "看信号是否持续")],
    },
    "2026-07-19_感受值得被爱.md": {
        "project_id": "worthy-of-love-echo-20260719",
        "core_message": "值得被爱不是等别人发资格证，而是不再让过去的伤害担任今天的审核员。",
        "key_points": ["过去可能还在续费", "宽恕不是宣布对方没错", "分清今天事实和过去回声"],
        "music": ["ambient", "warm piano", "calming", "纯音乐"],
        "queries": [
            ("person holding old memory alone window", "替过去续费"),
            ("empty chair relationship forgiveness", "宽恕不是替对方开脱"),
            ("inner critic mirror self doubt", "心里的老审核员"),
            ("couple gentle support conversation", "爱靠近时的资格感"),
            ("person journaling question fact or echo", "这是事实还是回声"),
            ("person standing in soft morning light", "不再让过去替今天做决定"),
        ],
        "cards": [(["爱的资格"], "不是别人发的证"), (["今天事实", "过去回声"], "别让回声替你决定")],
    },
    "2026-07-19_战争的真正代价.md": {
        "project_id": "war-future-bill-20260719",
        "core_message": "战争真正昂贵的部分，是爆炸停止之后，一个地方还要用几十年重新买回生活。",
        "key_points": ["停火不是账单清零", "地雷、通胀、教育和流失继续付款", "问谁的未来在买单"],
        "music": ["cinematic", "somber", "ambient", "纯音乐"],
        "queries": [
            ("destroyed school war aftermath empty classroom", "学校被毁后的未来损失"),
            ("landmine warning sign field war", "战争遗留物让土地无法耕种"),
            ("ruined city rebuilding aftermath", "爆炸后重建城市"),
            ("inflation empty wallet crisis", "普通人的积蓄被通胀吃掉"),
            ("children walking past damaged buildings", "孩子错过教育与稳定明天"),
            ("person looking at sunrise ruined city", "未来继续付款的收束"),
        ],
        "cards": [(["未来账单"], "停火不等于清零"), (["谁的未来", "继续付款"], "别只问谁赢了眼前")],
    },
    "2026-07-19_美学与认知科学.md": {
        "project_id": "aesthetic-label-story-20260719",
        "core_message": "美不只藏在物体里，也会被标签、来源故事和我们带来的知识一起改变。",
        "key_points": ["AI 标签会改变偏好", "眼睛从不单独上班", "喜欢来自结果也来自来处"],
        "music": ["ambient", "minimal", "piano", "纯音乐"],
        "queries": [
            ("person looking at painting gallery", "观看同一幅画"),
            ("ai generated art on screen gallery", "AI 生成标签改变感受"),
            ("artist hand painting brush close up", "知道人一笔笔画出来"),
            ("museum visitor reading artwork label", "标签和故事进入目光"),
            ("brain perception abstract art", "认知科学理解喜欢"),
            ("person looking thoughtful at artwork", "是它变了还是目光多了故事"),
        ],
        "cards": [(["标签变美"], "画没变，目光变了"), (["美"], "也被故事和知识改变")],
    },
    "2026-07-20_博尔赫斯教你如何征服时间.md": {
        "project_id": "borges-become-time-20260720",
        "core_message": "征服时间不是让钟停下，而是看见你不只在失去时间，你也正在成为时间。",
        "key_points": ["真正碰得到的只有当下", "时间之线可能是意识补上的", "你也是这条河"],
        "music": ["ambient", "neo-classical", "piano", "纯音乐"],
        "queries": [
            ("old clock close up moody", "时间一边带走你"),
            ("river flowing philosophical metaphor", "时间像河流"),
            ("person at dusk window contemplative", "夜晚和黄昏里的追问"),
            ("string of beads close up", "眼前这一下串成珠子"),
            ("flower close up sunlight moment", "花和此刻就是时间留下的样子"),
            ("person walking along river sunset", "你也正在成为时间"),
        ],
        "cards": [(["成为时间"], "你不是只在失去时间"), (["你也是", "这条河"], "征服时间不是让钟停下")],
    },
}


def parse_markdown(path: Path) -> tuple[dict[str, str], str, str]:
    text = path.read_text(encoding="utf-8").strip()
    match = re.match(r"^---\n(.*?)\n---\n+(.*)$", text, re.S)
    if not match:
        raise ValueError(f"Missing frontmatter: {path}")
    frontmatter_text, body = match.groups()
    meta: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    title_match = re.match(r"^#\s+(.+?)\n+(.*)$", body, re.S)
    if not title_match:
        raise ValueError(f"Missing H1 title: {path}")
    title, script = title_match.groups()
    return meta, title.strip(), script.strip()


def group_paragraphs(script: str, target_chars: int = 170) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", script) if p.strip()]
    groups: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        projected = current_len + len(paragraph)
        if current and current_len >= 90 and projected > 220:
            groups.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(paragraph)
        current_len += len(paragraph)
        if current_len >= target_chars:
            groups.append("\n\n".join(current))
            current = []
            current_len = 0
    if current:
        groups.append("\n\n".join(current))
    while len(groups) < 4 and any("\n\n" in group for group in groups):
        split_idx = max(range(len(groups)), key=lambda idx: len(groups[idx]))
        parts = groups[split_idx].split("\n\n")
        midpoint = max(1, len(parts) // 2)
        groups[split_idx : split_idx + 1] = ["\n\n".join(parts[:midpoint]), "\n\n".join(parts[midpoint:])]
    return groups


def label_for(index: int, count: int) -> str:
    if index == 0:
        return "Hook"
    if index == count - 1:
        return "Landing"
    labels = ["Context", "Mechanism", "Reframe", "Practice", "Boundary", "Application"]
    return labels[min(index - 1, len(labels) - 1)]


def card_positions(section_count: int, card_count: int) -> list[int]:
    positions: list[int] = []
    for idx in range(card_count):
        value = round((idx + 1) * (section_count - 1) / (card_count + 1))
        value = max(1, min(section_count - 1, value))
        while value in positions and value < section_count - 1:
            value += 1
        positions.append(value)
    return positions


def make_config(filename: str, spec: dict) -> dict:
    meta, title, raw_script = parse_markdown(SCRIPT_DIR / filename)
    grouped = group_paragraphs(raw_script)

    positions = card_positions(len(grouped), len(spec["cards"]))
    cards_by_section: dict[int, list[dict]] = {}
    for card_idx, (title_lines, subtitle) in enumerate(spec["cards"]):
        cards_by_section.setdefault(positions[card_idx], []).append(
            {"id": f"card-{card_idx + 1}", "title_lines": title_lines, "subtitle": subtitle}
        )

    sections = []
    for idx, text in enumerate(grouped):
        query_idx = round(idx * (len(spec["queries"]) - 1) / max(1, len(grouped) - 1))
        query, description = spec["queries"][query_idx]
        section = {
            "id": f"s{idx + 1}",
            "label": label_for(idx, len(grouped)),
            "text": text,
            "queries": [{"query": query, "description": description}],
        }
        if idx in cards_by_section:
            section["cards"] = cards_by_section[idx]
        sections.append(section)

    duration_numbers = [int(value) for value in re.findall(r"\d+", meta.get("target_duration", "90"))]
    target_duration = max(duration_numbers) if duration_numbers else 90
    tags = [item.strip() for item in meta.get("tags", "[]").strip("[]").split(",") if item.strip()]

    return {
        "project_id": spec["project_id"],
        "title": title,
        "cover_title": meta.get("cover_title", title[:4]),
        "cover_lines": [meta.get("cover_title", title[:4])],
        "profile": "youtube_landscape",
        "final_output_dir": "/Users/treeelf/Movies/zh-philosophy-video",
        "remotion_timeout_ms": 600000,
        "retention": {"cleanup_remotion_public": True, "cleanup_intermediate_renders": False},
        "stock_library": {"enabled": True, "min_match_score": 0.3},
        "target_platform": "16:9 landscape",
        "target_duration_seconds": target_duration,
        "tone": "克制、清醒、有温度",
        "target_audience": "抖音、小红书和视频号上关注心理机制、哲学解释、亲密关系与自我成长的中文观众",
        "key_points": spec["key_points"],
        "core_message": spec["core_message"],
        "voice_style": "安静、克制、有思考感的中文女声口播",
        "speaker_directions": "克制、自然、略慢；重点概念前后留短停顿，不要播音腔。",
        "sample_section_id": sections[min(len(sections) - 1, max(1, len(sections) // 2))]["id"],
        "source_script_md": str(SCRIPT_DIR / filename),
        "tags": tags,
        "raw_script": raw_script,
        "tts": {
            "provider": "edge",
            "version": "7.2.7",
            "voice": "zh-CN-XiaoxiaoNeural",
            "rate": "+0%",
            "pitch": "+0Hz",
            "volume": "+0%",
            "generation_mode": "single_pass",
        },
        "music": {"library_dir": MUSIC_DIR, "preferred_keywords": spec["music"]},
        "style": {
            "card_font": "fronts/漓雨手书_100font/LiyuXingkai.ttf",
            "cover_font": "fronts/漓雨手书_100font/LiyuXingkai.ttf",
            "black_overlay_opacity": 0.5,
            "cover_enabled": True,
            "cover_duration_frames": 1,
            "cover_font_size": 260,
            "card_title_font_size": 136,
            "card_subtitle_font_size": 54,
            "card_line_gap": 34,
            "title_color_rgb": [248, 246, 231],
            "accent_color_rgb": [214, 179, 90],
            "subtitle_color": "#FFFFFF",
            "subtitle_outline_color": "#000000",
            "subtitle_outline_width": 3,
            "subtitle_font_size": 52,
            "music_start_seconds": 60,
            "music_volume": 0.1,
        },
        "sections": sections,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    missing = sorted(set(PROJECTS) - {path.name for path in SCRIPT_DIR.glob("*.md")})
    if missing:
        raise SystemExit(f"Missing source scripts: {missing}")
    for filename, spec in PROJECTS.items():
        config = make_config(filename, spec)
        output = OUTPUT_DIR / f"{spec['project_id']}.json"
        output.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
