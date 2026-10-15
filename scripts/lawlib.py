"""Shared helpers for collecting and checking raw sources."""

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

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
IMAGE = re.compile(r"<img\b[^>]*>.*?</img>", re.S)
IMAGE_TAG = re.compile(r"</?img\b[^>]*>")
BOX = re.compile(r"[─-╿]")
LINE_BREAK = re.compile(r"(?<=[│┤┐┘])(?=[│├└┌])")


def env():
    values = {}
    for line in (VAULT / ".env").read_text(encoding="utf-8").splitlines():
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
    data = yaml.safe_load((VAULT / "ontology" / "release.yaml").read_text(encoding="utf-8"))
    as_of = data["asOf"] if isinstance(data["asOf"], date) else date.fromisoformat(str(data["asOf"]))
    match = re.fullmatch(r"P(\d+)Y(\d+)D", data["transitionalWindow"])
    years, days = int(match.group(1)), int(match.group(2))
    start = as_of.replace(year=as_of.year - years) - timedelta(days=days)
    return as_of, start


def now():
    stamp = datetime.now(KST).replace(second=0, microsecond=0)
    return stamp, stamp.strftime("%Y%m%dT%H%M")


def ymd(text):
    return date(int(text[:4]), int(text[4:6]), int(text[6:8]))


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


def cell_order(text):
    """Text with box-drawing tables read cell by cell: row by row, then column by column within a row.

    Table text inside images comes without line breaks; there a line end followed by a line start,
    such as "││", marks a break, because the table has no empty cell without spaces.
    """
    text = IMAGE.sub(lambda m: "\n" + LINE_BREAK.sub("\n", IMAGE_TAG.sub("", m.group(0))) + "\n", text)
    lines, row = [], []
    for line in text.splitlines():
        if "│" in line:
            cells = line.strip().removeprefix("│").removesuffix("│").split("│")
            row += [[] for _ in range(len(cells) - len(row))]
            for column, cell in enumerate(cells):
                row[column].append(cell)
            continue
        lines += ["".join(column) for column in row]
        row = []
        lines.append(line)
    lines += ["".join(column) for column in row]
    return "\n".join(lines)


def canonical(text):
    """Comparison text for quotes and numbers: cell order, no image tags, whitespace or box-drawing characters."""
    return BOX.sub("", re.sub(r"\s+", "", IMAGE_TAG.sub("", cell_order(text))))


def version_text(text):
    """Version text for hashes and version changes: comparison text without image elements."""
    return canonical(without_images(text))


def sha256(text):
    return hashlib.sha256(version_text(text).encode("utf-8")).hexdigest()


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
    """Canonical text of every unit of an eflaw response, keyed as in identifiers."""
    units = {}
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
            key = f"art-{row['조문번호']}" + (f"-{row['조문가지번호']}" if row.get("조문가지번호") else "")
        else:
            key = f"heading-{row.get('조문키')}"
        units[key] = text
    for row in as_list(law.get("별표", {}).get("별표단위")):
        kind = "annex" if row.get("별표구분") == "별표" else "form"
        number = row.get("별표번호", "").lstrip("0") or "0"
        branch = row.get("별표가지번호", "00").lstrip("0")
        key = f"{kind}-{number}" + (f"-{branch}" if branch else "")
        units[key if key not in units else f"{key}-{row.get('별표키')}"] = "\n".join(flatten(row.get("별표내용")))
    for row in as_list(law.get("부칙", {}).get("부칙단위")):
        units[f"sup-{row.get('부칙공포번호')}"] = "\n".join(flatten(row.get("부칙내용")))
    return units


def law_text(law):
    return "\n".join(law_units(law).values())


def amendment_dates(text):
    """Dates in amendment tags such as <개정 2019.1.15, 2021.1.5>, as YYYYMMDD."""
    found = []
    for match in TAG.finditer(text):
        found += [f"{y}{int(m):02d}{int(d):02d}" for y, m, d in TAG_DATE.findall(match.group(0))]
    return found


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


def write_json(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(text)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
