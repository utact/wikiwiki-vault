"""Tests for the text rules in scripts/lawlib.py, with excerpts of 법제처 responses."""

import lawlib as L

# 고용보험 및 산업재해보상보험의 보험료징수 등에 관한 법률 시행령 별표 2, one row in two layouts
NARROW = """├────┼────┤
│바. 법 제45조제1항(제48조의2제8   │법 제50조 │
│항제4호에 따라 준용되는 경우를    │제1항제4호│
│포함한다)                         │          │
└────┴────┘"""
WIDE = """├────────┼────┤
│바. 법 제45조제1항(제48조의2제8항제4호에 따라 준용되는 경우를 포함한다) │법 제50조 │
│                                                                    │제1항제4호│
└────────┴────┘"""

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


def test_image_table_is_read_by_cell():
    assert L.canonical(IMAGE) == (
        "다음표의구분에따른비율을곱한금액으로한다."
        "구분비율거짓이나그밖의부정한방법으로3회미만100분의100<개정2020.8.28,2026.7.1>"
    )


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
    assert L.amendment_dates("제40조(구직급여의 수급 요건) ① 2020.6.9 이후") == []


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
