"""Generate statute notes in wiki/ from the raw sources of the laws and notices in scripts/sources.yaml.

Usage:
    uv run python -X utf8 scripts/statutes.py           write the notes and append ledger lines
    uv run python -X utf8 scripts/statutes.py --check   list notes that differ from a fresh generation or the ledger, fetching nothing
    uv run python -X utf8 scripts/statutes.py --versions "고용보험법 시행령 제68조"   list versions in the window with block IDs

The units to generate are those that docs/competency-questions.md cites, their parent units,
and the units those units cite directly.
"""

import glob
import json
import re
import subprocess
import sys
from collections import namedtuple
from datetime import date, timedelta
from pathlib import Path

import yaml

import collect
import lawlib as L

WIKI = L.VAULT / "wiki"
LEDGER = L.VAULT / "ontology" / "verification.jsonl"
# --check fetches nothing: a version missing from the cache stops it instead.
OFFLINE = False
QUESTIONS = L.VAULT / "docs" / "competency-questions.md"
SOURCES = yaml.safe_load((Path(__file__).parent / "sources.yaml").read_text(encoding="utf-8"))
CIRCLED = {chr(0x2460 + i): i + 1 for i in range(20)} | {chr(0x3251 + i): i + 21 for i in range(15)}
LETTERS = "가나다라마바사아자차카타파하"
KIND_NOTES = {"A0002": "법률", "A0007": "대통령령", "A0097": "고용노동부령", "B0003": "고시"}
SUBDIVISIONS = {"heading-ch": "chapter", "heading-sec": "section", "article": "article", "annex": "annex", "form": "form", "addendum": "addendum"}
FAMILY = {"법": "", "영": " 시행령", "규칙": " 시행규칙"}
REFERENCE = re.compile(
    r"(?:「(?P<quoted>[^」]+)」\s*(?:\(이하\s*\"[^\"]+\"(?:이)?라\s*한다\)\s*)?|같은\s*(?P<same_law>법(?:\s*시행령|\s*시행규칙)?|영|규칙)\s+|(?P<short>법|영|규칙)\s+|(?P<alias>[가-힣]+법)\s+)?"
    r"(?:"
    r"같은\s*조\s*제(?P<same_p>\d+)항(?:\s*제(?P<same_i>\d+)호(?:의(?P<same_ib>\d+))?)?"
    r"|같은\s*항\s*제(?P<same_item>\d+)호(?:의(?P<same_item_b>\d+))?"
    r"|같은\s*호\s*(?P<same_m>[가나다라마바사아자차카타파하])목"
    r"|별표\s*(?P<annex>\d+)(?:의(?P<annex_b>\d+))?"
    r"|별지\s*제(?P<form>\d+)호(?:의(?P<form_b>\d+))?\s*서식"
    r"|제(?P<art>\d+)조(?:의(?P<art_b>\d+))?(?:\s*제(?P<p>\d+)항)?(?:\s*제(?P<i>\d+)호(?:의(?P<i_b>\d+))?)?(?:\s*(?P<m>[가나다라마바사아자차카타파하])목)?"
    r"|제(?P<part_p>\d+)항(?:\s*제(?P<part_i>\d+)호(?:의(?P<part_ib>\d+))?)?"
    r"|제(?P<part_item>\d+)호(?:의(?P<part_item_b>\d+))?"
    r"|(?P<part_m>[가나다라마바사아자차카타파하])목(?!적|록)"
    r")"
)
CONTINUATION = re.compile(r"\s*(?:부터|까지|ㆍ|·|,|및|와|과|또는)?\s*")
QUALIFIER = re.compile(r"\s*(?:본문|단서|전단|후단)?\s*\(\s*")
RANGE_START = re.compile(r"\s*부터\s*")
RANGE_END = re.compile(r"\s*까지")
ARTICLE_HEAD = re.compile(r"\s*제\d+조(?:의\d+)?\([^)]*\)")
PART_WORDS = r"\s*(?:본문|단서|전단|후단|각\s*호\s*외의\s*부분)?"
DELEGATED_TO = {False: re.compile(r"대통령령으로\s*정(?:하|한|할|함)"), True: re.compile(r"고용노동부령으로\s*정(?:하|한|할|함)")}
AMENDS_OTHER = re.compile(r"\s*제\d+조(?:의\d+)?\(다른\s*법(?:률|령)의\s*개정\)")
DELEGATION = re.compile(PART_WORDS + r"\s*(?P<joint>에\s*따라|에\s*따른|에서)")
QUOTED_PHRASE = re.compile(PART_WORDS + r'\s*에서\s*"([^"]+)"')
AMENDED = re.compile(PART_WORDS + r"\s*(?:의)?\s*개정\s*규정")
PART = re.compile(r"\s*(본문|단서|전단|후단|각\s*호\s*외의\s*부분)")
Ref = namedtuple("Ref", "law key block part delegation phrase amended follow lead applied", defaults=(False,))
APPLIED = re.compile(r"에서\s*준용하는\s*$")
PROVISION = re.compile(r"제(\d+)조(?:의(\d+))?(?:제(\d+)항)?(?:제(\d+)호(?:의(\d+))?)?(?:([가-하])목)?")
LAW_NAME = re.compile(r"(?:「|(?<![\w가-힣])\?)([^」「?]+)」")
BODY_MARK = re.compile(r"\s*(?:[①-⑳]|\d+(?:의\d+)?\.|[가-하]\.)?\s*")
TOPIC = re.compile(r"(?:[^,.]{0,60}?에도\s*불구하고,?\s+)?(?:[^,.]{0,60}?(?:은|는)\s+)?")
DESCRIPTIVE = re.compile(r"\s*(?:지급된|지급받은|지급받을|지급한|받은|받을|된|부과된|산정된|납부한|납부된)(?![가-힣])")
PARTICLE = re.compile(r"(?:에게|에서|으로|까지|부터|이나|은|는|이|가|을|를|의|에|로|과|와|도|만|나)$")


def segments(block):
    """Levels of a block suffix, keeping branch numbers with their item: p1-i3-2 is p1 and i3-2."""
    found = []
    for part in block.split("-"):
        if part.isdigit() and found:
            found[-1] += "-" + part
        else:
            found.append(part)
    return found


def following_word(text):
    """The first word after 에 따라, 에 따른 or 에서, without its particle, such as 기준기간 in "기준기간 동안"."""
    match = re.match(r"\s*([가-힣A-Za-z0-9]+)", text)
    if not match:
        return None
    word = match.group(1)
    stripped = PARTICLE.sub("", word)
    return stripped if len(stripped) >= 2 else word
DEFINED = re.compile(r"「([^」]+)」\s*\(이하\s*\"([^\"]+)\"(?:이)?라\s*한다\)")
CQ_GROUP = re.compile(r"\(((?:[^()]|\([^()]*\))*)\)")
CQ_REF = re.compile(
    r"(?:(?P<short>법|영|규칙)\s+)?"
    r"(?:부칙\(제(?P<sup>\d+)호\)|별표\s*(?P<annex>\d+)(?:의(?P<annex_b>\d+))?"
    r"|별지\s*제(?P<form>\d+)호(?:의(?P<form_b>\d+))?서식|제(?P<art>\d+)조(?:의(?P<art_b>\d+))?)"
)
CQ_NOTICE = re.compile(r"고용노동부 고시 제\d{4}-\d+호|\d{4}년 적용 최저임금 고시")
IMAGE_ELEMENT = re.compile(r"<img\b[^>]*>(?:(?:(?!<img\b).)*?</img>)?", re.S)


def day(text):
    return date(int(text[:4]), int(text[4:6]), int(text[6:8]))


def before(text):
    return (day(text) - timedelta(days=1)).strftime("%Y%m%d")


def iso(text):
    return day(text).isoformat()


def one_line(text):
    return re.sub(r"\s*\n\s*", " ", text).strip()


