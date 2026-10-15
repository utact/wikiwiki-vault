"""Shared helpers for collecting and checking raw sources."""

import glob
import hashlib
import io
import json
import re
import time
import urllib.parse
import urllib.request
from collections import namedtuple
from datetime import date, datetime, timedelta, timezone
from itertools import accumulate
from pathlib import Path

import yaml
from pypdf import PdfReader

VAULT = Path(__file__).resolve().parents[1]
RAW = VAULT / "raw"
CACHE = VAULT / ".cache"
KST = timezone(timedelta(hours=9))
LAW_API = "http://www.law.go.kr/DRF"
PUBLISHERS = {"law": "ministry-of-government-legislation", "work24": "korea-employment-information-service"}
LICENSES = {
    "law": "저작권법 제7조에 따라 보호받지 않는 저작물",
    "admrul": "저작권법 제7조에 따라 보호받지 않는 저작물",
    "work24": "공공누리 표시 없음. 한국고용정보원 저작권정책에 따라 재배포 전 사전 협의 필요",
}
TAG = re.compile(
    r"<(?:개정|신설|전문개정|삭제|본조신설)[^>]*>"
    r"|<\s*\d{4}\.[\d.,\s]*>"
    r"|\[(?:본조신설|전문개정|제목개정|본조제목개정|종전)[^\]]*\]"
)
TAG_DATE = re.compile(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})")
IMAGE = re.compile(r"<img\b[^>]*>(?:(?!<img\b).)*?</img>", re.S)
IMAGE_TAG = re.compile(r"</?img\b[^>]*>")
BOX = re.compile(r"[─-╿]")
LINE_END = "│┃┤┨┫┐┓┘┛"
LINE_START = "│┃├┠┣┌┏└┗"
LINE_BREAK = re.compile(f"(?<=[{LINE_END}])(?=[{LINE_START}])")
WIDE = re.compile(r"[^\x00-\x7f]")
LOST_GLYPH = re.compile(r"(?<=[^\x00-\x7f])\?(?=[^\x00-\x7f])")


def env():
    """Values in .env, or none in a clone without it."""
    values = {}
    path = VAULT / ".env"
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def secrets():
    """Strings that must never be stored: API keys, and the 법제처 OC as a parameter."""
    values = env()
    found = [v for k, v in values.items() if k != "LAW_OC" and len(v) >= 8]
    if values.get("LAW_OC"):
        found.append(f"OC={values['LAW_OC']}")
    return found


def release():
    """The reference date and the first day of the transitional window, from ontology/release.yaml."""
    data = yaml.safe_load((VAULT / "ontology" / "release.yaml").read_text(encoding="utf-8"))
    as_of = data["asOf"] if isinstance(data["asOf"], date) else date.fromisoformat(str(data["asOf"]))
    return as_of, window_start(as_of, data["transitionalWindow"])


def window_start(as_of, period):
    """The day a period such as P6Y120D before a date, counting 29 February as 28 February in other years."""
    match = re.fullmatch(r"P(\d+)Y(\d+)D", period)
    years, days = int(match.group(1)), int(match.group(2))
    day = 28 if (as_of.month, as_of.day) == (2, 29) else as_of.day
    return as_of.replace(year=as_of.year - years, day=day) - timedelta(days=days)


def now():
    stamp = datetime.now(KST).replace(second=0, microsecond=0)
    return stamp, stamp.strftime("%Y%m%dT%H%M")


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def flatten(value):
    if isinstance(value, list):
        for item in value:
            yield from flatten(item)
    elif value:
        yield str(value)


def without_images(text):
    """Text without embedded image elements, the table text inside them and stray image tags."""
    return IMAGE_TAG.sub("", IMAGE.sub("", text))


def columns(line):
    """Display column of each index of a line, and of its end: ASCII is 1 wide and the rest 2.

    A "?" between two wide characters stands for a lost wide glyph, such as an arrow, and is 2 wide.
    """
    widths = [1 if ch < "\x80" else 2 for ch in line]
    if "?" in line:
        for match in LOST_GLYPH.finditer(line):
            widths[match.start()] = 2
    return [0, *accumulate(widths)]


def width(line):
    """Display width of a line, counted as in columns()."""
    return len(line) + len(WIDE.findall(line)) + (len(LOST_GLYPH.findall(line)) if "?" in line else 0)


def image_lines(text):
    """Lines of the table text in an image element, which comes without line breaks.

    A line end followed by a line start, such as "││", marks a break, because these tables
    have no cell without spaces.
    """
    return text if "\n" in text.strip("\n") else "\n".join(LINE_BREAK.split(text))


