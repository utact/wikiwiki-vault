"""Write index.md: the wiki notes grouped by class.

Usage:
    uv run python -X utf8 scripts/index.py           write index.md
    uv run python -X utf8 scripts/index.py --check   fail if index.md is out of date
"""

import sys

import yaml

import lawlib as L

INDEX = L.VAULT / "index.md"
SCHEMA = L.VAULT / "ontology" / "schema.yaml"


def render():
    classes = [name for name, cls in yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))["classes"].items()
               if not cls.get("abstract") and (L.VAULT / "wiki" / name).exists()]
    notes = {}
    for path in sorted((L.VAULT / "wiki").rglob("*.md")):
        notes.setdefault(L.frontmatter(path).get("type"), []).append(path.stem)
    lines = ["# Index", "", "class별 노트 목록이다. class 정의는 [[schema]]에 있고, 노트는 이름 순으로 둔다.", ""]
    for name in classes:
        if notes.get(name):
            lines += [f"## {name}", "", *[f"- [[{stem}]]" for stem in sorted(notes[name])], ""]
    return "\n".join(lines).rstrip() + "\n"


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    text = render()
    if sys.argv[1:] == ["--check"]:
        current = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
        print("index.md is up to date" if current == text else "index.md is out of date")
        sys.exit(0 if current == text else 1)
    INDEX.write_text(text, encoding="utf-8", newline="\n")
    print(f"index.md: {text.count('- [[')} notes")


if __name__ == "__main__":
    main()
