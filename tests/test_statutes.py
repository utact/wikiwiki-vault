"""Tests for scripts/statutes.py: references, delegations, 부칙 blocks and block hashes, on a synthetic law family."""

import lawlib as L
import statutes as S

EFFECTIVE = "20260101"


def article(number, title, paragraphs=(), text=None):
    """An eflaw 조문단위 row: paragraphs are (항내용, [호내용]) pairs, or text alone for an article without 항."""
    row = {"조문여부": "조문", "조문번호": str(number), "조문내용": f"제{number}조({title})" + (f" {text}" if text else "")}
    if paragraphs:
        row["항"] = [
            {"항번호": chr(0x2460 + index), "항내용": f"{chr(0x2460 + index)} {content}",
             "호": [{"호번호": f"{n}.", "호내용": f"{n}. {item}"} for n, item in enumerate(items, 1)]}
            for index, (content, items) in enumerate(paragraphs)
        ]
    return row


class FakeLaw(S.Law):
    """A law with one stored version built from rows, without raw notes or cache."""

    def __init__(self, name, articles, addenda=()):
        self.name = name
        self.versions = {EFFECTIVE: {
            "기본정보": {"시행일자": EFFECTIVE, "법종구분": {"법종구분코드": "A0002"}},
            "조문": {"조문단위": list(articles)},
            "부칙": {"부칙단위": [{"부칙공포일자": "20251201", "부칙공포번호": "1", "부칙내용": list(lines)} for lines in addenda]},
        }}
        row = {"법령ID": "000001", "시행일자": EFFECTIVE, "공포일자": "20251201", "공포번호": "1", "법령일련번호": "1", "법령명한글": name}
        self.rows, self.notes, self.chosen = [row], {}, {EFFECTIVE: row}
        self.current, self.scheduled, self.law_id, self.kind_code = EFFECTIVE, [], "000001", "A0002"
        self.published, self.aliases = {EFFECTIVE: {"20251201": row}}, {}
        self._units, self._texts, self._rows = {}, {}, {}


DEFINITIONS = {
    "조문여부": "조문", "조문번호": "2", "조문내용": "제2조(정의) 이 법에서 사용하는 용어의 뜻은 다음과 같다.",
    "항": [{"항번호": "", "호": [{"호번호": "1.", "호내용": "1. \"보수\"란 대통령령으로 정하는 금품을 뺀 금액을 말한다. 다만, 고용노동부장관이 고시하는 금품은 보수로 본다."}]}],
}
ACT = [
    DEFINITIONS,
    article(10, "적용", [("적용 범위는 대통령령으로 정하는 바에 따른다.", []), ("제1항의 적용 제외는 고용노동부령으로 정한다.", [])]),
    article(11, "신고", [("신고한다.", []), ("변경을 신고한다.", []), ("말소를 신고한다.", [])]),
    article(12, "급여", [("급여를 지급한다. 다만, 고용노동부장관이 정하는 경우는 제외한다.", [])]),
    article(13, "기초일액", [("기초일액을 산정한다. 이 경우 소정근로시간은 고용노동부령으로 정하는 방법에 따라 산정한다.", [])]),
    article(14, "요건", [("다음 각 호의 요건을 갖추어야 한다.", ["대통령령으로 정하는 기간 이상일 것", "근로의 의사가 있을 것"])]),
    article(56, "지급", text="지급한다."),
    article(57, "제한", text="제한한다."),
    article(58, "반환", text="반환한다."),
]


def family(decree_articles=(), rule_articles=(), act_addenda=()):
    laws = {
        "시험법": FakeLaw("시험법", ACT, act_addenda),
        "시험법 시행령": FakeLaw("시험법 시행령", decree_articles),
        "시험법 시행규칙": FakeLaw("시험법 시행규칙", rule_articles),
    }
    statutes = object.__new__(S.Statutes)
    statutes.laws, statutes.review, statutes.as_of = laws, [], EFFECTIVE
    S.CITED.clear()
    S.VERSIONS.clear()
    return statutes


def refs(statutes, law, key):
    return statutes.references(S.Unit(statutes.laws[law], key))


def is_delegation(statutes, law, ref):
    target = S.Unit(statutes.laws[ref.law], ref.key)
    lines = {s: t for s, t, _ in S.unit_lines(target, EFFECTIVE)}
    return S.delegated(ref, lines, bool(ref.block and ref.block in lines), statutes.laws[law])


def test_same_article_is_the_article_cited_just_before():
    statutes = family([article(5, "범위", [("법 제11조제1항에 따른 신고와 같은 조 제2항에 따른 신고를 한다.", [])])])
    found = [(r.law, r.key, r.block) for r in refs(statutes, "시험법 시행령", "art-5")]
    assert found == [("시험법", "art-11", "p1"), ("시험법", "art-11", "p2")]


def test_continued_paragraphs_belong_to_the_law_before_them():
    statutes = family([article(5, "범위", [("법 제11조제2항ㆍ제3항에 따라 신고한다.", [])])])
    found = [(r.law, r.key, r.block) for r in refs(statutes, "시험법 시행령", "art-5")]
    assert found == [("시험법", "art-11", "p2"), ("시험법", "art-11", "p3")]