def segments(text):
    """Runs of text between box-drawing characters, as (line, start column, end column, text, boxed).

    boxed tells whether the line has box-drawing characters. Runs of spaces are left out:
    they carry no text and change with the layout.
    """
    found = []
    for number, line in enumerate(text.split("\n")):
        if not line.strip():
            continue
        if not BOX.search(line):
            found.append((number, 0, width(line), line, False))
            continue
        column = columns(line)
        start = 0
        for match in [*BOX.finditer(line), None]:
            end = match.start() if match else len(line)
            if line[start:end].strip():
                found.append((number, column[start], column[end], line[start:end], True))
            if match:
                start = match.end()
    return found


Cell = namedtuple("Cell", "table lines")


def cells(text):
    """Cells of box-drawing tables and the paragraphs around them, in reading order.

    Segments on adjacent lines that start at about the same display column and overlap belong
    to one cell, so a cell keeps its wrapped lines together whatever the widths of the other
    columns, and text that runs past a border does not join the next column. Lines with
    box-drawing characters and lines without them never join. Cells are ordered by their
    first line, then by column.
    """
    text = IMAGE.sub(lambda m: "\n" + image_lines(IMAGE_TAG.sub("", m.group(0))) + "\n", text)
    found = segments(IMAGE_TAG.sub("", text))
    parent = list(range(len(found)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by_line = {}
    for i, segment in enumerate(found):
        by_line.setdefault(segment[0], []).append(i)
    for number, indices in by_line.items():
        for i in indices:
            for j in by_line.get(number - 1, []):
                if found[i][4] != found[j][4] or abs(found[i][1] - found[j][1]) > 2:
                    continue
                overlap = min(found[i][2], found[j][2]) - max(found[i][1], found[j][1])
                narrow = min(found[i][2] - found[i][1], found[j][2] - found[j][1]) < 2
                if overlap >= (1 if narrow else 2):
                    parent[root(i)] = root(j)
    groups = {}
    for i in range(len(found)):
        groups.setdefault(root(i), []).append(i)
    ordered = sorted(groups.values(), key=lambda g: (found[g[0]][0], found[g[0]][1]))
    return [Cell(found[group[0]][4], tuple(found[i][3] for i in group)) for group in ordered]


def cell_order(text):
    """Text with box-drawing tables read cell by cell, one cell after another."""
    return "\n".join("\n".join(cell.lines) for cell in cells(text))


def number_text(text, wrapped=False):
    """Text for reading numbers as tokens, with a line break between cells.

    Lines of a table cell, and every line of wrapped text such as 별표, 별지 서식 and PDF text, wrap in the middle of words, as in "210" and "만원", so they join without a break. Lines of 조문 fields stay apart, because each is a 항, 호 or 목.
    """
    return "\n".join(
        "".join(line.strip() for line in cell.lines) if cell.table or wrapped else "\n".join(cell.lines)
        for cell in cells(text)
    )


def canonical(text):
    """Comparison text for quotes: cell order without whitespace and box-drawing characters."""
    return re.sub(r"\s+", "", cell_order(text))


def version_text(text):
    """Version text for hashes and version changes: comparison text without image elements."""
    return canonical(without_images(text))


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


IMAGE_REFERENCE = re.compile(r'<img\b[^>]*?(?:src="([^"]+)"|id="(\d+)")[^>]*>')
FILE_URL = "http://www.law.go.kr/flDownload.do?flSeq={}"
SIGNATURES = {b"GIF8": ".gif", b"\x89PNG": ".png", b"\xff\xd8\xff": ".jpg", b"BM": ".bmp"}


def strings(value):
    """Every string of a parsed JSON value, in document order."""
    if isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


def image_links(response):
    """URLs of the image files a 법제처 response links to, in order of first appearance.

    An image appears as <img src="..."> or, in some 고시, as <img id="..."> with the file number only.
    """
    links = []
    for text in strings(response):
        for match in IMAGE_REFERENCE.finditer(text):
            link = match.group(1) or FILE_URL.format(match.group(2))
            if link not in links:
                links.append(link)
    return links


def attachment_count(response):
    """Number of files a raw note of this response stores: the attachments of a 고시, then the linked images."""
    names = as_list(response.get("AdmRulService", {}).get("첨부파일", {}).get("첨부파일명"))
    return len(names) + len(image_links(response))


def stored_attachments(folder, stem):
    """Attachment files stored next to a raw note as <stem>-1, <stem>-2 and so on, up to the first gap."""
    found = []
    while matches := sorted(folder.glob(f"{glob.escape(stem)}-{len(found) + 1}.*")):
        found.append(matches[0])
    return found


def extension(data):
    """File extension of an image from its first bytes."""
    return next((suffix for signature, suffix in SIGNATURES.items() if data.startswith(signature)), ".bin")


def files_hash(payload, attachments=()):
    """SHA-256 of a stored response followed by the bytes of its attachments in their order."""
    digest = hashlib.sha256(payload.encode("utf-8"))
    for data in attachments:
        digest.update(data)
    return digest.hexdigest()


def body_hash(text):
    """Hash of a 고용24 body area, whose page stays out of Git: the SHA-256 of its text without whitespace."""
    return sha256(re.sub(r"\s+", "", text))


def scrub(text):
    """Remove credential parameters, then fail if any secret value is still present."""
    text = re.sub(r"([?&])OC=[^&\"'\s<>]*&?", r"\1", text)
    text = re.sub(r"[?&](?=[\"'\s<>])", "", text)
    for secret in secrets():
        if secret in text:
            raise ValueError("a secret value survived scrubbing")
    return text


def get(url, timeout=90):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))


