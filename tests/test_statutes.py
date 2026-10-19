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


def history_law(name, history, rows, current, notes=()):
    """A law with several stored versions: history maps 시행일자 to (articles, addenda), rows are the promulgations."""
    law = object.__new__(S.Law)
    law.name = name
    law.versions = {d: {"기본정보": {"시행일자": d, "법종구분": {"법종구분코드": "A0002"}}, "조문": {"조문단위": list(arts)},
                        "부칙": {"부칙단위": [{"부칙공포일자": p, "부칙공포번호": n, "부칙내용": list(lines)} for p, n, lines in addenda]}}
                    for d, (arts, addenda) in history.items()}
    law.rows = [{"법령ID": "000002", "법령명한글": name, **row} for row in rows]
    law.chosen = L.choose_versions(law.rows)
    law.current, law.law_id, law.kind_code = current, "000002", "A0002"
    law.scheduled = [d for d in law.chosen if d > current]
    law.notes = {d: L.VAULT / "raw" / f"{name} {d}-{law.chosen[d]['법령일련번호']} 20261016T0000.md" for d in notes}
    law.published = {}
    for row in law.rows:
        law.published.setdefault(row["시행일자"], {})[row["공포일자"]] = row
    law.aliases, law._units, law._texts, law._rows = {}, {}, {}, {}
    return law


def promulgation(effective, published, number, kind="일부개정", serial=None):
    return {"시행일자": effective, "공포일자": published, "공포번호": number, "법령일련번호": serial or number, "제개정구분명": kind}


def test_a_cited_earlier_version_ends_at_the_next_change():
    texts = {"20200101": "가 <개정 2019.12.1>", "20210101": "나 <개정 2020.12.1>", "20260101": "다 <개정 2025.12.1>"}
    history = {d: ([article(5, "시험", text=t)], []) for d, t in texts.items()}
    rows = [promulgation(d, f"{int(d[:4]) - 1}1201", str(i)) for i, d in enumerate(texts, 1)]
    law = history_law("이력법", history, rows, "20260101", notes=["20200101", "20260101"])
    S.CITED.clear()
    S.VERSIONS.clear()
    S.CITED[("이력법", "art-5")] = {"20200101"}
    versions = S.unit_versions(law, "art-5")
    assert [(v["first"], v.get("last")) for v in versions] == [("20200101", "20201231"), ("20260101", None)]
    assert S.CITED.get("review") is None


def test_promulgation_needs_the_tag_or_a_single_enactment():
    article_rows = {"20200101": ([article(5, "시험", text="본문")], [])}
    two = history_law("이력법", article_rows, [promulgation("20200101", "20191201", "1"), promulgation("20200101", "20191215", "2", "타법개정")], "20200101")
    review = []
    assert S.promulgation_of(two, "art-5", {"first": "20200101", "effective": "20200101"}, review) is None
    assert "not one 제정 or 전부개정" in review[0]
    one = history_law("이력법", article_rows, [promulgation("20200101", "20191201", "1", "제정")], "20200101")
    assert S.promulgation_of(one, "art-5", {"first": "20200101", "effective": "20200101"}, [])["공포번호"] == "1"
    tagged = history_law("이력법", {"20200101": ([article(5, "시험", text="본문 <개정 2019.12.15>")], [])},
                         [promulgation("20200101", "20191201", "1"), promulgation("20200101", "20191215", "2")], "20200101")
    assert S.promulgation_of(tagged, "art-5", {"first": "20200101", "effective": "20200101"}, [])["공포번호"] == "2"


def test_same_law_is_the_law_named_just_before():
    statutes = family([article(5, "범위", [("「시험법」 제10조제1항 및 같은 법 제11조제2항에 따른다.", [])]),
                       article(6, "범위", [("「다른법」 제3조 및 같은 법 제11조에 따른다.", [])])])
    assert [(r.law, r.key, r.block) for r in refs(statutes, "시험법 시행령", "art-5")] == [("시험법", "art-10", "p1"), ("시험법", "art-11", "p2")]
    assert refs(statutes, "시험법 시행령", "art-6") == []


def test_ranges_of_paragraphs_and_continued_subitems():
    subitems = {"조문여부": "조문", "조문번호": "20", "조문내용": "제20조(제한) 다음 각 호의 경우는 제외한다.",
                "항": [{"항번호": "", "호": [{"호번호": "1.", "호내용": "1. 다음 각 목의 경우",
                                           "목": [{"목번호": f"{m}.", "목내용": f"{m}. 경우"} for m in "가나다"]}]}]}
    ACT.append(subitems)
    try:
        statutes = family([article(5, "범위", [("법 제11조제1항부터 제3항까지의 규정과 법 제20조제1호나목 및 다목에 따른다.", [])])])
        found = [(r.key, r.block) for r in refs(statutes, "시험법 시행령", "art-5")]
    finally:
        ACT.remove(subitems)
    assert found == [("art-11", "p1"), ("art-11", "p2"), ("art-11", "p3"), ("art-20", "i1-m2"), ("art-20", "i1-m3")]


