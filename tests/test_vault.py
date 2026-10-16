"""Tests for scripts/vault.py on the fixture vault."""

import shutil
from pathlib import Path

import vault

FIXTURES = Path(__file__).parent / "fixtures" / "vault"


def test_fixtures_conform():
    problems, graph = vault.check(FIXTURES)
    assert problems == []
    assert len(graph) > 0


def test_broken_link_is_reported(tmp_path):
    root = tmp_path / "vault"
    shutil.copytree(FIXTURES, root)
    note = root / "wiki" / "PublicService" / "피보험자격 상실 신고.md"
    text = note.read_text(encoding="utf-8")
    assert "[[고용노동부]]" in text
    note.write_text(text.replace("[[고용노동부]]", "[[고용노동청]]"), encoding="utf-8", newline="\n")
    problems, _ = vault.check(root)
    assert any("broken link: [[고용노동청]]" in p for p in problems)


def test_unknown_raw_publisher_is_reported(tmp_path):
    root = tmp_path / "vault"
    shutil.copytree(FIXTURES, root)
    shutil.rmtree(root / "wiki" / "PublicOrganisation")
    problems, _ = vault.check(root)
    assert any("unknown identifier: ministry-of-government-legislation" in p for p in problems)


def test_official_shapes_report_a_missing_title():
    """CPSV-AP requires dct:title on a PublicService; vault.profile derives it from the note name."""
    problems, graph = vault.check(FIXTURES)
    assert problems == []
    service = next(graph.subjects(vault.RDF.type, vault.CPSV.PublicService))
    assert vault.standard_problems(graph) == []
    graph.remove((service, vault.DCT.title, None))
    assert any("dct:title" in p for p in vault.standard_problems(graph))


def test_links_to_legal_resources_name_works():
    """ELI, CPSV-AP and CCCEV give these properties works as range, so block links name the block, not its version."""
    _, graph = vault.check(FIXTURES)
    works = {vault.ELI.LegalResource, vault.ELI.LegalResourceSubdivision}
    predicates = [vault.ELI.cites, vault.ELI.based_on, vault.CPSV.implements,
                  vault.URIRef("http://data.europa.eu/m8g/isDerivedFrom"), vault.URIRef("http://data.europa.eu/m8g/hasLegalResource")]
    targets = [o for p in predicates for o in graph.objects(None, p)]
    assert targets
    assert all(set(graph.objects(o, vault.RDF.type)) & works for o in targets)
    sources = list(graph.objects(None, vault.DCT.source))
    assert any((s, vault.RDF.type, vault.ELI.LegalExpression) in graph for s in sources)


def test_block_versions_leave_out_act_properties():
    _, graph = vault.check(FIXTURES)
    blocks = [s for s in graph.subjects(vault.RDF.type, vault.ELI.LegalExpression) if "-p" in str(s).rsplit("-v", 1)[-1]]
    assert blocks
    for predicate in (vault.ELI.date_publication, vault.ELI.number, vault.ELI.id_local):
        assert not any(graph.value(s, predicate) for s in blocks)


def test_deviation_covers_only_the_missing_participant():
    _, graph = vault.check(FIXTURES)
    participation = next(graph.subjects(vault.RDF.type, vault.M8G.Participation))
    assert vault.standard_problems(graph) == []
    graph.add((participation, vault.M8G.hasParticipant, vault.Literal("사업주")))
    assert any("hasParticipant" in p for p in vault.standard_problems(graph))


def test_export_validates_without_the_alignment():
    """Statute units carry eli:LegalResource and cccev:ReferenceFramework as types, so the official shapes pass on the file alone."""
    from pyshacl import validate as shacl_validate

    _, graph = vault.check(FIXTURES)
    for path in sorted(vault.STANDARD_SHAPES.glob("*.ttl")):
        conforms, _, text = shacl_validate(graph, shacl_graph=vault.Graph().parse(path), inference="none")
        problems = [line for line in text.splitlines() if "Focus Node" in line]
        participations = set(graph.subjects(vault.RDF.type, vault.M8G.Participation))
        assert all(any(graph.qname(p) in line for p in participations) for line in problems), problems[:3]
