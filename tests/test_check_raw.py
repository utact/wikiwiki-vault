"""Tests for the gates in scripts/check_raw.py: each defect planted in small versions must be reported."""

from datetime import date

import check_raw as C

WINDOW, AS_OF = date(2020, 6, 16), date(2026, 10, 14)
IMAGE = '<img src="x" >│비율        │└──────┘</img>'


def version(effective, articles, supplements, annexes=()):
    return {
        "기본정보": {"시행일자": effective},
        "조문": {"조문단위": [
            {"조문여부": "조문", "조문번호": number, "조문가지번호": "", "조문키": f"{int(number):04d}001",
             "조문내용": text, "조문변경여부": flag, "조문이동이전": moved}
            for number, text, flag, moved in articles
        ]},
        "별표": {"별표단위": [{"별표구분": "별표", "별표번호": "0001", "별표가지번호": "00", "별표제목": "표", "별표내용": t} for t in annexes]},
        "부칙": {"부칙단위": [{"부칙공포일자": d, "부칙공포번호": n, "부칙내용": t} for d, n, t in supplements]},
    }


ROWS = [
    {"시행일자": "20200101", "공포일자": "20190101", "공포번호": "100", "제개정구분명": "전부개정", "법령일련번호": "1"},
    {"시행일자": "20210101", "공포일자": "20200601", "공포번호": "101", "제개정구분명": "일부개정", "법령일련번호": "2"},
]
SUP_100 = ("20190101", "100", "부칙 <제100호,2019.1.1>")
SUP_101 = ("20200601", "101", "부칙 <제101호,2020.6.1>")


def clean():
    return {
        "20200101": version("20200101", [("1", "제1조(목적) 이 법은 목적을 정한다.", "N", ""), ("2", "제2조(금액) 1만원으로 한다.", "N", "")], [SUP_100], ["금액 표"]),
        "20210101": version("20210101", [("1", "제1조(목적) 이 법은 목적을 정한다.", "N", ""), ("2", "제2조(금액) 2만원으로 한다. <개정 2020.6.1>", "N", "")], [SUP_100, SUP_101], ["금액 표"]),
    }


def run(versions, rows=ROWS):
    listing = {"totalCnt": len(rows), "pages": [{"law": rows}]}
    problems, _ = C.check_versions("시험법", versions, rows, listing, WINDOW, AS_OF)
    return problems


def test_clean_versions_pass():
    assert run(clean()) == []


def test_untagged_change_fails():
    versions = clean()
    versions["20210101"]["조문"]["조문단위"][0]["조문내용"] = "제1조(목적) 이 법은 다른 목적을 정한다."
    assert any("art-1 changed with no amendment tag" in p for p in run(versions))


def test_change_flag_explains_an_untagged_change():
    versions = clean()
    versions["20210101"]["조문"]["조문단위"][0].update({"조문내용": "제1조(목적) 이 법은 다른 목적을 정한다.", "조문변경여부": "Y"})
    assert run(versions) == []


def test_missing_supplement_fails():
    versions = clean()
    versions["20210101"]["부칙"]["부칙단위"].pop()
    assert any("부칙 missing" in p for p in run(versions))


def test_changed_supplement_fails():
    versions = clean()
    versions["20210101"]["부칙"]["부칙단위"][0]["부칙내용"] = "부칙 <제100호,2019.1.2>"
    assert any("sup-20190101-100 changed" in p for p in run(versions))


def test_missing_version_in_window_fails():
    rows = [*ROWS, {"시행일자": "20200701", "공포일자": "20200615", "공포번호": "102", "제개정구분명": "일부개정", "법령일련번호": "3"}]
    assert any("not collected ['20200701']" in p for p in run(clean(), rows))


def test_empty_annex_fails():
    versions = clean()
    versions["20210101"]["별표"]["별표단위"][0]["별표내용"] = "  "
    assert any("empty 별표" in p for p in run(versions))


def test_effective_date_mismatch_fails():
    versions = clean()
    versions["20210101"]["기본정보"]["시행일자"] = "20210102"
    assert any("response says 20210102" in p for p in run(versions))


def test_removed_article_fails_unless_moved():
    versions = clean()
    versions["20210101"]["조문"]["조문단위"].pop(0)
    assert any("art-1 removed" in p for p in run(versions))
    versions["20210101"]["조문"]["조문단위"].append(
        {"조문여부": "조문", "조문번호": "3", "조문가지번호": "", "조문키": "0003001", "조문내용": "제3조(목적) 이 법은 목적을 정한다. <개정 2020.6.1>",
         "조문변경여부": "N", "조문이동이전": "000100"})
    assert run(versions) == []


def test_image_change_across_a_version_without_image_text_fails():
    """The middle version leaves out the image text, as 고용보험법 시행규칙 제105조 does on 2024-07-01."""
    rows = [*ROWS, {"시행일자": "20220101", "공포일자": "20210601", "공포번호": "103", "제개정구분명": "일부개정", "법령일련번호": "4"}]
    first = "제1조(목적) 이 법은 목적을 정한다." + IMAGE
    second = "제2조(금액) 2만원으로 한다. <개정 2020.6.1>"

    def versions(third_image):
        found = clean()
        found["20200101"]["조문"]["조문단위"][0]["조문내용"] = first
        found["20210101"]["조문"]["조문단위"][0]["조문내용"] = first.replace("│비율        │", "")
        found["20220101"] = version(
            "20220101", [("1", first.replace("비율", third_image), "N", ""), ("2", second, "N", "")],
            [SUP_100, SUP_101, ("20210601", "103", "부칙 <제103호,2021.6.1>")], ["금액 표"])
        return found

    assert run(versions("비율"), rows) == []
    assert any("art-1 image text changed" in p for p in run(versions("요율"), rows))


def test_image_text_without_frames_fails():
    versions = clean()
    versions["20210101"]["조문"]["조문단위"][0]["조문내용"] += '<img src="x" >│비율 │표 끝</img>'
    assert any("without a frame" in p for p in run(versions))
