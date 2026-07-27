#!/usr/bin/env python3
"""Build the shared TreeElf local music metadata catalog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lib.treeelf_music import DEFAULT_CATALOG_PATH, DEFAULT_LIBRARY_DIR, build_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Build TreeElf music catalog without moving source audio")
    parser.add_argument("--library-dir", type=Path, default=DEFAULT_LIBRARY_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--skip-loudness", action="store_true")
    args = parser.parse_args()
    payload = build_catalog(args.library_dir, args.output, analyze_loudness=not args.skip_loudness)
    print(json.dumps({
        "catalog": str(args.output),
        "library_root": payload["library_root"],
        "file_count": payload["file_count"],
        "track_count": payload["track_count"],
        "duplicate_file_count": payload["duplicate_file_count"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
