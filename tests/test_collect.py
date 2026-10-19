"""Tests for the 고용24 guide parser in scripts/collect.py, with the structure of the 실업급여(상용직) page."""

import pytest

import collect

PAGE = """<h2>실업급여(상용직)</h2>
<ul class="box_list_doc type02">
<li><a href="#CI00001700" class="active">개요</a></li>
<li><a href="#CI00001701">지원내용</a></li>
<li><a href="#CI00001905">신청절차</a></li>
</ul>
<div id="CI00001700"><div class="se-contents"><p><br></p></div></div>
<h3 id="CI00001701" class="t1_sb">지원내용</h3>
<div class="box_border_type_policy"><div class="se-contents"><p><br></p></div></div>
<h3 id="CI00001905" class="t1_sb">신청절차</h3>
<div class="box_border_type_policy"><p>서류 제출 요청&nbsp;→ 사전 확인</p></div>
<h3 class="t1_sb">유사 제도</h3>
<ul><li><a href="#none">실업급여(일용직)</a></li></ul>
<p class="b1_r mt40">최종 수정일: 2026-08-25</p>"""


def test_sections_follow_the_table_of_contents():
    sections, modified = collect.page_sections(PAGE, "실업급여(상용직)")
    assert sections == {"개요": "", "지원내용": "", "신청절차": "서류 제출 요청 → 사전 확인"}
    assert modified == "2026-08-25"


NOTE = """---
identifier: raw-work24-si00000411-20261015t1337
title: 실업급여(상용직)
license: 공공누리 표시 없음
---

고용24 실업급여(상용직) 안내의 원문 노트다.
"""


def guide(tmp_path):
    folder = tmp_path / "raw" / "work24" / "실업급여(상용직)"
    folder.mkdir(parents=True)
    (folder / "실업급여(상용직) 20261015T1337.md").write_text(NOTE, encoding="utf-8", newline="\n")
    (folder / "실업급여(상용직) 20261015T1337.html").write_text(PAGE, encoding="utf-8", newline="\n")
    return folder / "실업급여(상용직) 20261015T1337.md"


def test_quote_appends_a_checked_quotation(tmp_path):
    note = guide(tmp_path)
    assert collect.quote("실업급여(상용직)", "신청절차", "서류 제출 요청 → 사전 확인", raw=tmp_path / "raw") == 1
    meta = collect.L.frontmatter(note)
    assert meta["hasPart"] == [{"identifier": "raw-work24-si00000411-20261015t1337-q1", "text": "서류 제출 요청 → 사전 확인",
                                "sha256": collect.L.body_hash("서류 제출 요청 → 사전 확인")}]
    assert collect.quotations(note) == {"q1": "서류 제출 요청 → 사전 확인"}
    assert collect.quote("실업급여(상용직)", "신청절차", "서류 제출 요청 → 사전 확인", raw=tmp_path / "raw") == 1


def test_quote_refuses_text_outside_the_section(tmp_path):
    guide(tmp_path)
    with pytest.raises(SystemExit):
        collect.quote("실업급여(상용직)", "지원내용", "서류 제출 요청", raw=tmp_path / "raw")


def test_check_raw_finds_a_changed_quotation(tmp_path, monkeypatch):
    import check_raw
    note = guide(tmp_path)
    collect.quote("실업급여(상용직)", "신청절차", "서류 제출 요청 → 사전 확인", raw=tmp_path / "raw")
    monkeypatch.setattr(collect.L, "RAW", tmp_path / "raw")
    monkeypatch.setattr(collect.L, "VAULT", tmp_path)
    problems = []
    check_raw.check_quotations(problems)
    assert problems == []
    note.write_text(note.read_text(encoding="utf-8").replace("사전 확인 ^q1", "사전 교육 ^q1"), encoding="utf-8", newline="\n")
    check_raw.check_quotations(problems)
    assert any("^q1 differs" in p for p in problems)