def test_range_cites_every_article_in_it():
    statutes = family([article(5, "범위", [("법 제56조부터 제58조까지의 규정에 따른다.", [])])])
    assert {r.key for r in refs(statutes, "시험법 시행령", "art-5")} == {"art-56", "art-57", "art-58"}


def test_title_line_is_not_a_reference():
    statutes = family([article(5, "법 제10조의 적용", [("이 영은 법 제11조제1항에 따른다.", [])])])
    assert [(r.key, r.block) for r in refs(statutes, "시험법 시행령", "art-5")] == [("art-11", "p1")]


def test_addendum_headings_and_amendments_of_other_laws_are_skipped():
    addendum = [
        "부칙 <제1호,2025.12.1>",
        "제1조(시행일) 이 법은 2026년 1월 1일부터 시행한다. 다만, 제11조제2항ㆍ제3항의 개정규정은 공포한 날부터 시행한다.",
        "제2조(다른 법률의 개정) 다른법 일부를 다음과 같이 개정한다. 제57조 중 \"보수\"를 \"임금\"으로 한다.",
    ]
    statutes = family(act_addenda=[addendum])
    found = refs(statutes, "시험법", "sup-20251201-1")
    assert [(r.key, r.block, r.amended) for r in found] == [("art-11", "p2", "20251201"), ("art-11", "p3", "20251201")]


def test_amended_provision_after_a_part_word():
    addendum = ["부칙 <제1호,2025.12.1>", "제1조(시행일) 이 법은 공포한 날부터 시행한다. 다만, 제12조제1항 단서의 개정규정은 2027년 1월 1일부터 시행한다."]
    statutes = family(act_addenda=[addendum])
    assert [(r.key, r.amended) for r in refs(statutes, "시험법", "sup-20251201-1")] == [("art-12", "20251201")]


def test_addendum_paragraphs_get_their_own_blocks():
    lines = S.addendum_lines("부칙 <제1호,2025.12.1>\n제2조(적용례) ① 첫째 항이다.\n② 둘째 항이다.")
    assert [s for s, _ in lines] == [None, "a2", "a2-p1", "a2-p2"]
    assert dict(lines)["a2"] == "제2조(적용례)"


def test_delegation_from_the_cited_paragraph():
    statutes = family([article(5, "범위", [("법 제10조제1항에 따라 적용 범위를 정한다.", [])])])
    [ref] = refs(statutes, "시험법 시행령", "art-5")
    assert ref.delegation and is_delegation(statutes, "시험법 시행령", ref)


def test_delegation_to_another_kind_of_law_does_not_count():
    statutes = family([article(5, "범위", [("법 제10조제2항에 따라 적용 제외를 정한다.", [])])])
    [ref] = refs(statutes, "시험법 시행령", "art-5")
    assert not is_delegation(statutes, "시험법 시행령", ref)


def test_delegation_in_a_child_item_does_not_count_for_the_paragraph():
    statutes = family([article(5, "범위", [("법 제14조제1항에 따라 요건을 확인한다.", [])])])
    [ref] = refs(statutes, "시험법 시행령", "art-5")
    assert not is_delegation(statutes, "시험법 시행령", ref)


def test_reference_in_parentheses_is_not_a_delegation():
    statutes = family([article(5, "범위", [("본인의 질병(법 제10조제1항에 따라 정한 경우는 제외한다)을 말한다.", [])])])
    [ref] = refs(statutes, "시험법 시행령", "art-5")
    assert not ref.delegation


def test_delegation_is_read_in_the_part_named():
    statutes = family(
        [article(5, "보수", [("법 제2조제1호 단서에 따라 고시하는 금품을 정한다.", [])])],
        [article(7, "소정근로시간", [("법 제13조제1항 후단에 따른 소정근로시간을 산정한다.", [])])],
    )
    [decree] = refs(statutes, "시험법 시행령", "art-5")
    [rule] = refs(statutes, "시험법 시행규칙", "art-7")
    assert decree.part == "단서" and not is_delegation(statutes, "시험법 시행령", decree)
    assert rule.part == "후단" and is_delegation(statutes, "시험법 시행규칙", rule)


def test_parts_of_a_provision():
    text = "지급한다. 다만, 제외한다."
    assert S.part_of(text, "본문") == "지급한다. "
    assert S.part_of(text, "단서") == "다만, 제외한다."
    assert S.part_of("산정한다. 이 경우 정한다.", "후단") == "이 경우 정한다."


def test_block_hash_covers_its_children():
    statutes = family()
    unit = S.Unit(statutes.laws["시험법"], "art-14")
    versions = S.unit_versions(unit.law, unit.key)
    hashes = S.block_hashes(unit, versions)
    lines = [t for s, t, _ in S.unit_lines(unit, EFFECTIVE) if s and s.startswith("p1")]
    assert hashes["v20260101-p1"] == L.sha256(L.version_text("\n".join(lines)))
    assert hashes["v20260101-p1-i1"] != hashes["v20260101-p1"]
