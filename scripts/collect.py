"""Collect raw sources listed in scripts/sources.yaml.

Usage:
    uv run python -X utf8 scripts/collect.py [laws|admrul|work24|all]

Writes raw notes under raw/, keeps uncited earlier law versions in .cache/law/,
and writes a report to .cache/collect-<what>.json.
"""

import json
import re
import sys
import urllib.parse
from pathlib import Path

import yaml
from pypdf import PdfReader

import lawlib as L

SOURCES = yaml.safe_load((Path(__file__).parent / "sources.yaml").read_text(encoding="utf-8"))
ARTICLE = re.compile(r"제(\d+)조(?:의(\d+))?\(([^)]*)\)")
UNIT = re.compile(r"(?:법\s*|영\s*|규칙\s*)?제\d+조(?:의\d+)?(?:제\d+항)?(?:제\d+호)?")


def latest(folder, pattern):
    found = sorted(folder.glob(pattern))
    return found[-1] if found else None


def save_raw(folder, basename, meta, body, payload, payload_ext):
    """Write a raw note unless the latest retrieval of the same source has the same sha256."""
    stem = basename.rsplit(" ", 1)[0]
    previous = latest(folder, f"{stem} *.md")
    if previous and L.frontmatter(previous).get("sha256") == meta["sha256"]:
        return None
    note = folder / f"{basename}.md"
    L.write_note(note, meta, body)
    if payload_ext == ".json":
        L.write_json(folder / f"{basename}.json", payload)
    else:
        (folder / f"{basename}{payload_ext}").write_bytes(payload)
    return note


def version_list(name):
    rows, pages, page = [], [], 1
    while True:
        text, _ = L.law_api("lawSearch", target="eflaw", query=name, display=100, page=page)
        data = json.loads(text)["LawSearch"]
        pages.append(data)
        found = L.as_list(data.get("law"))
        rows += [r for r in found if r.get("법령명한글") == name]
        if page * 100 >= int(data["totalCnt"]):
            break
        page += 1
    seen = sum(len(L.as_list(p.get("law"))) for p in pages)
    return rows, pages, seen, int(pages[0]["totalCnt"])


def transitional(law, window_start):
    """경과조치 and 적용례 articles of 부칙 promulgated within the window."""
    found = []
    for unit in L.as_list(law["부칙"]["부칙단위"]):
        published = unit.get("부칙공포일자", "")
        if not published or L.ymd(published) < window_start:
            continue
        text = "\n".join(L.flatten(unit.get("부칙내용")))
        for match in ARTICLE.finditer(text):
            title = match.group(3)
            if "경과조치" not in title and "적용례" not in title:
                continue
            end = text.find("\n제", match.end())
            body = text[match.end(): end if end > 0 else None]
            found.append({
                "promulgation": unit.get("부칙공포번호"),
                "published": published,
                "article": f"제{match.group(1)}조" + (f"의{match.group(2)}" if match.group(2) else ""),
                "title": title,
                "units": sorted({m.group(0) for m in UNIT.finditer(body)}),
            })
    return found


def fetch_law(mst, effective):
    text, url = L.law_api("lawService", target="eflaw", MST=mst, efYd=effective)
    law = json.loads(text)["법령"]
    if law["기본정보"]["시행일자"] != effective:
        raise ValueError(f"MST {mst}: asked for {effective}, got {law['기본정보']['시행일자']}")
    return text, law, url


