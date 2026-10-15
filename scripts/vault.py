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
WIKILINK = re.compile(r"^\[\[([^\]|#]+)(?:#\^([a-z0-9-]+))?(?:\|[^\]]*)?\]\]$")
IDENTIFIER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class StringLoader(yaml.SafeLoader):
    """Keep every scalar as a string, as Obsidian writes them."""


StringLoader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in resolvers if tag == "tag:yaml.org,2002:null"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def read_note(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: no frontmatter")
    end = text.index("\n---\n", 4)
    return yaml.load(text[4:end], Loader=StringLoader) or {}


class Vault:
    def __init__(self, root):
        self.root = Path(root)
        self.view = SchemaView(str(SCHEMA))
        self.errors = []
        self.notes = {}
        for folder in ("wiki", "raw"):
            for path in sorted((self.root / folder).rglob("*.md")):
                if path.stem in self.notes:
                    self.errors.append(f"duplicate note name: {path.stem}")
                self.notes[path.stem] = (path, folder, read_note(path))
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

    def resolve(self, value, where, curie=False):
        """Return the identifier a wikilink points to, as a CURIE for uriorcurie slots."""
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
        if match.group(2):
            identifier = f"{identifier}-{match.group(2)}"
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
                resolved = [self.resolve(v, where, curie=slot.range == "uriorcurie") for v in values]
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