def link(name, block=None, label=None):
    target = name + (f"#^{block}" if block else "")
    return f"[[{target}|{label}]]" if label else f"[[{target}]]"


def official_delegations(response):
    """Delegations to a 시행령 or 시행규칙 in the 위임조문 data of 법제처, as (lower law, article key, delegating provision).

    The data names the article of the lower law that receives the delegation and the provision that delegates, such as 제43조제4항.
    """
    found = []
    for item in L.as_list(response["lsDelegated"]["법령"].get("위임조문정보")):
        for entry in L.as_list(item.get("위임정보")):
            if entry.get("위임구분") not in ("시행령", "시행규칙"):
                continue
            for info in L.as_list(entry.get("위임법령조문정보")):
                found.append((entry["위임법령제목"], L.article_key(info["위임법령조문번호"], info.get("위임법령조문가지번호")), info["조항호목"]))
    return list(dict.fromkeys(found))


def provision_block(provision):
    """Unit key and block suffix of a provision such as 제10조제1항제3호, which are art-10 and p1-i3."""
    match = PROVISION.fullmatch(provision)
    if not match:
        raise ValueError(f"unknown provision {provision}")
    block = f"p{match[3]}" if match[3] else None
    if match[4]:
        block = (f"{block}-" if block else "") + f"i{match[4]}" + (f"-{match[5]}" if match[5] else "")
        if match[6]:
            block += f"-m{LETTERS.index(match[6]) + 1}"
    return L.article_key(match[1], match[2]), block


class Law:
    """A law with every stored version, extended into the past when a unit needs it."""

    def __init__(self, name, as_of):
        self.name = name
        self.versions, self.rows, _, self.notes = L.stored_versions(name)
        self.chosen = L.choose_versions(self.rows)
        self.current = L.in_force(self.chosen, as_of)
        self.scheduled = [d for d in self.chosen if d > self.current]
        self.law_id = self.rows[0]["법령ID"]
        self.kind_code = self.versions[self.current]["기본정보"]["법종구분"]["법종구분코드"]
        self.published = {}
        for row in self.rows:
            self.published.setdefault(row["시행일자"], {})[row["공포일자"]] = row
        self.aliases = {}
        for text in L.strings(self.versions[self.current]):
            for quoted, short in DEFINED.findall(text):
                self.aliases[short] = quoted
        self._units, self._texts, self._rows = {}, {}, {}

    @property
    def root(self):
        return self.name.removesuffix(" 시행규칙").removesuffix(" 시행령")

    def needed(self):
        """The versions a statute note shows: the current one and every scheduled one."""
        return [self.current, *self.scheduled]

    def units(self, effective):
        if effective not in self._units:
            self._units[effective] = L.law_units(self.versions[effective])
        return self._units[effective]

    def rows_of(self, effective):
        if effective not in self._rows:
            self._rows[effective] = unit_rows(self.versions[effective])
        return self._rows[effective]

    def text(self, effective, key):
        if (effective, key) not in self._texts:
            raw = self.units(effective).get(key)
            self._texts[effective, key] = None if raw is None else L.version_text(raw)
        return self._texts[effective, key]

    def extend(self):
        """Fetch the version before the earliest stored one into the cache. Returns False at the first version."""
        earlier = [d for d in self.chosen if d < min(self.versions)]
        if not earlier:
            return False
        effective = earlier[-1]
        mst = self.chosen[effective]["법령일련번호"]
        path = L.CACHE / "law" / self.law_id / f"{mst}-{effective}.json"
        if not path.exists():
            if OFFLINE:
                sys.exit(f"{self.name}: the cache lacks the version of {effective}; run scripts/statutes.py without --check, which fetches it")
            text, _ = collect.fetch_law(mst, effective)
            L.write_json(path, text)
        self.versions[effective] = json.loads(path.read_text(encoding="utf-8"))["법령"]
        self.versions = dict(sorted(self.versions.items()))
        return True


def unit_rows(law_json):
    """Rows of every unit of an eflaw response in document order, keyed as in lawlib.law_units, as (kind, row)."""
    rows, levels = {"law": ("law", law_json["기본정보"])}, {}
    for row in L.as_list(law_json.get("조문", {}).get("조문단위")):
        if row.get("조문여부") == "조문":
            rows[L.article_key(row["조문번호"], row.get("조문가지번호"))] = ("article", row)
        else:
            key = L.heading_key(row.get("조문내용", ""), levels)
            if key:
                rows[key] = ("heading", row)
    for row in L.as_list(law_json.get("별표", {}).get("별표단위")):
        kind = "annex" if row.get("별표구분") == "별표" else "form"
        number = row.get("별표번호", "").lstrip("0") or "0"
        branch = row.get("별표가지번호", "00").lstrip("0")
        rows[f"{kind}-{number}" + (f"-{branch}" if branch else "")] = (kind, row)
    for row in L.as_list(law_json.get("부칙", {}).get("부칙단위")):
        rows[L.sup_key(row.get("부칙공포일자", ""), row.get("부칙공포번호", ""))] = ("addendum", row)
    return rows


def first_date(law, key, effective):
    """시행일자 of the earliest law version in the unbroken run of versions up to effective with the same text."""
    text = law.text(effective, key)
    start = effective
    while True:
        earlier = [d for d in law.versions if d < start]
        if not earlier:
            if law.extend():
                continue
            return start
        if law.text(earlier[-1], key) != text:
            return start
        start = earlier[-1]


VERSIONS = {}


def unit_versions(law, key):
    """Versions of a unit in the current and scheduled law versions, oldest first.

    Each version has its first 시행일자, the law version whose raw note holds its text, and its last day when a later version replaces it.
    """
    if (law.name, key) not in VERSIONS:
        VERSIONS[law.name, key] = compute_versions(law, key)
    return VERSIONS[law.name, key]


CITED = {}


def raw_holder(law, key, first):
    """The committed law version that holds the version of a unit starting on first, or None when only the cache holds it."""
    text = law.text(first, key)
    for effective in sorted(d for d in law.versions if d >= first):
        if law.text(effective, key) != text:
            return None
        if effective in law.notes:
            return effective
    return None


def compute_versions(law, key):
    found = []
    for effective in law.needed():
        text = law.text(effective, key)
        if text is None:
            if found and "last" not in found[-1]:
                found[-1]["last"] = before(effective)
            continue
        if found and found[-1]["text"] == text and "last" not in found[-1]:
            continue
        found.append({"first": first_date(law, key, effective), "effective": effective, "text": text})
    for date_ in sorted(CITED.get((law.name, key), set()) - {v["first"] for v in found}):
        if date_ not in law.versions or law.text(date_, key) is None or first_date(law, key, date_) != date_:
            CITED.setdefault("review", []).append(f"{law.name} {key}: wiki notes cite a version dated {date_}, but no version of the unit starts on that date")
            continue
        holder = raw_holder(law, key, date_)
        if holder is None:
            CITED.setdefault("review", []).append(f"{law.name} {key}: wiki notes cite the version of {date_}, which has no raw note; run scripts/collect.py cited")
            continue
        found.append({"first": date_, "effective": holder, "text": law.text(date_, key)})
    found.sort(key=lambda v: v["first"])
    for version in found:
        version.pop("last", None)
        later = next((d for d in law.versions if d > version["first"] and law.text(d, key) != version["text"]), None)
        if later:
            version["last"] = before(later)
    return found


def promulgation_of(law, key, version, review):
    """The version-list row of the promulgation that gave a unit this text, checked against its latest amendment tag."""
    rows = law.published.get(version["first"], {})
    if key.startswith("sup-"):
        tag = key.split("-")[1]
    else:
        tags = L.amendment_dates(law.units(version["effective"])[key])
        tag = max(tags) if tags else None
    if tag in rows:
        return rows[tag]
    only = list(rows.values())
    if tag is None and len(only) == 1 and only[0].get("제개정구분명") in ("제정", "전부개정"):
        return only[0]
    if tag is None:
        kinds = ", ".join(f"{r['공포일자']} {r.get('제개정구분명', '')}" for r in only)
        review.append(f"{law.name} {key} v{version['first']}: the unit has no amendment tag, and the promulgations in force from {version['first']} are {kinds or 'none'}, not one 제정 or 전부개정")
        return None
    review.append(f"{law.name} {key} v{version['first']}: no promulgation in force from {version['first']} has the date of the latest amendment tag {tag}")
    return None