def law_api(endpoint, **params):
    """Call the 법제처 API and return (scrubbed text, public URL without OC)."""
    public = f"{LAW_API}/{endpoint}.do?" + urllib.parse.urlencode({"type": "JSON", **params})
    query = urllib.parse.urlencode({"OC": env()["LAW_OC"], "type": "JSON", **params})
    text = get(f"{LAW_API}/{endpoint}.do?{query}").decode("utf-8")
    return scrub(text), public


def law_units(law):
    """Canonical text of every unit of an eflaw response, keyed as in identifiers.

    부칙 are keyed by 공포일자 and 공포번호, because two 부칙 can share a 공포번호, such as the two 제263호 of 고용보험법 시행규칙 dated 2019-09-30 and 2019-10-15.
    """
    units, levels = {}, {}

    def put(key, text):
        if key in units:
            raise ValueError(f"two units with the key {key}")
        units[key] = text

    for row in as_list(law.get("조문", {}).get("조문단위")):
        parts = [row.get("조문내용", "")]
        for p in as_list(row.get("항")):
            parts.append(p.get("항내용", ""))
            for h in as_list(p.get("호")):
                parts.append(h.get("호내용", ""))
                for m in as_list(h.get("목")):
                    parts.append("".join(flatten(m.get("목내용"))))
        parts.append(row.get("조문참고자료", ""))
        text = "\n".join(x for x in parts if x)
        if row.get("조문여부") == "조문":
            key = article_key(row["조문번호"], row.get("조문가지번호"))
        else:
            key = heading_key(text, levels) or f"heading-{row.get('조문키')}"
        put(key, text)
    for row in as_list(law.get("별표", {}).get("별표단위")):
        kind = "annex" if row.get("별표구분") == "별표" else "form"
        number = row.get("별표번호", "").lstrip("0") or "0"
        branch = row.get("별표가지번호", "00").lstrip("0")
        put(f"{kind}-{number}" + (f"-{branch}" if branch else ""), "\n".join(flatten(row.get("별표내용"))))
    for row in as_list(law.get("부칙", {}).get("부칙단위")):
        put(sup_key(row.get("부칙공포일자", ""), row.get("부칙공포번호", "")), "\n".join(flatten(row.get("부칙내용"))))
    return units


def article_key(number, branch):
    """Key of an article, such as art-56-10 for 제56조의10."""
    return f"art-{int(number)}" + (f"-{int(branch)}" if branch and int(branch) else "")


HEADING = re.compile(r"\s*제(\d+)(편|장|절|관)(?:의(\d+))?")
LEVELS = {"편": "part", "장": "ch", "절": "sec", "관": "sub"}


def heading_key(text, levels):
    """Key of a 편, 장, 절 or 관 heading from its place in the hierarchy, such as heading-ch4-sec1."""
    match = HEADING.match(text)
    if not match:
        return None
    number = match.group(1) + (f"-{match.group(3)}" if match.group(3) else "")
    order = list(LEVELS.values())
    level = LEVELS[match.group(2)]
    for lower in order[order.index(level):]:
        levels.pop(lower, None)
    levels[level] = number
    return "heading-" + "-".join(f"{name}{levels[name]}" for name in order if name in levels)


def promulgation(number):
    """공포번호 as an integer, from forms such as "00479" and "제21473호"."""
    return int(re.sub(r"\D", "", number) or 0)


def sup_key(published, number):
    return f"sup-{published}-{promulgation(number)}"


def amendment_dates(text):
    """Dates in amendment tags such as <개정 2019.1.15, 2021.1.5>, as YYYYMMDD."""
    found = []
    for match in TAG.finditer(text):
        found += [f"{y}{int(m):02d}{int(d):02d}" for y, m, d in TAG_DATE.findall(match.group(0))]
    return found


