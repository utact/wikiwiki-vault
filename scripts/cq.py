"""Check the competency questions against the wiki.

Usage:
    uv run python -X utf8 scripts/cq.py [ROOT]

A question is checked when ontology/cq/<id>.rq holds its query. The query runs on the RDF that
scripts/vault.py exports and returns ?item and ?source rows: the parts of the answer and the
statute units or blocks they rest on. Every provision that the expected answer in
docs/competency-questions.md cites must be among the sources, or contain one of them.
Citations under 범위 밖, 관련 사항 and 검사 항목 are not part of the expected answer.
An item of a 별표 or 별지 서식 resolves to the whole unit, because their notes declare no item blocks; the verifier compares the items themselves.
"""

import re
import sys
from pathlib import Path

from rdflib import URIRef

import lawlib as L
import vault as V

QUESTIONS = L.VAULT / "docs" / "competency-questions.md"
QUERIES = L.VAULT / "ontology" / "cq"
ROOT_LAW = "고용보험법"
FAMILY = {"법": "", "영": " 시행령", "규칙": " 시행규칙"}
NOTICE = "2026년 적용 최저임금 고시"
GROUP = re.compile(r"\(((?:[^()]|\([^()]*\))*)\)")
CITATION = re.compile(
    r"(?:(?P<short>법|영|규칙)\s+)?"
    r"(?:부칙\(제(?P<sup>\d+)호\)\s*(?P<sup_arts>제\d+조(?:\s*[·ㆍ]\s*제\d+조)*)"
    r"|별표\s*(?P<annex>\d+)(?:의(?P<annex_b>\d+))?(?P<remarks>\s*비고)?(?:\s*제\d+호(?:의\d+)?(?:[가-하]목)?)?"
    r"|별지\s*제(?P<form>\d+)호(?:의(?P<form_b>\d+))?서식"
    r"|제(?P<art>\d+)조(?:의(?P<art_b>\d+))?(?:제(?P<p>\d+)항)?(?:제(?P<i>\d+)호(?:의(?P<i_b>\d+))?)?(?:(?P<m>[가-하])목)?"
    r"(?P<parts>(?:\s*[·ㆍ]\s*제\d+호(?:의\d+)?)*)"
    r"(?P<word>\s*(?:각\s*호\s*외의\s*부분|본문|단서|전단|후단))?"
    r"|제(?P<item>\d+)호(?:의(?P<item_b>\d+))?)"
)
LETTERS = "가나다라마바사아자차카타파하"


def sections():
    """Questions as id -> lines of the expected answer, without the lines under 범위 밖, 관련 사항 and 검사 항목."""
    found, current, keep = {}, None, False
    for line in QUESTIONS.read_text(encoding="utf-8").split("\n"):
        match = re.match(r"- 식별자: `(cq-\d+)`", line)
        if match:
            current, keep = match.group(1), False
            found[current] = []
            continue
        if current is None:
            continue
        if line.startswith("- "):
            keep = line.startswith("- 기대 답")
            continue
        if keep and line.strip():
            found[current].append(line)
    return found


