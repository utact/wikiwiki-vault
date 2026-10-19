"""Write Obsidian canvases that draw the ontology with labelled relations.

Usage:
    uv run python -X utf8 scripts/canvas.py [--check]

The graph view of Obsidian draws links without their kind, so these canvases draw each relation with its property name.
views/schema.canvas shows the classes of ontology/schema.yaml, grouped by standard, with their object properties and is_a links.
views/역량 질문/<number> <title>.canvas shows the answer to each competency question that ontology/cq holds a query for: the notes the query returns, the notes it names, the notes that join the two, and the statute blocks they cite as source.
--check lists the canvases that differ from a fresh generation, and changes nothing.
"""

import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import lawlib as L
import vault as V

VIEWS = Path("views")
QUESTIONS = Path("docs") / "competency-questions.md"
QUERIES = Path("ontology") / "cq"
BASE = "https://w3id.org/kr-employment/"
STATUTE = {"LegalResource", "LegalResourceSubdivision"}
LINK = re.compile(r"\[\[([^\]|#]+)(?:#\^([a-z0-9-]+))?(?:\|[^\]]*)?\]\]")
NOT_RELATIONS = {"source", "isDerivedFrom", "implements", "hasLegalResource", "cites", "basedOn", "isPartOf", "isRealizedBy", "decisionTable"}
STATUTE_RELATIONS = {"isDefinedBy"}

# One color per class, shared with the color groups of the graph view in .obsidian/graph.json.
COLORS = {
    "PublicService": "#e8590c", "LifeEvent": "#f59f00", "BusinessEvent": "#f59f00", "Event": "#f59f00",
    "PublicOrganisation": "#0ca678", "Agent": "#0ca678", "Participation": "#d6336c", "Channel": "#ae3ec9", "Output": "#ae3ec9",
    "Rule": "#7048e8", "Requirement": "#1c7ed6", "Criterion": "#1c7ed6", "Constraint": "#1098ad",
    "InformationConcept": "#37b24d", "EvidenceType": "#f76707", "ConceptScheme": "#c2255c", "Concept": "#e64980",
    "Work": "#495057", "LegalResource": "#495057", "LegalResourceSubdivision": "#868e96",
}
SOURCE_COLOR = "#868e96"
STANDARDS = [
    ("CPSV-AP", ["PublicService", "Participation", "Channel", "Output", "Rule", "Event", "LifeEvent", "BusinessEvent", "Agent", "PublicOrganisation"]),
    ("CCCEV", ["Requirement", "Criterion", "Constraint", "InformationConcept", "EvidenceType"]),
    ("ELI", ["Work", "LegalResource", "LegalResourceSubdivision"]),
    ("SKOS", ["ConceptScheme", "Concept"]),
]
NOTE_SIZE, BLOCK_SIZE, CLASS_SIZE = (400, 240), (440, 240), (320, 180)
COLUMN_GAP, ROW_GAP, GROUP_PAD = 160, 40, 60


def node_id(*parts):
    return hashlib.sha1("\0".join(parts).encode("utf-8")).hexdigest()[:16]


def links(value):
    """(note, block or None) for each wikilink in a frontmatter value or a list of them."""
    values = value if isinstance(value, list) else [value]
    return [(m.group(1).strip(), m.group(2)) for v in values if isinstance(v, str) for m in LINK.finditer(v)]


def layout(keys, edges):
    """(column, row) of each node: columns by the longest path over the edges without cycles, rows ordered by the rows of predecessors."""
    order = {key: index for index, key in enumerate(keys)}
    successors = defaultdict(list)
    for a, b in edges:
        if a != b and a in order and b in order and b not in successors[a]:
            successors[a].append(b)
    state, back = {}, set()
    for root in keys:
        if root in state:
            continue
        stack = [(root, iter(successors[root]))]
        state[root] = "open"
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                state[node] = "done"
                stack.pop()
            elif state.get(child) == "open":
                back.add((node, child))
            elif child not in state:
                state[child] = "open"
                stack.append((child, iter(successors[child])))
    forward = [(a, b) for a in keys for b in successors[a] if (a, b) not in back]
    incoming = defaultdict(list)
    for a, b in forward:
        incoming[b].append(a)
    column = {}
    remaining = list(keys)
    while remaining:
        ready = [k for k in remaining if all(p in column for p in incoming[k])]
        for key in ready:
            column[key] = max((column[p] + 1 for p in incoming[key]), default=0)
        remaining = [k for k in remaining if k not in column]
    rows, placed = {}, {}
    for current in range(max(column.values(), default=-1) + 1):
        members = [k for k in keys if column[k] == current]
        def weight(key):
            rows_of = [placed[p] for p in incoming[key] if p in placed]
            return (sum(rows_of) / len(rows_of) if rows_of else order[key], order[key])
        for row, key in enumerate(sorted(members, key=weight)):
            rows[key] = row
            placed[key] = row
    return {key: (column[key], rows[key]) for key in keys}