class Unit:
    """A unit of a law: the law itself, a 장 or 절 heading, an article, a 별표 or 서식, or a 부칙."""

    def __init__(self, law, key):
        self.law, self.key = law, key
        effective = next((d for d in law.needed() if key in law.rows_of(d)), None)
        if effective is None:
            raise KeyError(f"{law.name} has no unit {key}")
        self.kind, self.row = law.rows_of(effective)[key]

    def __eq__(self, other):
        return isinstance(other, Unit) and (self.law.name, self.key) == (other.law.name, other.key)

    def __hash__(self):
        return hash((self.law.name, self.key))

    @property
    def identifier(self):
        if self.kind == "law":
            return f"law-{self.law.law_id}"
        if self.kind == "heading":
            return f"law-{self.law.law_id}-" + re.sub(r"([a-z]+)(\d)", r"\1-\2", self.key.removeprefix("heading-"))
        return f"law-{self.law.law_id}-{self.key}"

    @property
    def subdivision(self):
        if self.kind == "heading":
            return "section" if re.search(r"sec\d+(?:-\d+)?$", self.key) else "chapter"
        return {"article": "article", "annex": "annex", "form": "form", "addendum": "addendum"}.get(self.kind)

    @property
    def number(self):
        row = self.row
        if self.kind == "heading":
            match = L.HEADING.match(row["조문내용"])
            return f"제{int(match.group(1))}{match.group(2)}" + (f"의{int(match.group(3))}" if match.group(3) else "")
        if self.kind == "article":
            return f"제{int(row['조문번호'])}조" + (f"의{int(row['조문가지번호'])}" if row.get("조문가지번호") else "")
        if self.kind in ("annex", "form"):
            number, branch = int(row["별표번호"]), int(row.get("별표가지번호") or 0)
            if self.kind == "annex":
                return f"별표 {number}" + (f"의{branch}" if branch else "")
            return f"별지 제{number}호" + (f"의{branch}" if branch else "") + "서식"
        if self.kind == "addendum":
            return f"부칙 제{L.promulgation(row['부칙공포번호'])}호"
        return None

    @property
    def name(self):
        if self.kind == "law":
            return self.law.name
        if self.kind == "heading":
            parents = [u.number for u in self.ancestors() if u.kind == "heading"]
            return " ".join([self.law.name, *reversed(parents), self.number])
        name = f"{self.law.name} {self.number}"
        if self.kind == "addendum":
            number = L.promulgation(self.row["부칙공포번호"])
            if sum(1 for k in self.law.rows_of(self.law.current) if re.fullmatch(rf"sup-\d+-{number}", k)) > 1:
                published = day(self.row["부칙공포일자"])
                name += f" ({published.year}. {published.month}. {published.day}.)"
        return name

    @property
    def title(self):
        if self.kind == "law":
            return self.law.name
        if self.kind == "heading":
            return one_line(re.sub(r"<[^>]*>", "", L.HEADING.sub("", self.row["조문내용"], count=1)))
        if self.kind == "article":
            return self.row.get("조문제목") or self.number
        if self.kind in ("annex", "form"):
            return one_line(re.sub(r"\([^)]*관련\)|\[[^\]]*\]|<[^>]*>", "", self.row.get("별표제목", ""))) or self.number
        return "부칙"

    def parent(self):
        if self.kind == "law":
            return None
        if self.kind == "heading":
            levels = re.findall(r"[a-z]+\d+(?:-\d+)?", self.key.removeprefix("heading-"))
            return Unit(self.law, "heading-" + "-".join(levels[:-1])) if len(levels) > 1 else Unit(self.law, "law")
        if self.kind == "article":
            for effective in self.law.needed():
                keys = list(self.law.rows_of(effective))
                if self.key in keys:
                    for candidate in reversed(keys[: keys.index(self.key)]):
                        if candidate.startswith("heading-"):
                            return Unit(self.law, candidate)
                    break
        return Unit(self.law, "law")

    def ancestors(self):
        found, unit = [], self.parent()
        while unit:
            found.append(unit)
            unit = unit.parent()
        return found


def item_suffix(number):
    """Block suffix of a 호 number such as "1." or "3의2."."""
    match = re.fullmatch(r"(\d+)(?:의(\d+))?\.", number.strip())
    return match.group(1) + (f"-{match.group(2)}" if match.group(2) else "")


def subitem_suffix(number):
    """Block suffix of a 목 number such as "가.", where 가 is 1."""
    match = re.fullmatch(r"([가-하])(?:의(\d+))?\.", number.strip())
    return str(LETTERS.index(match.group(1)) + 1) + (f"-{match.group(2)}" if match.group(2) else "")


def article_lines(row):
    """Lines of an article as (block suffix or None, text): the title line before 항 and the 조문참고자료 have no block."""
    paragraphs = L.as_list(row.get("항"))
    if any(p.get("항내용") for p in paragraphs):
        lines = [(None, row["조문내용"])]
    elif any(p.get("호") for p in paragraphs):
        lines = [("lead", row["조문내용"])]
    else:
        lines = [("t", row["조문내용"])]
    for paragraph in paragraphs:
        prefix = ""
        if paragraph.get("항내용"):
            prefix = f"p{CIRCLED[paragraph['항번호'].strip()]}"
            lines.append((prefix, paragraph["항내용"]))
        for item in L.as_list(paragraph.get("호")):
            suffix = (f"{prefix}-" if prefix else "") + f"i{item_suffix(item['호번호'])}"
            lines.append((suffix, item["호내용"]))
            for sub in L.as_list(item.get("목")):
                lines.append((f"{suffix}-m{subitem_suffix(sub['목번호'])}", " ".join(x.strip() for x in L.flatten(sub.get("목내용")))))
    if row.get("조문참고자료"):
        lines.append((None, row["조문참고자료"]))
    return lines


SUP_ARTICLE = re.compile(r"^\s*제(\d+)조(?:의(\d+))?\(")
SUP_PARAGRAPH = re.compile(r"^\s*([①-⑳])")
FIRST_PARAGRAPH = re.compile(r"\s*([①-⑳])")


def addendum_lines(text):
    """Lines of a 부칙 as (block suffix or None, text): its articles a1, a2 and their 항 a1-p1, or the whole text t."""
    lines, article = [], None
    for raw in (line for line in text.split("\n") if line.strip()):
        match = SUP_ARTICLE.match(raw)
        paragraph = SUP_PARAGRAPH.match(raw)
        if match:
            article = f"a{int(match.group(1))}" + (f"-{int(match.group(2))}" if match.group(2) else "")
            head = ARTICLE_HEAD.match(raw)
            first = FIRST_PARAGRAPH.match(raw, head.end()) if head else None
            if first:
                lines.append((article, raw[: head.end()].strip()))
                lines.append((f"{article}-p{CIRCLED[first.group(1)]}", raw[head.end():].strip()))
            else:
                lines.append((article, raw.strip()))
        elif article and paragraph:
            lines.append((f"{article}-p{CIRCLED[paragraph.group(1)]}", raw.strip()))
        elif article:
            lines[-1] = (lines[-1][0], lines[-1][1] + " " + raw.strip())
        else:
            lines.append((None, raw.strip()))
    if article is None:
        return [(None, lines[0][1]), ("t", " ".join(t for _, t in lines[1:]))] if len(lines) > 1 else [("t", lines[0][1])]
    return lines


NOTE_START = re.compile(r"^\s*비\s*고\s*$|^\s*비고\s*[:：]?\s")