def test_a_noun_after_에_따른_must_be_the_delegated_matter():
    statutes = family([article(5, "범위", [("법 제10조제1항에 따른 적용 범위는 다음과 같다.", []), ("법 제10조제1항에 따른 기간 동안 신고한다.", [])])])
    first, second = refs(statutes, "시험법 시행령", "art-5")
    assert is_delegation(statutes, "시험법 시행령", first) is True
    assert is_delegation(statutes, "시험법 시행령", second) == "review"


def test_same_item_is_the_item_cited_just_before():
    subitems = {"조문여부": "조문", "조문번호": "20", "조문내용": "제20조(제한) 다음 각 호의 경우는 제외한다.",
                "항": [{"항번호": "", "호": [{"호번호": "1.", "호내용": "1. 다음 각 목의 경우",
                                           "목": [{"목번호": f"{m}.", "목내용": f"{m}. 경우"} for m in "가나"]}]}]}
    ACT.append(subitems)
    try:
        statutes = family([article(5, "범위", [("법 제20조제1호나목에 해당하는 사람은 같은 호 가목에 따른다.", [])])])
        found = [(r.key, r.block) for r in refs(statutes, "시험법 시행령", "art-5")]
    finally:
        ACT.remove(subitems)
    assert found == [("art-20", "i1-m2"), ("art-20", "i1-m1")]


def test_same_article_after_an_out_of_scope_law_is_dropped():
    statutes = family([article(5, "범위", [("「근로기준법」 제74조제1항에 따른 휴가와 같은 조 제3항에 따른 휴가를 말한다.", [])])])
    assert refs(statutes, "시험법 시행령", "art-5") == []


def test_same_law_follows_every_law_name_in_the_line():
    statutes = family([article(5, "범위", [("법 제10조제1항, 「근로기준법」에 따른 휴업수당과 같은 법 제11조에 따른 금액을 말한다.", [])])])
    assert [(r.law, r.key) for r in refs(statutes, "시험법 시행령", "art-5")] == [("시험법", "art-10")]


def test_a_delegation_opens_its_provision():
    cases = [
        ("법 제10조제1항에 따라 적용 범위를 정한다.", [], True),
        ("사업주는 법 제10조제1항에 따라 적용 범위를 신고한다.", [], True),
        ("직업안정기관의 장은 법 제10조제1항에 따라 지급된 금액을 확인한다.", [], "review"),
        ("다음 각 호의 경우를 말한다.", ["법 제10조제1항에 따라 적용 범위를 정한 경우"], "review"),
    ]
    for content, items, expected in cases:
        statutes = family([article(5, "범위", [(content, items)])])
        found = [r for r in refs(statutes, "시험법 시행령", "art-5") if r.key == "art-10"]
        assert [is_delegation(statutes, "시험법 시행령", r) for r in found] == [expected], content


def test_every_member_of_a_list_opens_the_provision():
    statutes = family(rule_articles=[article(7, "범위", [("법 제10조제1항 및 제2항에 따라 적용 제외를 정한다.", [])])])
    second = next(r for r in refs(statutes, "시험법 시행규칙", "art-7") if r.block == "p2")
    assert second.lead and is_delegation(statutes, "시험법 시행규칙", second) is True


def test_a_clause_of_불구하고_may_precede_the_delegation():
    statutes = family([article(5, "범위", [("제2항에도 불구하고 법 제10조제1항에 따라 적용 범위를 정한다.", [])])])
    [ref] = [r for r in refs(statutes, "시험법 시행령", "art-5") if r.key == "art-10"]
    assert is_delegation(statutes, "시험법 시행령", ref) is True


def test_a_one_syllable_matter_is_left_for_review():
    ref = S.Ref("시험법", "art-13", "p1", None, True, None, None, "경", True)
    lines = {"p1": "① 기초일액을 산정한다. 이 경우 소정근로시간은 고용노동부령으로 정하는 방법에 따라 산정한다."}
    assert S.delegated(ref, lines, True, family().laws["시험법 시행규칙"]) == "review"


def test_a_law_name_with_its_short_name_in_parentheses_prefixes_the_reference():
    statutes = family([article(5, "범위", [("「시험법」(이하 \"시험법률\"이라 한다) 제11조제1항에 따른다.", [])])])
    statutes.laws["시험법 시행령"].aliases = {"시험법률": "시험법"}
    assert [(r.law, r.key, r.block) for r in refs(statutes, "시험법 시행령", "art-5")] == [("시험법", "art-11", "p1")]