def place(cells, sizes, origin=(0, 0)):
    """Pixel positions of nodes from their (column, row) cells, with each column as wide as its widest node."""
    widths, heights = defaultdict(int), defaultdict(int)
    for key, (column, row) in cells.items():
        widths[column] = max(widths[column], sizes[key][0])
        heights[(column, row)] = sizes[key][1]
    xs, x = {}, origin[0]
    for column in sorted(widths):
        xs[column] = x
        x += widths[column] + COLUMN_GAP
    positions = {}
    for key, (column, row) in cells.items():
        y = origin[1] + sum(heights[(column, r)] + ROW_GAP for r in range(row))
        positions[key] = (xs[column], y)
    return positions


def edge(a, b, label, color=None):
    data = {"id": node_id("edge", a, b, label), "fromNode": a, "fromSide": "right", "toNode": b, "toSide": "left", "label": label}
    if a == b:
        data.update(fromSide="top", toSide="right")
    if color:
        data["color"] = color
    return data


def dump(data):
    return json.dumps(data, ensure_ascii=False, indent="\t") + "\n"


# schema

def schema_canvas():
    view = V.SchemaView(str(V.SCHEMA))
    classes = {name: c for name, c in view.all_classes().items() if name != "NamedThing" and "NamedThing" in view.class_ancestors(name)}
    listed = [name for _, names in STANDARDS for name in names]
    assert sorted(listed) == sorted(classes), set(classes) ^ set(listed)
    relations = []
    for name, cls in classes.items():
        inherited = set(view.class_slots(cls.is_a)) if cls.is_a else set()
        for slot in view.class_slots(name):
            if slot in inherited:
                continue
            target = view.induced_slot(slot, name).range
            if target in classes:
                relations.append((name, target, slot))
        if cls.is_a in classes:
            relations.append((name, cls.is_a, "is_a"))
    nodes, edges, x = [], [], 0
    for standard, names in STANDARDS:
        cells = layout(names, [(a, b) for a, b, _ in relations])
        sizes = {name: CLASS_SIZE for name in names}
        positions = place(cells, sizes, origin=(x + GROUP_PAD, GROUP_PAD + 40))
        right = max(px + CLASS_SIZE[0] for px, _ in positions.values()) + GROUP_PAD
        bottom = max(py + CLASS_SIZE[1] for _, py in positions.values()) + GROUP_PAD
        nodes.append({"id": node_id("group", standard), "type": "group", "x": x, "y": 0, "width": right - x, "height": bottom, "label": standard})
        for name in names:
            cls = classes[name]
            text = f"### {name}\n\n`{cls.class_uri}`" + (" (abstract)" if cls.abstract else "") + f"\n\n{cls.description or ''}"
            px, py = positions[name]
            nodes.append({"id": node_id("class", name), "type": "text", "text": text, "x": px, "y": py,
                          "width": CLASS_SIZE[0], "height": CLASS_SIZE[1], "color": COLORS[name]})
        x = right + COLUMN_GAP
    for a, b, label in relations:
        edges.append(edge(node_id("class", a), node_id("class", b), label, SOURCE_COLOR if label == "is_a" else None))
    return {"nodes": nodes, "edges": edges}


# competency questions

def questions(root):
    """Competency questions as id -> (number, title, question) from docs/competency-questions.md."""
    found, title = {}, None
    for line in (root / QUESTIONS).read_text(encoding="utf-8").split("\n"):
        heading = re.match(r"## (\d+)\. (.+)", line)
        if heading:
            title = (int(heading.group(1)), heading.group(2).strip())
        identifier = re.match(r"- 식별자: `(cq-\d+)`", line)
        if identifier and title:
            current = identifier.group(1)
            found[current] = (title[0], title[1], "")
        question = re.match(r"- 질문: (.+)", line)
        if question and title and found:
            last = next(reversed(found))
            found[last] = (*found[last][:2], question.group(1).strip())
    return found