def table_lines(text, kind):
    """Blocks of a 별표 or 서식: the whole text t, or for a 별표 the text before its 비고 as t and the 비고 as remarks."""
    lines = text.split("\n")
    if kind == "annex":
        for index, line in enumerate(lines):
            if index and NOTE_START.match(line):
                return [("t", "\n".join(lines[:index])), ("remarks", "\n".join(lines[index:]))]
    return [("t", text)]


def unit_lines(unit, effective):
    """Lines of a unit in one law version as (block suffix or None, text, table)."""
    kind, row = unit.law.rows_of(effective)[unit.key]
    if kind == "article":
        return [(s, t, False) for s, t in article_lines(row)]
    if kind == "heading":
        return [("t", row["조문내용"].strip(), False)]
    if kind in ("annex", "form"):
        return [(s, t, True) for s, t in table_lines("\n".join(L.flatten(row.get("별표내용"))), kind)]
    if kind == "addendum":
        return [(s, t, False) for s, t in addendum_lines("\n".join(L.flatten(row.get("부칙내용"))))]
    return []


class Statutes:
    """The laws in scope, the units chosen for statute notes and their notes."""

    def __init__(self, as_of):
        self.as_of = as_of
        self.laws = {name: Law(name, as_of) for name in SOURCES["laws"] + SOURCES.get("references", [])}
        self.review = []
        self.load_delegations()
        CITED.clear()
        VERSIONS.clear()
        for path in sorted(WIKI.rglob("*.md")):
            if path.parent.name in ("LegalResource", "LegalResourceSubdivision"):
                continue
            for name, cited_date in re.findall(r"\[\[([^\]|#]+)#\^v(\d{8})-", path.read_text(encoding="utf-8")):
                unit = self.unit_named(name.strip())
                if unit is not None and unit.kind != "law":
                    CITED.setdefault((unit.law.name, unit.key), set()).add(cited_date)

    def load_delegations(self):
        """The 위임조문 data of the current version of every 법률 and 시행령 in scope: the raw note of each law and the delegations by lower article."""
        self.covered, self.delegations = {}, {}
        for name in SOURCES["laws"]:
            law = self.laws[name]
            if name.endswith(" 시행규칙"):
                continue
            mst = law.chosen[law.current]["법령일련번호"]
            folder = L.RAW / "law" / f"{name} 위임조문"
            notes = sorted(folder.glob(f"{glob.escape(name)} 위임조문 {law.current}-{mst} *.md"))
            if not notes:
                self.review.append(f"{name}: no 위임조문 data of the current version {law.current}-{mst}; basedOn comes from the text alone")
                continue
            self.covered[name] = notes[-1]
            for lower, key, provision in official_delegations(json.loads(notes[-1].with_suffix(".json").read_text(encoding="utf-8"))):
                self.delegations.setdefault((lower, key), []).append((name, provision))

    def decides(self, unit, upper):
        """Whether the 위임조문 data decides the delegations from a law to a unit: an article of the current version of a lower law."""
        return (upper in getattr(self, "covered", {}) and unit.kind == "article" and unit.law.name != upper
                and unit.key in unit.law.rows_of(unit.law.current))

    def family(self, law, short):
        return self.laws.get(law.root + FAMILY[short])

    def resolve(self, law, match, state):
        """The law, unit key and block suffix a reference points to, or None when it leaves the scope or stays inside the citing article.

        state holds the article and 항 cited just before in the same line, which 같은 조, 같은 항 and a continued 제3항 refer to.
        """
        target = law
        if match["quoted"]:
            compact = re.sub(r"\s+", "", match["quoted"])
            target = next((l for name, l in self.laws.items() if re.sub(r"\s+", "", name) == compact), None)
        elif match["same_law"]:
            named = state.get("named")
            if named is None:
                return None
            word = re.sub(r"\s+", "", match["same_law"])
            decree, rule = self.laws.get(named.root + " 시행령"), self.laws.get(named.root + " 시행규칙")
            target = {"법": named, "영": named if named.name.endswith(" 시행령") else decree,
                      "규칙": named if named.name.endswith(" 시행규칙") else rule, "법시행령": decree, "법시행규칙": rule}[word]
        elif match["short"]:
            target = self.family(law, match["short"])
        elif match["alias"]:
            target = self.laws.get(law.aliases.get(match["alias"], ""))
        if target is None:
            return None
        if match["same_p"]:
            if not state["key"]:
                return None
            block = f"p{match['same_p']}" + (f"-i{match['same_i']}" + (f"-{match['same_ib']}" if match["same_ib"] else "") if match["same_i"] else "")
            return state["law"], state["key"], block
        if match["same_item"]:
            if not state["key"]:
                return None
            prefix = f"{state['p']}-" if state["p"] else ""
            return state["law"], state["key"], prefix + f"i{match['same_item']}" + (f"-{match['same_item_b']}" if match["same_item_b"] else "")
        if match["part_m"] or match["same_m"]:
            item = re.sub(r"-m\d+$", "", state.get("block") or "")
            if not state["key"] or not (state["continued"] or match["same_m"]) or "i" not in item:
                return None
            return state["law"], state["key"], f"{item}-m{LETTERS.index(match['part_m'] or match['same_m']) + 1}"
        if match["part_p"] or match["part_item"]:
            if not state["key"] or not state["continued"]:
                return None
            if match["part_p"]:
                block = f"p{match['part_p']}" + (f"-i{match['part_i']}" + (f"-{match['part_ib']}" if match["part_ib"] else "") if match["part_i"] else "")
            else:
                prefix = f"{state['p']}-" if state["p"] else ""
                block = prefix + f"i{match['part_item']}" + (f"-{match['part_item_b']}" if match["part_item_b"] else "")
            return state["law"], state["key"], block
        if match["annex"]:
            return target, f"annex-{int(match['annex'])}" + (f"-{int(match['annex_b'])}" if match["annex_b"] else ""), None
        if match["form"]:
            return target, f"form-{int(match['form'])}" + (f"-{int(match['form_b'])}" if match["form_b"] else ""), None
        block = f"p{match['p']}" if match["p"] else None
        if match["i"]:
            block = (f"{block}-" if block else "") + f"i{match['i']}" + (f"-{match['i_b']}" if match["i_b"] else "")
            if match["m"]:
                block += f"-m{LETTERS.index(match['m']) + 1}"
        return target, L.article_key(match["art"], match["art_b"]), block

    def law_named(self, name):
        """The law in scope with this name, ignoring spaces, or None."""
        compact = re.sub(r"\s+", "", name)
        return next((law for law_name, law in self.laws.items() if re.sub(r"\s+", "", law_name) == compact), None)

    def range_inside(self, target, previous_law, previous, previous_block, key, block):
        """Units strictly inside a range such as 제56조부터 제58조까지 or 제1항부터 제3항까지, as (key, block) pairs."""
        if previous_law is not target:
            return []
        if key != previous and key.startswith("art-") and previous.startswith("art-") and not block and not previous_block:
            keys = [k for k in target.rows_of(target.current) if k.startswith("art-")]
            if previous in keys and key in keys:
                return [(k, None) for k in keys[keys.index(previous) + 1: keys.index(key)]]
            return []
        unit = self.unit(target.name, key) if key == previous and block and previous_block else None
        if unit is None:
            return []
        first, last = segments(previous_block), segments(block)
        if first[:-1] != last[:-1] or first[-1][0] != last[-1][0]:
            return []
        blocks = [s for s, _, _ in unit_lines(unit, target.current) if s]
        if previous_block not in blocks or block not in blocks:
            return []
        inside = blocks[blocks.index(previous_block) + 1: blocks.index(block)]
        return [(key, s) for s in inside if segments(s)[:-1] == first[:-1] and segments(s)[-1][0] == first[-1][0]]

    def delegates(self, law, target):
        """Whether a law can receive a delegation from the target: 시행령 from 법, 시행규칙 from 법 and 시행령."""
        if law.name.endswith(" 시행령"):
            return target.name == law.root
        if law.name.endswith(" 시행규칙"):
            return target.name in (law.root, law.root + " 시행령")
        return False

    def references(self, unit):
        """References in the shown versions of a unit, in order of appearance.

        Title lines, 조문참고자료 and the heading of each 부칙 article are not references.
        A 같은 조 or a continued 제3항 belongs to the article cited just before, and 같은 법 to the law named just before.
        A bare article that opens a parenthesis right after a reference belongs to the law of that reference.
        A reference after "에서 준용하는" is applied, as 법 제15조 in "법 제77조의10제1항에서 준용하는 법 제15조에 따라".
        A range such as 제56조부터 제58조까지 or 제1항부터 제3항까지 cites every unit in it.
        """
        found = []
        for effective in [v["effective"] for v in unit_versions(unit.law, unit.key)] or unit.law.needed():
            if unit.key not in unit.law.rows_of(effective):
                continue
            other_law = False
            for suffix, text, table in unit_lines(unit, effective):
                if suffix is None:
                    continue
                if table:
                    text = L.number_text(text, wrapped=True)
                if unit.kind == "addendum" and "-p" not in suffix:
                    other_law = bool(AMENDS_OTHER.match(text))
                if other_law:
                    continue
                head = ARTICLE_HEAD.match(text)
                body = BODY_MARK.match(text, head.end() if head else 0).end()
                opens = bool(re.fullmatch(r"t|lead|p\d+|a\d+(?:-\d+)?(?:-p\d+)?", suffix))
                names = [(m.end(), self.law_named(m.group(1))) for m in LAW_NAME.finditer(text)]
                state = {"law": unit.law, "key": unit.key if unit.kind == "article" else None, "p": None, "end": None, "continued": False}
                chain = []
                for match in REFERENCE.finditer(text, head.end() if head else 0):
                    while names and names[0][0] <= match.start():
                        state["named"] = names.pop(0)[1]
                    prefixed = match["quoted"] or match["short"] or match["alias"] or match["same_law"]
                    preceding = text[max(0, match.start() - 3): match.start()]
                    if not prefixed and preceding.endswith(("이 ", "부칙 ", "부칙")):
                        state["end"] = match.end()
                        continue
                    gap = text[state["end"]: match.start()] if state["end"] is not None else None
                    state["continued"] = gap is not None and bool(CONTINUATION.fullmatch(gap))
                    qualifies = gap is not None and bool(QUALIFIER.fullmatch(gap))
                    if not state["continued"]:
                        chain = []
                    origin = state["law"] if (state["continued"] or qualifies) and not prefixed else unit.law
                    previous = state["key"] if state["end"] is not None else None
                    previous_law, previous_block = state["law"], state.get("block")
                    state["end"] = match.end()
                    resolved = self.resolve(origin, match, state) if origin else None
                    if not resolved:
                        if prefixed or state["continued"]:
                            state.update(law=None, key=None, p=None, block=None)
                        if match["quoted"] or match["short"] or match["alias"]:
                            state["named"] = None
                        continue
                    target, key, block = resolved
                    if match["quoted"] or match["short"] or match["alias"]:
                        state["named"] = target
                    state.update(law=target, key=key if key.startswith("art-") else None, block=block,
                                 p=(block or "").split("-")[0] if block and block.startswith("p") else None)
                    if (target, key) == (unit.law, unit.key) and unit.kind == "article":
                        continue
                    if previous and RANGE_START.fullmatch(gap or "") and RANGE_END.match(text, match.end()):
                        for inner_key, inner_block in self.range_inside(target, previous_law, previous, previous_block, key, block):
                            chain.append(len(found))
                            found.append(Ref(target.name, inner_key, inner_block, None, False, None, None, None, False))
                    rest = text[match.end():]
                    before_match = text[:match.start()]
                    enclosed = before_match.count("(") > before_match.count(")") or before_match.count("[") > before_match.count("]")
                    delegation = DELEGATION.match(rest)
                    delegation = bool(target is not unit.law and self.delegates(unit.law, target) and delegation and not enclosed) and delegation
                    follow = None
                    if delegation:
                        joint = re.sub(r"\s+", "", delegation["joint"])
                        follow = "" if joint == "에따라" else following_word(rest[delegation.end():])
                        if joint == "에따라" and DESCRIPTIVE.match(rest, delegation.end()):
                            follow = None
                    if not chain:
                        opening = text[body: match.start()]
                        chain_lead = opens and (not opening.strip() or bool(TOPIC.fullmatch(opening)))
                    lead = chain_lead
                    part = PART.match(rest)
                    phrase = QUOTED_PHRASE.match(rest)
                    amended = unit.key.split("-")[1] if unit.kind == "addendum" and AMENDED.match(rest) else None
                    applied = bool(APPLIED.search(before_match)) or bool(chain and state["continued"] and found[chain[0]].applied)
                    chain.append(len(found))
                    found.append(Ref(target.name, key, block, re.sub(r"\s+", " ", part.group(1)) if part else None, bool(delegation),
                                     phrase.group(1) if phrase else None, amended, follow, lead, applied))
                    if delegation or amended:
                        for index in chain:
                            ref = found[index]
                            found[index] = ref._replace(delegation=ref.delegation or bool(delegation), lead=ref.lead or lead,
                                                        follow=ref.follow if ref.follow is not None else follow, amended=amended or ref.amended)
        return list(dict.fromkeys(found))

    def unit(self, name, key):
        law = self.laws.get(name)
        if law is None or not any(key in law.rows_of(d) for d in law.needed()):
            return None
        return Unit(law, key)

    def question_targets(self):
        """Units that the competency questions cite."""
        root = SOURCES["laws"][0]
        found = []
        for group in CQ_GROUP.findall(QUESTIONS.read_text(encoding="utf-8")):
            law, addendum = root, None
            for match in CQ_REF.finditer(group):
                if match["short"]:
                    law, addendum = root + FAMILY[match["short"]], None
                if match["sup"]:
                    key = next((k for k in self.laws[law].rows_of(self.laws[law].current) if re.fullmatch(rf"sup-\d+-{int(match['sup'])}", k)), None)
                    addendum = key
                    found.append((law, key))
                elif match["annex"]:
                    found.append((law, f"annex-{int(match['annex'])}" + (f"-{int(match['annex_b'])}" if match["annex_b"] else "")))
                elif match["form"]:
                    found.append((law, f"form-{int(match['form'])}" + (f"-{int(match['form_b'])}" if match["form_b"] else "")))
                elif match["art"] and not addendum:
                    found.append((law, L.article_key(match["art"], match["art_b"])))
        units = []
        for name, key in found:
            unit = self.unit(name, key) if key else None
            if unit is None:
                self.review.append(f"competency questions cite {name} {key}, which the current and scheduled versions lack")
            elif unit not in units:
                units.append(unit)
        return units

    def unit_named(self, name):
        """The unit a statute note name stands for, such as 고용보험법 제4장 제2절 or 고용보험법 시행규칙 부칙 제263호 (2019. 9. 30.)."""
        for law_name in sorted(self.laws, key=len, reverse=True):
            law = self.laws[law_name]
            if name == law_name:
                return Unit(law, "law")
            if not name.startswith(law_name + " "):
                continue
            rest = name[len(law_name) + 1:]
            if match := re.fullmatch(r"제(\d+)조(?:의(\d+))?", rest):
                return self.unit(law_name, L.article_key(match[1], match[2]))
            if match := re.fullmatch(r"별표 (\d+)(?:의(\d+))?", rest):
                return self.unit(law_name, f"annex-{match[1]}" + (f"-{match[2]}" if match[2] else ""))
            if match := re.fullmatch(r"별지 제(\d+)호(?:의(\d+))?서식", rest):
                return self.unit(law_name, f"form-{match[1]}" + (f"-{match[2]}" if match[2] else ""))
            if match := re.fullmatch(r"부칙 제(\d+)호(?: \((\d{4})\. (\d{1,2})\. (\d{1,2})\.\))?", rest):
                keys = [k for d in law.needed() for k in law.rows_of(d) if re.fullmatch(rf"sup-\d+-{int(match[1])}", k)]
                if match[2]:
                    keys = [k for k in keys if k.split("-")[1] == f"{match[2]}{int(match[3]):02d}{int(match[4]):02d}"]
                return self.unit(law_name, keys[0]) if len(set(keys)) == 1 else None
            if match := re.fullmatch(r"(제\d+장(?:의\d+)?)(?: (제\d+절(?:의\d+)?))?", rest):
                parts = [re.sub(r"제(\d+)(장|절)(?:의(\d+))?", lambda m: ("ch" if m[2] == "장" else "sec") + m[1] + (f"-{m[3]}" if m[3] else ""), p)
                         for p in match.groups() if p]
                return self.unit(law_name, "heading-" + "-".join(parts))
        return None

    def wiki_targets(self):
        """Units that wiki notes other than statute notes link to."""
        found = []
        for path in sorted(WIKI.rglob("*.md")):
            if path.parent.name in ("LegalResource", "LegalResourceSubdivision"):
                continue
            for name in re.findall(r"\[\[([^\]|#]+)", path.read_text(encoding="utf-8")):
                unit = self.unit_named(name.strip())
                if unit and unit not in found:
                    found.append(unit)
        return found

    def selection(self):
        """The cited units, their parents, the units they cite directly and the parents of those."""
        chosen = []

        def add(unit):
            for item in [unit, *unit.ancestors()]:
                if item not in chosen:
                    chosen.append(item)

        targets = self.question_targets()
        targets += [unit for unit in self.wiki_targets() if unit not in targets]
        for unit in targets:
            add(unit)
        for unit in targets:
            for ref in self.references(unit):
                cited = self.unit(ref.law, ref.key)
                if cited is None:
                    self.review.append(f"{unit.name} cites {ref.law} {ref.key}, which the current and scheduled versions lack")
                else:
                    add(cited)
        for unit in self.existing():
            if unit not in chosen:
                self.review.append(f"{unit.name}: kept because its note exists; nothing in scope cites it")
            add(unit)
        return chosen

    def existing(self):
        """Units that already have statute notes, which keep being generated so that no note goes stale."""
        found = []
        for folder in ("LegalResource", "LegalResourceSubdivision"):
            for path in sorted((WIKI / folder).glob("*.md")):
                unit = self.unit_named(path.stem)
                if unit is not None:
                    found.append(unit)
        return found


