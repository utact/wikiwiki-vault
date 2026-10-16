"""Lint the wiki against the checks under Lint in CLAUDE.md.

Usage:
    uv run python -X utf8 scripts/lint.py [ROOT]

ROOT defaults to the vault root. The tests run it on tests/fixtures/lint, a small vault with clean notes and notes with planted defects. On the vault root it also runs the checks that need the whole repository: the schema document, the index, the statute notes and secrets in tracked files.
"""

import ast
import json
import math
import operator
import re
import subprocess
import sys
from datetime import date
from fractions import Fraction
from pathlib import Path

import feel
import lawlib as L
import vault as V

STATUTE_TYPES = ("LegalResource", "LegalResourceSubdivision")
LINK = re.compile(r"(!?)\[\[([^\]|#]+)(?:#\^([a-z0-9-]+))?(?:\|([^\]]*))?\]\]")
FOOTNOTE_DEF = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
FOOTNOTE_REF = re.compile(r"\[\^([^\]]+)\]")
QUOTE = re.compile(r"“([^”]+)”((?:\[\^[^\]]+\])*)")
SENTENCE_END = re.compile(r"(?:다\.|[.?!])((?:\[\^[^\]]+\])*)(?=\s|$)")
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
        self.meta, self.body = V.read_note(path)
        self.type = self.meta.get("type")
        self.statute = self.type in STATUTE_TYPES
        self.blocks = block_texts(self.body)

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
        self.files = {p.name for folder in ("wiki", "raw") for p in (self.root / folder).rglob("*") if p.is_file()}
        self.terms = sorted((n.stem for n in self.notes.values() if n.folder == "wiki" and not n.statute and re.search(r"\d", n.stem)),
                            key=len, reverse=True)
        self.as_of = L.release()[0].strftime("%Y%m%d") if (self.root / "ontology" / "release.yaml").exists() else L.release()[0].strftime("%Y%m%d")
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
            for embed, name, block, _ in LINK.findall(note.text):
                name = name.strip().split("/")[-1]
                if embed:
                    if name not in self.files:
                        self.problem(note, f"embedded file not found: {name}")
                    continue
                target = self.notes.get(name)
                if target is None:
                    self.problem(note, f"broken link: [[{name}]]")
                    continue
                if block and block not in target.blocks:
                    self.problem(note, f"undeclared block: [[{name}#^{block}]]")
                if target.stem != note.stem:
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
        """Footnote definitions as id -> (links, inline code)."""
        found = {}
        for line in note.body.split("\n"):
            match = FOOTNOTE_DEF.match(line.strip())
            if match:
                found[match.group(1)] = (LINK.findall(match.group(2)), CODE_SPAN.findall(match.group(2)))
        return found

    def cited(self, note, links):
        """Texts of the sources that footnote links point to, as (text, table, target, block) tuples."""
        found = []
        for embed, name, block, _ in links:
            target = self.notes.get(name.strip())
            if target is None or embed:
                continue
            if block and block in target.blocks:
                parts = [target.blocks[b] for b in target.blocks if b == block or b.startswith(block + "-")]
                found.append(("\n".join(text for text, _ in parts), any(table for _, table in parts), target, block))
            elif target.folder == "raw" and not block:
                payload = target.path.with_suffix(".json")
                found.append((payload.read_text(encoding="utf-8") if payload.exists() else target.body, False, target, None))
            elif target.statute and not block:
                self.problem(note, f"footnote cites [[{name}]] without a block")
        return found

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
            for links, _ in self.footnotes(note).values():
                for embed, name, block, _ in links:
                    target = self.notes.get(name.strip())
                    if target is not None and target.type != "Rule":
                        footnote_links.add((target.stem, block))
            for stem, block in sorted(footnote_links - source_links):
                self.problem(note, f"footnote source missing from source: [[{stem}{'#^' + block if block else ''}]]")
            for stem, block in sorted(source_links - footnote_links):
                if self.content(note):
                    self.problem(note, f"source no footnote cites: [[{stem}{'#^' + block if block else ''}]]")

    def content(self, note):
        """Lines of a note body that state facts: paragraphs, list items and warning callouts."""
        found, in_code, in_question = [], False, False
        for line in note.body.split("\n"):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if stripped.startswith(">"):
                inner = stripped.lstrip(">").strip()
                callout = re.match(r"\[!(\w+)\]", inner)
                if callout:
                    in_question = callout.group(1) == "question"
                    continue
                if not in_question and inner:
                    found.append(inner)
                continue
            in_question = False
            if not stripped or stripped.startswith("#") or FOOTNOTE_DEF.match(stripped):
                continue
            found.append(re.sub(r"^(?:[-*]|\d+\.)\s+", "", stripped))
        return found

    def check_sentences(self):
        for note in self.authored():
            notes = self.footnotes(note)
            for links, _ in notes.values():
                self.check_labels(note, links)
            applies = bool(note.meta.get("appliesWhen"))
            for line in self.content(note):
                quotes = []

                def hide(match):
                    quotes.append(match)
                    return f"\x00{len(quotes) - 1}\x00" + match.group(2)

                masked = QUOTE.sub(hide, line)
                start = 0
                pieces = []
                for match in SENTENCE_END.finditer(masked):
                    pieces.append(masked[start: match.end()])
                    start = match.end()
                if masked[start:].strip():
                    pieces.append(masked[start:])
                for piece in pieces:
                    sentence = re.sub(r"\x00(\d+)\x00", lambda m: "“" + quotes[int(m.group(1))].group(1) + "”", piece).strip()
                    self.check_sentence(note, sentence, quotes, piece, notes, applies)

    def check_sentence(self, note, sentence, quotes, piece, notes, applies):
        bare = LINK.sub("", FOOTNOTE_REF.sub("", sentence))
        for name in self.terms:
            bare = bare.replace(name, " ")
        if not re.search(r"[가-힣A-Za-z0-9]", CODE_SPAN.sub("", bare)):
            return
        refs = FOOTNOTE_REF.findall(sentence)
        if not refs:
            self.problem(note, f"sentence without a source: {sentence[:60]}")
            return
        sources, values = [], set()
        for ref in refs:
            if ref not in notes:
                self.problem(note, f"footnote [^{ref}] has no definition")
                continue
            links, codes = notes[ref]
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
                values.update(Fraction(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", code))
                stated = {v for kind, v, _ in L.number_tokens(bare) if kind == "number"}
                if result not in stated:
                    self.problem(note, f"calculation `{code}` gives {float(result):g}, which the sentence does not state")
        for _, _, target, block in sources:
            if target.statute and block and not applies and not self.current(target, block):
                self.problem(note, f"cites a version not in force on the reference date without appliesWhen: [[{target.stem}#^{block}]]")
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
        pool = []
        for text, table, _, _ in sources:
            pool += L.number_tokens(L.number_text(text, wrapped=table))
        for kind, value, unit in L.number_tokens(bare):
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
        """A footnote label of a statute block is the official citation, optionally with 본문, 단서, 전단, 후단 or 각 호 외의 부분."""
        for embed, name, block, label in links:
            target = self.notes.get(name.strip())
            if not (target and target.statute and block and label):
                continue
            suffix = block.split("-", 1)[1] if "-" in block else block
            expected = target.stem + ("" if suffix == "t" else V.block_label(suffix))
            if label.strip() not in [expected + part for part in PARTS]:
                self.problem(note, f"footnote label {label!r} is not the citation {expected!r}")

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
                for name in feel.unknown_names(meta["literalExpression"], inputs):
                    self.problem(note, f"literalExpression uses {name!r}, which is not in requiredInput")
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
        for expression in expressions:
            for name in feel.unknown_names(expression, self.concepts(note)):
                self.problem(note, f"{where} uses {name!r}, which is not a concept the note links")

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
                except feel.FeelError as error:
                    self.problem(note, f"rule {number} output does not parse: {error}")
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

    # whole repository

    def check_repository(self):
        commands = [
            ("schema document", ["scripts/schema_doc.py", "--check"]),
            ("index", ["scripts/index.py", "--check"]),
            ("statute notes", ["scripts/statutes.py", "--check"]),
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
        self.check_rules()
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
