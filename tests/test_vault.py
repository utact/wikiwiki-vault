"""Tests for scripts/vault.py on the fixture vault."""

import shutil
from pathlib import Path

import vault

FIXTURES = Path(__file__).parent / "fixtures" / "vault"


def test_fixtures_conform():
    problems, graph = vault.check(FIXTURES)
    assert problems == []
    assert len(graph) > 0


def test_broken_link_is_reported(tmp_path):
    root = tmp_path / "vault"
    shutil.copytree(FIXTURES, root)
    note = root / "wiki" / "PublicService" / "피보험자격 상실 신고.md"
    text = note.read_text(encoding="utf-8")
    assert "[[고용노동부]]" in text
    note.write_text(text.replace("[[고용노동부]]", "[[고용노동청]]"), encoding="utf-8", newline="\n")
    problems, _ = vault.check(root)
    assert any("broken link: [[고용노동청]]" in p for p in problems)


def test_unknown_raw_publisher_is_reported(tmp_path):
    root = tmp_path / "vault"
    shutil.copytree(FIXTURES, root)
    shutil.rmtree(root / "wiki" / "PublicOrganisation")
    problems, _ = vault.check(root)
    assert any("unknown identifier: ministry-of-government-legislation" in p for p in problems)
