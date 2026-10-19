"""Tests for scripts/lint.py: the fixture vault is clean, and each planted defect is reported."""

import shutil
from pathlib import Path

import pytest

import lint

FIXTURES = Path(__file__).parent / "fixtures" / "vault"
CAP = "wiki/Constraint/기초일액 상한.md"
RULE = "wiki/Rule/최저기초일액 산정.md"
TABLE = "wiki/Rule/소정급여일수 산정.md"
ARTICLE = "wiki/LegalResourceSubdivision/고용보험법 제45조.md"
BASE_RULE = "wiki/Rule/기초일액 산정.md"
DEADLINE = "wiki/Constraint/피보험자격 상실 신고 기한.md"
NOTICE_RAW = "raw/law/2026년 적용 최저임금 고시/2026년 적용 최저임금 고시 20260101-2100000262710 20261015T1337.md"


def run(tmp_path, *edits, schema=False):
    """Lint a copy of the fixture vault after replacing text in its files, or writing new ones when old is None."""
    root = tmp_path / "vault"
    shutil.copytree(FIXTURES, root)
    for path, old, new in edits:
        target = root / path
        if old is None:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new, encoding="utf-8", newline="\n")
            continue
        text = target.read_text(encoding="utf-8")
        assert old in text, (path, old)
        target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    return lint.Linter(root).run(repository=False, schema=schema)


def test_fixture_vault_is_clean(tmp_path):
    assert run(tmp_path, schema=True) == []


NOTE = """---
type: InformationConcept
identifier: test-concept
definition: 시험 개념
typeRef: number
source:
- '[[고용보험법 제45조#^v20210701-p1]]'
status: draft
---

{body}

[^1]: [[고용보험법 제45조#^v20210701-p1|고용보험법 제45조제1항]]
"""

