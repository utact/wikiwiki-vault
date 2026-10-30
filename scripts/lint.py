"""Lint the wiki against the checks under Lint in CLAUDE.md.

Usage:
    uv run python -X utf8 scripts/lint.py [ROOT]

ROOT defaults to the vault root. The tests run it on copies of tests/fixtures/vault, a small clean vault, with planted defects. On the vault root it also runs the checks that need the whole repository: the schema document, the index, the statute notes and secrets in tracked files.

Lint compares each number with the cited blocks, not the claim it makes: a sentence that puts two numbers of a block together wrongly passes, so the verifier agent compares the meaning.
"""

import ast
import json
import math
import operator
import re
import subprocess
import sys
import urllib.parse
from datetime import date
from fractions import Fraction
from pathlib import Path

import feel
import lawlib as L
import vault as V

STATUTE_TYPES = ("LegalResource", "LegalResourceSubdivision")
DECISIONS = Path("docs") / "decisions.md"
LINK = re.compile(r"(!?)\[\[([^\]|#]+)(?:#\^([a-z0-9-]+))?(?:\|([^\]]*))?\]\]")
ANY_LINK = re.compile(r"(!?)\[\[([^\]|#]+)(#[^\]|]*)?(?:\|([^\]]*))?\]\]")
FOOTNOTE_DEF = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
FOOTNOTE_REF = re.compile(r"\[\^([^\]]+)\]")
QUOTE = re.compile(r"“([^”]+)”((?:\[\^[^\]]+\])*)")
OTHER_QUOTE = re.compile(r"‘[^’]*’|\"[^\"]*\"")
SENTENCE_END = re.compile(r"(?:다\.|[.?!])((?:\[\^[^\]]+\])*)(?=\s|$)")
DOTTED_DATE = re.compile(r"\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.")
MARKDOWN_LINK = re.compile(r"(!?)\[([^\]]*)\]\((?:<([^>]*)>|([^)\s]+))[^)]*\)")
SINO = "[일이삼사오육칠팔구십백천만억]*(?:[일이삼사오육칠팔구][십백천만억]|[십백천만억][일이삼사오육칠팔구십백천만억])[일이삼사오육칠팔구십백천만억]*"
NATIVE = "(?:(?:열|스물|스무)\\s?)?(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉)|열|스무|서른|마흔|쉰|예순|일흔|여든|아흔"
KOREAN_NUMERAL = re.compile(
    r"(?<![가-힣\d])(?:"
    + SINO + r"\s?(?:원|개월|년|세|시간|명|회|배|주|번|일)"
    r"|[일삼사오육칠팔구]\s(?:년|개월|세|시간|명|회|배|번|일)"
    r"|(?<![을를]\s)(?:" + NATIVE + r")\s?(?:번|회|배|명|달|해|개월|시간|살|가지|차례|날)"
    r"|(?:두|세|네|다섯|여섯|일곱|여덟|아홉|스무)\s[가-힣]+"
    r"|하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘|보름"
    r"|[일이삼사오육칠팔구십백천만]+분의\s?[일이삼사오육칠팔구십백천만]+"
    r")(?=$|[^가-힣]|[은는이가을를의에과와도만로으까부보간다인씩쯤마째분안])"
)
UNITS = {"DAY": {"일"}, "WEE": {"주"}, "MON": {"개월", "달"}, "ANN": {"년", "세"}, "HUR": {"시간"}, "KRW": {"원"}}
DURATION_UNITS = {"D": "DAY", "W": "WEE", "M": "MON", "Y": "ANN", "H": "HUR"}
CREDENTIALS = {"oc", "servicekey", "authkey", "apikey", "key", "crtfckey", "token"}
TABLE_DELIMITER = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+$")
CODE_SPAN = re.compile(r"`([^`]+)`")
BLOCK_LINE = re.compile(r"\s\^([a-z0-9-]+)\s*$")
PARTS = ("", " 본문", " 단서", " 전단", " 후단", " 각 호 외의 부분")
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv}
FUNCTIONS = {"min": min, "max": max, "floor": lambda x: Fraction(math.floor(x)), "ceiling": lambda x: Fraction(math.ceil(x))}


def block_texts(body):
    """Declared blocks of a note body as id -> (text, table): a paragraph ending in ^id, or a fenced block followed by a line ^id."""
    found, lines, index = {}, body.split("\n"), 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            end = next((j for j in range(index + 1, len(lines)) if lines[j].startswith("```")), len(lines))
            after = next((j for j in range(end + 1, len(lines)) if lines[j].strip()), None)
            if after is not None and re.fullmatch(r"\^([a-z0-9-]+)", lines[after].strip()):
                found[lines[after].strip()[1:]] = ("\n".join(lines[index + 1:end]), True)
                index = after + 1
                continue
            index = end + 1
            continue
        match = BLOCK_LINE.search(line)
        if match:
            found[match.group(1)] = (line[: match.start()], False)
        index += 1
    return found


class Note:
    def __init__(self, path, folder, root):
        self.path, self.folder, self.stem = path, folder, path.stem
        self.where = path.relative_to(root).as_posix()
        self.text = path.read_text(encoding="utf-8")
        self.meta, self.body = ({}, self.text) if folder == "docs" else V.read_note(path)
        self.type = self.meta.get("type")
        self.statute = self.type in STATUTE_TYPES
        self.blocks = block_texts(self.body)
        self.headings = {m.group(1).strip() for m in re.finditer(r"^#{1,6}\s+(.+)$", self.body, re.M)}

    def versions(self):
        """Versions of a statute note as first date -> (first, last), dates as YYYYMMDD and last None when open."""
        found = {}
        for entry in self.meta.get("isRealizedBy") or []:
            first = entry["firstDateEntryInForce"].replace("-", "")
            last = entry.get("dateNoLongerInForce")
            found[first] = (first, last.replace("-", "") if last else None)
        return found


