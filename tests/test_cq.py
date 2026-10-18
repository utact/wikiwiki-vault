"""Tests for scripts/cq.py: the scope of BIND and FILTER in queries, and the citations of expected answers."""

import cq as C

PREFIX = "PREFIX employment: <https://w3id.org/kr-employment/>\n"


class FakeResolver(C.Resolver):
    """A resolver over a fixed set of notes and blocks, without an RDF graph."""

    def __init__(self, notes, blocks):
        self.notes = {name: (None, None, {"identifier": identifier}) for name, identifier in notes.items()}
        self.blocks = set(blocks)

    def iri(self, identifier):
        return identifier

    def exists(self, identifier):
        return identifier in self.blocks


def test_bind_of_an_outer_variable_is_unscoped():
    query = PREFIX + """SELECT ?item WHERE {
      ?rule employment:variable employment:base-daily-wage .
      { BIND(?rule AS ?item) } UNION { ?rule employment:requiredInput ?item }
    }"""
    assert C.unscoped(query) == ["rule"]


def test_bind_inside_its_group_is_scoped():
    query = PREFIX + """SELECT ?item WHERE {
      { ?rule employment:variable employment:base-daily-wage . BIND(?rule AS ?item) }
      UNION
      { BIND(employment:separation-before-2028-01-01 AS ?item) }
    }"""
    assert C.unscoped(query) == []


def test_filter_of_an_outer_variable_is_unscoped():
    query = PREFIX + """SELECT ?item WHERE {
      ?rule employment:variable ?concept .
      { ?item employment:requiredInput ?input . FILTER(?concept != ?input) }
    }"""
    assert C.unscoped(query) == ["concept"]


def test_bare_article_after_an_addendum_continues_it():
    resolver = FakeResolver({"고용보험법 부칙 제21473호": "law-001761-sup-20260317-21473", "고용보험법 제3조": "law-001761-art-3"},
                            ["law-001761-sup-20260317-21473-a1", "law-001761-sup-20260317-21473-a3"])
    found = resolver.citations("- 종전의 규정 (법 부칙(제21473호) 제1조 본문, 제3조)")
    assert found == [("고용보험법 부칙 제21473호 제1조", "law-001761-sup-20260317-21473-a1"),
                     ("고용보험법 부칙 제21473호 제3조", "law-001761-sup-20260317-21473-a3")]


def test_law_prefix_ends_the_addendum():
    resolver = FakeResolver({"고용보험법 부칙 제21473호": "law-001761-sup-20260317-21473", "고용보험법 제45조": "law-001761-art-45"},
                            ["law-001761-sup-20260317-21473-a3", "law-001761-art-45-p1"])
    found = resolver.citations("- 평균임금으로 산정 (법 부칙(제21473호) 제3조, 법 제45조제1항)")
    assert found == [("고용보험법 부칙 제21473호 제3조", "law-001761-sup-20260317-21473-a3"),
                     ("고용보험법 제45조제1항", "law-001761-art-45-p1")]
