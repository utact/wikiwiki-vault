"""Check collected raw sources against the phase 3 gates.

Usage:
    uv run python -X utf8 scripts/check_raw.py

Needs the local cache that scripts/collect.py writes, because the gates compare every
version within the transitional window.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml
from pypdf.errors import PyPdfError

import collect
import lawlib as L

NOTE = L.RAW_NOTE
REQUIRED = ("identifier", "title", "publisher", "url", "generatedAtTime", "sha256", "license")
DELETED = re.compile(r"(?:제\d+(?:조|장|절|편|관)(?:의\d+)?|■[가-힣]+)?삭제")


IMAGE_FILE = re.compile(r'<img\b[^>]*?src="([^"]+)"[^>]*>(?:(?:(?!<img\b).)*?</img>)?', re.S)


def deleted(text):
    """Whether a whole unit is a deletion, such as "제22조 삭제 <2006.12.28>" or "[별지 제33호서식] 삭제 <2018. 7. 11.>"."""
    return bool(DELETED.fullmatch(re.sub(r"\s+|<[^>]*>|\[[^\]]*\]", "", text)))


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def changed_flags(law):
    """Articles that 법제처 marks as changed (조문변경여부 Y) in this version."""
    return {
        L.article_key(row["조문번호"], row.get("조문가지번호"))
        for row in L.as_list(law["조문"]["조문단위"])
        if row.get("조문여부") == "조문" and row.get("조문변경여부") == "Y"
    }


def moved_from(law):
    """Articles that this version says it moved, from the 조문이동이전 of their new place, such as 005610."""
    return {
        L.article_key(code[:4], code[4:])
        for row in L.as_list(law["조문"]["조문단위"])
        if (code := row.get("조문이동이전", "")) and int(code or 0)
    }


def image_text(text):
    """Comparison text inside the image elements of a unit, empty when the response leaves it out."""
    return L.canonical("".join(L.IMAGE.findall(text)))


def images(text):
    """Image files of a unit with the comparison text each carries, empty when the response leaves it out."""
    return [(m.group(1), L.canonical(m.group(0))) for m in IMAGE_FILE.finditer(text)]


def replaced_without_text(before, after):
    """Whether image files changed where no image text shows that their content stayed the same."""
    if [source for source, _ in before] == [source for source, _ in after]:
        return False
    return len(before) != len(after) or any(not (a and a == b) for (_, a), (_, b) in zip(before, after))


def image_problems(name, effective, key, text):
    """Lines restored from image text must start and end with a frame and be about as wide as each other."""
    found = []
    for image in L.IMAGE.findall(text):
        inner = L.IMAGE_TAG.sub("", image)
        if not L.canonical(inner) or "\n" in inner.strip("\n"):
            continue
        lines = [line for line in L.image_lines(inner).split("\n") if line]
        unframed = [line for line in lines if not (line[0] in L.LINE_START and line[-1] in L.LINE_END)]
        widths = [L.width(line) for line in lines]
        if unframed:
            found.append(f"{name} {effective}: {key} image text breaks into a line without a frame: {unframed[0][:40]}")
        elif max(widths) - min(widths) > 2:
            found.append(f"{name} {effective}: {key} image text breaks into lines of widths {min(widths)} to {max(widths)}")
    return found


def check_versions(name, versions, rows, listing, window_start, as_of):
    """Gates on the versions of one law. Returns problems and notes."""
    problems, notes = [], []
    seen = sum(len(L.as_list(p.get("law"))) for p in listing["pages"])
    if seen != listing["totalCnt"]:
        problems.append(f"{name}: list pages hold {seen} rows, totalCnt is {listing['totalCnt']}")
    chosen = L.choose_versions(rows)
    versions = {d: law for d, law in versions.items() if d >= L.in_force(chosen, window_start)}
    missing = sorted(d for d in chosen if d >= L.in_force(chosen, window_start) and d not in versions)
    if missing:
        problems.append(f"{name}: versions in the list but not collected {missing}")
    published_on = defaultdict(set)
    for row in rows:
        published_on[row["시행일자"]].add(row["공포일자"])
    units, texts = {}, {}
    for effective, law in versions.items():
        if law["기본정보"]["시행일자"] != effective:
            problems.append(f"{name} {effective}: response says {law['기본정보']['시행일자']}")
        revisions = [r["공포일자"] for r in rows if r.get("제개정구분명") in ("제정", "전부개정") and r["시행일자"] <= effective]
        since = max(revisions, default="")
        expected = {L.sup_key(r["공포일자"], r["공포번호"]) for r in rows if r["시행일자"] <= effective and r["공포일자"] >= since}
        units[effective] = L.law_units(law)
        texts[effective] = {key: L.version_text(text) for key, text in units[effective].items()}
        absent = sorted(expected - set(units[effective]))
        if absent:
            problems.append(f"{name} {effective}: 부칙 missing for promulgations {absent[:10]}")
        for annex in L.as_list(law.get("별표", {}).get("별표단위")):
            title = annex.get("별표제목", "")
            if "삭제" not in title and not L.canonical("".join(L.flatten(annex.get("별표내용")))):
                problems.append(f"{name} {effective}: empty {annex.get('별표구분')} {annex.get('별표번호')} {title[:30]}")
        for key, text in units[effective].items():
            problems += image_problems(name, effective, key, text)
    dates = list(versions)
    last_image = {}
    for key, text in units[dates[0]].items():
        if image_text(text):
            last_image[key] = (image_text(text), texts[dates[0]][key])
    for before, after in zip(dates, dates[1:]):
        old, new = units[before], units[after]
        flagged, moved = changed_flags(versions[after]), moved_from(versions[after])
        allowed = published_on[after]
        counts = defaultdict(int)
        for key in old.keys() - new.keys():
            if key in moved or deleted(old[key]):
                counts["removed"] += 1
            else:
                problems.append(f"{name} {before}->{after}: {key} removed with no move or earlier deletion")
        for key, text in new.items():
            current = texts[after][key]
            pictured = image_text(text)
            if pictured:
                seen_image = last_image.get(key)
                if seen_image and seen_image[0] != pictured and seen_image[1] == current:
                    problems.append(f"{name} {before}->{after}: {key} image text changed, version text did not")
                last_image[key] = (pictured, current)
            if texts[before].get(key, "") == current:
                if replaced_without_text(images(old.get(key, "")), images(text)):
                    problems.append(f"{name} {before}->{after}: {key} image files changed with no text to compare")
                continue
            if key.startswith("sup-") and key not in old and key.split("-")[1] in allowed:
                counts["new 부칙"] += 1
            elif set(L.amendment_dates(text)) & allowed:
                counts["tag"] += 1
            elif key in flagged:
                counts["flag"] += 1
            else:
                problems.append(f"{name} {before}->{after}: {key} changed with no amendment tag dated {sorted(allowed)} and no change flag")
        notes.append(
            f"{name} {before}->{after}: changed units explained by tag {counts['tag']}, flag {counts['flag']}, "
            f"new 부칙 {counts['new 부칙']}; removed {counts['removed']}"
        )
    current_units = units[L.in_force(dates, as_of)]
    textless = sorted(k for k, t in current_units.items() if L.IMAGE_TAG.search(t) and not image_text(t))
    if textless:
        notes.append(f"{name}: current units with images that carry no text, for review: {textless}")
    return problems, notes


def check_law(name, problems, notes):
    if not (L.CACHE / "law").exists():
        problems.append(f"{name}: no local cache; run scripts/collect.py laws first")
        return
    versions, rows, listing, _ = L.stored_versions(name)
    as_of, window_start = L.release()
    found, remarks = check_versions(name, versions, rows, listing, window_start, as_of)
    problems += found
    notes += remarks


attachments = L.note_attachments


def latest_retrievals():
    """The latest raw note of each source version, by retrieval time."""
    latest = {}
    for note in L.RAW.rglob("*.md"):
        match = NOTE.match(note.stem)
        if match:
            key = (note.parent, match["name"], match["date"], match["serial"])
            if key not in latest or note.stem > latest[key].stem:
                latest[key] = note
    return set(latest.values())


def check_reference(name, problems):
    """A reference law: its list pages, and its current and scheduled versions with the 시행일자 asked for."""
    versions, rows, listing, raw = L.stored_versions(name)
    seen = sum(len(L.as_list(p.get("law"))) for p in listing["pages"])
    if seen != listing["totalCnt"]:
        problems.append(f"{name}: list pages hold {seen} rows, totalCnt is {listing['totalCnt']}")
    chosen = L.choose_versions(rows)
    expected = {d for d in chosen if d >= L.in_force(chosen, L.release()[0])}
    if expected - set(raw):
        problems.append(f"{name}: current or scheduled versions not collected {sorted(expected - set(raw))}")
    for effective in raw:
        if versions[effective]["기본정보"]["시행일자"] != effective:
            problems.append(f"{name} {effective}: response says {versions[effective]['기본정보']['시행일자']}")


def check_notices(problems, notes):
    """Raw notes of 행정규칙: 시행일자 as named, and a text that is not empty."""
    for note in sorted(L.RAW.glob("law/*/*.md")):
        match = NOTE.match(note.stem)
        payload = note.with_suffix(".json")
        if not match or not payload.exists() or "AdmRulService" not in load(payload):
            continue
        service = load(payload)["AdmRulService"]
        if service["행정규칙기본정보"]["시행일자"] != match["date"]:
            problems.append(f"{note.name}: response says {service['행정규칙기본정보']['시행일자']}")
        stored = attachments(note, load(payload))
        try:
            text = L.notice_text(service, stored)
        except PyPdfError as error:
            problems.append(f"{note.name}: PDF attachment unreadable: {error}")
            continue
        if not L.canonical(text):
            problems.append(f"{note.name}: no text in the response or its PDF attachment")
    as_of, window_start = L.release()
    for listing in sorted((L.CACHE / "admrul").glob("*/versions.json")):
        chosen = load(listing)
        stored = {p.stem.split("-")[1] for p in listing.parent.glob("*-*.json")}
        stored |= {m["date"] for p in L.RAW.glob("law/*/*.md") if (m := NOTE.match(p.stem)) and m["serial"] in {r["행정규칙일련번호"] for r in chosen.values()}}
        missing = sorted(d for d in chosen if d >= L.in_force(chosen, window_start) and d not in stored)
        if missing:
            problems.append(f"행정규칙 {listing.parent.name}: versions in the list but not collected {missing}")
        notes.append(f"행정규칙 {listing.parent.name}: {len(chosen)} versions listed, {len(stored)} collected")


def check_notes(problems):
    """Required properties of every raw note, its sha256 against the stored files, and complete attachments in the latest retrieval.

    An earlier retrieval keeps the files it stored, such as a 법령 response stored before its images were collected.
    """
    latest = latest_retrievals()
    for note in sorted(L.RAW.rglob("*.md")):
        meta = L.frontmatter(note)
        missing = [k for k in REQUIRED if not meta.get(k)]
        if missing:
            problems.append(f"{note.relative_to(L.VAULT)}: missing {missing}")
        payload, page = note.with_suffix(".json"), note.with_suffix(".html")
        if payload.exists():
            text = payload.read_text(encoding="utf-8")
            stored = attachments(note, json.loads(text))
            if note in latest and len(stored) != L.attachment_count(json.loads(text)):
                problems.append(f"{note.relative_to(L.VAULT)}: attachments missing")
            digest = L.files_hash(text, [data for data, _ in stored])
        elif page.exists():
            sections, _ = collect.page_sections(page.read_text(encoding="utf-8"), meta["title"])
            digest = L.body_hash("\n".join(f"{k}\n{v}" for k, v in sections.items()))
        else:
            continue
        if digest != meta.get("sha256"):
            problems.append(f"{note.relative_to(L.VAULT)}: sha256 differs from the stored file")


def check_quotations(problems):
    """Quotations of 고용24 raw notes: numbered in the order of hasPart, declared as blocks with the same text, hashed, and found in the stored page."""
    for note in sorted((L.RAW / "work24").rglob("*.md")):
        where = note.relative_to(L.VAULT)
        meta = L.frontmatter(note)
        parts = meta.get("hasPart") or []
        blocks = collect.quotations(note)
        if set(blocks) != {f"q{n}" for n in range(1, len(parts) + 1)}:
            problems.append(f"{where}: quotation blocks {sorted(blocks)} do not match the {len(parts)} quotations of hasPart")
        page = note.with_suffix(".html")
        stored = ""
        if page.exists():
            sections, _ = collect.page_sections(page.read_text(encoding="utf-8"), meta["title"])
            stored = re.sub(r"\s+", "", "".join(sections.values()))
        for number, part in enumerate(parts, 1):
            text = part.get("text", "")
            if part.get("identifier") != f"{meta['identifier']}-q{number}":
                problems.append(f"{where}: quotation {number} has identifier {part.get('identifier')!r}")
            if blocks.get(f"q{number}") != text:
                problems.append(f"{where}: block ^q{number} differs from quotation {number} of hasPart")
            if part.get("sha256") != L.body_hash(text):
                problems.append(f"{where}: quotation {number} has a wrong sha256")
            if stored and re.sub(r"\s+", "", text) not in stored:
                problems.append(f"{where}: quotation {number} is not in the stored page")


def check_secrets(problems, notes):
    secrets = L.secrets()
    if not secrets:
        notes.append("no .env: secret check skipped")
        return
    for path in list(L.RAW.rglob("*")) + list(L.CACHE.rglob("*.json")):
        if path.is_file() and path.suffix in (".md", ".json", ".html"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if any(s in text for s in secrets):
                problems.append(f"{path.relative_to(L.VAULT)}: contains a secret value")


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    sources = yaml.safe_load((Path(__file__).parent / "sources.yaml").read_text(encoding="utf-8"))
    problems, notes = [], []
    for name in sources["laws"]:
        check_law(name, problems, notes)
    for name in sources.get("references", []):
        check_reference(name, problems)
    check_notices(problems, notes)
    check_notes(problems)
    check_quotations(problems)
    check_secrets(problems, notes)
    for line in notes:
        print(line)
    for line in problems:
        print("FAIL", line)
    print(f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