def evaluate(expression):
    """Value of an arithmetic expression with numbers, + - * / //, parentheses and min, max, floor and ceiling."""

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Fraction(str(node.value))
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS:
            return Fraction(FUNCTIONS[node.func.id](*[walk(a) for a in node.args]))
        raise ValueError(f"not an arithmetic expression: {expression}")

    return walk(ast.parse(expression.replace(",", ""), mode="eval"))


def feel_numbers(text):
    """Numbers and dates in a FEEL text as (kind, value, ratio pairs, unit code).

    The ratio pairs are the a / b pairs that may state a ratio such as 100분의 60, and the unit code of a duration part is DAY, MON or ANN.
    """
    text = re.sub(r'"(?:\\.|[^"\\])*"', lambda m: m.group(0) if re.fullmatch(r'"(?:\d{4}-\d{2}-\d{2}|-?P[0-9YMWDTHS]+)"', m.group(0)) else '""', text)
    pairs = [(Fraction(a), Fraction(b)) for a, b in re.findall(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text)]
    found = [("date", d, pairs, None) for d in re.findall(r'"(\d{4}-\d{2}-\d{2})"', text)]
    text = re.sub(r'"\d{4}-\d{2}-\d{2}"', " ", text)
    for duration in re.findall(r'"-?P([0-9YMWDTHS]+)"', text):
        date_part, _, time_part = duration.partition("T")
        found += [("number", Fraction(n), pairs, DURATION_UNITS.get(u)) for n, u in re.findall(r"(\d+)([YMWD])", date_part)]
        found += [("number", Fraction(n), pairs, "HUR" if u == "H" else None) for n, u in re.findall(r"(\d+)([HMS])", time_part)]
    text = re.sub(r'"-?P[0-9YMWDTHS]+"', " ", text)
    for match in re.finditer(r"(?<![\w가-힣])(?<!\d\.)\d+(?:\.\d+)?(?![\w가-힣])", text):
        operand = text[: match.start()].rstrip().endswith(("*", "/")) or text[match.end():].lstrip().startswith(("*", "/"))
        found.append(("number", Fraction(match.group(0)), pairs, "operand" if operand else None))
    return found


def intersect(a, b):
    """The interval two intervals of one type share, or None."""
    if not feel.meet(a, b):
        return None
    low, low_closed = feel.max_bound((a[1], a[2]), (b[1], b[2]))
    high, high_closed = feel.min_bound((a[3], a[4]), (b[3], b[4]))
    return (a[0], low, low_closed, high, high_closed)