DEFECTS = {
    "broken link": ((CAP, "## 근거", "[[없는 노트]]\n\n## 근거"),),
    "undeclared block": ((CAP, "[^2]: [[고용보험법 시행령 부칙 제35934호#^v20260101-a1|", "[^2]: [[고용보험법 시행령 부칙 제35934호#^v20260101-a9|"),),
    "embedded file not found": ((CAP, "## 근거", "![[없는 그림.gif]]\n\n## 근거"),),
    "outside the graph": (("wiki/InformationConcept/시험 개념.md", None, NOTE.format(body="시험 개념은 구직급여의 산정 기초가 되는 임금일액이다.[^1]")),),
    "source is not a raw note": ((CAP, "source:\n", "source:\n- '[[기초일액]]'\n"),),
    "footnote source missing from source": ((CAP, "source:\n- '[[고용보험법 시행령 제68조#^v20260101-p1]]'\n", "source:\n"),),
    "source no footnote cites": ((CAP, "source:\n", "source:\n- '[[고용보험법 제45조#^v20210701-p1]]'\n"),),
    "sentence without a source": ((CAP, "## 근거", "기초일액에는 상한이 있다.\n\n## 근거"),),
    "quote does not match": ((CAP, "11만3500원을 해당 임금일액으로 한다.”", "11만3500원을 기초일액으로 한다.”"),),
    "quote without a footnote": ((CAP, "해당 임금일액으로 한다.”[^1]", "해당 임금일액으로 한다.” 이 조항이다.[^1]"),),
    "number 114500원 is not in the cited blocks": ((CAP, "기초일액은 11만3500원을", "기초일액은 11만4500원을"),),
    "date 2026-02-01 is not in the cited blocks": ((CAP, "2026-01-01 이후 이직한 사람의 기초일액은", "2026-02-01 이후 이직한 사람의 기초일액은"),),
    "code A0003 is not in the cited sources": (("wiki/Concept/법률.md", "코드 A0002로 나타내는 법령의 종류다", "코드 A0003으로 나타내는 법령의 종류다"),),
    "calculation `8 * 10320` gives 82560": ((RULE, "8만2560원", "8만2570원"),),
    "links no Rule": ((RULE, "[^3]: [[최저기초일액 산정]] 예시 `8 * 10320`", "[^3]: [[2026년 적용 최저임금 고시#^v20260101-t|2026년 적용 최저임금 고시]] 예시 `8 * 10320`"),),
    "is not the citation": ((CAP, "|고용보험법 시행령 제68조제1항]]", "|고용보험법 시행령 제68조]]"),),
    "without an appliesWhen date condition": (("wiki/InformationConcept/기초일액.md", "[^1]: [[고용보험법 제45조#^v20210701-p1|", "[^1]: [[고용보험법 제45조#^v20280101-p1|"),
                            ("wiki/InformationConcept/기초일액.md", "source:\n- '[[고용보험법 제45조#^v20210701-p1]]'", "source:\n- '[[고용보험법 제45조#^v20280101-p1]]'")),
    "unaryTests does not parse": ((CAP, "unaryTests: <= 113500", "unaryTests: << 113500"),),
    "but the concept is number": ((CAP, "unaryTests: <= 113500", "unaryTests: <= date(\"2026-01-01\")"),),
    "uses '상한액', which is not a concept the note links": ((CAP, "unaryTests: <= 113500", "unaryTests: <= 상한액 * 2"),),
    "literalExpression uses '시간당 임금'": ((RULE, "literalExpression: 이직 전 1일 소정근로시간 * 시간 단위 최저임금액", "literalExpression: 이직 전 1일 소정근로시간 * 시간당 임금"),),
    "decision table input 피보험기간 is not in requiredInput": ((TABLE, "requiredInput:\n- '[[이직일 현재 연령]]'\n- '[[피보험기간]]'", "requiredInput:\n- '[[이직일 현재 연령]]'"),),
    "are not the variable": ((TABLE, "  output:\n  - '[[소정급여일수]]'", "  output:\n  - '[[피보험기간]]'"),),
    "rules 1 and 2 overlap": ((TABLE, "'[1..3)'", "'[0..3)'"),),
    "statute note differs from its ledger entry": ((ARTICLE, "급여의 기초가 되는 임금일액)의 법령 노트다", "급여의 기초가 되는 임금일액)의 노트다"),),
    "verified note without a matching ledger entry": ((CAP, "status: draft", "status: verified"),),
    "reviewed note without reviewedBy": ((CAP, "status: draft", "status: reviewed"),),
    "duplicate note name": (("synthetic/기초일액.md", None, "---\ntype: InformationConcept\nidentifier: synthetic-base\nsynthetic: true\n---\n"),),
    "identifier base-daily-wage also in": (("wiki/InformationConcept/시험 개념.md", None, NOTE.format(body="시험 개념은 구직급여의 산정 기초가 되는 임금일액이다.[^1]").replace("test-concept", "base-daily-wage")),),
    "alias 기초일액 is another note's name": (("wiki/InformationConcept/평균임금.md", "definition:", "aliases:\n- 기초일액\ndefinition:"),),
    "links synthetic note": (("synthetic/합성 이직자.md", None, "---\ntype: InformationConcept\nidentifier: synthetic-person\nsynthetic: true\n---\n"),
                             (CAP, "## 근거", "[[합성 이직자]]\n\n## 근거")),
    "embeds synthetic note": (("synthetic/합성 이직자.md", None, "---\ntype: InformationConcept\nidentifier: synthetic-person\nsynthetic: true\n---\n"),
                              (CAP, "## 근거", "![[합성 이직자]]\n\n## 근거")),
    "links synthetic data": ((CAP, "## 근거", "[합성 데이터](../../synthetic/person.md)\n\n## 근거"),),
    "has no citation label": ((CAP, "[^1]: [[고용보험법 시행령 제68조#^v20260101-p1|고용보험법 시행령 제68조제1항]]", "[^1]: [[고용보험법 시행령 제68조#^v20260101-p1]]"),),
    "names the 단서, but the block has no 단서": ((CAP, "|고용보험법 시행령 제68조제1항]]", "|고용보험법 시행령 제68조제1항 단서]]"),),
    "quote statutory text in “ ”": ((CAP, "## 근거", "기초일액은 ‘해당 임금일액’이다.[^1]\n\n## 근거"),),
    "number 114500원 is not in the cited blocks: 2026-01-01 이후 이직한 사람의 기초일액은 [11만4500원]": ((CAP, "기초일액은 11만3500원을", "기초일액은 [11만4500원]을"),),
    "number 113500달러 is not in the cited blocks": ((CAP, "기초일액은 11만3500원을", "기초일액은 11만3500달러를"),),
    "write numbers in Arabic numerals": ((CAP, "## 근거", "상한은 두 번 바뀌었다.[^1]\n\n## 근거"),),
    "question callout line is not a question": ((CAP, "## 근거", "> [!question] 확인\n> 상한은 11만4500원이다.\n\n## 근거"),),
    "outside the dates of its appliesWhen": ((BASE_RULE, "[^2]: [[고용보험법 제45조#^v20210701-p1|", "[^2]: [[고용보험법 제45조#^v20280101-p1|"),
                                             (BASE_RULE, "- '[[고용보험법 제45조#^v20210701-p1]]'", "- '[[고용보험법 제45조#^v20280101-p1]]'")),
    "literalExpression does not parse": ((RULE, "literalExpression: 이직 전 1일 소정근로시간 * 시간 단위 최저임금액", "literalExpression: 이직 전 1일 소정근로시간 *"),),
    "is boolean, but the concept is number": ((RULE, "literalExpression: 이직 전 1일 소정근로시간 * 시간 단위 최저임금액", "literalExpression: 이직 전 1일 소정근로시간 > 시간 단위 최저임금액"),),
    "literalExpression has number 1.5": ((RULE, "literalExpression: 이직 전 1일 소정근로시간 * 시간 단위 최저임금액", "literalExpression: 이직 전 1일 소정근로시간 * 시간 단위 최저임금액 * 1.5"),),
    "unaryTests has number 114500": ((CAP, "unaryTests: <= 113500", "unaryTests: <= 114500"),),
    "definition has date 2026-02-01": ((CAP, "definition: 2026-01-01 이후", "definition: 2026-02-01 이후"),),
    "rule 2 has number 13": ((TABLE, "'[1..3)'", "'[1..13)'"),),
    "uses 9, which is not in the cited blocks": ((RULE, "소정근로시간이 8시간이고", "소정근로시간이 9시간이고"),
                                                 (RULE, "8만2560원", "9만2880원"), (RULE, "예시 `8 * 10320`", "`9 * 10320`")),
    "number 113500원 is not in the cited blocks": ((CAP, "[^1]: [[고용보험법 시행령 제68조#^v20260101-p1|고용보험법 시행령 제68조제1항]]",
                                                   "[^1]: [[고용보험법 시행령 20260918-288717 20261015T1940]]"),),
    "url keeps the credential parameter oc": ((NOTICE_RAW, "ID=2100000262710", "ID=2100000262710&OC=test"),),
    "cite no statute block, quotation or raw note: 상한은 바뀌었다": ((CAP, "## 근거", "상한은 바뀌었다.[^9]\n\n## 근거"),
                                                                 (CAP, "[^3]: [[고용보험법 시행령 부칙", "[^9]: 고용보험법 시행령 제68조제3항\n[^3]: [[고용보험법 시행령 부칙")),
    "cite no statute block, quotation or raw note: 상한은 정해져 있다": ((CAP, "## 근거", "상한은 정해져 있다.[^9]\n\n## 근거"),
                                                                   (CAP, "[^3]: [[고용보험법 시행령 부칙", "[^9]: [[기초일액 산정]]\n[^3]: [[고용보험법 시행령 부칙")),
    "sentence without a source: 기초일액 상한은 11만4500원이다": ((CAP, "## 근거", "> [!note] 기초일액 상한은 11만4500원이다.\n\n## 근거"),),
    "number 114500원 is not in the cited blocks: 2026-01-01 이후 이직한 사람의 기초일액은 [[기초일액|11만4500원]]": (
        (CAP, "기초일액은 11만3500원을", "기초일액은 [[기초일액|11만4500원]]을"),),
    "broken link: [[없는 노트#근거]]": ((CAP, "## 근거", "[[없는 노트#근거]]\n\n## 근거"),),
    "link to a heading the note lacks: [[기초일액#없는 절]]": ((CAP, "## 근거", "[[기초일액#없는 절]]\n\n## 근거"),),
    "links synthetic note [[합성 이직자]]": (("synthetic/합성 이직자.md", None, "---\ntype: InformationConcept\nidentifier: synthetic-person\nsynthetic: true\n---\n"),
                                       (CAP, "## 근거", "[[합성 이직자#요약]]\n\n## 근거")),
    "links synthetic data: ../../synthetic/합성 이직자.md": ((CAP, "## 근거", "[합성](<../../synthetic/합성 이직자.md>)\n\n## 근거"),),
    "undeclared block: [[고용보험법 시행령 제68조#^V20260101-p1]]": ((CAP, "## 근거", "[[고용보험법 시행령 제68조#^V20260101-p1]]\n\n## 근거"),),
    "without an appliesWhen date condition: [[고용보험법 제45조#^v20280101-p1]]": (
        (BASE_RULE, "- '[[2028-01-01 전 이직]]'", "- '[[2026년 시간급 최저임금]]'"),
        (BASE_RULE, "[^2]: [[고용보험법 제45조#^v20210701-p1|", "[^2]: [[고용보험법 제45조#^v20280101-p1|"),
        (BASE_RULE, "- '[[고용보험법 제45조#^v20210701-p1]]'", "- '[[고용보험법 제45조#^v20280101-p1]]'")),
    "outside the dates of its appliesWhen: [[고용보험법 제45조#^v20280101-p1]]": (
        (BASE_RULE, "- '[[2028-01-01 전 이직]]'", "- '[[2028-01-01 전 이직]]'\n- '[[2026-01-01 이후 이직]]'"),
        (BASE_RULE, "[^2]: [[고용보험법 제45조#^v20210701-p1|", "[^2]: [[고용보험법 제45조#^v20280101-p1|"),
        (BASE_RULE, "- '[[고용보험법 제45조#^v20210701-p1]]'", "- '[[고용보험법 제45조#^v20280101-p1]]'")),
    "uses 10500, which is neither in the sentence nor in the cited blocks": (
        (RULE, "시간 단위 최저임금액이 10,320원이면 최저기초일액은 8만2560원이다", "최저기초일액은 8만4000원이다"),
        (RULE, "예시 `8 * 10320`", "예시 `8 * 10500`")),
    "unaryTests has number 15개월/달": ((DEADLINE, 'duration("P1M")', 'duration("P15M")'),),
    "write numbers in Arabic numerals unless the cited block writes them in words: 칠십 세": ((CAP, "## 근거", "칠십 세 이상은 다르다.[^1]\n\n## 근거"),),
    "write numbers in Arabic numerals unless the cited block writes them in words: 두배": ((CAP, "## 근거", "상한은 두배다.[^1]\n\n## 근거"),),
    "write numbers in Arabic numerals unless the cited block writes them in words: 백분의 육십": ((CAP, "## 근거", "비율은 백분의 육십이다.[^1]\n\n## 근거"),),
    "write numbers in Arabic numerals unless the cited block writes them in words: 두 달": ((CAP, "## 근거", "신고는 두 달 안에 한다.[^1]\n\n## 근거"),),
    "write numbers in Arabic numerals unless the cited block writes them in words: 오 년": ((CAP, "## 근거", "보존은 오 년이다.[^1]\n\n## 근거"),),
    "in words: 두 달": ((CAP, "## 근거", "신고는 두 달마다 한다.[^1]\n\n## 근거"),),
    "in words: 오 년": ((CAP, "## 근거", "보존은 오 년마다 한다.[^1]\n\n## 근거"),),
    "in words: 열흘": ((CAP, "## 근거", "신고는 열흘 안에 한다.[^1]\n\n## 근거"),),
    "in words: 두 번": ((CAP, "## 근거", "두 번째 신고다.[^1]\n\n## 근거"),),
    "sentence without a source: 기초일액에는 상한이 없다": ((CAP, "## 근거", "> [!info] 기초일액에는 상한이 없다\n\n## 근거"),),
    "links synthetic data: 합성 이직자.md": (("synthetic/합성 이직자.md", None, "---\ntype: InformationConcept\nidentifier: synthetic-person\nsynthetic: true\n---\n"),
                                        (CAP, "## 근거", "[합성](합성%20이직자.md)\n\n## 근거")),
    "definition: write numbers in Arabic numerals": ((CAP, "definition: 2026-01-01 이후 이직한 사람의 기초일액 상한", "definition: 2026-01-01 이후 이직한 사람의 기초일액 상한으로 두 번 바뀐 금액"),),
}


