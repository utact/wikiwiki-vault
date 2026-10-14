"""Render ontology/schema.md from ontology/schema.yaml.

Usage:
    uv run python -X utf8 scripts/schema_doc.py           # write ontology/schema.md
    uv run python -X utf8 scripts/schema_doc.py --check   # exit 1 if ontology/schema.md is stale
"""

import sys
from pathlib import Path

from linkml_runtime.utils.schemaview import OrderedBy, SchemaView

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "ontology" / "schema.yaml"
DOC = ROOT / "ontology" / "schema.md"

NOTE_ROOT = "NamedThing"
DMN_CLASSES = ["DecisionTable", "InputClause", "OutputClause", "DecisionRule"]
RAW_CLASS = "Entity"
SYNTHETIC_CLASSES = ["Person", "Evidence"]
TYPED_RANGES = {"date", "datetime", "decimal", "boolean", "uri"}

STANDARDS = {
    "cpsv": "CPSV-AP 3.2.0 (Core Public Service Vocabulary Application Profile)",
    "cv": "CPSV-AP 3.2.0, CCCEV 2.1.0 (Core Criterion and Core Evidence Vocabulary)",
    "eli": "ELI 1.4 (European Legislation Identifier)",
    "skos": "SKOS (Simple Knowledge Organization System)",
    "dcat": "DCAT (Data Catalog Vocabulary)",
    "foaf": "FOAF (Friend of a Friend)",
    "prov": "PROV-O (PROV Ontology)",
    "dmn": "DMN 1.3 (Decision Model and Notation)",
    "dct": "DCMI Metadata Terms",
    "employment": "이 ontology",
    "org": "W3C Organization Ontology",
    "rdf": "RDF",
    "rdfs": "RDF Schema",
    "schema": "Schema.org",
    "sh": "SHACL (Shapes Constraint Language)",
    "spdx": "SPDX",
}


def code(text):
    return f"`{text}`"


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


