"""Collect raw sources listed in scripts/sources.yaml.

Usage:
    uv run python -X utf8 scripts/collect.py [laws|admrul|work24|shapes|all]

Writes raw notes under raw/, keeps uncited earlier versions in .cache/law/ and
.cache/admrul/, and writes a report to .cache/collect-<what>.json.
"""

import html as htmllib
import json
import re
import sys
import urllib.parse
from pathlib import Path

import yaml

import lawlib as L

SOURCES = yaml.safe_load((Path(__file__).parent / "sources.yaml").read_text(encoding="utf-8"))
DRAFT = re.compile(r"안\s*고시$")


def latest(folder, pattern):
    found = sorted(folder.glob(pattern))
    return found[-1] if found else None


def images(text):
    """The image files a response links to, as (content, extension) pairs in order of first appearance."""
    files = []
    for link in L.image_links(json.loads(text)):
        data = L.get(link)
        files.append((data, L.extension(data)))
    return files


def cached_images(path):
    """Whether a cached response has every attachment and image file stored next to it."""
    response = json.loads(path.read_text(encoding="utf-8"))
    return len(L.stored_attachments(path.parent, path.stem)) == L.attachment_count(response)


def write_attachments(folder, basename, files):
    """Write attachments as <basename>-1, <basename>-2 and so on, with their own extensions."""
    for index, (data, suffix) in enumerate(files, start=1):
        (folder / f"{basename}-{index}{suffix}").write_bytes(data)


def unchanged(folder, basename, digest):
    """Whether the latest retrieval of the same source has the same sha256."""
    stem = basename.rsplit(" ", 1)[0]
    previous = latest(folder, f"{stem} *.md")
    return bool(previous) and L.frontmatter(previous).get("sha256") == digest


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


def fetch_law(mst, effective):
    text, url = L.law_api("lawService", target="eflaw", MST=mst, efYd=effective)
    law = json.loads(text)["법령"]
    if law["기본정보"]["시행일자"] != effective:
        raise ValueError(f"MST {mst}: asked for {effective}, got {law['기본정보']['시행일자']}")
    return text, url


def collect_laws(as_of, window_start, stamp, generated, report):
    """Laws in scope with their earlier versions in the window, and reference laws with their current and scheduled versions only."""
    for name in SOURCES["laws"] + SOURCES.get("references", []):
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
        current = L.in_force(chosen, as_of)
        law_id = rows[0]["법령ID"]
        entry = {"law": name, "rows": len(rows), "seen": seen, "totalCnt": total, "current": current,
                 "scheduled": [d for d in chosen if d > current], "written": [], "cached": []}
        for effective in (d for d in chosen if d >= current):
            mst = chosen[effective]["법령일련번호"]
            text, url = fetch_law(mst, effective)
            files = images(text)
            basename = f"{name} {effective}-{mst} {stamp}"
            digest = L.files_hash(L.json_payload(text), [data for data, _ in files])
            if unchanged(folder, basename, digest):
                continue
            L.write_json(folder / f"{basename}.json", text)
            write_attachments(folder, basename, files)
            meta = {
                "identifier": f"raw-law-{law_id}-{effective}-{mst}-{stamp.lower()}",
                "title": name,
                "publisher": L.PUBLISHERS["law"],
                "url": url,
                "generatedAtTime": generated,
                "sha256": digest,
                "license": L.LICENSES["law"],
            }
            body = f"{name}의 {effective} 시행 버전 원문 노트다. 원문 응답은 같은 이름의 JSON 파일이고, 응답이 링크하는 이미지는 같은 이름 뒤에 나오는 순서대로 번호를 붙여 둔다."
            L.write_note(folder / f"{basename}.md", meta, body)
            entry["written"].append(f"{basename}.md")
        cache = L.CACHE / "law" / law_id
        earlier = [d for d in chosen if L.in_force(chosen, window_start) <= d < current] if name in SOURCES["laws"] else []
        for effective in earlier:
            mst = chosen[effective]["법령일련번호"]
            path = cache / f"{mst}-{effective}.json"
            if not path.exists():
                text, _ = fetch_law(mst, effective)
                L.write_json(path, text)
                entry["cached"].append(path.name)
        report["laws"].append(entry)
        print(f"{name}: current {current}, scheduled {entry['scheduled']}, written {len(entry['written'])}, cached {len(entry['cached'])}")


