"""Tests for the 고용24 guide parser in scripts/collect.py, with the structure of the 실업급여(상용직) page."""

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