@pytest.mark.parametrize("expected", list(DEFECTS))
def test_planted_defect_is_reported(tmp_path, expected):
    problems = run(tmp_path, *DEFECTS[expected])
    assert any(expected in p for p in problems), problems


def test_overlapping_statute_versions_are_reported(tmp_path):
    problems = run(tmp_path, (ARTICLE, "  dateNoLongerInForce: '2027-12-31'", "  dateNoLongerInForce: '2028-06-30'"))
    assert any("overlap" in p for p in problems)
    assert all("overlap" in p or "ledger" in p for p in problems), problems


def test_stale_scheduled_heading_is_reported(tmp_path):
    problems = run(tmp_path, (ARTICLE, "## 2028-01-01 시행 (시행예정)", "## 2026-01-01 시행 (시행예정)"))
    assert any("comes into force on or before the reference date" in p for p in problems)


def test_schema_violation_is_reported(tmp_path):
    problems = run(tmp_path, (CAP, "type: Constraint", "type: Limit"), schema=True)
    assert any("unknown type" in p for p in problems)


def test_changed_cited_block_is_reported(tmp_path):
    """A verified note records the hashes of its cited blocks; a later change of a block shows against the statute ledger."""
    import json

    import lawlib as L

    root = tmp_path / "vault"
    shutil.copytree(FIXTURES, root)
    note = root / CAP
    text = note.read_text(encoding="utf-8").replace("status: draft", "status: verified")
    note.write_text(text, encoding="utf-8", newline="\n")
    linter = lint.Linter(root)
    cited = {f"{n.strip()}#^{b}" for _, n, b, _ in lint.LINK.findall(text) if b and linter.notes[n.strip()].statute}
    hashes = {}
    for statute in linter.wiki():
        if statute.statute:
            hashes.update({f"{statute.stem}#^{b}": d for b, d in linter.ledger[statute.meta["identifier"]]["blocks"].items()})
    blocks = {key: hashes[key] for key in cited}
    blocks["고용보험법 시행령 제68조#^v20260101-p1"] = "0" * 64
    entry = {"identifier": "base-daily-wage-cap", "note": L.note_hash(text), "blocks": blocks, "verifier": "test"}
    ledger = root / "ontology" / "verification.jsonl"
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    problems = lint.Linter(root).run(repository=False, schema=False)
    assert problems == ["wiki/Constraint/기초일액 상한.md: cited block 고용보험법 시행령 제68조#^v20260101-p1 changed since verification"]
    del blocks["고용보험법 시행령 부칙 제35934호#^v20260101-a1"]
    with ledger.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    problems = lint.Linter(root).run(repository=False, schema=False)
    assert "wiki/Constraint/기초일액 상한.md: ledger entry lacks the cited block 고용보험법 시행령 부칙 제35934호#^v20260101-a1" in problems


