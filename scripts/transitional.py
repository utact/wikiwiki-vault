"""List the 경과조치, 적용례, 특례 and 유효기간 articles of 부칙 that still matter within the transitional window.

Usage:
    uv run python -X utf8 scripts/transitional.py

Reads the committed raw notes of the laws in scripts/sources.yaml: their current and
scheduled versions and the latest version list.
"""

import json
import sys
from pathlib import Path

import yaml

import lawlib as L


def entries(name, window_start):
    folder = L.RAW / "law" / name
    laws = [json.loads(p.read_text(encoding="utf-8"))["법령"] for p in sorted(folder.glob(f"{name} *-* *.json"))]
    listing = json.loads(sorted(folder.glob(f"{name} versions *.json"))[-1].read_text(encoding="utf-8"))
    rows = [r for p in listing["pages"] for r in L.as_list(p.get("law")) if r.get("법령명한글") == name]
    return L.transitional(laws, rows, window_start)


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    sources = yaml.safe_load((Path(__file__).parent / "sources.yaml").read_text(encoding="utf-8"))
    _, window_start = L.release()
    for name in sources["laws"]:
        for entry in entries(name, window_start):
            units = ", ".join(entry["units"]) or "대상 단위 없음"
            print(f"{name} 부칙 {entry['promulgation']} {entry['article']}({entry['title']}) 시행 {','.join(entry['effective'])}: {units}")


if __name__ == "__main__":
    main()
