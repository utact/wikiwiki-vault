"""Tests for the text rules in scripts/lawlib.py, with excerpts of 법제처 responses."""

from datetime import date

import lawlib as L

# 고용보험 및 산업재해보상보험의 보험료징수 등에 관한 법률 시행령 별표 2, one row in two layouts
NARROW = """├─────────────────┼─────┤
│바. 법 제45조제1항(제48조의2제8   │법 제50조 │
│항제4호에 따라 준용되는 경우를    │제1항제4호│
│포함한다)                         │          │
└─────────────────┴─────┘"""
WIDE = """├──────────────────────────────────┼─────┤
│바. 법 제45조제1항(제48조의2제8항제4호에 따라 준용되는 경우를 포함한다) │법 제50조 │
│                                                                    │제1항제4호│
└──────────────────────────────────┴─────┘"""

# 고용보험법 시행령 별표 2, a merged cell beside rows split by partial borders inside a heavy frame
MERGED = """┠──────────────┬───────┼──────┨
┃거짓이나 그 밖의 부정한 방  │300만원 미만  │3개월       ┃
┃법으로 지급받거나 받으려고  ├───────┼──────┨
┃한 금액                     │300만원 이상  │6개월       ┃
┃                            │  500만원 미만│            ┃
┃                            ├───────┼──────┨"""

# 고용보험법 시행규칙 별지 제1호서식, a form without an outer frame whose first column is blank on a line
FORM = """────┬──────────────────────────────────────────────────────────────
  사업장│사업장관리번호는 상시 4명 이하의 근로자를 사용하는 법인이 아닌 농업·임업 및 어업 사업장이 고용보험에 가입
        │하면서 근로복지공단으로부터 부여받은 관리번호를 적습니다.
────┼──────────────────────────────────────────────────────────────
  신청  │1. 성명 및 주민등록번호는 주민등록표 상의 성명 및 주민등록번호를 적습니다.
  근로자│2. 채용일은 최초 근로계약 개시일을 적습니다.                                                                                """

# 고용보험법 시행규칙 제105조제1항, a table that exists only inside an image, without line breaks
IMAGE = (
    "다음 표의 구분에 따른 비율을 곱한 금액으로 한다. "
    '<img src="http://www.law.go.kr/flDownload.do?flSeq=1"  alt="img1" >'
    "│구분            │비율        │├──────┬─────┼──────┤"
    "│거짓이나 그 밖의 │3회 미만  │100분의 100 ││부정한 방법으로  │          │            │"
    "└──────┴─────┴──────┘</img> <개정 2020.8.28, 2026.7.1>"
)


def test_table_layouts_read_the_same():
    expected = "바.법제45조제1항(제48조의2제8항제4호에따라준용되는경우를포함한다)법제50조제1항제4호"
    assert L.canonical(NARROW) == L.canonical(WIDE) == expected


def test_merged_cell_stays_together():
    cells = [" ".join(" ".join(c.lines).split()) for c in L.cells(MERGED)]
    assert "거짓이나 그 밖의 부정한 방 법으로 지급받거나 받으려고 한 금액" in cells
    assert cells.index("300만원 미만") < cells.index("3개월") < cells.index("300만원 이상 500만원 미만")


def test_form_sentence_stays_together():
    quote = "사업장관리번호는 상시 4명 이하의 근로자를 사용하는 법인이 아닌 농업·임업 및 어업 사업장이 고용보험에 가입하면서 근로복지공단으로부터 부여받은 관리번호를 적습니다."
    assert L.canonical(quote) in L.canonical(FORM)


def test_lines_of_spaces_do_not_change_the_reading():
    spaced = FORM.replace("\n  신청", "\n" + " " * 40 + "\n  신청")
    assert L.canonical(spaced) == L.canonical(FORM)


def test_image_table_is_read_by_cell():
    assert L.canonical(IMAGE) == (
        "다음표의구분에따른비율을곱한금액으로한다."
        "구분비율거짓이나그밖의부정한방법으로3회미만100분의100<개정2020.8.28,2026.7.1>"
    )


def test_cells_keep_numbers_apart():
    assert "100분의 100" in [" ".join(c.lines).strip() for c in L.cells(IMAGE)]


def test_version_text_leaves_out_images():
    assert L.version_text(IMAGE) == "다음표의구분에따른비율을곱한금액으로한다.<개정2020.8.28,2026.7.1>"
    assert L.version_text(IMAGE) == L.version_text(IMAGE.replace("100분의 100", "100분의 150"))


