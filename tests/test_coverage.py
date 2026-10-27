"""Tests for scripts/coverage.py: the scope of chapters, articles, exclusions and delegations, and the count of cited articles."""

import coverage as C
import statutes as S
from test_statutes import FakeLaw, article


def heading(text):
    return {"조문여부": "전문", "조문번호": "0", "조문내용": text}


ACT = [
    heading("제1장 총칙"),
    article(2, "정의", text="뜻은 다음과 같다."),
    article(3, "목적", text="목적으로 한다."),
    heading("제2장 급여"),
    article(10, "급여", [("급여를 지급한다.", []), ("기준은 대통령령으로 정한다.", [])]),
    article(11, "특례", [("특례는 대통령령으로 정한다.", [])]),
    {"조문여부": "조문", "조문번호": "12", "조문내용": "제12조 삭제 <2020. 1. 1.>"},
]
DECREE = [heading("제1장 총칙"), article(1, "목적", text="목적으로 한다."), article(5, "기준", text="기준을 정한다."), article(6, "특례", text="특례를 정한다.")]
RULE = [article(7, "서식", text="서식을 정한다.")]


def statutes(delegations):
    found = object.__new__(S.Statutes)
    found.laws = {"시험법": FakeLaw("시험법", ACT), "시험법 시행령": FakeLaw("시험법 시행령", DECREE), "시험법 시행규칙": FakeLaw("시험법 시행규칙", RULE)}
    found.review, found.delegations = [], delegations
    return found


DELEGATIONS = {
    ("시험법 시행령", "art-5"): [("시험법", "제10조제2항")],
    ("시험법 시행령", "art-6"): [("시험법", "제11조제1항")],
    ("시험법 시행규칙", "art-7"): [("시험법 시행령", "제5조")],
}


def test_scope_takes_chapters_articles_and_delegations_down_the_family():
    chosen, _ = C.scope(statutes(DELEGATIONS), {"시험법": {"units": ["제2조", "제2장"]}})
    assert chosen == {("시험법", "art-2"), ("시험법", "art-10"), ("시험법", "art-11"),
                      ("시험법 시행령", "art-5"), ("시험법 시행령", "art-6"), ("시험법 시행규칙", "art-7")}


def test_left_out_article_does_not_bring_its_delegations():
    config = {"시험법": {"units": ["제2장"], "exclude": {"제11조": "다른 급여"}}}
    chosen, left_out = C.scope(statutes(DELEGATIONS), config)
    assert ("시험법", "art-11") not in chosen and ("시험법 시행령", "art-6") not in chosen
    assert left_out == {("시험법", "art-11"): "다른 급여"}


def test_deleted_article_is_not_in_scope():
    chosen, _ = C.scope(statutes({}), {"시험법": {"units": ["제2장"]}})
    assert ("시험법", "art-12") not in chosen


def test_report_counts_links_from_notes_but_not_from_statute_notes(tmp_path):
    (tmp_path / "Rule").mkdir()
    (tmp_path / "Rule" / "급여 산정.md").write_text("근거다.[^1]\n\n[^1]: [[시험법 제10조#^v20260101-p2|시험법 제10조제2항]]\n", encoding="utf-8")
    (tmp_path / "LegalResourceSubdivision").mkdir()
    (tmp_path / "LegalResourceSubdivision" / "시험법 제11조.md").write_text("[[시험법 제11조]]\n", encoding="utf-8")
    lines = C.report(statutes({}), {"시험법": {"units": ["제2장"]}}, tmp_path)
    assert lines[:4] == ["시험법: 1/2", "  제2장 급여: 1/2", "    - 제11조", "total: 1/2"]