def part_of(text, part):
    """The 본문, 단서, 전단 or 후단 of a provision: 단서 starts at "다만", 후단 at "이 경우"."""
    marks = {"본문": "다만", "단서": "다만", "전단": "이 경우", "후단": "이 경우"}
    if part not in marks:
        return text
    head, mark, tail = text.partition(marks[part])
    if part in ("본문", "전단"):
        return head
    return mark + tail


def delegated(ref, lines, found, law):
    """Whether a reference is a delegation, as True, False or "review" when the cited provision delegates but the matter may differ.

    "법 제61조제2항 본문에서 "대통령령으로 정하는 사유"란" counts when the quoted phrase is in the 본문 of 제61조제2항.
    "법 제45조제5항에 따라" counts when a sentence of 제45조제5항 says "대통령령으로 정하는" and the reference opens its 항 or article.
    It may open it alone, after a topic, as in "사업주나 하수급인은 법 제15조에 따라", or after a clause such as "제2항에도 불구하고".
    Every member of a list such as "법 제21조제1항 및 제2항에 따라" opens it when the first one does.
    A reference inside a 호 or in the middle of a sentence describes, as in "법 제48조에 따른 수급기간이 종료된 경우".
    So does "에 따라" before a participle, as in "법 제75조에 따라 지급된".
    "법 제62조제2항 본문에 따른 추가징수액" counts when such a sentence of the 본문 also has 추가, the start of the word after 에 따른.
    "법 제40조제2항제1호에 따른 기준기간" does not, when the delegating sentence of that 호 lacks 기준.
    The cited provision is the text of the block itself, without its 호, or the part named, or every 항 and 호 of a whole article.
    A reference to a block that the cited version does not declare never counts.
    """
    if not ref.delegation or (ref.block and not found):
        return False
    if ref.block:
        own = [lines[ref.block]]
    elif ref.part == "각 호 외의 부분" and "lead" in lines:
        own = [lines["lead"]]
    else:
        own = [t for s, t in lines.items() if s]
    cited = " ".join(part_of(t, ref.part) for t in own)
    if ref.phrase:
        return bool(re.search(r"대통령령|고용노동부령", ref.phrase)) and L.canonical(ref.phrase) in L.canonical(cited)
    pattern = DELEGATED_TO[law.name.endswith(" 시행규칙")]
    sentences = [s for s in re.split(r"(?<=다\.)\s+", cited) if pattern.search(s)]
    if not sentences:
        return False
    if not ref.lead or ref.follow is None or (ref.follow and len(ref.follow) < 2):
        return "review"
    if ref.follow == "" or ref.follow == "위임" or any(ref.follow[:2] in s for s in sentences):
        return True
    return "review"


