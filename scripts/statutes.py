"""Generate statute notes in wiki/ from the raw sources of the laws and notices in scripts/sources.yaml.

Usage:
    uv run python -X utf8 scripts/statutes.py           write the notes and append ledger lines
    uv run python -X utf8 scripts/statutes.py --check   list notes that differ from a fresh generation

The units to generate are those that docs/competency-questions.md cites, their parent units,
and the units those units cite directly.
"""

import hashlib
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

import collect
import lawlib as L

WIKI = L.VAULT / "wiki"
LEDGER = L.VAULT / "ontology" / "verification.jsonl"
QUESTIONS = L.VAULT / "docs" / "competency-questions.md"
SOURCES = yaml.safe_load((Path(__file__).parent / "sources.yaml").read_text(encoding="utf-8"))
CIRCLED = {chr(0x2460 + i): i + 1 for i in range(20)} | {chr(0x3251 + i): i + 21 for i in range(15)}
LETTERS = "가나다라마바사아자차카타파하"
KIND_NOTES = {"A0002": "법률", "A0007": "대통령령", "A0097": "고용노동부령", "B0003": "고시"}
SUBDIVISIONS = {"heading-ch": "chapter", "heading-sec": "section", "article": "article", "annex": "annex", "form": "form", "addendum": "addendum"}
FAMILY = {"법": "", "영": " 시행령", "규칙": " 시행규칙"}
REFERENCE = re.compile(
    r"(?:「(?P<quoted>[^」]+)」\s*|(?P<short>법|영|규칙)\s+|(?P<alias>[가-힣]+법)\s+)?"
    r"(?:"
    r"같은\s*조\s*제(?P<same_p>\d+)항(?:\s*제(?P<same_i>\d+)호(?:의(?P<same_ib>\d+))?)?"
    r"|별표\s*(?P<annex>\d+)(?:의(?P<annex_b>\d+))?"
    r"|별지\s*제(?P<form>\d+)호(?:의(?P<form_b>\d+))?\s*서식"
    r"|제(?P<art>\d+)조(?:의(?P<art_b>\d+))?(?:\s*제(?P<p>\d+)항)?(?:\s*제(?P<i>\d+)호(?:의(?P<i_b>\d+))?)?(?:\s*(?P<m>[가-하])목)?"
    r")"
)
CONTINUATION = re.compile(r"\s*(?:부터|까지|ㆍ|·|,|및|와|과|또는)?\s*")
DELEGATED_TO = {False: re.compile(r"대통령령으로\s*정하"), True: re.compile(r"고용노동부령으로\s*정하")}
AMENDS_OTHER = re.compile(r"\s*제\d+조(?:의\d+)?\(다른\s*법(?:률|령)의\s*개정\)")
DELEGATION = re.compile(r"\s*(?:에\s*따라|에\s*따른|에서\s*\"|에서\s*(?:대통령령|고용노동부령)으로\s*정하는)")
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
    for version, following in zip(found, found[1:]):
        version.setdefault("last", before(following["first"]))
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
    if tag is None and (key.startswith("heading-") or version["first"] == min(law.chosen)
                        or any(r.get("제개정구분명") in ("제정", "전부개정") for r in rows.values())):
        return law.chosen[version["first"]]
    review.append(f"{law.name} {key} v{version['first']}: no promulgation in force from {version['first']} has the date of the latest amendment tag {tag}")
    return law.chosen[version["first"]]


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