def test_a_law_out_of_scope_with_its_short_name_takes_its_references_along():
    statutes = family([article(5, "범위", [("「다른법」(이하 \"다른법률\"이라 한다) 제11조제1항에 따른다.", [])])])
    assert refs(statutes, "시험법 시행령", "art-5") == []


def test_a_bare_article_opening_a_parenthesis_belongs_to_the_law_before_it():
    statutes = family([article(5, "범위", [("법 제11조제1항(제12조제1항에서 준용하는 경우를 포함한다)에 따른다.", [])]),
                       article(12, "준용", text="준용한다.")])
    found = [(r.law, r.key, r.block) for r in refs(statutes, "시험법 시행령", "art-5")]
    assert found == [("시험법", "art-11", "p1"), ("시험법", "art-12", "p1")]


def test_a_bare_article_opening_a_parenthesis_after_a_law_out_of_scope_is_dropped():
    statutes = family([article(5, "범위", [("「다른법」 제11조(제12조에서 준용하는 경우를 포함한다)에 따른다.", [])]),
                       article(12, "준용", text="준용한다.")])
    assert refs(statutes, "시험법 시행령", "art-5") == []


def test_provisions_of_the_delegation_data_name_blocks():
    assert S.provision_block("제10조제1항제3호") == ("art-10", "p1-i3")
    assert S.provision_block("제2조제5호") == ("art-2", "i5")
    assert S.provision_block("제58조제1호나목") == ("art-58", "i1-m2")
    assert S.provision_block("제77조의8제2항") == ("art-77-8", "p2")
    assert S.provision_block("제23조") == ("art-23", None)


def test_delegation_data_keeps_delegations_to_lower_laws_only():
    response = {"lsDelegated": {"법령": {"위임조문정보": [
        {"조정보": {"조문번호": "43"}, "위임정보": [
            {"위임구분": "시행규칙", "위임법령제목": "시험법 시행규칙", "위임법령조문정보": [
                {"위임법령조문번호": "82", "위임법령조문가지번호": "2", "조항호목": "제43조제4항"},
                {"위임법령조문번호": "82", "위임법령조문가지번호": "2", "조항호목": "제43조제4항"}]},
            {"위임구분": "위임행정규칙", "위임행정규칙조문정보": {"조항호목": "제43조제1항"}},
            {"위임구분": ["인용법령", "인용법령"], "위임법령제목": ["가법", "나법"], "위임법령조문정보": [{"위임법령조문번호": "1", "조항호목": "제43조"}]}]},
        {"조정보": {"조문번호": "23"}, "위임정보": {"위임구분": "시행령", "위임법령제목": "시험법 시행령",
                                               "위임법령조문정보": {"위임법령조문번호": "29", "조항호목": "제23조"}}}]}}}
    assert S.official_delegations(response) == [("시험법 시행규칙", "art-82-2", "제43조제4항"), ("시험법 시행령", "art-29", "제23조")]


def test_a_reference_after_a_provision_that_applies_it_is_applied():
    statutes = family([article(5, "범위", [("법 제12조제1항에서 준용하는 법 제11조제3항 및 제2항에 따라 신고한다.", [])])])
    found = [(r.key, r.block, r.applied) for r in refs(statutes, "시험법 시행령", "art-5")]
    assert found == [("art-12", "p1", False), ("art-11", "p3", True), ("art-11", "p2", True)]


def test_delegation_data_decides_for_articles_of_the_current_version():
    statutes = family([article(5, "범위", [("신고한다.", [])])])
    statutes.covered, statutes.delegations = {"시험법": None}, {}
    unit = S.Unit(statutes.laws["시험법 시행령"], "art-5")
    assert statutes.decides(unit, "시험법")
    assert not statutes.decides(unit, "시험법 시행규칙")
    assert not statutes.decides(S.Unit(statutes.laws["시험법"], "art-10"), "시험법")


def moved_article(reference):
    row = article(5, "범위", [("신고한다.", [])])
    row["조문참고자료"] = reference
    return family([row])


def test_a_move_before_the_earliest_version_is_not_listed():
    statutes = moved_article("[제4조에서 이동, 종전 제5조는 제7조로 이동 <2009.10.9>]")
    assert S.review_unit(S.Unit(statutes.laws["시험법 시행령"], "art-5")) == []


def test_a_move_after_the_earliest_version_is_listed():
    statutes = moved_article("[제4조에서 이동, 종전 제5조는 제7조로 이동 <2026.3.1>]")
    found = S.review_unit(S.Unit(statutes.laws["시험법 시행령"], "art-5"))
    assert any("moved here from art-4" in line for line in found)
    assert any("moved to art-7" in line and "reused" in line for line in found)
