"""Tests for scripts/canvas.py: layout, the schema canvas and answer canvases on the fixture vault."""

from pathlib import Path

import canvas as C
import vault as V

FIXTURES = Path(__file__).parent / "fixtures" / "vault"


def overlaps(nodes):
    """Pairs of non-group nodes whose rectangles intersect."""
    boxes = [n for n in nodes if n["type"] != "group"]
    found = []
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if a["x"] < b["x"] + b["width"] and b["x"] < a["x"] + a["width"] and a["y"] < b["y"] + b["height"] and b["y"] < a["y"] + a["height"]:
                found.append((a["id"], b["id"]))
    return found


def test_layout_orders_columns_along_edges_and_survives_cycles():
    cells = C.layout(["a", "b", "c", "d"], [("a", "b"), ("b", "c"), ("c", "a"), ("a", "d")])
    assert cells["a"][0] < cells["b"][0] < cells["c"][0]
    assert len({cells[k] for k in cells}) == 4


def test_schema_canvas_draws_every_class_and_property():
    data = C.schema_canvas()
    texts = [n["text"] for n in data["nodes"] if n["type"] == "text"]
    for _, names in C.STANDARDS:
        for name in names:
            assert any(t.startswith(f"### {name}\n") for t in texts), name
    ids = {n["id"] for n in data["nodes"]}
    labels = {e["label"] for e in data["edges"]}
    assert {"holdsRequirement", "hasRequirement", "inScheme", "is_a"} <= labels
    assert all(e["fromNode"] in ids and e["toNode"] in ids for e in data["edges"])
    assert overlaps(data["nodes"]) == []


def test_answer_canvas_links_notes_and_their_statute_blocks():
    vault = V.Vault(FIXTURES)
    stems = ["피보험자격 상실 신고", "피보험자격 상실 신고의 사업주 신고 의무", "피보험자격 상실 신고 기한"]
    data = C.answer_canvas(vault, stems, "## 시험")
    files = {n["id"]: n for n in data["nodes"] if n["type"] == "file"}
    labels = {(files[e["fromNode"]]["file"].rsplit("/", 1)[-1], e["label"], files[e["toNode"]]["file"].rsplit("/", 1)[-1]) for e in data["edges"]}
    assert ("피보험자격 상실 신고.md", "hasParticipation", "피보험자격 상실 신고의 사업주 신고 의무.md") in labels
    assert ("피보험자격 상실 신고의 사업주 신고 의무.md", "holdsRequirement", "피보험자격 상실 신고 기한.md") in labels
    blocks = [n for n in files.values() if n.get("subpath")]
    assert blocks and all(n["subpath"].startswith("#^v") for n in blocks)
    assert all((FIXTURES / n["file"]).exists() for n in files.values())
    assert overlaps(data["nodes"]) == []
    sources = [e for e in data["edges"] if e["label"] == "source"]
    assert sources and all(files[e["toNode"]].get("subpath") for e in sources)


def test_answer_canvas_is_deterministic():
    vault = V.Vault(FIXTURES)
    stems = ["피보험자격 상실 신고", "피보험자격 상실 신고 기한"]
    assert C.dump(C.answer_canvas(vault, stems, "x")) == C.dump(C.answer_canvas(vault, stems, "x"))