def block_id(version, suffix):
    return f"v{version['first']}-{suffix}"


def attachments_of(law, effective):
    """Stored image files of the raw note that holds a law version, keyed by their link."""
    note = law.notes[effective]
    response = json.loads(note.with_suffix(".json").read_text(encoding="utf-8"))
    stored = L.stored_attachments(note.parent, note.stem)
    return dict(zip(L.image_links(response), (path.name for path in stored)))


def render_text(text, images):
    """Statute text for a note: image elements become embeds of the stored image files.

    The table text that an image carries follows in an Obsidian comment, hidden when reading, so that quotes and numbers can be checked against it.
    """

    def embed(match):
        source = re.search(r'src="([^"]+)"|id="(\d+)"', match.group(0))
        link_ = source.group(1) or L.FILE_URL.format(source.group(2))
        if link_ not in images:
            return match.group(0)
        inner = L.IMAGE_TAG.sub("", match.group(0))
        comment = f" %%<img>{inner}</img>%%" if L.canonical(inner) else ""
        return f" ![[{images[link_]}]]{comment} "

    return IMAGE_ELEMENT.sub(embed, text)


def render_unit(statutes, unit, chosen):
    """Frontmatter and body of the note of a unit."""
    law = unit.law
    names = {(u.law.name, u.key): u for u in chosen}
    versions = unit_versions(law, unit.key) if unit.kind != "law" else []
    meta = {"type": "LegalResource" if unit.kind == "law" else "LegalResourceSubdivision", "identifier": unit.identifier}
    cites, based = [], []
    current = {}
    for target in chosen:
        if target.kind != "law":
            current[(target.law.name, target.key)] = next(
                (v for v in unit_versions(target.law, target.key) if v["first"] <= target.law.current and v.get("last", "99999999") >= target.law.current),
                None,
            )
    if unit.kind != "law":
        for ref in statutes.references(unit):
            target = names.get((ref.law, ref.key))
            if target is None or target == unit:
                continue
            version = current.get((ref.law, ref.key))
            if ref.amended:
                version = next((v for v in unit_versions(target.law, target.key)
                                if (promulgation_of(target.law, target.key, v, []) or {}).get("공포일자") == ref.amended), None)
                if version is None and ref.block:
                    statutes.review.append(f"{unit.name}: the 개정규정 of {target.name} is the version promulgated on {ref.amended}, "
                                           "which its note does not show; the link names the unit")
            lines = {s: t for s, t, _ in unit_lines(target, version["effective"])} if version else {}
            found = bool(version and ref.block and ref.block in lines)
            text = link(target.name, block_id(version, ref.block) if found else None)
            cites.append(text)
            delegation = delegated(ref, lines, found, law) if unit.kind != "form" else False
            if statutes.decides(unit, ref.law) and not ref.applied:
                listed = {provision_block(p)[0] for upper, p in statutes.delegations.get((law.name, unit.key), []) if upper == ref.law}
                if delegation is True and ref.key not in listed:
                    statutes.review.append(f"{unit.name}: the text reads a delegation from {text}, which the 위임조문 data does not list; no basedOn is written")
                continue
            if delegation == "review":
                if not ref.lead:
                    why = "it does not open its provision"
                elif ref.follow is None:
                    why = "it describes what the provision did, as in 에 따라 지급된"
                elif len(ref.follow) < 2:
                    why = f"the word after it, {ref.follow!r}, is too short to name the matter"
                else:
                    why = f"the delegating sentence does not name {ref.follow!r}"
                statutes.review.append(f"{unit.name}: cites {text}, which delegates, but {why}; no basedOn is written")
            elif delegation:
                based.append(text)
    data_notes = []
    if unit.kind == "article":
        for upper, provision in statutes.delegations.get((law.name, unit.key), []) if hasattr(statutes, "delegations") else []:
            key, block = provision_block(provision)
            target = names.get((upper, key))
            if target is None:
                continue
            version = current.get((upper, key))
            lines = {s: t for s, t, _ in unit_lines(target, version["effective"])} if version else {}
            if block and block not in lines:
                statutes.review.append(f"{unit.name}: the 위임조문 data names {upper} {provision}, which the current version does not declare; the link names the unit")
            based.append(link(target.name, block_id(version, block) if block in lines else None))
            data_notes.append(statutes.covered[upper].stem)
    if based:
        meta["basedOn"] = list(dict.fromkeys(based))
    if cites:
        meta["cites"] = list(dict.fromkeys(cites))
    review = statutes.review
    if unit.kind == "law":
        meta["idLocal"] = law.law_id
        realized = []
        for effective in law.needed():
            row = law.chosen[effective]
            realized.append({
                "identifier": f"{unit.identifier}-v{effective}",
                "firstDateEntryInForce": iso(effective),
                "datePublication": iso(row["공포일자"]),
                "idLocal": row["법령일련번호"],
                "number": f"제{L.promulgation(row['공포번호'])}호",
                "wasDerivedFrom": link(law.notes[effective].stem),
            })
        for version, following in zip(realized, realized[1:]):
            version["dateNoLongerInForce"] = (date.fromisoformat(following["firstDateEntryInForce"]) - timedelta(days=1)).isoformat()
        meta["isRealizedBy"] = [order(v) for v in realized]
        meta["title"] = unit.title
        meta["typeDocument"] = link(KIND_NOTES[law.kind_code])
    else:
        realized = []
        for version in versions:
            row = promulgation_of(law, unit.key, version, review)
            entry = {
                "identifier": f"{unit.identifier}-v{version['first']}",
                "firstDateEntryInForce": iso(version["first"]),
                "idLocal": (row or law.chosen[version["first"]])["법령일련번호"],
                "wasDerivedFrom": link(law.notes[version["effective"]].stem),
            }
            if row:
                entry["datePublication"] = iso(row["공포일자"])
                entry["number"] = f"제{L.promulgation(row['공포번호'])}호"
            if "last" in version:
                entry["dateNoLongerInForce"] = iso(version["last"])
            realized.append(order(entry))
        meta["isRealizedBy"] = realized
        meta["title"] = unit.title
        meta["isPartOf"] = link(unit.parent().name)
        meta["typeSubdivision"] = unit.subdivision
        meta["number"] = unit.number
    sources = [law.notes[v["effective"]].stem for v in versions] if versions else [law.notes[d].stem for d in law.needed()]
    meta["source"] = [link(s) for s in dict.fromkeys(sources + data_notes)]
    meta["status"] = "verified"
    body = body_of(unit, versions)
    return meta, body