def addendum_lines(text):
    """Lines of a 부칙 as (block suffix or None, text): its articles a1, a2 and their 항 a1-p1, or the whole text t."""
    lines, article = [], None
    for raw in (line for line in text.split("\n") if line.strip()):
        match = SUP_ARTICLE.match(raw)
        paragraph = SUP_PARAGRAPH.match(raw)
        if match:
            article = f"a{int(match.group(1))}" + (f"-{int(match.group(2))}" if match.group(2) else "")
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

    def family(self, law, short):
        return self.laws.get(law.root + FAMILY[short])

    def resolve(self, law, match, article):
        """The law, unit key and block suffix a reference points to, or None when it leaves the scope."""
        target = law
        if match["quoted"]:
            compact = re.sub(r"\s+", "", match["quoted"])
            target = next((l for name, l in self.laws.items() if re.sub(r"\s+", "", name) == compact), None)
        elif match["short"]:
            target = self.family(law, match["short"])
        elif match["alias"]:
            target = self.laws.get(law.aliases.get(match["alias"], ""))
        if target is None:
            return None
        if match["same_p"]:
            if article is None:
                return None
            block = f"p{match['same_p']}" + (f"-i{match['same_i']}" + (f"-{match['same_ib']}" if match["same_ib"] else "") if match["same_i"] else "")
            return target, article, block
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

    def delegates(self, law, target):
        """Whether a law can receive a delegation from the target: 시행령 from 법, 시행규칙 from 법 and 시행령."""
        if law.name.endswith(" 시행령"):
            return target.name == law.root
        if law.name.endswith(" 시행규칙"):
            return target.name in (law.root, law.root + " 시행령")
        return False

    def references(self, unit):
        """References in the shown versions of a unit as (law, key, block, delegation), in order of appearance."""
        found = []
        article = unit.key if unit.kind == "article" else None
        for effective in unit.law.needed():
            if unit.key not in unit.law.rows_of(effective):
                continue
            other_law = False
            for suffix, text, table in unit_lines(unit, effective):
                if table:
                    text = L.number_text(text, wrapped=True)
                if unit.kind == "addendum" and suffix and "-p" not in suffix:
                    other_law = bool(AMENDS_OTHER.match(text))
                if other_law:
                    continue
                previous_end, previous_law = None, unit.law
                for match in REFERENCE.finditer(text):
                    preceding = text[max(0, match.start() - 3): match.start()]
                    prefixed = match["quoted"] or match["short"] or match["alias"]
                    if not prefixed and preceding.endswith(("이 ", "부칙 ", "부칙")):
                        continue
                    continued = previous_end is not None and CONTINUATION.fullmatch(text[previous_end: match.start()])
                    origin = previous_law if continued and not prefixed else unit.law
                    previous_end = match.end()
                    resolved = self.resolve(origin, match, article) if origin else None
                    previous_law = resolved[0] if resolved else (None if prefixed or continued else unit.law)
                    if not resolved:
                        continue
                    target, key, block = resolved
                    delegation = target is not unit.law and self.delegates(unit.law, target) and bool(DELEGATION.match(text, match.end()))
                    entry = (target.name, key, block, delegation)
                    if entry not in found:
                        found.append(entry)
        return found

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
            for name, key, _, _ in self.references(unit):
                cited = self.unit(name, key)
                if cited is None:
                    self.review.append(f"{unit.name} cites {name} {key}, which the current and scheduled versions lack")
                else:
                    add(cited)
        return chosen


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
        for name, key, block, delegation in statutes.references(unit):
            target = names.get((name, key))
            if target is None or target == unit:
                continue
            version = current.get((name, key))
            lines = {s: t for s, t, _ in unit_lines(target, version["effective"])} if version else {}
            found = version and block and block in lines
            text = link(target.name, block_id(version, block) if found else None)
            cites.append(text)
            delegated = lines[block] if found else " ".join(t for t in lines.values())
            if delegation and DELEGATED_TO[law.name.endswith(" 시행규칙")].search(delegated):
                based.append(text)
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
                "datePublication": iso(row["공포일자"]),
                "idLocal": law.chosen[version["first"]]["법령일련번호"],
                "number": f"제{L.promulgation(row['공포번호'])}호",
                "wasDerivedFrom": link(law.notes[version["effective"]].stem),
            }
            if "last" in version:
                entry["dateNoLongerInForce"] = iso(version["last"])
            realized.append(order(entry))
        meta["isRealizedBy"] = realized
        meta["title"] = unit.title
        meta["isPartOf"] = link(unit.parent().name)
        meta["typeSubdivision"] = unit.subdivision
        meta["number"] = unit.number
    sources = [law.notes[v["effective"]].stem for v in versions] if versions else [law.notes[d].stem for d in law.needed()]
    meta["source"] = [link(s) for s in dict.fromkeys(sources)]
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
    found = {}
    for version in versions:
        for suffix, text, _ in unit_lines(unit, version["effective"]):
            if suffix:
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
    for source in SOURCES["admrul"]:
        path, identifier, meta, body, blocks = render_notice(source, as_of)
        notes[path] = (identifier, note_text(meta, body), blocks)
    names = [path.stem for path in notes]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(f"two statute notes would share a name: {duplicates}")
    return statutes, notes


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    check = sys.argv[1:] == ["--check"]
    statutes, notes = generate()
    changed = [path for path, (_, text, _) in notes.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
    for line in statutes.review:
        print("REVIEW", line)
    if check:
        for path in changed:
            print("DIFFERS", path.relative_to(L.VAULT))
        print(f"{len(notes)} notes, {len(changed)} differ")
        sys.exit(1 if changed else 0)
    ledger, head = latest_ledger(), commit()
    entries = []
    for path, (identifier, text, blocks) in notes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path in changed:
            path.write_text(text, encoding="utf-8", newline="\n")
        digest = note_hash(text)
        if ledger.get(identifier, {}).get("note") != digest:
            entries.append({"identifier": identifier, "note": digest, "blocks": blocks, "generator": "scripts/statutes.py", "commit": head})
    if entries:
        with LEDGER.open("a", encoding="utf-8", newline="\n") as handle:
            for entry in entries:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"{len(notes)} notes, {len(changed)} written, {len(entries)} ledger lines")


if __name__ == "__main__":
    main()
