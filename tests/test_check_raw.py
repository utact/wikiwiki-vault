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


def heading(text):
    return {"조문여부": "전문", "조문번호": "1", "조문가지번호": "", "조문키": "0001000", "조문내용": text}


def test_list_rows_must_match_total_count():
    listing = {"totalCnt": len(ROWS) + 1, "pages": [{"law": ROWS}]}
    problems, _ = C.check_versions("시험법", clean(), ROWS, listing, WINDOW, AS_OF)
    assert any("totalCnt is 3" in p for p in problems)


def test_changed_heading_fails():
    versions = clean()
    versions["20200101"]["조문"]["조문단위"].insert(0, heading("제1장 총칙"))
    versions["20210101"]["조문"]["조문단위"].insert(0, heading("제1장 일반 규정"))
    assert any("heading-ch1 changed" in p for p in run(versions))


def test_new_supplement_of_another_promulgation_fails():
    versions = clean()
    versions["20210101"]["부칙"]["부칙단위"].append({"부칙공포일자": "20180101", "부칙공포번호": "99", "부칙내용": "부칙 <제99호,2018.1.1>"})
    assert any("sup-20180101-99 changed" in p for p in run(versions))


def test_removal_needs_a_whole_unit_deletion():
    versions = clean()
    versions["20200101"]["조문"]["조문단위"][0]["조문내용"] = "제1조(목적)\n1. 목적을 정한다.\n2. 삭제 <2010.2.8>"
    versions["20210101"]["조문"]["조문단위"].pop(0)
    assert any("art-1 removed" in p for p in run(versions))
    versions["20200101"]["조문"]["조문단위"][0]["조문내용"] = "제1조 삭제 <2010.2.8>"
    assert run(versions) == []


def test_flag_does_not_excuse_an_image_change():
    versions = clean()
    versions["20200101"]["조문"]["조문단위"][0]["조문내용"] += IMAGE
    versions["20210101"]["조문"]["조문단위"][0].update({"조문내용": versions["20200101"]["조문"]["조문단위"][0]["조문내용"].replace("비율", "요율"), "조문변경여부": "Y"})
    assert any("art-1 image text changed" in p for p in run(versions))


def test_replaced_image_without_text_fails():
    versions = clean()
    versions["20200101"]["조문"]["조문단위"][0]["조문내용"] += '<img src="a" >┌┐││└┘</img>'
    versions["20210101"]["조문"]["조문단위"][0]["조문내용"] += '<img src="b" >┌┐││└┘</img>'
    assert any("image files changed with no text" in p for p in run(versions))


def test_image_lines_of_uneven_width_fail():
    versions = clean()
    versions["20210101"]["조문"]["조문단위"][0]["조문내용"] += '<img src="x" >│비율        ││요율 │</img>'
    assert any("lines of widths" in p for p in run(versions))


NOTICE = "시험 고시"


def notice_vault(tmp_path, monkeypatch, effective="20260101", text="시간급 10,320원", attachment=None):
    """A raw note of a 고시 with its response and one attachment, under a temporary vault."""
    import json

    import lawlib as L

    monkeypatch.setattr(L, "VAULT", tmp_path)
    monkeypatch.setattr(L, "RAW", tmp_path / "raw")
    monkeypatch.setattr(L, "CACHE", tmp_path / ".cache")
    monkeypatch.setattr(L, "release", lambda: (AS_OF, WINDOW))
    folder = tmp_path / "raw" / "law" / NOTICE
    folder.mkdir(parents=True)
    stem = f"{NOTICE} 20260101-7 20261015T1337"
    response = {"AdmRulService": {"행정규칙기본정보": {"시행일자": effective, "행정규칙명": NOTICE},
                                  "조문내용": text, "첨부파일": {"첨부파일명": [f"{NOTICE}.pdf"]}}}
    payload = L.json_payload(json.dumps(response, ensure_ascii=False))
    (folder / f"{stem}.json").write_text(payload, encoding="utf-8", newline="\n")
    data = b"%PDF-1.4 stand-in" if attachment is None else attachment
    (folder / f"{stem}-1.pdf").write_bytes(data)
    meta = {"identifier": "raw-admrul-1-20260101-7-20261015t1337", "title": NOTICE, "publisher": "ministry-of-government-legislation",
            "url": "http://www.law.go.kr/DRF/lawService.do?type=JSON&target=admrul&ID=7", "generatedAtTime": "2026-10-15T13:37:00+09:00",
            "sha256": L.files_hash(payload, [data]), "license": "저작권법 제7조에 따라 보호받지 않는 저작물"}
    L.write_note(folder / f"{stem}.md", meta, "시험용 원문 노트다.")
    return folder / f"{stem}.md"