def notice_versions(source, as_of):
    """Raw notes of a 행정규칙 series keyed by 시행일자: the current version and every scheduled one."""
    found = {}
    for note in L.RAW.glob("law/*/*.md"):
        match = L.RAW_NOTE.match(note.stem)
        payload = note.with_suffix(".json")
        if not match or not payload.exists():
            continue
        response = json.loads(payload.read_text(encoding="utf-8"))
        info = response.get("AdmRulService", {}).get("행정규칙기본정보")
        if info and info["행정규칙ID"] == source["id"]:
            if match["date"] not in found or note.stem > found[match["date"]][0].stem:
                found[match["date"]] = (note, response)
    current = L.in_force(found, as_of)
    return {d: found[d] for d in sorted(found) if d >= current}, current


def render_notice(source, as_of):
    """Path, identifier, frontmatter, body and block hashes of the note of a 행정규칙 series such as the 최저임금 고시."""
    versions, current = notice_versions(source, as_of)
    identifier = f"admrul-{source['id']}"
    info = {d: response["AdmRulService"]["행정규칙기본정보"] for d, (_, response) in versions.items()}
    realized, body, blocks = [], [], {}
    dates = list(versions)
    for effective, following in zip(dates, [*dates[1:], None]):
        note, response = versions[effective]
        entry = {
            "identifier": f"{identifier}-v{effective}",
            "firstDateEntryInForce": iso(effective),
            "dateNoLongerInForce": iso(before(following)) if following else None,
            "datePublication": iso(info[effective]["발령일자"]),
            "idLocal": info[effective]["행정규칙일련번호"],
            "number": f"제{info[effective]['발령번호']}호",
            "wasDerivedFrom": link(note.stem),
        }
        realized.append(order({k: v for k, v in entry.items() if v}))
        text = L.notice_text(response["AdmRulService"], L.note_attachments(note, response))
        label = "현행" if effective == current else "시행예정"
        body += [f"## {iso(effective)} 시행 ({label})", "", f"{info[effective]['행정규칙명']}, {info[effective]['소관부처명']} 고시 {entry['number']}", "",
                 "```text", text.rstrip("\n"), "```", "", f"^v{effective}-t", ""]
        blocks[f"v{effective}-t"] = L.sha256(L.version_text(text))
    name = info[current]["행정규칙명"]
    meta = {
        "type": "LegalResource",
        "identifier": identifier,
        "idLocal": source["id"],
        "isRealizedBy": realized,
        "title": name,
        "typeDocument": link(KIND_NOTES[info[current]["행정규칙종류코드"]]),
        "source": [link(note.stem) for note, _ in versions.values()],
        "status": "verified",
    }
    text = f"{name}의 법령 노트다. 같은 행정규칙ID의 해마다 고시를 시행일 버전으로 두고, 본문은 원문의 PDF 첨부파일에서 스크립트로 옮겼다."
    return WIKI / "LegalResource" / f"{name}.md", identifier, meta, "\n".join([text, "", *body]).rstrip() + "\n", blocks


LEGAL_EXPRESSION_ORDER = ("identifier", "firstDateEntryInForce", "dateNoLongerInForce", "datePublication", "idLocal", "number", "wasDerivedFrom")


def order(entry):
    return {k: entry[k] for k in LEGAL_EXPRESSION_ORDER if k in entry}


def body_of(unit, versions):
    law = unit.law
    if unit.kind == "law":
        lines = [f"{law.name}의 법령 노트다. 시행일 버전마다 원문 노트를 잇는다.", ""]
        for effective in law.needed():
            label = "현행" if effective == law.current else "시행예정"
            row = law.chosen[effective]
            lines += [f"## {iso(effective)} 시행 ({label})", "", f"{iso(row['공포일자'])} 공포 제{L.promulgation(row['공포번호'])}호, 원문은 {link(law.notes[effective].stem)}이다.", ""]
        return "\n".join(lines).rstrip() + "\n"
    lines = [f"{unit.name}({unit.title})의 법령 노트다. 본문은 원문에서 스크립트로 옮겼고, 시행일 버전마다 따로 둔다.", ""]
    for version in versions:
        current = version["first"] <= law.current and version.get("last", "99999999") >= law.current
        label = "현행" if current else ("시행예정" if version["first"] > law.current else "종전")
        lines += [f"## {iso(version['first'])} 시행 ({label})", ""]
        images = attachments_of(law, version["effective"])
        for suffix, text, table in unit_lines(unit, version["effective"]):
            if table:
                lines += ["```text", render_text(text, images).rstrip("\n"), "```", ""]
                if suffix:
                    lines += [f"^{block_id(version, suffix)}", ""]
            else:
                rendered = one_line(render_text(text, images))
                lines += [rendered + (f" ^{block_id(version, suffix)}" if suffix else ""), ""]
    return "\n".join(lines).rstrip() + "\n"


