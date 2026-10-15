"""Check collected raw sources against the phase 3 gates.

Usage:
    uv run python -X utf8 scripts/check_raw.py
"""

import json
import re
import sys
from collections import defaultdict

import lawlib as L

NOTE = re.compile(r"^(?P<name>.+) (?P<date>\d{8})-(?P<serial>\d+) (?P<stamp>\d{8}T\d{4})$")
REQUIRED = ("identifier", "title", "publisher", "url", "generatedAtTime", "sha256", "license")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def law_versions(name):
    """Every stored version of a law, from raw notes and the cache, keyed by 시행일자."""
    versions = {}
    folder = L.RAW / "law" / name
    for note in sorted(folder.glob(f"{name} *-* *.md")):
        match = NOTE.match(note.stem)
        if match:
            versions[match["date"]] = load(note.with_suffix(".json"))["법령"]
    listing = sorted(folder.glob(f"{name} versions *.json"))
    rows = [r for p in load(listing[-1])["pages"] for r in L.as_list(p.get("law")) if r.get("법령명한글") == name]
    cache = L.CACHE / "law" / rows[0]["법령ID"]
    for path in sorted(cache.glob("*.json")):
        effective = path.stem.split("-")[1]
        versions.setdefault(effective, load(path)["법령"])
    return dict(sorted(versions.items())), rows, load(listing[-1])


def changed_flags(law):
    """Articles that 법제처 marks as changed (조문변경여부 Y) in this version."""
    flagged = set()
    for row in L.as_list(law["조문"]["조문단위"]):
        if row.get("조문여부") == "조문" and row.get("조문변경여부") == "Y":
            flagged.add(f"art-{row['조문번호']}" + (f"-{row['조문가지번호']}" if row.get("조문가지번호") else ""))
    return flagged


def image_text(text):
    """Comparison text inside the image elements of a unit, empty when the response leaves it out."""
    return L.canonical("".join(L.IMAGE.findall(text)))


def check_law(name, problems, notes):
    versions, rows, listing = law_versions(name)
    seen = sum(len(L.as_list(p.get("law"))) for p in listing["pages"])
    if seen != listing["totalCnt"]:
        problems.append(f"{name}: list pages hold {seen} rows, totalCnt is {listing['totalCnt']}")
    published_on = defaultdict(set)
    for row in rows:
        published_on[row["시행일자"]].add(row["공포일자"])
    _, window_start = L.release()
    chosen = L.choose_versions(rows)
    expected_dates = {d for d in chosen if d >= L.in_force(chosen, window_start)}
    if expected_dates - set(versions):
        problems.append(f"{name}: versions in the list but not collected {sorted(expected_dates - set(versions))}")
    for effective, law in versions.items():
        if law["기본정보"]["시행일자"] != effective:
            problems.append(f"{name} {effective}: response says {law['기본정보']['시행일자']}")
        revisions = [r["공포일자"] for r in rows if r.get("제개정구분명") in ("제정", "전부개정") and r["시행일자"] <= effective]
        since = max(revisions, default="")
        expected = {
            re.sub(r"\D", "", r["공포번호"]).lstrip("0")
            for r in rows if r["시행일자"] <= effective and r["공포일자"] >= since
        }
        present = {re.sub(r"\D", "", u.get("부칙공포번호", "")).lstrip("0") for u in L.as_list(law["부칙"]["부칙단위"])}
        missing = sorted(expected - present, key=int)
        if missing:
            problems.append(f"{name} {effective}: 부칙 missing for promulgations {missing[:10]}")
        for annex in L.as_list(law.get("별표", {}).get("별표단위")):
            title = annex.get("별표제목", "")
            if "삭제" not in title and not L.canonical("".join(L.flatten(annex.get("별표내용")))):
                problems.append(f"{name} {effective}: empty {annex.get('별표구분')} {annex.get('별표번호')} {title[:30]}")
    dates = list(versions)
    for before, after in zip(dates, dates[1:]):
        old, new = L.law_units(versions[before]), L.law_units(versions[after])
        flagged = changed_flags(versions[after])
        allowed = published_on[after]
        counts = defaultdict(int)
        for key, text in new.items():
            if key.startswith(("sup-", "heading-")):
                continue
            if L.version_text(old.get(key, "")) == L.version_text(text):
                before_images, after_images = image_text(old.get(key, "")), image_text(text)
                if before_images and after_images and before_images != after_images:
                    problems.append(f"{name} {before}->{after}: {key} image text changed, version text did not")
                continue
            if set(L.amendment_dates(text)) & allowed:
                counts["tag"] += 1
            elif key in flagged:
                counts["flag"] += 1
            else:
                problems.append(f"{name} {before}->{after}: {key} changed with no amendment tag dated {sorted(allowed)} and no change flag")
        notes.append(f"{name} {before}->{after}: changed units explained by tag {counts['tag']}, flag {counts['flag']}")


def check_notes(problems):
    for note in sorted(L.RAW.rglob("*.md")):
        meta = L.frontmatter(note)
        missing = [k for k in REQUIRED if not meta.get(k)]
        if missing:
            problems.append(f"{note.relative_to(L.VAULT)}: missing {missing}")
        payload = note.with_suffix(".json")
        if note.parts[-3] == "law" and payload.exists():
            data = load(payload)
            text = L.law_text(data["법령"]) if "법령" in data else None
            if text is not None and L.sha256(text) != meta.get("sha256"):
                problems.append(f"{note.relative_to(L.VAULT)}: sha256 differs from the response")


def check_secrets(problems):
    secrets = L.secrets()
    for path in list(L.RAW.rglob("*")) + list(L.CACHE.rglob("*.json")):
        if path.is_file() and path.suffix in (".md", ".json", ".html"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(s in text for s in secrets):
                problems.append(f"{path.relative_to(L.VAULT)}: contains a secret value")


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    import yaml
    from pathlib import Path
    sources = yaml.safe_load((Path(__file__).parent / "sources.yaml").read_text(encoding="utf-8"))
    problems, notes = [], []
    for name in sources["laws"]:
        check_law(name, problems, notes)
    check_notes(problems)
    check_secrets(problems)
    for line in notes:
        print(line)
    for line in problems:
        print("FAIL", line)
    print(f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