def notices(source):
    """Versions of an administrative rule by 시행일자, without proposals such as 최저임금안 고시."""
    found, page = [], 1
    while True:
        text, _ = L.law_api("lawSearch", target="admrul", query=source["query"], display=100, nw=2, page=page)
        data = json.loads(text)["AdmRulSearch"]
        found += L.as_list(data.get("admrul"))
        if page * 100 >= int(data["totalCnt"]):
            break
        page += 1
    if len(found) != int(data["totalCnt"]):
        raise ValueError(f"{source['query']}: {len(found)} rows for totalCnt {data['totalCnt']}")
    rows = [r for r in found if r.get("행정규칙ID") == source["id"] and not DRAFT.search(r["행정규칙명"])]
    by_date = {}
    for row in rows:
        rank = (row.get("발령일자", ""), int(row.get("행정규칙일련번호", "0")))
        if row["시행일자"] not in by_date or rank > by_date[row["시행일자"]][0]:
            by_date[row["시행일자"]] = (rank, row)
    return {d: row for d, (_, row) in sorted(by_date.items())}


def fetch_notice(row):
    """The 행정규칙 response, its attachments and its text, which is in a PDF when 조문내용 is empty."""
    text, url = L.law_api("lawService", target="admrul", ID=row["행정규칙일련번호"])
    service = json.loads(text)["AdmRulService"]
    effective = service.get("행정규칙기본정보", {}).get("시행일자")
    if effective != row["시행일자"]:
        raise ValueError(f"{row['행정규칙명']}: listed for {row['시행일자']}, response says {effective}")
    links = L.as_list(service.get("첨부파일", {}).get("첨부파일링크"))
    names = L.as_list(service.get("첨부파일", {}).get("첨부파일명"))
    attached = [(L.get(link), Path(name).suffix) for link, name in zip(links, names)]
    return text, url, attached + images(text)


def collect_admrul(as_of, window_start, stamp, generated, report):
    for source in SOURCES["admrul"]:
        chosen = notices(source)
        current = L.in_force(chosen, as_of)
        listing = L.CACHE / "admrul" / source["id"] / "versions.json"
        L.write_json(listing, json.dumps(chosen, ensure_ascii=False))
        for effective, row in chosen.items():
            if effective < L.in_force(chosen, window_start):
                continue
            serial, name = row["행정규칙일련번호"], row["행정규칙명"]
            if effective < current:
                cache = L.CACHE / "admrul" / source["id"]
                path = cache / f"{serial}-{effective}.json"
                if not path.exists() or not cached_images(path):
                    text, _, files = fetch_notice(row)
                    L.write_json(path, text)
                    write_attachments(cache, path.stem, files)
                report["admrul"].append({"name": name, "effective": effective, "cached": path.name})
                continue
            text, url, files = fetch_notice(row)
            folder = L.RAW / "law" / name
            basename = f"{name} {effective}-{serial} {stamp}"
            digest = L.files_hash(L.json_payload(text), [data for data, _ in files])
            written = not unchanged(folder, basename, digest)
            if written:
                L.write_json(folder / f"{basename}.json", text)
                write_attachments(folder, basename, files)
                meta = {
                    "identifier": f"raw-admrul-{source['id']}-{effective}-{serial}-{stamp.lower()}",
                    "title": name,
                    "publisher": L.PUBLISHERS["law"],
                    "url": url,
                    "generatedAtTime": generated,
                    "sha256": digest,
                    "license": L.LICENSES["admrul"],
                }
                body = f"{name}의 원문 노트다. 원문 응답은 같은 이름의 JSON 파일이고, 첨부파일은 같은 이름 뒤에 응답의 순서대로 번호를 붙여 둔다."
                L.write_note(folder / f"{basename}.md", meta, body)
            report["admrul"].append({"name": name, "effective": effective, "written": written})
            print(f"{name}: {effective}, written {written}")


