"""Load vault notes into the LinkML model, validate them and export RDF.

Usage:
    uv run python -X utf8 scripts/vault.py check [ROOT]
    uv run python -X utf8 scripts/vault.py export [ROOT] OUT.ttl

ROOT defaults to the vault root. Notes are read from ROOT/wiki and ROOT/raw.
"""

import re
import sys
from pathlib import Path

import yaml
from linkml.generators.shaclgen import ShaclGenerator
from linkml.validator import validate
from linkml_runtime.utils.schemaview import SchemaView
from pyshacl import validate as shacl_validate
from rdflib import RDF, RDFS, SH, XSD, BNode, Graph, Literal, Namespace, URIRef

VAULT = Path(__file__).resolve().parents[1]
SCHEMA = VAULT / "ontology" / "schema.yaml"
PREFIX = "employment"
NOTE_SLOTS = ("source", "status", "reviewedBy", "lastReviewed")
# Links to legal resources, whose ranges in ELI, CPSV-AP and CCCEV are works, never versions.
WORK_SLOTS = ("cites", "basedOn", "isDerivedFrom", "implements", "hasLegalResource")
# Properties of the act that gave a unit its text, which a block of the unit does not have.
ACT_PROPERTIES = ("identifier", "realizes", "datePublication", "idLocal", "number")
WIKILINK = re.compile(r"^\[\[([^\]|#]+)(?:#\^([a-z0-9-]+))?(?:\|[^\]]*)?\]\]$")
IDENTIFIER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class StringLoader(yaml.SafeLoader):
    """Keep every scalar as a string, as Obsidian writes them."""


StringLoader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in resolvers if tag == "tag:yaml.org,2002:null"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


BLOCK = re.compile(r"\^(v(\d{8})-([a-z0-9-]+)|q\d+)\s*$", re.M)
STATUTE_TYPES = ("LegalResource", "LegalResourceSubdivision")
BLOCK_TYPES = {"p": "paragraph", "i": "point", "m": "subpoint", "a": "article", "lead": "lead", "remarks": "remarks"}


