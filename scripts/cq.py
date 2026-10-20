"""Check the competency questions against the wiki.

Usage:
    uv run python -X utf8 scripts/cq.py [ROOT]

A question is checked when ontology/cq/<id>.rq holds its query. The query runs on the RDF that
scripts/vault.py exports and returns ?item and ?source rows: the parts of the answer and the
statute units or blocks they rest on. Every provision that the expected answer in
docs/competency-questions.md cites must be among the sources, or contain one of them.
Citations under 범위 밖, 관련 사항 and 검사 항목 are not part of the expected answer.
An item of a 별표 or 별지 서식 resolves to the whole unit, because their notes declare no item blocks; the verifier compares the items themselves.
A bare 호 continues the article and 항 before it, and a range such as 제1호부터 제3호까지 cites every 호 in it.
A query fails when a BIND or FILTER uses a variable that its own group does not bind. SPARQL evaluates such a group before the outer pattern, so the variable is unbound there, and a later triple pattern then matches every note.

The scenarios in docs/scenarios.md are checked too. A step that names its service and states that an earlier step is its 선행 조건 must have that service `requires` the earlier step's service, and every competency question a step lists must be checked and pass.
"""

import re
import sys
from pathlib import Path

from rdflib import URIRef, Variable
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.parserutils import CompValue

import lawlib as L
import vault as V

QUESTIONS = L.VAULT / "docs" / "competency-questions.md"
SCENARIOS = L.VAULT / "docs" / "scenarios.md"
STEP = re.compile(r"^  (\d+)\. (.+)$")
STEP_ITEM = re.compile(r"^     - (.+)$")
SERVICE = re.compile(r"서비스는 `([a-z0-9-]+)`")
PRECONDITION = re.compile(r"선행 조건은 (\d+)단계")
QUESTION_ID = re.compile(r"cq-\d+")
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
            law, article, sup, paragraph, previous = ROOT_LAW, None, None, None, None
            if NOTICE in group or "최저임금 고시" in group:
                unit = self.unit(NOTICE)
                found.append((NOTICE, self.iri(unit) if unit else None))
                continue
            for match in CITATION.finditer(group):
                if match["short"]:
                    law, sup = ROOT_LAW + FAMILY[match["short"]], None
                if match["sup"] or match["annex"] or match["form"]:
                    article, sup = None, None
                if match["sup"]:
                    name = next((n for n in self.notes if re.fullmatch(rf"{re.escape(law)} 부칙 제{match['sup']}호(?: \(.*\))?", n)), None)
                    sup = (law, match["sup"], self.unit(name) if name else None)
                    found += [self.addendum(sup, number) for number in re.findall(r"제(\d+)조", match["sup_arts"])]
                    continue
                if match["art"] and sup:
                    found.append(self.addendum(sup, match["art"]))
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
                    paragraph, previous = p, (items[-1], match.end()) if items else None
                    continue
                if match["item"] and article:
                    item = (match["item"], match["item_b"])
                    if previous and re.search(r"부터", group[previous[1]:match.start()]) and not previous[0][1] and not item[1]:
                        found += [self.article(article, paragraph, (str(n), None)) for n in range(int(previous[0][0]) + 1, int(item[0]))]
                    found.append(self.article(article, paragraph, item))
                    previous = (item, match.end())
        return found

    def addendum(self, sup, number):
        """An article of a 부칙, which a bare 제N조 after the 부칙 in the same group continues."""
        law, act, unit = sup
        block = self.block(unit, [f"a{number}"]) if unit else None
        return f"{law} 부칙 제{act}호 제{number}조", self.iri(block) if block else None

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


def variables(node):
    """Variables used in an algebra expression, without the bookkeeping keys that rdflib adds."""
    if isinstance(node, Variable):
        return {node}
    if isinstance(node, CompValue):
        return set().union(set(), *(variables(value) for key, value in node.items() if not key.startswith("_")))
    if isinstance(node, (list, tuple)):
        return set().union(set(), *(variables(value) for value in node))
    return set()


def unscoped(text):
    """Variables that a BIND or FILTER of the query uses but its own group does not bind."""
    found = []

    def visit(node):
        if isinstance(node, CompValue):
            if node.name in ("Extend", "Filter"):
                bound = node.p.get("_vars") or set()
                found.extend(sorted(str(variable) for variable in variables(node.expr) - bound))
            for key, value in node.items():
                if not key.startswith("_"):
                    visit(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                visit(value)

    visit(prepareQuery(text).algebra)
    return found


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


def scenario_steps(text):
    """The numbered steps of each scenario, as id -> steps with their number, name, service, 선행 조건 and questions."""
    found, current, step = {}, None, None
    for line in text.split("\n"):
        match = re.match(r"- 식별자: `(sc-\d+)`", line)
        if match:
            current, step = match.group(1), None
            found[current] = []
            continue
        if line.startswith("## "):
            current, step = None, None
            continue
        if current is None:
            continue
        match = STEP.match(line)
        if match:
            step = {"number": int(match.group(1)), "name": match.group(2), "service": None, "requires": [], "questions": []}
            found[current].append(step)
            continue
        item = STEP_ITEM.match(line)
        if step and item:
            sentence = item.group(1)
            service = SERVICE.search(sentence)
            if service:
                step["service"] = service.group(1)
            step["requires"] += [int(n) for n in PRECONDITION.findall(sentence)]
            if sentence.startswith("검사하는 역량 질문은"):
                step["questions"] += QUESTION_ID.findall(sentence)
        elif not line.startswith("     "):
            step = None
    return {k: v for k, v in found.items() if v}


def check_scenarios(text, graph, writer, checked, failed):
    """Problems of the scenarios: missing `requires` between the services of steps, and step questions that are unchecked or fail."""
    found = []
    for scenario, steps in scenario_steps(text).items():
        services = {step["number"]: step["service"] for step in steps}
        for step in steps:
            where = f"{scenario} step {step['number']} {step['name']}"
            for number in step["requires"]:
                if not step["service"] or not services.get(number):
                    found.append(f"{where}: its 선행 조건 is step {number}, but the step or that step names no service")
                    continue
                subject, target = writer.iri(step["service"]), writer.iri(services[number])
                if (subject, None, None) not in graph:
                    found.append(f"{where}: no note has the identifier {step['service']}")
                elif (subject, V.DCT.requires, target) not in graph:
                    found.append(f"{where}: {step['service']} does not require {services[number]}, the service of step {number}")
            for question in step["questions"]:
                if question not in checked:
                    found.append(f"{where}: {question} has no query yet")
                elif question in failed:
                    found.append(f"{where}: {question} fails")
    return found


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
        text = query.read_text(encoding="utf-8")
        found += [f"{identifier}: a BIND or FILTER uses ?{variable}, which its own group does not bind" for variable in unscoped(text)]
        rows = list(graph.query(text))
        sources = {row.source for row in rows if isinstance(row.source, URIRef)}
        report[identifier] = rows
        for citation, iri in resolver.citations("\n".join(lines)):
            if iri is None:
                found.append(f"{identifier}: the expected answer cites {citation}, which has no statute note or block")
            elif not any(within(source, iri, graph) for source in sources):
                found.append(f"{identifier}: no part of the answer rests on {citation}")
    failed = {line.split(":")[0] for line in found}
    found += check_scenarios(SCENARIOS.read_text(encoding="utf-8"), graph, resolver.writer, set(report), failed)
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