def test_versions_with_one_date_are_reported(tmp_path):
    problems = run(tmp_path, (ARTICLE, "  firstDateEntryInForce: '2028-01-01'", "  firstDateEntryInForce: '2021-07-01'"))
    assert any("two versions with the same date" in p for p in problems)


def test_clean_variants_are_not_reported(tmp_path):
    """Clean notes in forms that lint once misread stay clean.

    Dotted dates and links inside a sentence, table header rows, item labels of a 별표, footnotes that go on over an
    indented line, external links with numbers in their URL, words such as 이사회 and callout titles that are labels.
    """
    table_row = "| 구분 | 금액 |\n| --- | --- |\n| 상한 | 11만3500원[^1] |\n\n## 근거"
    problems = run(
        tmp_path,
        (CAP, "2026-01-01 이후 이직한 사람의 기초일액은", "이직일이 2026. 1. 1. 이후인 사람의 [[기초일액|기초일액(2026. 1. 1. 이후)]]은"),
        (CAP, "## 근거", table_row),
        (TABLE, "|고용보험법 별표 1]]", "|고용보험법 별표 1 제1호]]"),
        (CAP, "[^1]: [[고용보험법 시행령 제68조#^v20260101-p1|고용보험법 시행령 제68조제1항]]",
         "[^1]:\n    [[고용보험법 시행령 제68조#^v20260101-p1|고용보험법 시행령 제68조제1항]]"),
        (CAP, "## 근거", "- [법제처](https://www.law.go.kr/lsInfoP.do?lsiSeq=280525)\n\n## 근거"),
        (CAP, "## 근거", "> [!warning] 출처 불일치\n> 이사회 결의와 무관하게 상한은 11만3500원이다.[^1]\n\n## 근거"),
        (CAP, "## 근거", "근무를 한 시간과 이직을 한 달은 이 시간 동안 따지지 않는다.[^1]\n\n## 근거"),
        (CAP, "## 근거", "> [!note] 2026-01-01 시행 개정\n> 상한은 11만3500원이다.[^1]\n\n> [!question] 2028년 개정 이후\n> 상한이 바뀌는가?\n\n## 근거"),
        (CAP, "## 근거", "[[고용보험법 시행령 부칙 제35934호|부칙 제35934호(2025. 12. 23.)]]에 따라 상한은 11만3500원이다.[^1]\n\n## 근거"),
    )
    assert problems == []