def test_side_by_side_boxes_outside_images_stay_on_one_line():
    assert L.canonical("│담당││팀장│\n│    ││    │") == "담당팀장"


def test_middle_dots_stay_different():
    assert L.canonical("거부ㆍ방해") != L.canonical("거부·방해")


def test_amendment_dates():
    assert L.amendment_dates("<개정 2019. 1. 15., 2021.1.5>") == ["20190115", "20210105"]
    assert L.amendment_dates("[본조신설 2020.6.9]") == ["20200609"]
    assert L.amendment_dates("제18조 삭제 <2024.12.24>") == ["20241224"]
    assert L.amendment_dates("제40조(구직급여의 수급 요건) ① 2020.6.9 이후") == []


def law(articles=(), annexes=(), supplements=()):
    return {
        "조문": {"조문단위": [{"조문여부": kind, "조문번호": number, "조문가지번호": "", "조문키": key, "조문내용": text}
                          for kind, number, key, text in articles]},
        "별표": {"별표단위": list(annexes)},
        "부칙": {"부칙단위": [{"부칙공포일자": d, "부칙공포번호": n, "부칙내용": t} for d, n, t in supplements]},
    }


def test_headings_are_keyed_by_place():
    units = L.law_units(law([
        ("전문", "37", "0037000", "제4장 실업급여"),
        ("전문", "37", "0037000", "제1절 통칙"),
        ("조문", "37", "0037001", "제37조(실업급여의 종류)"),
        ("전문", "40", "0040000", "제2절 구직급여"),
    ]))
    assert list(units) == ["heading-ch4", "heading-ch4-sec1", "art-37", "heading-ch4-sec2"]


def test_supplements_with_one_number_stay_apart():
    units = L.law_units(law(supplements=[("20190930", "00263", "부칙 <제263호,2019.9.30>"), ("20191015", "00263", "부칙 <제263호,2019.10.15>")]))
    assert list(units) == ["sup-20190930-263", "sup-20191015-263"]


def test_transitional_articles():
    text = "\n".join([
        "부칙 <제17429호,2020.6.9>",
        "제1조(시행일) 이 법은 공포 후 6개월이 경과한 날부터 시행한다.",
        "제2조(예술인의 피보험자격 취득일에 관한 적용례) 제77조의2의 개정규정은 부칙 제1조에 따른 시행일 이후 체결하는 계약부터 적용한다.",
        "제3조(서식에 관한 경과조치) 별지 제32호서식 및 제34호서식은 같은 조 제3항에 따라 별표 1과 함께 쓴다.",
    ])
    old = ("20190827", "16557", "부칙 <제16557호,2019.8.27>\n제1조(시행일) 생략\n제9조(추가 징수에 관한 경과조치) 제62조제2항에 따른다.")
    stale = ("20150101", "13000", "부칙\n제1조(시행일) 생략\n제2조(경과조치) 제1조에 따른다.")
    rows = [
        {"공포일자": "20200609", "공포번호": "17429", "시행일자": "20201210"},
        {"공포일자": "20190827", "공포번호": "16557", "시행일자": "20200828"},
        {"공포일자": "20150101", "공포번호": "13000", "시행일자": "20150701"},
    ]
    found = L.transitional([law(supplements=[("20200609", "17429", text), old, stale])], rows, date(2020, 6, 16))
    assert [(f["promulgation"], f["article"], f["units"]) for f in found] == [
        ("20200609-17429", "제2조", ["제77조의2"]),
        ("20200609-17429", "제3조", ["별지 제32호서식", "제34호서식", "같은 조 제3항", "별표 1"]),
        ("20190827-16557", "제9조", ["제62조제2항"]),
    ]


def test_window_start():
    assert L.window_start(date(2026, 10, 14), "P6Y120D") == date(2020, 6, 16)
    assert L.window_start(date(2028, 2, 29), "P6Y0D") == date(2022, 2, 28)


def test_scrub_removes_the_oc_parameter(monkeypatch):
    monkeypatch.setattr(L, "secrets", lambda: ["OC=secret"])
    url = "http://www.law.go.kr/DRF/lawService.do?OC=secret&target=eflaw&MST=1"
    assert L.scrub(f'"{url}"') == '"http://www.law.go.kr/DRF/lawService.do?target=eflaw&MST=1"'