def page_sections(html, title):
    """Sections of a 고용24 guide, from each anchor of its table of contents to the next."""
    html = re.sub(r"<!--.*?-->|<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    start = html.find(f">{title}<")
    end = html.find("최종 수정일", start)
    if start < 0 or end < 0:
        raise ValueError("body area not found")
    region = html[start:end]
    contents = re.search(r'<ul class="box_list_doc[^"]*">(.*?)</ul>', region, re.S)
    if not contents:
        raise ValueError("table of contents not found")
    anchors = re.findall(r'href="#([A-Z]{2}\d+)"[^>]*>([^<]+)<', contents.group(1))
    positions = [region.find(f'id="{anchor}"') for anchor, _ in anchors]
    if min(positions) < 0:
        raise ValueError("a section of the table of contents is missing")
    positions = [region.rfind("<", 0, position) for position in positions]
    last = region.find("<h3", positions[-1] + 1)
    bounds = [*positions[1:], last if last > 0 else len(region)]
    sections = {}
    for (_, heading), begin, finish in zip(anchors, positions, bounds):
        chunk = re.sub(r"<h3[^>]*>.*?</h3>", " ", region[begin:finish], flags=re.S)
        text = htmllib.unescape(re.sub(r"<[^>]+>", " ", chunk))
        sections[heading.strip()] = re.sub(r"[ \t ]+", " ", text).strip()
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
        digest = L.body_hash(text)
        written = not unchanged(folder, basename, digest)
        if written:
            (folder / f"{basename}.html").parent.mkdir(parents=True, exist_ok=True)
            (folder / f"{basename}.html").write_bytes(html.encode("utf-8"))
            meta = {
                "identifier": f"raw-work24-{system}-{stamp.lower()}",
                "title": source["name"],
                "publisher": L.PUBLISHERS["work24"],
                "url": source["url"],
                "generatedAtTime": generated,
                "sha256": digest,
                "license": L.LICENSES["work24"],
            }
            if modified:
                meta["modified"] = modified
            body = f"고용24 {source['name']} 안내의 원문 노트다. 본문은 같은 이름의 HTML 파일이며 Git에 넣지 않는다."
            L.write_note(folder / f"{basename}.md", meta, body)
        empty = sorted(set(sections) - set(filled))
        report["work24"].append({"name": source["name"], "written": written, "sections": list(sections), "empty": empty, "modified": modified})
        print(f"{source['name']}: sections {len(sections)}, empty {empty}, written {written}")


def collect_shapes(generated, report):
    """Official SHACL shapes of the standards the schema follows, stored with their attribution."""
    folder = L.VAULT / "ontology" / "shapes"
    folder.mkdir(parents=True, exist_ok=True)
    lines = ["# 공식 SHACL shape", "", "schema가 따르는 표준의 공식 SHACL shape이다. `scripts/vault.py check`가 RDF를 이 shape으로도 검사한다.", "",
             "| 파일 | 표준 | 원본 | 이용 조건 | 수집 일시 | SHA-256 |", "| --- | --- | --- | --- | --- | --- |"]
    for source in SOURCES.get("shapes", []):
        data = L.get(source["url"])
        path = folder / source["file"]
        written = not path.exists() or path.read_bytes() != data
        if written:
            path.write_bytes(data)
        digest = L.sha256(path.read_text(encoding="utf-8"))
        lines.append(f"| `{source['file']}` | {source['name']} | [{source['url'].rsplit('/', 1)[-1]}]({source['url']}) | {source['license']} | {generated[:16].replace('T', ' ')} | `{digest[:12]}` |")
        report["shapes"].append({"file": source["file"], "written": written})
        print(f"{source['file']}: written {written}")
    readme = folder / "README.md"
    previous = readme.read_text(encoding="utf-8") if readme.exists() else ""
    if any(entry["written"] for entry in report["shapes"]) or not previous:
        readme.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    as_of, window_start = L.release()
    stamp_time, stamp = L.now()
    generated = stamp_time.isoformat()
    report = {"asOf": str(as_of), "windowStart": str(window_start), "stamp": stamp, "laws": [], "admrul": [], "work24": [], "shapes": []}
    if what in ("laws", "all"):
        collect_laws(as_of, window_start, stamp, generated, report)
    if what in ("admrul", "all"):
        collect_admrul(as_of, window_start, stamp, generated, report)
    if what in ("work24", "all"):
        collect_work24(stamp, generated, report)
    if what in ("shapes", "all"):
        collect_shapes(generated, report)
    L.CACHE.mkdir(exist_ok=True)
    (L.CACHE / f"collect-{what}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