def note_text(meta, body):
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=1000)
    return f"---\n{front}---\n\n{body}"


def note_path(unit):
    folder = "LegalResource" if unit.kind == "law" else "LegalResourceSubdivision"
    return WIKI / folder / f"{unit.name}.md"


note_hash = L.note_hash


def block_hashes(unit, versions):
    """Hash of each block over its version text, which includes the text of its children, such as the 호 of a 항."""
    found = {}
    for version in versions:
        lines = [(suffix, text) for suffix, text, _ in unit_lines(unit, version["effective"]) if suffix]
        for suffix, _ in lines:
            text = "\n".join(t for s, t in lines if s == suffix or s.startswith(suffix + "-"))
            found[block_id(version, suffix)] = L.sha256(L.version_text(text))
    return found


def latest_ledger():
    found = {}
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                found[entry["identifier"]] = entry
    return found


def commit():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=L.VAULT, capture_output=True, text=True, check=True).stdout.strip()


SIDE_BY_SIDE = re.compile(r"\S {8,}\S")
MOVED_FROM = re.compile(r"제(\d+)조(?:의(\d+))?에서\s*이동")
MOVED_AWAY = re.compile(r"종전\s*제\d+조(?:의\d+)?[은는]\s*제(\d+)조(?:의(\d+))?로\s*이동")


def review_unit(unit):
    """Things in a unit that a person should look at: moved or reused numbers, images without text, lost glyphs and text side by side in a form."""
    if unit.kind in ("law", "heading"):
        return []
    found = []
    law = unit.law
    if unit.kind == "article":
        dates = sorted({v["first"] for v in unit_versions(law, unit.key)} | set(law.needed()))
        for effective in dates:
            kind_row = law.rows_of(effective).get(unit.key)
            row = kind_row[1] if kind_row else {}
            for field, meaning in (("조문이동이전", "moved here from"), ("조문이동이후", "moved away to")):
                code = row.get(field, "")
                if code and int(code):
                    line = f"{unit.name}: the article {meaning} {L.article_key(code[:4], code[4:])} by the version of {effective}"
                    if effective > law.current:
                        line += "; notes follow numbers, not moves, so this note will show another article from then on"
                    found.append(line)
            note = row.get("조문참고자료", "")
            for number, branch in MOVED_FROM.findall(note):
                found.append(f"{unit.name}: the article moved here from {L.article_key(number, branch)}, as its 조문참고자료 says")
            for number, branch in MOVED_AWAY.findall(note):
                found.append(f"{unit.name}: the earlier article of this number moved to {L.article_key(number, branch)}, as its 조문참고자료 says; the number is reused")
    text = law.units(law.needed()[-1] if unit.key not in law.units(law.current) else law.current)[unit.key]
    for element in IMAGE_ELEMENT.findall(text):
        if not L.canonical(L.IMAGE_TAG.sub("", element)):
            found.append(f"{unit.name}: an image carries no text, such as a formula; quote it from the stored image file")
            break
    if L.LOST_GLYPH.search(text):
        found.append(f"{unit.name}: \"?\" stands for lost glyphs; check quotes against the PDF of the 서식 or 별표")
    if unit.kind in ("annex", "form") and IMAGE_ELEMENT.search(text):
        found.append(f"{unit.name}: an image inside the text of a 별표 or 서식 shows as an embed that its code block does not render")
    if unit.kind == "form" and any(SIDE_BY_SIDE.search(line) and not L.BOX.search(line) for line in text.split("\n")):
        found.append(f"{unit.name}: text stands side by side without frames; quotes across it can fail")
    return list(dict.fromkeys(found))


def generate():
    """Every statute note as path -> (identifier, text, block hashes), and the generator with its review list."""
    as_of, _ = L.release()
    statutes = Statutes(as_of)
    chosen = statutes.selection()
    notes = {}
    for unit in chosen:
        meta, body = render_unit(statutes, unit, chosen)
        versions = unit_versions(unit.law, unit.key) if unit.kind != "law" else []
        notes[note_path(unit)] = (unit.identifier, note_text(meta, body), block_hashes(unit, versions))
        statutes.review += review_unit(unit)
    statutes.review += list(dict.fromkeys(CITED.pop("review", [])))
    for source in SOURCES["admrul"]:
        path, identifier, meta, body, blocks = render_notice(source, as_of)
        notes[path] = (identifier, note_text(meta, body), blocks)
    names = [path.stem for path in notes]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(f"two statute notes would share a name: {duplicates}")
    return statutes, notes


def window_versions(name):
    """Versions of a unit within the transitional window with their block IDs, for citing an earlier version."""
    as_of, start = L.release()
    statutes = Statutes(as_of)
    unit = statutes.unit_named(name)
    if unit is None or unit.kind == "law":
        sys.exit(f"no unit named {name}")
    law = unit.law
    previous = None
    for effective in [d for d in law.versions if d >= L.in_force(law.versions, start)]:
        text = law.text(effective, unit.key)
        if text is None or text == previous:
            previous = text
            continue
        previous = text
        first = first_date(law, unit.key, effective)
        blocks = " ".join(f"^v{first}-{s}" for s, _, _ in unit_lines(unit, effective) if s)
        stored = "raw note" if raw_holder(law, unit.key, first) else "cache only, run scripts/collect.py cited after citing it"
        print(f"{iso(first)} ({stored}): {blocks}")


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    if sys.argv[1:2] == ["--versions"] and len(sys.argv) == 3:
        window_versions(sys.argv[2])
        return
    check = sys.argv[1:] == ["--check"]
    if not check and subprocess.run(["git", "status", "--porcelain", "--", "scripts"], cwd=L.VAULT, capture_output=True, text=True).stdout.strip():
        sys.exit("Commit scripts/ first, so that the ledger names the generator that wrote the notes.")
    global OFFLINE
    OFFLINE = check
    statutes, notes = generate()
    changed = [path for path, (_, text, _) in notes.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
    for line in dict.fromkeys(statutes.review):
        print("REVIEW", line)
    if check:
        ledger = latest_ledger()
        stale = [path for path, (identifier, text, blocks) in notes.items()
                 if path not in changed and (ledger.get(identifier, {}).get("note") != note_hash(text) or ledger.get(identifier, {}).get("blocks") != blocks)]
        for path in changed:
            print("DIFFERS", path.relative_to(L.VAULT))
        for path in stale:
            print("LEDGER", path.relative_to(L.VAULT))
        print(f"{len(notes)} notes, {len(changed)} differ, {len(stale)} differ from the ledger")
        sys.exit(1 if changed or stale else 0)
    ledger, head = latest_ledger(), commit()
    entries = []
    for path, (identifier, text, blocks) in notes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path in changed:
            path.write_text(text, encoding="utf-8", newline="\n")
        digest = note_hash(text)
        if ledger.get(identifier, {}).get("note") != digest or ledger.get(identifier, {}).get("blocks") != blocks:
            entries.append({"identifier": identifier, "note": digest, "blocks": blocks, "generator": "scripts/statutes.py", "commit": head})
    if entries:
        with LEDGER.open("a", encoding="utf-8", newline="\n") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"{len(notes)} notes, {len(changed)} written, {len(entries)} ledger lines")


if __name__ == "__main__":
    main()