def test_choose_versions_prefers_the_later_promulgation():
    rows = [
        {"시행일자": "20260918", "공포일자": "20260317", "공포번호": "제21473호", "법령일련번호": "1"},
        {"시행일자": "20260918", "공포일자": "20260317", "공포번호": "제21480호", "법령일련번호": "2"},
        {"시행일자": "20260918", "공포일자": "20250101", "공포번호": "제30000호", "법령일련번호": "3"},
    ]
    assert L.choose_versions(rows)["20260918"]["법령일련번호"] == "2"


# 고용보험법 시행규칙 별지 제32호서식, where the text of the middle column runs past its border on one line
OVERFLOW = """───────┬─────────────────────────────────────┬─────────
  신청인      │ 1. 근로자의 월별 임금대장 사본 1부                                       │수수료            
  제출서류    │ 2. 고용유지조치 기간 중 사업주가 임금을 보전하기 위하여 지급한 금품을 확인할 수 있는 자료 1부│없음              
              │ 3. 출퇴근카드 또는 출퇴근기록부 등 출퇴근 현황을 확인할 수 있는 서류 사본 1부│                  
───────┼─────────────────────────────────────┤"""


def test_text_past_a_border_does_not_join_the_next_column():
    texts = [" ".join(" ".join(cell.lines).split()) for cell in L.cells(OVERFLOW)]
    middle = next(t for t in texts if t.startswith("1. 근로자의"))
    assert middle.startswith("1. 근로자의 월별 임금대장 사본 1부 2. 고용유지조치")
    assert "수수료" not in middle and "수수료" in texts


def test_paragraph_lines_stay_apart_from_table_cells():
    found = L.cells("①법 제62조제2항 본문에 따른 추가징수액은 다음 표와 같다." + IMAGE[IMAGE.index("<img"):])
    assert [cell.table for cell in found][:3] == [False, True, True]


def test_number_text_joins_wrapped_lines():
    # 고용보험법 시행령 별표 3 and 고용보험법 시행규칙 별지 제52호서식
    cell = "┌──────┐\n│피보험자  │\n│1명당 3   │\n│만원      │\n└──────┘"
    assert "1명당 3만원" in L.number_text(cell)
    paragraph = "  14. 정년연장형 840만원(분기 210  \n  만원, 월 70만원)"
    assert "분기 210만원" in L.number_text(paragraph, wrapped=True)
    assert "분기 210만원" not in L.number_text(paragraph)


def test_image_links_in_order_of_first_appearance():
    response = {"법령": {"조문": [
        {"항내용": '1. 제1항제1호의 경우:<img src="http://www.law.go.kr/flDownload.do?flSeq=102803859"  alt="img102803859" >┌┐</img>'},
        {"조문내용": '1. 최저임금액<img id="44188166"></img> <img src="http://www.law.go.kr/flDownload.do?flSeq=102803859" >'},
    ]}}
    assert L.image_links(response) == [
        "http://www.law.go.kr/flDownload.do?flSeq=102803859",
        "http://www.law.go.kr/flDownload.do?flSeq=44188166",
    ]
    assert [L.extension(data) for data in (b"GIF89a", b"BM6", b"\x89PNG\r\n")] == [".gif", ".bmp", ".png"]


def test_lost_glyph_counts_wide_at_the_start_of_a_line():
    assert L.width("?민원") == 6
    assert L.width("가?나") == 6
    assert L.width("a?나") == 4


def test_same_name_ignores_spaces():
    assert L.same_name("고용보험법시행령", "고용보험법 시행령")
    assert not L.same_name("고용보험법", "고용보험법 시행령")


def test_a_name_with_digits_is_not_a_number():
    assert L.number_tokens("고용24 안내는 90일 안에 청구한다고 적는다.", notes=False) == [("number", 90, "일")]


def test_notice_preamble_keeps_the_lines_of_its_개정문():
    service = {"개정문": {"개정문내용": [["⊙고용노동부고시 제2022-116호", "  「고용보험법」 제2조제5호 단서에 따라 고시합니다."]]}}
    assert L.notice_preamble(service) == "⊙고용노동부고시 제2022-116호\n  「고용보험법」 제2조제5호 단서에 따라 고시합니다."
    assert L.notice_preamble({"개정문": ""}) == ""
    assert L.notice_preamble({}) == ""
