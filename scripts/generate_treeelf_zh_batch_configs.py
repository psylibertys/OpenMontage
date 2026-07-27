#!/usr/bin/env python3
"""Generate zh-philosophy-video configs from approved TreeElf Markdown scripts."""

from __future__ import annotations

import json
import re
from pathlib import Path


PSYNAUT = Path("/Users/treeelf/Desktop/Psynaut")
SCRIPT_DIR = PSYNAUT / "treeElfNotes/07产出/心哲灵/短视频文案"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "workflow_configs/zh-philosophy-video"
MUSIC_DIR = "/Users/treeelf/Desktop/crewai/music/music-sucai/纯音乐"


SPECS = {
    "2026-07-09_吾丧我_精神内耗.md": {
        "project_id": "wu-sang-wo-mental-rumination-20260709",
        "core_message": "脑中的声音正在发生，但它不等于你；觉察本身就是退出内耗的开始。",
        "key_points": ["区分吾与我", "默认模式网络会维持自我叙事", "用行动把注意力带回现场"],
        "music": ["ambient", "calming", "piano", "纯音乐"],
        "queries": [
            ("anxious person replaying conversation alone at night", "反复复盘失言的内耗感"),
            ("person waiting for unread phone message anxiety", "等待回复时脑补剧情"),
            ("person listening to inner voice mirror reflection", "把脑内声音误认成自己"),
            ("brain default mode network abstract animation", "大脑后台自我叙事隐喻"),
            ("person washing cup mindful simple action", "用具体行动离开脑内剧场"),
            ("sunlight tree shadows calm observation", "注意力回到当下现场"),
        ],
        "cards": [(["吾", "不等于", "我"], "听见声音的人 / 评判的声音"), (["声音在发生"], "不等于声音就是你")],
    },
    "2026-07-09_圣人无名_犬儒.md": {
        "project_id": "sheng-ren-wu-ming-cynicism-20260709",
        "core_message": "怀疑保护判断力，嘲讽却会冻结行动力；真正的无名是不靠掌声也不靠反掌声。",
        "key_points": ["犬儒常是失望后的防御", "冷嘲防御会固化无助", "从评价系统撤出"],
        "music": ["ambient", "post-rock", "calming", "纯音乐"],
        "queries": [
            ("sarcastic coworker dismissing idea office meeting", "冷嘲认真与理想的社交场景"),
            ("disappointed person alone after failure dark room", "失望累积后的防御"),
            ("defensive wall emotional protection metaphor", "冷嘲作为心理防御"),
            ("person mocking crowd social judgment", "被评价系统持续牵引"),
            ("person walking away from applause spotlight", "退出掌声与反掌声"),
            ("calm person standing alone sunrise", "不靠评价确认自己"),
        ],
        "cards": [(["怀疑", "保护判断力"], "嘲讽会冻结行动力"), (["圣人无名"], "不靠掌声，也不靠反掌声")],
    },
    "2026-07-09_大死一番_诛己心.md": {
        "project_id": "great-death-old-program-20260709",
        "core_message": "看见童年和评价系统留下的自动程序，旧声音就不再拥有审判你的权力。",
        "key_points": ["旧身份可以退出自我定义", "自动程序会伪装成命运", "辨认声音并重写地图"],
        "music": ["soundtrack", "neo-classical", "ambient", "纯音乐"],
        "queries": [
            ("adult criticized by parent family tension", "一句否定让成年人退回童年"),
            ("child shadow behind adult psychological memory", "童年经验留下的影子"),
            ("old tape recorder repeating voice dark", "旧环境留下的复读机"),
            ("puppet strings controlling person choice", "自动程序替人做选择"),
            ("burning old map symbolic freedom", "烧掉别人给的旧地图"),
            ("person choosing own road sunrise", "离开别人的判决书"),
        ],
        "cards": [(["旧声音"], "不等于你的声音"), (["真正的改命"], "先烧掉旧地图")],
    },
    "2026-07-09_心外无物_社恐.md": {
        "project_id": "xin-wai-wu-wu-social-anxiety-20260709",
        "core_message": "社恐常把事实自动翻译成审判；区分观察与解释，目光就开始失效。",
        "key_points": ["事实与解释不同", "自动思维不是现实", "把判断句改成观察句"],
        "music": ["ambient", "lo-fi", "calming", "纯音乐"],
        "queries": [
            ("awkward coworkers silent elevator", "电梯里没有打招呼的尴尬"),
            ("person checking social media no likes anxiety", "没人点赞后的自我怀疑"),
            ("spotlight effect person in crowd anxiety", "聚光灯效应隐喻"),
            ("courtroom judgment metaphor anxious person", "把目光接成审判"),
            ("person observing facts writing notes", "把判断句改成观察句"),
            ("calm person walking through crowd", "回到现场而非脑内解释"),
        ],
        "cards": [(["事实"], "他看了两秒，没说话"), (["解释"], "他肯定觉得我很奇怪"), (["判断句", "改成观察句"], "把自己带回现场")],
    },
    "2026-07-09_放下_停止较劲.md": {
        "project_id": "let-go-stop-struggling-20260709",
        "core_message": "放下不是更用力地停止思考，而是看见念头、停止辩论并转向一个小行动。",
        "key_points": ["认知解离让想法与自我拉开距离", "放下四步", "行动打断反刍循环"],
        "music": ["ambient", "calming", "piano", "纯音乐"],
        "queries": [
            ("person awake in bed overthinking night", "念头像钟摆一样来回撞"),
            ("hand holding cup too long metaphor", "一直举着杯子的隐喻"),
            ("pendulum swinging close up", "反复念头的钟摆"),
            ("person writing thoughts on paper mindful", "写下反复出现的句子"),
            ("person washing cup small mindful action", "转身做一个小动作"),
            ("open hands releasing object calm", "松手并不需要更大的力气"),
        ],
        "cards": [(["见钟摆", "认钟摆"], "先看见，再拉开距离"), (["断钟摆", "转身"], "停止辩论，做一个小动作")],
    },
    "2026-07-09_相濡以沫_恋爱选择.md": {
        "project_id": "xiang-ru-yi-mo-love-choice-20260709",
        "core_message": "恋爱不是寻找最优商品；先判断关系是滋养你的江湖，还是让你抓住出口的干涸车辙。",
        "key_points": ["相濡以沫之后还有相忘江湖", "选择悖论放大后悔", "从谁更好退回关系是否滋养"],
        "music": ["neo-classical", "ambient", "soundtrack", "纯音乐"],
        "queries": [
            ("conflicted person between two romantic choices", "关系中的选择困境"),
            ("couple distant relationship dry emotional", "干涸关系中的互相拯救"),
            ("two fish shallow water drought metaphor", "相濡以沫的车辙意象"),
            ("person overwhelmed by too many choices", "选择悖论带来的焦虑"),
            ("crossroads relationship decision alone", "从单选题退回真实问题"),
            ("open lake water freedom peaceful", "重新接近江湖与滋养"),
        ],
        "cards": [(["相濡以沫"], "不如相忘于江湖"), (["谁更好？"], "还是这段关系是否滋养？"), (["爱"], "至少应该让人重新接近水")],
    },
    "2026-07-16_为什么一进房间就忘了自己要干什么.md": {
        "project_id": "doorway-event-boundary-20260716",
        "core_message": "门框不是记忆删除键；场景切换会更新事件模型，后台越忙越容易暂时压住旧任务。",
        "key_points": ["事件分段更新当前情境模型", "门口效应并非稳定超能力", "过门前给下一场戏报幕"],
        "music": ["lo-fi", "ambient", "chillwave", "纯音乐"],
        "queries": [
            ("person enters room suddenly forgets task", "进房间后突然忘记目的"),
            ("doorway transition walking between rooms", "门口作为场景边界"),
            ("film set stage change behind scenes", "大脑像场务一样换场"),
            ("multitasking working memory overload laptop phone", "额外工作记忆负担"),
            ("person saying reminder before entering room", "过门前给任务报幕"),
            ("charging cable on bedroom table", "卧室拿充电线的具体目标"),
        ],
        "cards": [(["门框"], "不是记忆删除键"), (["事件分段"], "布景变了，大脑换场"), (["卧室"], "拿充电线")],
    },
    "2026-07-16_为什么越想表现好越容易失常.md": {
        "project_id": "pressure-choking-manual-control-20260716",
        "core_message": "压力下的失常有两条常见路径：难题被担忧抢占带宽，熟练动作被意识手动接管。",
        "key_points": ["工作记忆带宽会被担忧占用", "显性监控会拆坏自动技能", "按任务类型重新放置注意力"],
        "music": ["soundtrack", "ambient", "post-rock", "纯音乐"],
        "queries": [
            ("nervous speaker on stage forgetting words", "关键场合突然失常"),
            ("athlete overthinking movement competition", "熟练动作被过度监控"),
            ("working memory overload stress abstract", "担忧抢占有限带宽"),
            ("hands controlling machine manual override", "意识手动接管自动程序"),
            ("person writing calculation steps on paper", "让纸面分担工作记忆"),
            ("athlete focusing on target not body", "把注意放回外部目标"),
        ],
        "cards": [(["难题"], "怕带宽被抢"), (["熟练动作"], "怕被手动接管"), (["先判断任务类型"], "再决定注意力放哪里")],
    },
    "2026-07-16_先给情绪一个准确名字.md": {
        "project_id": "name-emotion-accurately-20260716",
        "core_message": "准确命名情绪能把模糊警报变成可区分的信息，再为下一步行动提供方向。",
        "key_points": ["情感标注是识别而非消灭情绪", "烦是总警报不是地图", "承认、细分、定位指向"],
        "music": ["ambient", "calming", "piano", "纯音乐"],
        "queries": [
            ("person tense after argument emotional", "争执后只会说烦死了"),
            ("person labeling emotions journal", "用词语识别当下情绪"),
            ("fire alarm warning light metaphor", "烦像一声总警报"),
            ("map with different paths emotion choices", "不同情绪指向不同动作"),
            ("writing fear disappointment shame anger", "把烦往前拆一层"),
            ("calm person breathing with notebook", "先定位再决定下一步"),
        ],
        "cards": [(["烦"], "是一声总警报，不是一张地图"), (["承认", "细分", "指向"], "情绪定位三步法")],
    },
    "2026-07-16_切换任务后大脑没有立刻跟上.md": {
        "project_id": "attention-residue-task-switching-20260716",
        "core_message": "切换任务前给旧任务一个外部停靠点，能减少未完成目标留下的注意力残留。",
        "key_points": ["未完成任务更容易留下注意力残留", "任务切换不是窗口切换", "三行便签提高结束质量"],
        "music": ["lo-fi", "ambient", "downtempo", "纯音乐"],
        "queries": [
            ("laptop meeting chat document multitasking", "人已切换而注意力仍留在上一任务"),
            ("unfinished work desk open notebook", "未完成任务占着带宽"),
            ("coat caught in closing door metaphor", "注意力尾巴夹在上一扇门"),
            ("sticky note next step task planning", "给旧任务一个外部停靠点"),
            ("focused person working single task", "提高任务结束质量后重新专注"),
            ("closing laptop calm transition", "完成清晰的任务切换"),
        ],
        "cards": [(["注意力残留"], "人到了，注意力还在加班"), (["做到哪", "下一步", "何时回来"], "切换前留三行便签")],
    },
    "2026-07-16_太省力的生活为什么不一定满足.md": {
        "project_id": "effort-paradox-participation-20260716",
        "core_message": "工具可以减少重复成本，但要保留一个有意义的判断或参与，才能留下能力感与所有感。",
        "key_points": ["努力在选择前是成本、投入后可能增加价值", "省力和值得是两套账", "保留关键参与而非故意受苦"],
        "music": ["lo-fi", "ambient", "folk", "纯音乐"],
        "queries": [
            ("person using ai tool generated text detached", "工具代劳后成果不像自己的"),
            ("hobby equipment shopping without practicing", "爱好只剩装备与观看"),
            ("craftsperson making object hands close up", "投入留下能力感和所有感"),
            ("person making important decision at desk", "保留一个关键判断"),
            ("assistive technology helping participation", "省力工具也可能是参与的必要条件"),
            ("person finishing meaningful project satisfied", "参与生成价值感"),
        ],
        "cards": [(["省力", "值得"], "是两套账"), (["重复劳动"], "交给工具"), (["关键判断"], "留给自己")],
    },
    "2026-07-16_想刷不等于刷了会快乐.md": {
        "project_id": "wanting-liking-phone-reward-20260716",
        "core_message": "想要很强不代表奖励很好；把打开前的冲动与结束后的满足分开评分，才能看清两条曲线。",
        "key_points": ["wanting与liking可以分离", "线索会点燃获得冲动", "双评分后优先处理线索"],
        "music": ["lo-fi", "electronic", "chillwave", "纯音乐"],
        "queries": [
            ("person scrolling phone bored at night", "刷着并不快乐却继续点开"),
            ("phone notification temptation close up", "线索点燃获得冲动"),
            ("pushy salesman doorway metaphor", "冲动像过分勤奋的推销员"),
            ("rating scale before and after phone use", "打开前与结束后的双评分"),
            ("turning off phone notifications settings", "处理提示与顺手入口"),
            ("phone placed away person relaxed", "让冲动和满足分别交答卷"),
        ],
        "cards": [(["wanting"], "去获得"), (["liking"], "实际愉悦"), (["很想刷"], "不等于刷完会满足")],
    },
    "2026-07-16_计划失败在没有触发器.md": {
        "project_id": "implementation-intention-trigger-plan-20260716",
        "core_message": "把模糊目标改写成如果情境出现、就执行一个具体小动作，计划才真正接上触发器。",
        "key_points": ["执行意图把线索和动作连接", "动作要具体且足够小", "失败时检查线索、动作和现实条件"],
        "music": ["lo-fi", "ambient", "folk", "纯音乐"],
        "queries": [
            ("unfinished planner goals procrastination", "计划写好但新生活没来上班"),
            ("electrical plug disconnected socket metaphor", "目标没有接上触发器"),
            ("putting dishes in sink after dinner", "晚饭后收碗作为线索"),
            ("putting on shoes going for short walk", "换鞋下楼作为最低动作"),
            ("small first step habit formation", "先设计开始再设计坚持"),
            ("night shift worker realistic schedule", "现实条件需要被纳入计划"),
        ],
        "cards": [(["如果 X 出现"], "我就执行动作 Y"), (["先设计开始"], "再设计坚持"), (["线索", "动作", "条件"], "失败后检查三件事")],
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
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    title_match = re.match(r"^#\s+(.+?)\n+(.*)$", body, re.S)
    if not title_match:
        raise ValueError(f"Missing H1 title: {path}")
    title, script = title_match.groups()
    return meta, title.strip(), script.strip()


def group_paragraphs(script: str, target_chars: int = 105) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", script) if p.strip()]
    groups: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        projected = current_len + len(paragraph)
        if current and current_len >= 65 and projected > 135:
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
    if len(groups) < 4:
        raise ValueError("Script grouping produced fewer than four sections")
    return groups


def label_for(index: int, count: int) -> str:
    if index == 0:
        return "Hook"
    if index == count - 1:
        return "Landing"
    labels = ["Context", "Mechanism", "Reframe", "Practice", "Evidence", "Application"]
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
    source_path = SCRIPT_DIR / filename
    meta, title, raw_script = parse_markdown(source_path)
    grouped = group_paragraphs(raw_script)
    positions = card_positions(len(grouped), len(spec["cards"]))
    cards_by_section: dict[int, list[dict]] = {}
    for card_idx, (title_lines, subtitle) in enumerate(spec["cards"]):
        section_idx = positions[card_idx]
        cards_by_section.setdefault(section_idx, []).append(
            {"id": f"card-{card_idx + 1}", "title_lines": title_lines, "subtitle": subtitle}
        )

    sections = []
    for idx, section_text in enumerate(grouped):
        query_idx = round(idx * (len(spec["queries"]) - 1) / max(1, len(grouped) - 1))
        query, description = spec["queries"][query_idx]
        section = {
            "id": f"s{idx + 1}",
            "label": label_for(idx, len(grouped)),
            "text": section_text,
            "queries": [{"query": query, "description": description}],
        }
        if idx in cards_by_section:
            section["cards"] = cards_by_section[idx]
        sections.append(section)

    range_numbers = [int(value) for value in re.findall(r"\d+", meta.get("target_duration", "90"))]
    declared_max = max(range_numbers) if range_numbers else 90
    spoken_chars = len(re.sub(r"[\s，。！？；：、“”‘’（）《》A-Za-z0-9_-]", "", raw_script))
    estimated_seconds = round(spoken_chars / 3.8 + len(sections) * 0.8)
    target_duration = max(declared_max, estimated_seconds)
    tags = [item.strip() for item in meta.get("tags", "[]").strip("[]").split(",") if item.strip()]

    return {
        "project_id": spec["project_id"],
        "title": title,
        "cover_title": meta.get("cover_title", title[:8]),
        "cover_lines": [meta.get("cover_title", title[:8])],
        "profile": "youtube_landscape",
        "final_output_dir": "/Users/treeelf/Movies/zh-philosophy-video",
        "remotion_timeout_ms": 600000,
        "retention": {"cleanup_remotion_public": True, "cleanup_intermediate_renders": False},
        "stock_library": {"enabled": True, "min_match_score": 0.3},
        "target_platform": "16:9 landscape",
        "target_duration_seconds": target_duration,
        "tone": "克制、清醒、有温度",
        "target_audience": "抖音、小红书和B站上关注心理机制、哲学解释与自我成长的中文观众",
        "key_points": spec["key_points"],
        "core_message": spec["core_message"],
        "voice_style": "成年女性普通话声线，中等音高，中速，清晰发音；整体活泼、温暖，有微笑语气。",
        "speaker_directions": "像在自然分享；遇到更有趣或轻微幽默的内容时，可以自然轻笑，同时保持语义清楚和表达可信。",
        "sample_section_id": sections[min(len(sections) - 1, max(1, len(sections) // 2))]["id"],
        "source_script_md": str(source_path),
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
    missing = sorted(set(SPECS) - {path.name for path in SCRIPT_DIR.glob("*.md")})
    if missing:
        raise SystemExit(f"Missing source scripts: {missing}")
    for filename, spec in SPECS.items():
        config = make_config(filename, spec)
        output = OUTPUT_DIR / f"{spec['project_id']}.json"
        output.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