def collect_laws(as_of, window_start, stamp, generated, report):
    for name in SOURCES["laws"]:
        folder = L.RAW / "law" / name
        rows, pages, seen, total = version_list(name)
        listing = {"query": name, "totalCnt": total, "pages": pages}
        previous = latest(folder, f"{name} versions *.json")
        rows_key = sorted((r["법령일련번호"], r["시행일자"], r["공포번호"]) for r in rows)
        old_key = None
        if previous:
            old = json.loads(previous.read_text(encoding="utf-8"))
            old_rows = [r for p in old["pages"] for r in L.as_list(p.get("law")) if r.get("법령명한글") == name]
            old_key = sorted((r["법령일련번호"], r["시행일자"], r["공포번호"]) for r in old_rows)
        if rows_key != old_key:
            L.write_json(folder / f"{name} versions {stamp}.json", json.dumps(listing, ensure_ascii=False))
        chosen = L.choose_versions(rows)
        current = max(d for d in chosen if d <= as_of.strftime("%Y%m%d"))
        targets = [d for d in chosen if d >= current]
        law_id = rows[0]["법령ID"]
        entry = {"law": name, "rows": len(rows), "seen": seen, "totalCnt": total, "current": current,
                 "scheduled": targets[1:], "written": [], "cached": []}
        current_law = None
        for effective in targets:
            mst = chosen[effective]["법령일련번호"]
            text, law, url = fetch_law(mst, effective)
            if effective == current:
                current_law = law
            meta = {
                "identifier": f"raw-law-{law_id}-{effective}-{mst}-{stamp.lower()}",
                "title": name,
                "publisher": L.PUBLISHERS["law"],
                "url": url,
                "generatedAtTime": generated,
                "sha256": L.sha256(L.law_text(law)),
                "license": L.LICENSES["law"],
            }
            body = f"{name}의 {effective} 시행 버전 원문 노트다. 원문 응답은 같은 이름의 JSON 파일이다."
            note = save_raw(folder, f"{name} {effective}-{mst} {stamp}", meta, body, text, ".json")
            if note:
                entry["written"].append(note.name)
        cache = L.CACHE / "law" / law_id
        first = L.in_force(chosen, window_start)
        for effective in (d for d in chosen if first <= d < current):
            mst = chosen[effective]["법령일련번호"]
            path = cache / f"{mst}-{effective}.json"
            if not path.exists():
                text, _, _ = fetch_law(mst, effective)
                L.write_json(path, text)
                entry["cached"].append(path.name)
        entry["transitional"] = transitional(current_law, window_start)
        report["laws"].append(entry)
        print(f"{name}: current {current}, scheduled {targets[1:]}, written {len(entry['written'])}, cached {len(entry['cached'])}")


def pdf_text(data):
    import io
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def collect_admrul(as_of, stamp, generated, report):
    for source in SOURCES["admrul"]:
        text, _ = L.law_api("lawSearch", target="admrul", query=source["query"], display=100)
        rows = [r for r in L.as_list(json.loads(text)["AdmRulSearch"].get("admrul")) if r.get("행정규칙ID") == source["id"]]
        by_date = {}
        for row in rows:
            key = row["시행일자"]
            rank = (row.get("발령일자", ""), row.get("행정규칙일련번호", ""))
            if key not in by_date or rank > by_date[key][0]:
                by_date[key] = (rank, row)
        current = max(d for d in by_date if d <= as_of.strftime("%Y%m%d"))
        for effective in sorted(d for d in by_date if d >= current):
            row = by_date[effective][1]
            serial = row["행정규칙일련번호"]
            name = row["행정규칙명"]
            body_text, url = L.law_api("lawService", target="admrul", ID=serial)
            service = json.loads(body_text)["AdmRulService"]
            article_text = "\n".join(L.flatten(service.get("조문내용")))
            links = L.as_list(service.get("첨부파일", {}).get("첨부파일링크"))
            names = L.as_list(service.get("첨부파일", {}).get("첨부파일명"))
            attachments = [L.get(link) for link in links]
            if not article_text:
                main = next((i for i, n in enumerate(names) if name in n), 0)
                article_text = pdf_text(attachments[main])
            folder = L.RAW / "law" / name
            basename = f"{name} {effective}-{serial} {stamp}"
            meta = {
                "identifier": f"raw-admrul-{source['id']}-{effective}-{serial}-{stamp.lower()}",
                "title": name,
                "publisher": L.PUBLISHERS["law"],
                "url": url,
                "generatedAtTime": generated,
                "sha256": L.sha256(article_text),
                "license": L.LICENSES["admrul"],
            }
            body = f"{name}의 원문 노트다. 원문 응답은 같은 이름의 JSON 파일이고, 첨부파일은 같은 이름 뒤에 번호를 붙여 둔다."
            note = save_raw(folder, basename, meta, body, body_text, ".json")
            if note:
                for index, (data, file_name) in enumerate(zip(attachments, names), start=1):
                    (folder / f"{basename}-{index}{Path(file_name).suffix}").write_bytes(data)
            report["admrul"].append({"name": name, "effective": effective, "written": bool(note), "chars": len(L.canonical(article_text))})
            print(f"{name}: {effective}, written {bool(note)}")