def notices(tmp_path, monkeypatch, **kwargs):
    import lawlib as L

    note = notice_vault(tmp_path, monkeypatch, **kwargs)
    monkeypatch.setattr(L, "notice_text", lambda service, attachments: "\n".join(L.flatten(service.get("조문내용"))))
    problems, notes = [], []
    C.check_notices(problems, notes)
    return note, problems


def test_clean_notice_passes(tmp_path, monkeypatch):
    _, problems = notices(tmp_path, monkeypatch)
    C.check_notes(problems)
    assert problems == []


def test_notice_effective_date_must_match(tmp_path, monkeypatch):
    _, problems = notices(tmp_path, monkeypatch, effective="20260102")
    assert any("response says 20260102" in p for p in problems)


def test_notice_without_text_fails(tmp_path, monkeypatch):
    _, problems = notices(tmp_path, monkeypatch, text="")
    assert any("no text" in p for p in problems)


def test_unreadable_pdf_is_reported(tmp_path, monkeypatch):
    notice_vault(tmp_path, monkeypatch, text="", attachment=b"not a pdf")
    problems = []
    C.check_notices(problems, [])
    assert any("PDF attachment unreadable" in p for p in problems)


def test_notice_versions_in_the_window_must_be_collected(tmp_path, monkeypatch):
    import json

    _, problems = notices(tmp_path, monkeypatch)
    listing = tmp_path / ".cache" / "admrul" / "1" / "versions.json"
    listing.parent.mkdir(parents=True)
    listing.write_text(json.dumps({"20250101": {"행정규칙일련번호": "6"}, "20260101": {"행정규칙일련번호": "7"}}), encoding="utf-8")
    C.check_notices(problems, [])
    assert any("not collected ['20250101']" in p for p in problems)


def test_changed_attachment_changes_the_hash(tmp_path, monkeypatch):
    note = notice_vault(tmp_path, monkeypatch)
    note.with_name(note.stem + "-1.pdf").write_bytes(b"%PDF-1.4 another")
    problems = []
    C.check_notes(problems)
    assert any("sha256 differs" in p for p in problems)


def test_missing_property_and_attachment_fail(tmp_path, monkeypatch):
    note = notice_vault(tmp_path, monkeypatch)
    note.write_text(note.read_text(encoding="utf-8").replace("license:", "licence:"), encoding="utf-8", newline="\n")
    note.with_name(note.stem + "-1.pdf").unlink()
    problems = []
    C.check_notes(problems)
    assert any("missing ['license']" in p for p in problems)
    assert any("attachments missing" in p for p in problems)


def test_secret_in_a_raw_file_fails(tmp_path, monkeypatch):
    import lawlib as L

    note = notice_vault(tmp_path, monkeypatch)
    monkeypatch.setattr(L, "secrets", lambda: ["OC=secret"])
    note.write_text(note.read_text(encoding="utf-8") + "\nhttp://x/?OC=secret\n", encoding="utf-8", newline="\n")
    problems = []
    C.check_secrets(problems, [])
    assert any("contains a secret value" in p for p in problems)