def test_numerals_that_the_block_writes_in_words_pass(tmp_path):
    linter = lint.Linter(FIXTURES)
    note = linter.notes["기초일액 상한"]
    linter.check_numerals(note, "두 번 이상 위반하면 다르다", ["2회 이상 위반하거나 두 번 이상 위반한 경우"], "sentence")
    linter.check_numerals(note, "세 번 위반하면", ["2회 이상"], "sentence")
    assert linter.problems == ["wiki/Constraint/기초일액 상한.md: sentence: write numbers in Arabic numerals unless the cited block writes them in words: 세 번"]


def test_operands_of_a_calculation_carry_no_unit():
    """In "<= 기초일액 * 60 / 100", 60 and 100 state a ratio such as 100분의 60, not an amount in 원."""
    found = lint.feel_numbers("<= 기초일액 * 60 / 100")
    assert [(value, unit) for _, value, _, unit in found] == [(60, "operand"), (100, "operand")]
    assert lint.feel_numbers("<= 113500")[0][3] is None


def test_decision_table_outputs_may_be_expressions(tmp_path):
    """A DMN output entry is a FEEL expression, so a cell may compute its value from the inputs."""
    problems = run(tmp_path, (TABLE, "    - '120'\n  - - < 50\n    - '[1..3)'", "    - 피보험기간 * 120\n  - - < 50\n    - '[1..3)'"))
    assert not any("rule 1 output" in p for p in problems), problems
    problems = run(tmp_path / "bad", (TABLE, "    - '120'\n  - - < 50\n    - '[1..3)'", "    - 근속기간 * 120\n  - - < 50\n    - '[1..3)'"))
    assert any("rule 1 output uses '근속기간'" in p for p in problems), problems