def page_sections(html, title):
    html = re.sub(r"<!--.*?-->|<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    start = html.find(f">{title}<")
    end = html.find("최종 수정일", start)
    if start < 0 or end < 0:
        raise ValueError("body area not found")
    region = html[start:end]
    parts = re.split(r"<h[2-4][^>]*>(.*?)</h[2-4]>", region, flags=re.S)
    sections = {}
    for heading, content in zip(parts[1::2], parts[2::2]):
        text = re.sub(r"<[^>]+>", " ", content).replace("&nbsp;", " ")
        sections[re.sub(r"<[^>]+>|\s+", " ", heading).strip()] = re.sub(r"[ \t]+", " ", text).strip()
    modified = re.search(r"최종 수정일:\s*(\d{4}-\d{2}-\d{2})", html[end: end + 200])
    return sections, modified.group(1) if modified else None


def collect_work24(stamp, generated, report):
    for source in SOURCES["work24"]:
        html = L.get(source["url"]).decode("utf-8", errors="replace")
        sections, modified = page_sections(html, source["name"])
        filled = {k: v for k, v in sections.items() if L.canonical(v)}
        if not filled:
            raise ValueError(f"{source['name']}: no text in the body area")
        text = "\n".join(f"{k}\n{v}" for k, v in sections.items())
        system = urllib.parse.parse_qs(urllib.parse.urlparse(source["url"]).query)["systId"][0].lower()
        folder = L.RAW / "work24" / source["name"]
        basename = f"{source['name']} {stamp}"
        meta = {
            "identifier": f"raw-work24-{system}-{stamp.lower()}",
            "title": source["name"],
            "publisher": L.PUBLISHERS["work24"],
            "url": source["url"],
            "generatedAtTime": generated,
            "sha256": L.sha256(text),
            "license": L.LICENSES["work24"],
        }
        if modified:
            meta["modified"] = modified
        body = f"고용24 {source['name']} 안내의 원문 노트다. 본문은 같은 이름의 HTML 파일이며 Git에 넣지 않는다."
        note = save_raw(folder, basename, meta, body, html.encode("utf-8"), ".html")
        empty = sorted(set(sections) - set(filled))
        report["work24"].append({"name": source["name"], "written": bool(note), "sections": list(sections), "empty": empty, "modified": modified})
        print(f"{source['name']}: sections {len(sections)}, empty {empty}, written {bool(note)}")


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    as_of, window_start = L.release()
    stamp_time, stamp = L.now()
    generated = stamp_time.isoformat()
    report = {"asOf": str(as_of), "windowStart": str(window_start), "stamp": stamp, "laws": [], "admrul": [], "work24": []}
    if what in ("laws", "all"):
        collect_laws(as_of, window_start, stamp, generated, report)
    if what in ("admrul", "all"):
        collect_admrul(as_of, stamp, generated, report)
    if what in ("work24", "all"):
        collect_work24(stamp, generated, report)
    L.CACHE.mkdir(exist_ok=True)
    (L.CACHE / f"collect-{what}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
