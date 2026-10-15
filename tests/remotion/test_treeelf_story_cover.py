from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
REMOTION_ROOT = REPO_ROOT / "remotion-composer"


@pytest.mark.parametrize("title", ["她叫孙梅兰", "闻不见春天的人", "一个长度超过九个字的故事标题"])
def test_treeelf_story_cover_renders_horizontal_png(tmp_path: Path, title: str) -> None:
    if not (REMOTION_ROOT / "node_modules" / ".bin" / "remotion").is_file():
        pytest.skip("Remotion dependencies are not installed")
    output = tmp_path / "cover.png"
    props = {
        "backgroundSrc": (
            "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
            "width='1800' height='766'%3E%3Crect width='1800' height='766' fill='%23112233'/%3E"
            "%3Ccircle cx='1400' cy='300' r='260' fill='%23557799'/%3E%3C/svg%3E"
        ),
        "chineseTitle": title,
        "englishTitle": "",
        "brand": "树精灵",
        "titlePosition": "center",
        "textAlign": "center",
        "gradientDirection": "center",
        "overlayOpacity": 0.34,
    }
    subprocess.run(
        [
            str(REMOTION_ROOT / "node_modules" / ".bin" / "remotion"),
            "still",
            "src/index.tsx",
            "TreeElfStoryCover",
            str(output),
            "--props",
            json.dumps(props, ensure_ascii=False),
            "--image-format",
            "png",
        ],
        cwd=REMOTION_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    with Image.open(output) as image:
        assert image.size == (1800, 766)


def test_treeelf_cover_has_liyu_handwriting_as_implicit_default() -> None:
    source = (REMOTION_ROOT / "src" / "TreeElfCover.tsx").read_text(encoding="utf-8")

    assert 'from "../../fronts/漓雨手书_100font/LiyuXingkai.ttf"' in source
    assert "chineseFontSrc ? resolveAsset(chineseFontSrc) : defaultChineseFontUrl" in source
    assert 'new FontFace("TreeElfCoverCN"' in source