SUP_ARTICLE = re.compile(r"(?:^|\n)\s*제(\d+)조(?:의(\d+))?\(([^)\n]*)\)")
TRANSITIONAL = re.compile(r"경과조치|적용례|특례|유효기간")
OWN_ARTICLES = re.compile(r"부칙\s*제\d+조(?:의\d+)?(?:\s*(?:부터|,|및|ㆍ|·|와|과)\s*제\d+조(?:의\d+)?)*(?:\s*까지)?")
REFERENCE = re.compile(
    r"(?:「[^」]+」\s*)?(?:별지\s*)?제\d+호(?:의\d+)?\s*서식"
    r"|(?:「[^」]+」\s*)?별표\s*\d+(?:의\d+)?"
    r"|같은\s*조\s*제\d+항(?:\s*제\d+호(?:의\d+)?)?(?:\s*각\s*호\s*외의\s*부분)?(?:\s*(?:본문|단서|전단|후단))?"
    r"|(?<!부칙 )(?<!부칙)(?:「[^」]+」\s*|(?:법|영|규칙)\s*)?제\d+조(?:의\d+)?(?:\s*제\d+항)?(?:\s*제\d+호(?:의\d+)?)?"
    r"(?:\s*각\s*호\s*외의\s*부분)?(?:\s*(?:본문|단서|전단|후단))?"
)


def transitional(laws, rows, window_start):
    """Articles of 부칙 titled 경과조치, 적용례, 특례 or 유효기간 whose promulgation still comes into force within the window.

    laws are the current and scheduled versions, whose 부칙 together cover every promulgation, and rows the version list.
    A promulgation counts when any of its 시행일자 is on or after the first day of the window.
    """
    effective = {}
    for row in rows:
        effective.setdefault((row["공포일자"], promulgation(row["공포번호"])), set()).add(row["시행일자"])
    start = window_start.strftime("%Y%m%d")
    seen, found = set(), []
    for law in laws:
        for unit in as_list(law["부칙"]["부칙단위"]):
            key = (unit.get("부칙공포일자", ""), promulgation(unit.get("부칙공포번호", "")))
            if key in seen:
                continue
            seen.add(key)
            dates = effective.get(key, {key[0]})
            if max(dates) < start:
                continue
            text = "\n".join(flatten(unit.get("부칙내용")))
            articles = list(SUP_ARTICLE.finditer(text))
            for match, following in zip(articles, [*articles[1:], None]):
                if not TRANSITIONAL.search(match.group(3)):
                    continue
                body = text[match.end(): following.start() if following else None]
                body = OWN_ARTICLES.sub(" ", body)
                units = [re.sub(r"\s+", " ", m.group(0)).strip() for m in REFERENCE.finditer(body)]
                found.append({
                    "promulgation": f"{key[0]}-{key[1]}",
                    "effective": sorted(dates),
                    "article": f"제{match.group(1)}조" + (f"의{match.group(2)}" if match.group(2) else ""),
                    "title": match.group(3),
                    "units": list(dict.fromkeys(units)),
                })
    return found


def pdf_text(data):
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def notice_text(service, attachments):
    """Text of a 고시: its 조문내용, then the text of the PDF attachment named after it.

    Some years keep the text only in the PDF, and 조문내용 is empty or points to the attachment.
    attachments are (content, file name) pairs in the order of the response.
    """
    text = "\n".join(flatten(service.get("조문내용")))
    name = service["행정규칙기본정보"]["행정규칙명"]
    pdf = next((data for data, file_name in attachments if file_name.lower().endswith(".pdf") and name in file_name), None)
    return "\n".join(x for x in (text, pdf_text(pdf) if pdf else "") if x)


def choose_versions(rows):
    """One version per 시행일자: the later 공포일자, then the later 공포번호."""
    chosen = {}
    for row in rows:
        key = row["시행일자"]
        rank = (row["공포일자"], int(re.sub(r"\D", "", row["공포번호"]) or 0))
        if key not in chosen or rank > chosen[key][0]:
            chosen[key] = (rank, row)
    return {d: r for d, (_, r) in sorted(chosen.items())}


def in_force(dates, day):
    """The 시행일자 of the version in force on a day, or the earliest one if none was yet."""
    key = day.strftime("%Y%m%d")
    return max((d for d in dates if d <= key), default=min(dates))


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def write_note(path, meta, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000)
    path.write_text(f"---\n{front}---\n\n{body}\n", encoding="utf-8", newline="\n")


def json_payload(text):
    """The stored form of a JSON response: parsed, then written with an indent of one space."""
    return json.dumps(json.loads(text), ensure_ascii=False, indent=1) + "\n"


def write_json(path, text):
    """Write a JSON response in its stored form and return the SHA-256 of what was written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json_payload(text)
    path.write_text(payload, encoding="utf-8", newline="\n")
    return sha256(payload)