def read_note(path):
    """Frontmatter and body of a note."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: no frontmatter")
    end = text.index("\n---\n", 4)
    return yaml.load(text[4:end], Loader=StringLoader) or {}, text[end + 5:]


def block_label(suffix):
    """Official citation of a block suffix, such as p1-i5-m1 for 제1항제5호가목."""
    words = {"lead": "각 호 외의 부분", "remarks": "비고"}
    if suffix in words:
        return " " + words[suffix]
    label = ""
    for part in suffix.split("-"):
        if part[0].isdigit():
            label += f"의{part}"
        elif part[0] == "m":
            label += "가나다라마바사아자차카타파하"[int(part[1:]) - 1] + "목"
        else:
            label += {"p": "제{}항", "i": "제{}호", "a": " 제{}조"}[part[0]].format(part[1:])
    return label


class Vault:
    def __init__(self, root):
        self.root = Path(root)
        self.view = SchemaView(str(SCHEMA))
        self.errors = []
        self.notes, self.blocks = {}, {}
        for folder in ("wiki", "raw"):
            for path in sorted((self.root / folder).rglob("*.md")):
                if path.stem in self.notes:
                    self.errors.append(f"duplicate note name: {path.stem}")
                meta, body = read_note(path)
                self.notes[path.stem] = (path, folder, meta)
                self.blocks[path.stem] = [m.group(1) for m in BLOCK.finditer(body)]
        self.ids = {}
        for stem, (path, _, meta) in self.notes.items():
            identifier = meta.get("identifier")
            if not identifier:
                self.errors.append(f"{path}: no identifier")
            elif identifier in self.ids.values():
                self.errors.append(f"duplicate identifier: {identifier}")
            self.ids[stem] = identifier

    def curie(self, identifier):
        return f"{PREFIX}:{identifier}"

    def resolve(self, value, where, curie=False, work=False):
        """Return the identifier a wikilink points to, as a CURIE for uriorcurie slots.

        A link to a statute block names a version of the block, such as law-001761-art-45-v20210701-p5.
        With work, it names the block itself, such as law-001761-art-45-p5, and a whole-text block names the unit.
        """
        wrap = self.curie if curie else (lambda identifier: identifier)
        if where.startswith("raw/") and isinstance(value, str) and IDENTIFIER.match(value):
            if value in self.ids.values():
                return wrap(value)
            self.errors.append(f"{where}: unknown identifier: {value}")
            return None
        match = WIKILINK.match(value.strip()) if isinstance(value, str) else None
        if not match:
            self.errors.append(f"{where}: not a wikilink: {value!r}")
            return None
        stem = match.group(1).split("/")[-1]
        if stem not in self.ids:
            self.errors.append(f"{where}: broken link: {value}")
            return None
        identifier = self.ids[stem]
        block = match.group(2)
        if block:
            if block not in self.blocks.get(stem, []):
                self.errors.append(f"{where}: undeclared block: {value}")
                return None
            versioned = re.fullmatch(r"v\d{8}-([a-z0-9-]+)", block)
            if work and versioned:
                identifier += "" if versioned.group(1) == "t" else f"-{versioned.group(1)}"
            else:
                identifier = f"{identifier}-{block.removesuffix('-t')}"
        return wrap(identifier)

    def is_link_slot(self, slot):
        rng = slot.range
        if rng == "uriorcurie":
            return True
        if slot.inlined or slot.inlined_as_list:
            return False
        return rng in self.view.all_classes() and self.view.get_identifier_slot(rng) is not None

    def convert(self, cls, data, where):
        out = {}
        for key, value in data.items():
            if key not in self.view.class_slots(cls):
                self.errors.append(f"{where}: {key} is not a property of {cls}")
                continue
            slot = self.view.induced_slot(key, cls)
            if key == "type":
                out[key] = self.view.get_uri(value, expand=False)
            elif key == "identifier":
                out[key] = value
            elif key == "decisionTable":
                out[key] = self.decision_table(value, where)
            elif key == "hasEvidenceTypeList":
                lists = value if value and isinstance(value[0], list) else [value]
                out[key] = [
                    {"specifiesEvidenceType": [self.resolve(v, where) for v in items]} for items in lists
                ]
            elif self.is_link_slot(slot):
                values = value if isinstance(value, list) else [value]
                resolved = [self.resolve(v, where, curie=slot.range == "uriorcurie", work=key in WORK_SLOTS) for v in values]
                out[key] = resolved if slot.multivalued else resolved[0]
            elif slot.range in self.view.all_classes():
                rng = slot.range
                items = value if isinstance(value, list) else [value]
                converted = [self.convert(rng, item, where) for item in items]
                if key == "isRealizedBy":
                    for item in converted:
                        item.setdefault("realizes", data["identifier"])
                out[key] = converted if slot.multivalued else converted[0]
            else:
                out[key] = value
        return out

    def decision_table(self, table, where):
        inputs = [self.resolve(v, where) for v in table.get("input", [])]
        outputs = [self.resolve(v, where) for v in table.get("output", [])]
        rules = []
        for index, row in enumerate(table.get("rule", []), start=1):
            if len(row) != len(inputs) + len(outputs):
                self.errors.append(f"{where}: rule {index} has {len(row)} cells")
                continue
            rules.append({
                "position": index,
                "inputEntry": [{"position": i, "text": t} for i, t in enumerate(row[: len(inputs)], start=1)],
                "outputEntry": [{"position": i, "text": t} for i, t in enumerate(row[len(inputs):], start=1)],
            })
        return {
            "hitPolicy": table.get("hitPolicy"),
            "input": [{"position": i, "inputExpression": c} for i, c in enumerate(inputs, start=1)],
            "output": [{"position": i, "name": c} for i, c in enumerate(outputs, start=1)],
            "rule": rules,
        }

    def block_things(self, thing, stem, where):
        """Version-independent blocks of a statute note, such as law-001761-art-45-p5, each with its versions.

        A block ID such as v20260918-p5 names the version of block p5 that comes into force on 2026-09-18.
        The whole text block t is the version of the note's own unit.
        """
        expressions = {e["identifier"]: e for e in thing.get("isRealizedBy", [])}
        works = {}
        for block in self.blocks.get(stem, []):
            match = re.fullmatch(r"v(\d{8})-([a-z0-9-]+)", block)
            if not match or match.group(2) == "t":
                continue
            date, suffix = match.groups()
            version = expressions.get(f"{thing['identifier']}-v{date}")
            if version is None:
                self.errors.append(f"{where}: block {block} has no version dated {date} in isRealizedBy")
                continue
            parts = re.findall(r"[a-z]+\d*(?:-\d+)?", suffix)
            identifier = f"{thing['identifier']}-{suffix}"
            parent = f"{thing['identifier']}-{'-'.join(parts[:-1])}" if len(parts) > 1 else thing["identifier"]
            kind = parts[-1] if parts[-1] in BLOCK_TYPES else parts[-1][0]
            work = works.setdefault(identifier, {
                "type": self.view.get_uri("LegalResourceSubdivision", expand=False),
                "identifier": identifier,
                "prefLabel": stem + block_label(suffix),
                "isPartOf": parent,
                "typeSubdivision": BLOCK_TYPES[kind],
                "isRealizedBy": [],
            })
            expression = {k: v for k, v in version.items() if k not in ACT_PROPERTIES}
            work["isRealizedBy"].append({"identifier": f"{thing['identifier']}-{block}", "realizes": identifier, **expression})
        return list(works.values())

    def container(self):
        things, documents, sources = [], [], []
        for stem, (path, folder, meta) in self.notes.items():
            where = path.relative_to(self.root).as_posix()
            if folder == "raw":
                sources.append(self.convert("Entity", meta, where))
                continue
            cls = meta.get("type")
            if cls not in self.view.all_classes():
                self.errors.append(f"{where}: unknown type {cls!r}")
                continue
            body = {k: v for k, v in meta.items() if k not in NOTE_SLOTS}
            thing = self.convert(cls, body, where)
            thing["prefLabel"] = stem
            things.append(thing)
            if cls in STATUTE_TYPES:
                things += self.block_things(thing, stem, where)
            note = {k: v for k, v in meta.items() if k in NOTE_SLOTS}
            note = self.convert("NoteDocument", note, where)
            note["identifier"] = f"{meta.get('identifier')}-note"
            note["primaryTopic"] = thing.get("identifier")
            documents.append(note)
        return {"things": things, "documents": documents, "sources": sources}


def shapes_graph():
    """SHACL shapes generated from the schema, without the shapes of abstract classes.

    The generated shape of a concrete class already carries the constraints it inherits.
    Abstract shapes would apply again through rdfs:subClassOf and ignore slot_usage.
    """
    view = SchemaView(str(SCHEMA))
    writer = RdfWriter(view)
    graph = Graph()
    graph.parse(data=ShaclGenerator(str(SCHEMA)).serialize(), format="turtle")
    for name in view.all_classes():
        if view.get_class(name).abstract:
            target = writer.iri(view.get_uri(name, expand=False))
            for shape in list(graph.subjects(SH.targetClass, target)):
                for _, _, prop in list(graph.triples((shape, SH.property, None))):
                    graph.remove((prop, None, None))
                graph.remove((shape, None, None))
    return graph


class RdfWriter:
    """Write Container data as RDF, using the IRIs that the schema declares."""

    DATATYPES = {"date": XSD.date, "datetime": XSD.dateTime, "integer": XSD.integer, "decimal": XSD.decimal, "boolean": XSD.boolean}

    def __init__(self, view):
        self.view = view
        self.graph = Graph()
        self.prefixes = {p: str(v.prefix_reference) for p, v in view.schema.prefixes.items()}
        for prefix, iri in self.prefixes.items():
            self.graph.bind(prefix, Namespace(iri))
        self.class_by_uri = {view.get_uri(c, expand=False): c for c in view.all_classes()}

    def iri(self, value):
        """Expand a CURIE, or a bare identifier against the default prefix."""
        prefix, _, local = value.rpartition(":")
        if prefix in self.prefixes:
            return URIRef(self.prefixes[prefix] + local)
        return URIRef(self.prefixes[PREFIX] + value)

    def literal(self, value, slot):
        rng = slot.range
        if rng in self.view.all_enums():
            meaning = self.view.get_enum(rng).permissible_values[value].meaning
            return self.iri(meaning) if meaning else Literal(value)
        if rng == "uri":
            return URIRef(value)
        return Literal(value, datatype=self.DATATYPES.get(rng))

    def node(self, obj, cls):
        if "type" in obj:
            cls = self.class_by_uri[obj["type"]]
        subject = self.iri(obj["identifier"]) if "identifier" in obj else BNode()
        self.graph.add((subject, RDF.type, self.iri(self.view.get_uri(cls, expand=False))))
        for key, value in obj.items():
            if key == "type":
                continue
            slot = self.view.induced_slot(key, cls)
            predicate = self.iri(slot.slot_uri)
            if key == "identifier":
                self.graph.add((subject, predicate, Literal(value)))
                continue
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, dict):
                    self.graph.add((subject, predicate, self.node(item, slot.range)))
                elif slot.range == "uriorcurie" or (
                    slot.range in self.view.all_classes() and not slot.inlined and not slot.inlined_as_list
                ):
                    self.graph.add((subject, predicate, self.iri(item)))
                else:
                    self.graph.add((subject, predicate, self.literal(item, slot)))
        return subject

    def write(self, data):
        for key, cls in (("things", "NamedThing"), ("documents", "NoteDocument"), ("sources", "Entity")):
            for obj in data.get(key, []):
                self.node(obj, cls)
        return self.graph


def to_rdf(data):
    return RdfWriter(SchemaView(str(SCHEMA))).write(data)


def class_hierarchy():
    """rdfs:subClassOf axioms from the schema's is_a links, so that sh:class sees subclasses."""
    view = SchemaView(str(SCHEMA))
    writer = RdfWriter(view)
    graph = Graph()
    for name in view.all_classes():
        parent = view.get_class(name).is_a
        if parent:
            graph.add((
                writer.iri(view.get_uri(name, expand=False)),
                RDFS.subClassOf,
                writer.iri(view.get_uri(parent, expand=False)),
            ))
    return graph