def answer_canvas(vault, stems, header):
    """A canvas of the notes in stems and the relations among them, with the statute blocks they cite as source in the last column."""
    notes = vault.notes
    wiki = {s for s, (_, folder, meta) in notes.items() if folder == "wiki" and meta.get("type") not in STATUTE}
    chosen = [s for s in stems if s in wiki]
    outgoing = {s: [(key, target) for key, value in notes[s][2].items() if key not in NOT_RELATIONS
                    for target, block in links(value) if target in notes and not block] for s in wiki}
    bridges = [s for s in sorted(wiki - set(chosen))
               if any(t in chosen for _, t in outgoing[s]) and any(t == s for c in chosen for _, t in outgoing[c])]
    chosen += bridges
    relations = [(s, t, key) for s in chosen for key, t in outgoing[s] if t in chosen]
    statute_relations = [(s, t, key) for s in chosen for key, t in outgoing[s] if key in STATUTE_RELATIONS and notes[t][2].get("type") in STATUTE]
    blocks = []
    for s in chosen:
        for target, block in links(notes[s][2].get("source")):
            if target in notes and notes[target][2].get("type") in STATUTE and block:
                blocks.append((s, (target, block)))
    keys = chosen
    cells = layout(keys, [(a, b) for a, b, _ in relations])
    last = max((c for c, _ in cells.values()), default=-1) + 1
    statutes = list(dict.fromkeys([("unit", t, "") for _, t, _ in statute_relations] + [("block", t, b) for _, (t, b) in blocks]))
    citing = defaultdict(list)
    for s, t, _ in statute_relations:
        citing[("unit", t, "")].append(s)
    for s, (t, b) in blocks:
        citing[("block", t, b)].append(s)
    ordered = sorted(statutes, key=lambda k: (sum(cells[s][1] for s in citing[k]) / len(citing[k]), k))
    for row, key in enumerate(ordered):
        cells[key] = (last, row)
    sizes = {k: (BLOCK_SIZE if isinstance(k, tuple) else NOTE_SIZE) for k in cells}
    positions = place(cells, sizes, origin=(0, 0))
    ids = {k: node_id("note", k) if not isinstance(k, tuple) else node_id(*k) for k in cells}
    nodes = [{"id": node_id("header"), "type": "text", "text": header, "x": 0, "y": -320, "width": 880, "height": 260}]
    for key in cells:
        x, y = positions[key]
        if isinstance(key, tuple):
            _, stem, block = key
            data = {"id": ids[key], "type": "file", "file": notes[stem][0].relative_to(vault.root).as_posix(), "x": x, "y": y,
                    "width": BLOCK_SIZE[0], "height": BLOCK_SIZE[1], "color": COLORS[notes[stem][2]["type"]]}
            if block:
                data["subpath"] = f"#^{block}"
        else:
            data = {"id": ids[key], "type": "file", "file": notes[key][0].relative_to(vault.root).as_posix(), "x": x, "y": y,
                    "width": NOTE_SIZE[0], "height": NOTE_SIZE[1], "color": COLORS.get(notes[key][2].get("type"), SOURCE_COLOR)}
        nodes.append(data)
    edges = [edge(ids[a], ids[b], label) for a, b, label in relations]
    edges += [edge(ids[s], ids[("unit", t, "")], key) for s, t, key in statute_relations]
    edges += [edge(ids[s], ids[("block", t, b)], "source", SOURCE_COLOR) for s, (t, b) in blocks]
    return {"nodes": nodes, "edges": list({e["id"]: e for e in edges}.values())}


def question_canvases(root):
    problems, graph = V.check(root)
    if problems:
        sys.exit("vault check fails: " + problems[0])
    vault = V.Vault(root)
    by_identifier = {identifier: stem for stem, identifier in vault.ids.items()}
    found = {}
    for identifier, (number, title, question) in questions(root).items():
        query = root / QUERIES / f"{identifier}.rq"
        if not query.exists():
            continue
        text = query.read_text(encoding="utf-8")
        items = sorted({str(row.item).removeprefix(BASE) for row in graph.query(text) if row.item is not None})
        named = re.findall(r"employment:([a-z0-9-]+)", text)
        stems = list(dict.fromkeys(by_identifier[i] for i in named + items if i in by_identifier))
        header = (f"## {identifier} {title}\n\n질문: {question}\n\n"
                  f"`ontology/cq/{identifier}.rq`가 돌려주는 노트와 그 노트들의 관계, 근거 조문 block이다. 연결선의 이름은 schema의 property다.")
        found[VIEWS / "역량 질문" / f"{number:02d} {title}.canvas"] = answer_canvas(vault, stems, header)
    return found


def canvases(root):
    found = {VIEWS / "schema.canvas": schema_canvas()}
    found.update(question_canvases(root))
    return {path: dump(data) for path, data in found.items()}


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    root = L.VAULT
    expected = canvases(root)
    generated = set((root / VIEWS).rglob("*.canvas")) if (root / VIEWS).exists() else set()
    if "--check" in sys.argv[1:]:
        stale = [str(p) for p, text in expected.items() if not (root / p).exists() or (root / p).read_text(encoding="utf-8") != text]
        stale += [str(p.relative_to(root)) for p in generated if p.relative_to(root) not in expected]
        for path in sorted(stale):
            print(path)
        print(f"{len(expected)} canvases, {len(stale)} differ")
        sys.exit(1 if stale else 0)
    for path in generated:
        if path.relative_to(root) not in expected:
            path.unlink()
    for path, text in expected.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(expected)} canvases written")


if __name__ == "__main__":
    main()