FORM = """---
type: LegalResourceSubdivision
identifier: law-006288-form-6
title: 시험 서식
isPartOf: '[[고용보험법]]'
typeSubdivision: form
number: 별지 제6호서식
status: verified
---

## 2023-07-01 시행 (현행)

```text
  작성방법
───┬──────────────────────
  고용│1. 상실 연월일란에는 다음 날을 적습니다.
  보험│2. 상실사유란에는 구분코드를 함께 적습니다.
  산재│
  보험│
```

^v20230701-t
"""

FORM_CITER = """---
type: Concept
identifier: test-loss-code
definition: 시험 코드
inScheme: '[[법령 종류]]'
source:
- '[[고용보험법 시행규칙 별지 제6호서식#^v20230701-t]]'
status: draft
---

이 코드는 상실사유란에 구분코드와 함께 적는다.[^1]

[^1]: [[고용보험법 시행규칙 별지 제6호서식#^v20230701-t|LABEL]]
"""


@pytest.mark.parametrize("label, problem", [
    ("고용보험법 시행규칙 별지 제6호서식", None),
    ("고용보험법 시행규칙 별지 제6호서식 고용보험·산재보험 작성방법 제2호", None),
    ("고용보험법 시행규칙 별지 제6호서식 국민연금 작성방법 제2호", "names 국민연금, which the form does not contain"),
    ("고용보험법 시행규칙 별지 제6호서식 작성방법", "is not the citation"),
])
def test_form_item_labels(tmp_path, label, problem):
    found = run(tmp_path, ("wiki/LegalResourceSubdivision/고용보험법 시행규칙 별지 제6호서식.md", None, FORM),
                ("wiki/Concept/시험 코드.md", None, FORM_CITER.replace("LABEL", label)))
    labels = [p for p in found if "시험 코드" in p and "footnote label" in p]
    assert labels == [] if problem is None else any(problem in p for p in labels), labels


@pytest.mark.parametrize("sentence, flagged", [
    ("이 두 제한은 기초일액에 적용한다.", "두 제한은"),
    ("이 세 경우는 하나로 모인다.", "세 경우는"),
    ("이 제한은 한 종류의 제한이다.", None),
])
def test_native_numeral_determiners(tmp_path, sentence, flagged):
    original = "2026-01-01 이후 이직한 사람의 기초일액은 11만3500원을 넘을 수 없다.[^1][^2][^3]"
    found = run(tmp_path, (CAP, original, original + "\n\n" + sentence[:-1] + ".[^1]"))
    numerals = [p for p in found if "Arabic numerals" in p]
    assert numerals == [] if flagged is None else any(flagged in p for p in numerals), numerals