DCT = Namespace("http://purl.org/dc/terms/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
ELI = Namespace("http://data.europa.eu/eli/ontology#")
M8G = Namespace("http://data.europa.eu/m8g/")
CPSV = Namespace("http://purl.org/vocab/cpsv#")
ORG = Namespace("http://www.w3.org/ns/org#")
STANDARD_SHAPES = VAULT / "ontology" / "shapes"
ALIGNMENT = [
    (ELI.LegalResourceSubdivision, RDFS.subClassOf, ELI.LegalResource),
    (ELI.LegalResource, RDFS.subClassOf, M8G.ReferenceFramework),
    (M8G.PublicOrganisation, RDFS.subClassOf, ORG.Organization),
]
DESCRIBED = {CPSV.PublicService, CPSV.Rule, M8G.Criterion, M8G.Constraint, M8G.Participation, M8G.PublicOrganisation,
             M8G.Channel, M8G.Output, M8G.LifeEvent, M8G.BusinessEvent, M8G.EvidenceType, M8G.InformationConcept}
DEVIATIONS = {(M8G.Participation, M8G.hasParticipant, SH.MinCountConstraintComponent)}


def profile(graph):
    """The graph as the standards expect it.

    dct:title and dct:description come from the name and the definition, names and definitions carry the language tag ko, public organisations get the jurisdiction in ontology/release.yaml as dct:spatial, and the values of the schema's enumerations become SKOS concepts in concept schemes.
    Statute units also get the types that the alignment gives them, eli:LegalResource and cccev:ReferenceFramework, and public organisations get org:Organization, so that the export validates without the alignment.
    """
    jurisdiction = URIRef(yaml.safe_load((VAULT / "ontology" / "release.yaml").read_text(encoding="utf-8"))["jurisdiction"])
    tagged = language_tagged()
    out = Graph()
    for prefix, namespace in graph.namespaces():
        out.bind(prefix, namespace)
    out += graph

    hierarchy = class_hierarchy()
    for triple in ALIGNMENT:
        hierarchy.add(triple)

    def lineage(cls):
        found, queue = set(), [cls]
        while queue:
            item = queue.pop()
            if item not in found:
                found.add(item)
                queue += list(hierarchy.objects(item, RDFS.subClassOf))
        return found

    tagged = {(cls, predicate) for cls in set(graph.objects(None, RDF.type)) for ancestor in lineage(cls)
              for anc, predicate in tagged if anc == ancestor}

    def text(subject, cls, predicate, value):
        return Literal(str(value), lang="ko") if (cls, predicate) in tagged else Literal(str(value))

    for subject, cls in graph.subject_objects(RDF.type):
        if cls in DESCRIBED:
            for label in graph.objects(subject, SKOS.prefLabel):
                out.add((subject, DCT.title, text(subject, cls, DCT.title, label)))
            for definition in graph.objects(subject, SKOS.definition):
                out.add((subject, DCT.description, text(subject, cls, DCT.description, definition)))
            for predicate in (SKOS.prefLabel, SKOS.altLabel, SKOS.definition):
                if (cls, predicate) in tagged:
                    for value in list(graph.objects(subject, predicate)):
                        out.remove((subject, predicate, value))
                        out.add((subject, predicate, Literal(str(value), lang="ko")))
        if cls == M8G.PublicOrganisation:
            out.add((subject, DCT.spatial, jurisdiction))
            out.add((jurisdiction, RDF.type, DCT.Location))
        for ancestor in lineage(cls) - {cls}:
            if any(ancestor == parent for _, _, parent in ALIGNMENT):
                out.add((subject, RDF.type, ancestor))
    view = SchemaView(str(SCHEMA))
    writer = RdfWriter(view)
    for name, enum in view.all_enums().items():
        values = {k: v for k, v in enum.permissible_values.items() if v.meaning}
        if not values:
            continue
        scheme = writer.iri(f"{PREFIX}:" + re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower())
        out.add((scheme, RDF.type, SKOS.ConceptScheme))
        out.add((scheme, SKOS.prefLabel, Literal(enum.description, lang="ko")))
        for key, permissible in values.items():
            concept = writer.iri(permissible.meaning)
            out.add((concept, RDF.type, SKOS.Concept))
            out.add((concept, SKOS.inScheme, scheme))
            out.add((concept, SKOS.notation, Literal(key)))
            out.add((concept, SKOS.prefLabel, Literal(permissible.description, lang="ko")))
    return out


def language_tagged():
    """(class, property) pairs whose values the official shapes require as rdf:langString."""
    found = set()
    for path in STANDARD_SHAPES.glob("*.ttl"):
        shapes = Graph().parse(path)
        for shape, cls in shapes.subject_objects(SH.targetClass):
            for prop in shapes.objects(shape, SH.property):
                if (prop, SH.datatype, RDF.langString) in shapes:
                    found.add((cls, shapes.value(prop, SH.path)))
    return found


def standard_problems(graph):
    """Violations of the official CPSV-AP and CCCEV shapes in ontology/shapes, except the deviations the schema documents."""
    ontology = class_hierarchy()
    for triple in ALIGNMENT:
        ontology.add(triple)
    found = []
    for path in sorted(STANDARD_SHAPES.glob("*.ttl")):
        _, report, _ = shacl_validate(graph, shacl_graph=Graph().parse(path), ont_graph=ontology, inference="none")
        for result in report.subjects(SH.resultSeverity, SH.Violation):
            focus, predicate = report.value(result, SH.focusNode), report.value(result, SH.resultPath)
            component = report.value(result, SH.sourceConstraintComponent)
            if any((focus, RDF.type, cls) in graph and (predicate, component) == (prop, kind) for cls, prop, kind in DEVIATIONS):
                continue
            found.append(f"{path.name}: {graph.qname(focus) if isinstance(focus, URIRef) else focus} "
                         f"{graph.qname(predicate) if isinstance(predicate, URIRef) else predicate}: {report.value(result, SH.resultMessage)}")
    return found


def check(root):
    vault = Vault(root)
    data = vault.container()
    problems = list(vault.errors)
    if not problems:
        report = validate(data, str(SCHEMA), "Container")
        problems += [f"linkml: {r.message}" for r in report.results]
    graph = None
    if not problems:
        graph = to_rdf(data)
        conforms, _, text = shacl_validate(
            graph, shacl_graph=shapes_graph(), ont_graph=class_hierarchy(), inference="none"
        )
        if not conforms:
            problems.append(f"shacl:\n{text}")
    if not problems:
        graph = profile(graph)
        problems += standard_problems(graph)
    return problems, graph


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    args = sys.argv[1:]
    if args[:1] == ["check"] and len(args) <= 2:
        root, out = (Path(args[1]) if len(args) == 2 else VAULT), None
    elif args[:1] == ["export"] and len(args) in (2, 3):
        root, out = (Path(args[1]) if len(args) == 3 else VAULT), args[-1]
    else:
        sys.exit(__doc__)
    problems, graph = check(root)
    for problem in problems:
        print(problem)
    if problems:
        sys.exit(1)
    if out:
        graph.serialize(destination=out, format="turtle")
    print(f"ok: {len(graph)} triples")


if __name__ == "__main__":
    main()