class Renderer:
    def __init__(self, view):
        self.view = view
        self.classes = list(view.all_classes(ordered_by=OrderedBy.PRESERVE))
        self.common = list(view.class_slots(NOTE_ROOT))

    def uri(self, element):
        return self.view.get_uri(element, expand=False)

    def prefix(self, element):
        return self.uri(element).split(":", 1)[0]

    def is_note_class(self, name):
        return name != NOTE_ROOT and NOTE_ROOT in self.view.class_ancestors(name)

    def is_object(self, slot):
        rng = slot.range
        return (
            rng in self.view.all_classes()
            and self.view.get_identifier_slot(rng) is not None
            and not slot.inlined
        )

    def value_text(self, slot):
        text = slot.description or ""
        if slot.range in self.view.all_enums():
            enum = self.view.get_enum(slot.range)
            values = ", ".join(
                f"{code(name)}({value.description})" for name, value in enum.permissible_values.items()
            )
            return f"{text}: {values}"
        if slot.range in TYPED_RANGES:
            return f"{text} ({slot.range})"
        if slot.range in self.view.all_classes():
            return f"{text} ({code(slot.range)})"
        return text

    def target_text(self, slot):
        return f"{slot.description} ({code(slot.range)})"

    def own_slots(self, class_name):
        cls = self.view.get_class(class_name)
        names = [s for s in cls.slots]
        return [self.view.induced_slot(s, class_name) for s in names if s not in self.common]

    def sorted_slots(self, slots):
        return sorted(slots, key=lambda s: (not s.required, s.name))

    def slot_rows(self, slots, describe):
        return [
            [code(s.name), code(self.uri(s)), "예" if s.required else "아니요", describe(s)] for s in slots
        ]

    def slot_comments(self, slots):
        lines = []
        for slot in slots:
            for comment in self.view.get_slot(slot.name).comments:
                lines.append(f"- {code(slot.name)}: {comment}")
        return lines

    def descendants(self, class_name):
        return [
            c for c in self.classes
            if c != class_name and class_name in self.view.class_ancestors(c)
            and not self.view.get_class(c).abstract
        ]

    def class_section(self, title, intro, kind):
        parts = [f"## {title}", intro]
        for name in self.classes:
            if not (self.is_note_class(name)):
                continue
            slots = [s for s in self.own_slots(name) if self.is_object(s) == (kind == "object")]
            if not slots:
                continue
            parts.append(f"### {name}")
            if self.view.get_class(name).abstract:
                parts.append(f"{', '.join(code(c) for c in self.descendants(name))}에 쓴다.")
            slots = self.sorted_slots(slots)
            describe = self.target_text if kind == "object" else self.value_text
            header = ["이름", "표준", "필수", "대상" if kind == "object" else "값"]
            parts.append(table(header, self.slot_rows(slots, describe)))
            comments = self.slot_comments(slots)
            if comments:
                parts.append("\n".join(comments))
        return parts

    def fixed_section(self, title, intro, class_names, ordered):
        parts = [f"## {title}", intro]
        for name in class_names:
            cls = self.view.get_class(name)
            slots = [self.view.induced_slot(s, name) for s in cls.slots]
            if not ordered:
                slots = self.sorted_slots(slots)
            if len(class_names) > 1:
                parts.append(f"### {name}")
            parts.append(f"{code(name)}({code(self.uri(name))}): {cls.description}")
            if cls.comments:
                parts.append("\n".join(f"- {c}" for c in cls.comments))
            describe = lambda s: self.target_text(s) if self.is_object(s) else self.value_text(s)
            parts.append(table(["이름", "표준", "필수", "값"], self.slot_rows(slots, describe)))
            comments = self.slot_comments(slots)
            if comments:
                parts.append("\n".join(comments))
        return parts

    def standards_section(self):
        class_prefixes = []
        for name in self.classes:
            if self.view.get_class(name).class_uri:
                p = self.prefix(name)
                if p not in class_prefixes:
                    class_prefixes.append(p)
        used = set()
        for slot in self.view.all_slots().values():
            if slot.slot_uri:
                used.add(slot.slot_uri.split(":", 1)[0])
        for enum in self.view.all_enums().values():
            for value in enum.permissible_values.values():
                if value.meaning:
                    used.add(value.meaning.split(":", 1)[0])
        property_prefixes = sorted(used - set(class_prefixes))
        prefixes = self.view.schema.prefixes
        rows = [
            [code(p), STANDARDS[p], code(prefixes[p].prefix_reference)]
            for p in class_prefixes + property_prefixes
        ]
        return [
            "## Standards",
            "class를 정의하는 표준은 Classes 표의 순서로, property만 쓰는 표준은 접두어의 알파벳순으로 둔다.",
            table(["접두어", "표준", "이름공간"], rows),
        ]

    def classes_section(self):
        rows = []
        notes = []
        abstract = []
        for name in self.classes:
            if not self.is_note_class(name):
                continue
            cls = self.view.get_class(name)
            if cls.abstract:
                abstract.append(f"- {code(name)}({code(self.uri(name))}): {cls.description}")
                continue
            examples = cls.annotations.get("examples")
            rows.append([code(name), code(self.uri(name)), cls.description, examples.value if examples else ""])
            notes += [f"- {code(name)}: {c}" for c in cls.comments]
        parts = [
            "## Classes",
            "`wiki/` 노트의 `type`에 쓰는 class다. CPSV-AP, CCCEV, ELI, SKOS, DCAT 순서로 묶는다.",
            table(["이름", "표준", "뜻", "예"], rows),
        ]
        if notes:
            parts.append("\n".join(notes))
        parts.append("아래 추상 class는 `type`에 쓰지 않고, 공통 property를 묶는 데만 쓴다.")
        parts.append("\n".join(abstract))
        return parts

    def common_section(self):
        slots = [self.view.induced_slot(s, NOTE_ROOT) for s in self.common]
        note_slots = [s.name for s in slots if "describes" in self.view.get_slot(s.name).annotations]
        describe = lambda s: self.target_text(s) if self.is_object(s) else self.value_text(s)
        parts = [
            "## Common properties",
            "모든 `wiki/` 노트에 쓰는 property다. 내용, 근거, 적용 기간, 편집 상태의 순서로 둔다. frontmatter에도 이 순서로 적고, class별 property는 `definition`과 `source` 사이에 둔다.",
            table(["이름", "표준", "필수", "값"], self.slot_rows(slots, describe)),
            f"{', '.join(code(n) for n in note_slots)}는 instance가 아니라 노트를 설명한다.",
        ]
        comments = self.slot_comments(slots)
        if comments:
            parts.append("\n".join(comments))
        return parts

    def render(self):
        schema = self.view.schema
        parts = [
            "# Ontology schema",
            schema.description,
            "이 문서는 `ontology/schema.yaml`에서 `scripts/schema_doc.py`로 생성한다. 이 문서를 직접 고치지 않는다.",
            "\n".join(f"- {c}" for c in schema.comments),
        ]
        parts += self.standards_section()
        parts += self.classes_section()
        parts += self.common_section()
        parts += self.class_section(
            "Object properties",
            "다른 노트를 wikilink로 가리키는 class별 property다. 관계마다 이 표의 방향으로만 적는다. 표 안에서는 필수 property를 먼저, 나머지를 알파벳순으로 둔다.",
            "object",
        )
        parts += self.class_section(
            "Datatype properties",
            "wikilink가 아닌 값을 담는 class별 property다. 배치 기준은 Object properties와 같다.",
            "datatype",
        )
        parts += self.fixed_section(
            "Decision tables",
            "Rule의 `decisionTable` 안에 inline으로 적는 DMN 결정표 구조다. 배치 기준은 Object properties와 같다.",
            DMN_CLASSES,
            ordered=False,
        )
        parts += self.fixed_section(
            "Raw source properties",
            "`raw/` 노트의 frontmatter에 이 표의 순서로 적는 property다. 원문은 wiki보다 먼저 존재하므로 wikilink를 쓰지 않는다.",
            [RAW_CLASS],
            ordered=True,
        )
        parts += self.fixed_section(
            "Synthetic data",
            "`synthetic/` 노트에만 쓰는 class와 property다. frontmatter에 이 표의 순서로 적는다.",
            SYNTHETIC_CLASSES,
            ordered=True,
        )
        return "\n\n".join(p for p in parts if p) + "\n"


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    text = Renderer(SchemaView(str(SCHEMA))).render()
    if "--check" in sys.argv:
        if DOC.read_text(encoding="utf-8") != text:
            sys.exit(f"{DOC.relative_to(ROOT)} is stale. Run scripts/schema_doc.py.")
        return
    DOC.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