class Resolver:
    """Version-independent IRIs of the statute units and blocks that the questions cite."""

    def __init__(self, graph, notes):
        self.graph, self.notes = graph, notes
        self.writer = V.RdfWriter(V.SchemaView(str(V.SCHEMA)))

    def iri(self, identifier):
        return self.writer.iri(identifier)

    def unit(self, name):
        note = self.notes.get(name)
        return note[2].get("identifier") if note else None

    def exists(self, identifier):
        return (self.iri(identifier), None, None) in self.graph

    def block(self, unit, suffixes):
        """The first block of a unit among the candidate suffixes that the graph declares, or the unit itself."""
        for suffix in suffixes:
            if self.exists(f"{unit}-{suffix}"):
                return f"{unit}-{suffix}"
        return None

    def citations(self, text):
        """(citation, IRI or None) for each provision a parenthesised group of an expected answer cites."""
        found = []
        for group in GROUP.findall(text):
            law, article, sup = ROOT_LAW, None, None
            if NOTICE in group or "최저임금 고시" in group:
                unit = self.unit(NOTICE)
                found.append((NOTICE, self.iri(unit) if unit else None))
                continue
            for match in CITATION.finditer(group):
                if match["short"]:
                    law = ROOT_LAW + FAMILY[match["short"]]
                if match["sup"] or match["annex"] or match["form"]:
                    article = None
                if match["sup"]:
                    name = next((n for n in self.notes if re.fullmatch(rf"{re.escape(law)} 부칙 제{match['sup']}호(?: \(.*\))?", n)), None)
                    unit = self.unit(name) if name else None
                    for number in re.findall(r"제(\d+)조", match["sup_arts"]):
                        block = self.block(unit, [f"a{number}"]) if unit else None
                        found.append((f"{law} 부칙 제{match['sup']}호 제{number}조", self.iri(block) if block else None))
                    continue
                if match["annex"]:
                    name = f"{law} 별표 {match['annex']}" + (f"의{match['annex_b']}" if match["annex_b"] else "")
                    unit = self.unit(name)
                    block = (self.block(unit, ["remarks"]) if match["remarks"] else unit) if unit else None
                    found.append((match.group(0).strip(), self.iri(block) if block else None))
                    continue
                if match["form"]:
                    name = f"{law} 별지 제{match['form']}호" + (f"의{match['form_b']}" if match["form_b"] else "") + "서식"
                    unit = self.unit(name)
                    found.append((name, self.iri(unit) if unit else None))
                    continue
                if match["art"]:
                    article = (law, match["art"], match["art_b"])
                    p, items = match["p"], [(match["i"], match["i_b"])] if match["i"] else []
                    items += [(n, b) for n, b in re.findall(r"제(\d+)호(?:의(\d+))?", match["parts"] or "")]
                    found += [self.article(article, p, i, m=match["m"] if not k else None, word=match["word"]) for k, i in enumerate(items or [None])]
                    continue
                if match["item"] and article:
                    found.append(self.article(article, None, (match["item"], match["item_b"])))
        return found

    def article(self, article, p, item, m=None, word=None):
        law, number, branch = article
        name = f"{law} 제{number}조" + (f"의{branch}" if branch else "")
        unit = self.unit(name)
        label = name + (f"제{p}항" if p else "") + (f"제{item[0]}호" if item else "") + (f"{m}목" if m else "") + (word or "")
        if unit is None:
            return label, None
        parts = ([f"p{p}"] if p else []) + ([f"i{item[0]}" + (f"-{item[1]}" if item[1] else "")] if item else [])
        if m:
            parts.append(f"m{LETTERS.index(m) + 1}")
        if not parts:
            if word and re.sub(r"\s+", "", word) == "각호외의부분":
                block = self.block(unit, ["lead"])
            elif word:
                block = self.block(unit, ["lead", "t"])
            else:
                block = unit
        else:
            block = self.block(unit, ["-".join(parts)])
        return label, self.iri(block) if block else None


def within(source, cited, graph):
    """Whether a source is the cited unit or block, or a part of it."""
    seen, queue = set(), [source]
    while queue:
        node = queue.pop()
        if node == cited:
            return True
        if node in seen:
            continue
        seen.add(node)
        queue += list(graph.objects(node, V.ELI.is_part_of))
    return False


def check(root):
    problems, graph = V.check(root)
    if problems:
        return [f"vault check: {p}" for p in problems], {}
    notes = {stem: entry for stem, entry in V.Vault(root).notes.items()}
    resolver = Resolver(graph, notes)
    found, report = [], {}
    for identifier, lines in sections().items():
        query = QUERIES / f"{identifier}.rq"
        if not query.exists():
            continue
        rows = list(graph.query(query.read_text(encoding="utf-8")))
        sources = {row.source for row in rows if isinstance(row.source, URIRef)}
        report[identifier] = rows
        for citation, iri in resolver.citations("\n".join(lines)):
            if iri is None:
                found.append(f"{identifier}: the expected answer cites {citation}, which has no statute note or block")
            elif not any(within(source, iri, graph) for source in sources):
                found.append(f"{identifier}: no part of the answer rests on {citation}")
    return found, report


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else L.VAULT
    problems, report = check(root)
    for identifier, rows in report.items():
        print(f"{identifier}: {len(rows)} rows")
    for line in problems:
        print(line)
    print(f"{len(report)} questions checked, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