class Linter:
    def __init__(self, root):
        self.root = Path(root)
        self.problems = []
        self.notes = {}
        for folder in ("wiki", "raw", "synthetic"):
            for path in sorted((self.root / folder).rglob("*.md")):
                note = Note(path, folder, self.root)
                if note.stem in self.notes:
                    self.problem(note, f"duplicate note name {note.stem}")
                self.notes[note.stem] = note
        decisions = self.root / DECISIONS
        if decisions.exists():
            self.notes[decisions.stem] = Note(decisions, "docs", self.root)
        self.files = {p.name for folder in ("wiki", "raw") for p in (self.root / folder).rglob("*") if p.is_file()}
        self.terms = sorted((n.stem for n in self.notes.values() if n.folder == "wiki" and not n.statute and re.search(r"\d", n.stem)),
                            key=len, reverse=True)
        self.as_of = L.release(self.root)[0].strftime("%Y%m%d")
        ledger = self.root / "ontology" / "verification.jsonl"
        self.ledger = {}
        if ledger.exists():
            for line in ledger.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    self.ledger[entry["identifier"]] = entry

    def problem(self, note, message):
        self.problems.append(f"{note.where}: {message}")

    def wiki(self):
        return [n for n in self.notes.values() if n.folder == "wiki"]

    def authored(self):
        """Notes written by the LLM: wiki notes other than generated statute notes."""
        return [n for n in self.notes.values() if n.folder in ("wiki", "synthetic") and not n.statute]

    # links

    def check_links(self):
        """Broken links and undeclared blocks, links to synthetic notes, and notes outside the graph.

        A note is outside the graph when no other note links to it and it links to nothing but statute and raw notes.
        """
        incoming = {stem: 0 for stem in self.notes}
        outgoing = {stem: 0 for stem in self.notes}
        for note in self.notes.values():
            if note.folder == "raw":
                publisher = note.meta.get("publisher")
                for target in self.notes.values():
                    if target.meta.get("identifier") == publisher:
                        incoming[target.stem] += 1
                continue
            if note.folder == "wiki":
                for _, _, angled, plain in MARKDOWN_LINK.findall(note.text):
                    target_path = urllib.parse.unquote(angled or plain).replace("\\", "/")
                    target = self.notes.get(Path(target_path.split("#")[0]).stem)
                    if "synthetic/" in target_path or (target and target.folder == "synthetic"):
                        self.problem(note, f"links synthetic data: {target_path}")
            for embed, name, anchor, _ in ANY_LINK.findall(note.text):
                name = name.strip().split("/")[-1]
                block = anchor[2:] if anchor.startswith("#^") else None
                if embed:
                    if name not in self.files and name not in self.notes:
                        self.problem(note, f"embedded file not found: {name}")
                    elif note.folder == "wiki" and name in self.notes and self.notes[name].folder == "synthetic":
                        self.problem(note, f"embeds synthetic note [[{name}]]")
                    continue
                target = self.notes.get(name)
                if target is None:
                    self.problem(note, f"broken link: [[{name}{anchor}]]")
                    continue
                if block is not None and block not in target.blocks:
                    self.problem(note, f"undeclared block: [[{name}{anchor}]]")
                elif anchor and block is None and anchor[1:].strip() not in target.headings:
                    self.problem(note, f"link to a heading the note lacks: [[{name}{anchor}]]")
                if target.stem != note.stem and note.folder != "docs":
                    incoming[target.stem] += 1
                    if target.folder == "wiki" and not target.statute:
                        outgoing[note.stem] += 1
                if note.folder == "wiki" and target.folder == "synthetic":
                    self.problem(note, f"links synthetic note [[{name}]]")
        for note in self.authored():
            if note.folder == "wiki" and incoming[note.stem] == 0 and outgoing[note.stem] == 0:
                self.problem(note, "outside the graph: no note links to it, and it links only to statute and raw notes")

    # sources and sentences

    def footnotes(self, note):
        """Footnote definitions as id -> (links, inline code, whether the calculation is an example marked with 예시).

        A definition goes on over the indented lines after it, as Markdown footnotes do.
        """
        texts, current = {}, None
        for line in note.body.split("\n"):
            match = FOOTNOTE_DEF.match(line.strip()) if not line.startswith((" ", "\t")) else None
            if match:
                current = match.group(1)
                texts[current] = match.group(2)
            elif current and line.startswith(("    ", "\t")) and line.strip():
                texts[current] += " " + line.strip()
            elif line.strip():
                current = None
        return {key: (LINK.findall(text), CODE_SPAN.findall(text), "예시" in CODE_SPAN.sub("", LINK.sub("", text)))
                for key, text in texts.items()}

    def cited(self, note, links):
        """Texts of the sources that footnote links point to, as (text, table, target, block) tuples."""
        found = []
        for embed, name, block, _ in links:
            target = self.notes.get(name.strip())
            if target is None or embed or target.folder == "docs":
                continue
            if block and block in target.blocks:
                parts = [target.blocks[b] for b in target.blocks if b == block or b.startswith(block + "-")]
                found.append(("\n".join(text for text, _ in parts), any(table for _, table in parts), target, block))
            elif target.folder == "raw" and not block:
                found.append((self.raw_facts(target), False, target, None))
            elif target.statute and not block:
                self.problem(note, f"footnote cites [[{name}]] without a block")
        return found

    @staticmethod
    def version_dates(sources):
        """The 시행일 of the version of each cited statute block, which its block ID names, as 2020-08-28 for ^v20200828-p2.

        A 부칙 may set it as a time after 공포, such as 공포 후 1년이 경과한 날, and then only the versions of the provisions it starts state the date.
        """
        found = []
        for _, _, target, block in sources:
            match = re.match(r"v(\d{4})(\d{2})(\d{2})-", block or "")
            if target.statute and match:
                found.append(("date", "-".join(match.groups()), None))
        return found

    def raw_facts(self, note):
        """What a footnote to a whole raw note can rest on: its frontmatter and the basic information of its response, such as 시행일자 and 공포번호.

        The text of a statute is not among them, because a footnote to statute text cites its block.
        """
        found = [json.dumps(note.meta, ensure_ascii=False, default=str)]
        payload = note.path.with_suffix(".json")
        if payload.exists():
            data = json.loads(payload.read_text(encoding="utf-8"))
            for value in (data.values() if isinstance(data, dict) else []):
                if isinstance(value, dict):
                    found += [json.dumps(v, ensure_ascii=False) for k, v in value.items() if "기본정보" in k]
        return "\n".join(found)

    def check_sources(self):
        for note in self.authored():
            sources = note.meta.get("source") or []
            sources = sources if isinstance(sources, list) else [sources]
            source_links = set()
            for value in sources:
                match = LINK.fullmatch(value.strip())
                target = self.notes.get(match.group(2).strip()) if match else None
                if target is None:
                    continue
                block = match.group(3)
                if not (target.folder == "raw" or (target.statute and block)):
                    self.problem(note, f"source is not a raw note, a statute block or a quotation: {value}")
                source_links.add((target.stem, block or ""))
            footnote_links = set()
            for links, *_ in self.footnotes(note).values():
                for embed, name, block, _ in links:
                    target = self.notes.get(name.strip())
                    if target is not None and target.type != "Rule" and target.folder != "docs":
                        footnote_links.add((target.stem, block))
            for stem, block in sorted(footnote_links - source_links):
                self.problem(note, f"footnote source missing from source: [[{stem}{'#^' + block if block else ''}]]")
            for stem, block in sorted(source_links - footnote_links):
                if self.content(note):
                    self.problem(note, f"source no footnote cites: [[{stem}{'#^' + block if block else ''}]]")

    def content(self, note, questions=False):
        """Lines of a note body that state facts: paragraphs, list items, table rows and warning callouts.

        With questions, the lines of question callouts instead. Table header and delimiter rows state nothing.
        """
        facts, asked, in_code, in_question, in_footnote = [], [], False, False, False
        lines = note.body.split("\n")
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if in_footnote and line.startswith(("    ", "\t")) and stripped:
                continue
            in_footnote = bool(FOOTNOTE_DEF.match(line)) or (in_footnote and not stripped)
            if stripped.startswith(">"):
                inner = stripped.lstrip(">").strip()
                callout = re.match(r"\[!(\w+)\][+-]?\s*(.*)$", inner)
                if callout:
                    in_question = callout.group(1) == "question"
                    title = callout.group(2).strip()
                    if title and re.search(r"(?:다\.?|[.?!])$", title):
                        (asked if in_question else facts).append(title)
                    continue
                if inner:
                    (asked if in_question else facts).append(inner)
                continue
            in_question = False
            if not stripped or stripped.startswith("#") or FOOTNOTE_DEF.match(stripped):
                continue
            following = lines[index + 1].strip() if index + 1 < len(lines) else ""
            if stripped.startswith("|") and (TABLE_DELIMITER.match(stripped) or TABLE_DELIMITER.match(following)):
                continue
            facts.append(re.sub(r"^(?:[-*]|\d+\.)\s+", "", stripped))
        return asked if questions else facts

    def check_sentences(self):
        for note in self.authored():
            notes = self.footnotes(note)
            for links, *_ in notes.values():
                self.check_labels(note, links)
            periods = self.applies_periods(note)
            for line in self.content(note, questions=True):
                if not re.search(r"\?((?:\[\^[^\]]+\])*)\s*$", line):
                    self.problem(note, f"question callout line is not a question: {line[:60]}")
            for line in self.content(note):
                quotes, kept = [], []

                def hide(match):
                    quotes.append(match)
                    return f"\x00{len(quotes) - 1}\x00" + match.group(2)

                def keep(match):
                    kept.append(match.group(0))
                    return f"\x01{len(kept) - 1}\x01"

                masked = QUOTE.sub(hide, line)
                masked = DOTTED_DATE.sub(keep, MARKDOWN_LINK.sub(keep, ANY_LINK.sub(keep, masked)))
                for other in OTHER_QUOTE.findall(CODE_SPAN.sub("", masked)):
                    self.problem(note, f"quote statutory text in “ ”, not {other[:1]}…{other[-1:]}: {other[:40]}")
                start = 0
                pieces = []
                for match in SENTENCE_END.finditer(masked):
                    pieces.append(masked[start: match.end()])
                    start = match.end()
                if masked[start:].strip():
                    pieces.append(masked[start:])
                for piece in pieces:
                    piece = re.sub(r"\x01(\d+)\x01", lambda m: kept[int(m.group(1))], piece)
                    sentence = re.sub(r"\x00(\d+)\x00", lambda m: "“" + quotes[int(m.group(1))].group(1) + "”", piece).strip()
                    self.check_sentence(note, sentence, quotes, piece, notes, periods)

    def check_frontmatter(self, note):
        """Numbers and dates in definition, unaryTests, decision table cells and literalExpression must be in the blocks of source or isDerivedFrom."""
        links = []
        for key in ("source", "isDerivedFrom"):
            values = note.meta.get(key) or []
            for value in values if isinstance(values, list) else [values]:
                links += LINK.findall(str(value))
        sources = self.cited(note, links)
        pool = []
        for text, table, _, _ in sources:
            pool += L.number_tokens(L.number_text(text, wrapped=table))
        pool += self.version_dates(sources)
        numbers = {v for k, v, _ in pool if k == "number"}
        ratios = {v for k, v, _ in pool if k == "ratio"}
        dates = {v for k, v, _ in pool if k == "date"}

        def report(where, kind, value, unit=""):
            shown = value if kind == "date" else f"{float(value):g}{unit}"
            self.problem(note, f"{where} has {kind} {shown}, which is not in the blocks of source or isDerivedFrom")

        definition = str(note.meta.get("definition") or "")
        for name in self.terms:
            definition = definition.replace(name, " ")
        for kind, value, unit in L.number_tokens(definition, notes=False):
            if kind == "date" and value not in dates:
                report("definition", kind, value)
            elif kind == "ratio" and value not in ratios:
                report("definition", kind, value)
            elif kind == "number" and not (("number", value, unit) in pool if unit else value in numbers):
                report("definition", kind, value)
        self.check_numerals(note, definition, [text for text, _, _, _ in sources], "definition")
        expressions = []
        if note.meta.get("unaryTests") is not None:
            concept = (note.meta.get("hasConcept") or [None])[0] if note.type == "Criterion" else note.meta.get("constrains")
            expressions.append(("unaryTests", str(note.meta["unaryTests"]), self.concept_unit(concept)))
        if note.meta.get("literalExpression"):
            expressions.append(("literalExpression", str(note.meta["literalExpression"]), None))
        table = note.meta.get("decisionTable") or {}
        columns = [self.concept_unit(v) for v in (table.get("input") or []) + (table.get("output") or [])]
        for number, row in enumerate(table.get("rule") or [], start=1):
            expressions += [(f"rule {number}", str(cell), unit) for cell, unit in zip(row, columns + [None] * len(row))]
        for where, text, column_unit in expressions:
            for kind, value, pairs, unit in feel_numbers(text):
                units = None if unit == "operand" else UNITS.get(unit or column_unit)
                if kind == "date" and value not in dates:
                    report(where, kind, value)
                elif kind == "number" and value not in (0, 1) and units and not any(("number", value, u) in pool for u in units) and not (
                    # FEEL durations have no weeks, so the days of a duration may state 주 of the block, as P14D for 2주간.
                    unit == "DAY" and value % 7 == 0 and ("number", value / 7, "주") in pool
                ):
                    report(where, kind, value, "/".join(sorted(units)))
                elif kind == "number" and value not in (0, 1) and not units and not (
                    value in numbers or value in ratios or any(value in (a, b) and b and a / b in ratios for a, b in pairs)
                ):
                    report(where, kind, value)

    def concept_unit(self, value):
        """The UN/CEFACT unit code or ISO 4217 currency of a linked concept, such as DAY or KRW."""
        match = LINK.fullmatch(str(value or "").strip())
        target = self.notes.get(match.group(2).strip()) if match else None
        return (target.meta.get("unitCode") or target.meta.get("currency")) if target else None

    def label_text(self, name, label):
        """The label of a wikilink, without the 공포일자 or 시행일자 of the statute note it names, as in 부칙 제35934호(2025. 12. 23.)."""
        target = self.notes.get(name.strip())
        if not (target and target.statute):
            return label
        dates = {f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in re.findall(r"sup-(\d{8})-", str(target.meta.get("identifier") or ""))}
        for entry in target.meta.get("isRealizedBy") or []:
            dates.update(str(entry.get(key)) for key in ("datePublication", "firstDateEntryInForce") if entry.get(key))
        return L.DATE_TOKEN.sub(lambda m: " " if f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}" in dates else m.group(0), label)

    def check_numerals(self, note, text, cited, where):
        """Numbers written in Korean words, such as 두 배, unless a cited block writes them the same way, as 두 번 이상."""
        pool = "".join(L.canonical(t) for t in cited)
        for numeral in KOREAN_NUMERAL.finditer(text):
            if re.sub(r"\s+", "", numeral.group(0)) not in pool:
                self.problem(note, f"{where}: write numbers in Arabic numerals unless the cited block writes them in words: {numeral.group(0)}")

    def applies_periods(self, note):
        """Date intervals in which all the criteria a note applies when can hold, or None when none of them tests a date.

        A note applies when every criterion holds, so the intervals of the criteria intersect.
        A criterion on a date holds only in the dates its own test admits, so its own test counts too.
        """
        values = note.meta.get("appliesWhen") or []
        values = values if isinstance(values, list) else [values]
        criteria = [note] if note.type == "Criterion" else []
        for value in values:
            match = LINK.fullmatch(str(value).strip())
            criteria.append(self.notes.get(match.group(2).strip()) if match else None)
        periods = None
        for target in criteria:
            if target is None or target.type != "Criterion" or target.meta.get("unaryTests") is None:
                continue
            concept = (target.meta.get("hasConcept") or [None])[0]
            if self.concept_type(concept) != "date":
                continue
            try:
                negated, tests = feel.unary_tests(str(target.meta["unaryTests"]))
            except feel.FeelError:
                continue
            if any(kind == "expression" for kind, *_ in tests):
                continue
            intervals = [("date", *t[1:]) for t in (feel.complement(tests) if negated else tests)]
            periods = intervals if periods is None else [i for a in periods for b in intervals if (i := intersect(a, b))]
        return periods

    def version_meets(self, target, block, periods):
        """Whether the period of a cited version shares a day with one of the periods."""
        match = re.match(r"v(\d{8})-", block)
        if not match:
            return True
        first, last = target.versions().get(match.group(1), (match.group(1), None))
        iso = lambda d: f"{d[:4]}-{d[4:6]}-{d[6:]}"
        span = ("date", iso(first), True, iso(last) if last else feel.INFINITY, bool(last))
        return any(feel.meet(span, period) for period in periods)

    def check_sentence(self, note, sentence, quotes, piece, notes, periods):
        unlinked = FOOTNOTE_REF.sub("", sentence)
        skeleton = ANY_LINK.sub(" ", MARKDOWN_LINK.sub(" ", unlinked))
        bare = ANY_LINK.sub(lambda m: f" {self.label_text(m.group(2), m.group(4))} " if m.group(4) else " ",
                            MARKDOWN_LINK.sub(lambda m: f" {m.group(2)} ", unlinked))
        for name in self.terms:
            bare = bare.replace(name, " ")
            skeleton = skeleton.replace(name, " ")
        if not re.search(r"[가-힣A-Za-z0-9]", CODE_SPAN.sub("", skeleton)):
            return
        refs = FOOTNOTE_REF.findall(sentence)
        if not refs:
            self.problem(note, f"sentence without a source: {sentence[:60]}")
            return
        sources, values, operands = [], set(), []
        stated = {v for kind, v, _ in L.number_tokens(bare, notes=False) if kind == "number"}
        for ref in refs:
            if ref not in notes:
                self.problem(note, f"footnote [^{ref}] has no definition")
                continue
            links, codes, example = notes[ref]
            sources += self.cited(note, links)
            rules = [n for _, n, _, _ in links if self.notes.get(n.strip()) and self.notes[n.strip()].type == "Rule"]
            for code in codes:
                if not rules:
                    self.problem(note, f"calculation `{code}` in footnote [^{ref}] links no Rule")
                    continue
                try:
                    result = evaluate(code)
                except (ValueError, SyntaxError, ZeroDivisionError) as error:
                    self.problem(note, f"calculation `{code}` does not evaluate: {error}")
                    continue
                values.add(result)
                numbers = [Fraction(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", code)]
                ratios = [(Fraction(a.replace(",", "")), Fraction(b.replace(",", "")))
                          for a, b in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*/\s*(\d[\d,]*(?:\.\d+)?)", code)]
                for number in numbers:
                    if example and number in stated:
                        values.add(number)
                    else:
                        operands.append((code, number, ratios, example))
                if result not in stated:
                    self.problem(note, f"calculation `{code}` gives {float(result):g}, which the sentence does not state")
        if not sources and not values:
            self.problem(note, f"sentence without a source: its footnotes cite no statute block, quotation or raw note: {sentence[:60]}")
            return
        self.check_numerals(note, ANY_LINK.sub(" ", MARKDOWN_LINK.sub(" ", re.sub(r"\x00\d+\x00", " ", piece))),
                            [text for text, _, _, _ in sources], "sentence")
        for _, _, target, block in sources:
            if not (target.statute and block) or self.current(target, block):
                continue
            if periods is None:
                self.problem(note, f"cites a version not in force on the reference date without an appliesWhen date condition: [[{target.stem}#^{block}]]")
            elif not self.version_meets(target, block, periods):
                self.problem(note, f"cites a version outside the dates of its appliesWhen: [[{target.stem}#^{block}]]")
        for index in map(int, re.findall(r"\x00(\d+)\x00", piece)):
            quote = quotes[index]
            if not quote.group(2):
                self.problem(note, f"quote without a footnote: “{quote.group(1)[:40]}”")
                continue
            quoted_sources = []
            for ref in FOOTNOTE_REF.findall(quote.group(2)):
                if ref in notes:
                    quoted_sources += self.cited(note, notes[ref][0])
            if not any(L.canonical(quote.group(1)) in L.canonical(text) for text, _, _, _ in quoted_sources):
                self.problem(note, f"quote does not match the cited block: “{quote.group(1)[:40]}”")
        pool = self.version_dates(sources)
        for text, table, _, _ in sources:
            pool += L.number_tokens(L.number_text(text, wrapped=table))
        numbers = {v for k, v, _ in pool if k == "number"}
        ratios = {v for k, v, _ in pool if k == "ratio"}
        for code, number, pairs, example in operands:
            in_ratio = any(number in (a, b) and b and a / b in ratios for a, b in pairs)
            if number in numbers or number in ratios or number in values or in_ratio:
                continue
            if example:
                self.problem(note, f"calculation `{code}` uses {float(number):g}, which is neither in the sentence nor in the cited blocks")
            else:
                self.problem(note, f"calculation `{code}` uses {float(number):g}, which is not in the cited blocks; mark an example input with 예시")
        for kind, value, unit in L.number_tokens(bare, notes=False):
            if value in values and kind == "number":
                continue
            if kind == "code":
                if not any(value in text for text, _, _, _ in sources):
                    self.problem(note, f"code {value} is not in the cited sources")
                continue
            if kind == "number" and unit:
                ok = ("number", value, unit) in pool
            elif kind == "number":
                ok = any(k == "number" and v == value for k, v, _ in pool)
            else:
                ok = (kind, value, None) in pool
            if not ok:
                shown = value if kind in ("date", "code") else f"{float(value):g}{unit or ''}"
                self.problem(note, f"{kind} {shown} is not in the cited blocks: {sentence[:60]}")

    def current(self, target, block):
        """Whether the version of a block is in force on the reference date."""
        match = re.match(r"v(\d{8})-", block)
        if not match:
            return True
        first, last = target.versions().get(match.group(1), (match.group(1), None))
        return first <= self.as_of and (last is None or self.as_of <= last)

    def check_labels(self, note, links):
        """A footnote link to a statute block carries the official citation as its label.

        The label may add 본문, 단서, 전단, 후단 or 각 호 외의 부분 when the block has that part, and an item of a 별표 or 서식, such as 제1호나목.
        A 서식 item may follow the words of the section that holds it, such as 고용보험·산재보험 작성방법 제2호, and each word must appear in the form.
        An article of a 행정규칙 is one block, so the label may name its 항 and 호, such as 제12조제2항제1호, and the article must have that 항.
        """
        for embed, name, block, label in links:
            target = self.notes.get(name.strip())
            if not (target and target.statute and block):
                continue
            suffix = block.split("-", 1)[1] if "-" in block else block
            expected = target.stem + ("" if suffix == "t" else V.block_label(suffix))
            if not label:
                self.problem(note, f"footnote link [[{target.stem}#^{block}]] has no citation label")
                continue
            items, kind = "", target.meta.get("typeSubdivision")
            if suffix in ("t", "remarks") and kind == "annex":
                items = r"(?: ?제\d+호(?:의\d+)?(?:[가-하]목)?)?"
            elif suffix == "t" and kind == "form":
                items = r"(?: (?P<words>(?:[^\s제]\S* )*)제\d+호(?:의\d+)?(?:[가-하]목)?)?"
            elif suffix == "t" and kind == "article" and str(target.meta.get("identifier", "")).startswith("admrul-"):
                items = r"(?:제(?P<paragraph>\d+)항)?(?:제\d+호(?:의\d+)?(?:[가-하]목)?)?"
            parts = "|".join(re.escape(p) for p in PARTS if p)
            match = re.fullmatch(re.escape(expected) + items + f"(?P<part>{parts})?", label.strip())
            if not match:
                self.problem(note, f"footnote label {label!r} is not the citation {expected!r}")
                continue
            part = (match.group("part") or "").strip()
            own = target.blocks.get(block, ("", False))[0]
            words = match.groupdict().get("words") or ""
            missing = [w for w in words.split() if re.sub(r"[·ㆍ]", "", w) not in L.canonical(own)]
            if missing:
                self.problem(note, f"footnote label {label!r} names {' '.join(missing)}, which the form does not contain")
            paragraph = match.groupdict().get("paragraph")
            if paragraph and chr(0x2460 + int(paragraph) - 1) not in own:
                self.problem(note, f"footnote label {label!r} names 제{paragraph}항, which the article does not contain")
            if part in ("본문", "단서") and "다만" not in own:
                self.problem(note, f"footnote label {label!r} names the {part}, but the block has no 단서")
            elif part in ("전단", "후단") and "이 경우" not in own:
                self.problem(note, f"footnote label {label!r} names the {part}, but the block has no 후단")
            elif part == "각 호 외의 부분" and not any(b.startswith(block + "-i") for b in target.blocks) and not block.endswith("-lead"):
                self.problem(note, f"footnote label {label!r} names the 각 호 외의 부분, but the block has no 호")

    # rules

    def concept_type(self, value):
        match = LINK.fullmatch((value or "").strip())
        target = self.notes.get(match.group(2).strip()) if match else None
        return target.meta.get("typeRef") if target else None

    def check_rules(self):
        for note in self.authored():
            meta = note.meta
            if meta.get("unaryTests") is not None:
                concept = (meta.get("hasConcept") or [None])[0] if note.type == "Criterion" else meta.get("constrains")
                self.check_tests(note, meta["unaryTests"], self.concept_type(concept), "unaryTests")
            if note.type != "Rule":
                continue
            inputs = [LINK.fullmatch(v.strip()).group(2) for v in meta.get("requiredInput") or [] if LINK.fullmatch(v.strip())]
            if meta.get("literalExpression"):
                self.check_expression(note, str(meta["literalExpression"]), {n: self.concept_type(f"[[{n}]]") for n in inputs},
                                      self.concept_type(meta.get("variable")), "literalExpression", "in requiredInput")
            table = meta.get("decisionTable")
            if table:
                self.check_table(note, table, inputs)

    def concepts(self, note):
        """Names of the InformationConcept notes that a note's frontmatter links."""
        front = note.text[: note.text.find("\n---\n", 4)]
        return sorted({n.strip() for _, n, _, _ in LINK.findall(front)
                       if self.notes.get(n.strip()) and self.notes[n.strip()].type == "InformationConcept"})

    def check_tests(self, note, text, type_ref, where):
        try:
            kinds = feel.types(text)
            expressions = feel.expressions(text)
        except feel.FeelError as error:
            self.problem(note, f"{where} does not parse: {error}")
            return
        if type_ref and kinds - {type_ref}:
            self.problem(note, f"{where} {text!r} compares {sorted(kinds)}, but the concept is {type_ref}")
        names = {n: self.concept_type(f"[[{n}]]") for n in self.concepts(note)}
        for expression in expressions:
            self.check_expression(note, expression, names, type_ref, where, "a concept the note links")

    def check_expression(self, note, expression, names, type_ref, where, scope):
        """Report an expression that does not parse, uses names outside its scope or has another type than its concept."""
        try:
            kind, unknown = feel.expression_type(expression, names)
        except feel.FeelError as error:
            self.problem(note, f"{where} does not parse: {error}")
            return
        for name in unknown:
            self.problem(note, f"{where} uses {name!r}, which is not {scope}")
        if kind and type_ref and kind != type_ref:
            self.problem(note, f"{where} {expression!r} is {kind}, but the concept is {type_ref}")

    def check_table(self, note, table, inputs):
        names = [LINK.fullmatch(v.strip()).group(2) for v in table.get("input", [])]
        outputs = [LINK.fullmatch(v.strip()).group(2) for v in table.get("output", [])]
        variable = LINK.fullmatch((note.meta.get("variable") or "").strip())
        for name in names:
            if name not in inputs:
                self.problem(note, f"decision table input {name} is not in requiredInput")
        if not variable or outputs != [variable.group(2)]:
            self.problem(note, f"decision table outputs {outputs} are not the variable")
        types = [self.concept_type(f"[[{name}]]") for name in names]
        out_types = [self.concept_type(f"[[{name}]]") for name in outputs]
        rows = table.get("rule", [])
        for number, row in enumerate(rows, start=1):
            if len(row) != len(names) + len(outputs):
                continue
            for cell, type_ref in zip(row[: len(names)], types):
                self.check_tests(note, str(cell), type_ref, f"rule {number}")
            for cell, type_ref in zip(row[len(names):], out_types):
                try:
                    kind, _ = feel.value(str(cell))
                except feel.FeelError:
                    self.check_expression(note, str(cell), {n: self.concept_type(f"[[{n}]]") for n in inputs}, type_ref,
                                          f"rule {number} output", "in requiredInput")
                    continue
                if type_ref and kind != type_ref:
                    self.problem(note, f"rule {number} output {cell!r} is {kind}, but the concept is {type_ref}")
        if table.get("hitPolicy") == "UNIQUE":
            for i, a in enumerate(rows):
                for j, b in enumerate(rows[i + 1:], start=i + 2):
                    try:
                        if all(feel.overlaps(str(x), str(y)) for x, y in zip(a[: len(names)], b[: len(names)])):
                            self.problem(note, f"UNIQUE decision table rules {i + 1} and {j} overlap")
                    except feel.FeelError:
                        pass

    # ledger, versions and duplicates

    def check_ledger(self):
        statute_blocks = {}
        for note in self.wiki():
            if note.statute:
                entry = self.ledger.get(note.meta.get("identifier"))
                if entry is None or entry["note"] != L.note_hash(note.text):
                    self.problem(note, "statute note differs from its ledger entry")
                elif entry:
                    for block, digest in entry.get("blocks", {}).items():
                        statute_blocks[f"{note.stem}#^{block}"] = digest
        for note in self.authored():
            status = note.meta.get("status")
            if status == "reviewed" and not (note.meta.get("reviewedBy") and note.meta.get("lastReviewed")):
                self.problem(note, "reviewed note without reviewedBy and lastReviewed")
            if status in ("verified", "reviewed"):
                entry = self.ledger.get(note.meta.get("identifier"))
                if entry is None or entry["note"] != L.note_hash(note.text):
                    self.problem(note, f"{status} note without a matching ledger entry")
                    continue
                for block, digest in entry.get("blocks", {}).items():
                    if statute_blocks.get(block) != digest:
                        self.problem(note, f"cited block {block} changed since verification")
                for _, name, block, _ in LINK.findall(note.text):
                    target = self.notes.get(name.strip())
                    if target and target.statute and block and f"{target.stem}#^{block}" not in entry.get("blocks", {}):
                        self.problem(note, f"ledger entry lacks the cited block {target.stem}#^{block}")

    def check_versions(self):
        for note in self.wiki():
            if not note.statute:
                continue
            spans = sorted(
                ((e["firstDateEntryInForce"].replace("-", ""), (e.get("dateNoLongerInForce") or "").replace("-", "") or None)
                 for e in note.meta.get("isRealizedBy") or []),
                key=lambda span: (span[0], span[1] or "99999999"),
            )
            firsts = [first for first, _ in spans]
            if len(firsts) != len(set(firsts)):
                self.problem(note, "two versions with the same date")
            for (first, last), following in zip(spans, spans[1:] + [None]):
                if last and last < first:
                    self.problem(note, f"version {first} ends before it starts")
                if following and (last is None or last >= following[0]):
                    self.problem(note, f"versions {first} and {following[0]} overlap")
            for heading_date, label in re.findall(r"^## (\d{4}-\d{2}-\d{2}) 시행 \((\S+)\)", note.body, re.M):
                if label == "시행예정" and heading_date.replace("-", "") <= self.as_of:
                    self.problem(note, f"scheduled version {heading_date} comes into force on or before the reference date")

    def check_duplicates(self):
        seen, names = {}, {stem.casefold() for stem in self.notes}
        for note in self.notes.values():
            if note.folder == "docs":
                continue
            identifier = note.meta.get("identifier")
            if identifier in seen:
                self.problem(note, f"identifier {identifier} also in {seen[identifier]}")
            seen[identifier] = note.where
        aliases = {}
        for note in self.authored():
            for alias in note.meta.get("aliases") or []:
                if alias.casefold() in names or alias in aliases:
                    self.problem(note, f"alias {alias} is another note's name or alias")
                aliases[alias] = note.stem

    def check_raw_urls(self):
        for note in self.notes.values():
            url = note.meta.get("url") if note.folder == "raw" else None
            if not url:
                continue
            names = {key.lower() for key, _ in urllib.parse.parse_qsl(urllib.parse.urlsplit(str(url)).query, keep_blank_values=True)}
            for name in sorted(names & CREDENTIALS):
                self.problem(note, f"url keeps the credential parameter {name}")

    # whole repository

    def check_repository(self):
        commands = [
            ("schema document", ["scripts/schema_doc.py", "--check"]),
            ("index", ["scripts/index.py", "--check"]),
            ("statute notes", ["scripts/statutes.py", "--check"]),
            ("canvases", ["scripts/canvas.py", "--check"]),
        ]
        for name, args in commands:
            result = subprocess.run([sys.executable, "-X", "utf8", *args], cwd=L.VAULT, capture_output=True, text=True)
            if result.returncode:
                self.problems.append(f"{name} out of date: {result.stdout.strip().splitlines()[-1] if result.stdout.strip() else result.stderr.strip()[-200:]}")
        secrets = [s.encode("utf-8") for s in L.secrets()]
        tracked = subprocess.run(["git", "ls-files", "-z"], cwd=L.VAULT, capture_output=True, check=True).stdout.decode("utf-8").split("\0")
        for name in filter(None, tracked):
            path = L.VAULT / name
            if path.is_file() and any(s in path.read_bytes() for s in secrets):
                self.problems.append(f"{name}: contains a secret value")

    def run(self, repository, schema=True):
        if schema:
            problems, _ = V.check(self.root)
            self.problems += [f"vault check: {p}" for p in problems]
        self.check_links()
        self.check_sources()
        self.check_sentences()
        for note in self.authored():
            self.check_frontmatter(note)
        self.check_rules()
        self.check_raw_urls()
        self.check_ledger()
        self.check_versions()
        self.check_duplicates()
        if repository:
            self.check_repository()
        return self.problems


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else L.VAULT
    problems = Linter(root).run(repository=root == L.VAULT)
    for line in problems:
        print(line)
    print(f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
