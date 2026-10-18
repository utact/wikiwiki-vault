"""Tests for scripts/verify.py on a copy of the fixture vault."""

import json
import shutil
from pathlib import Path

import pytest

import lint
import verify

FIXTURES = Path(__file__).parent / "fixtures" / "vault"
NOTE = "기초일액 상한"


def copy(tmp_path):
    root = tmp_path / "vault"
    shutil.copytree(FIXTURES, root)
    return root


def test_context_shows_the_note_its_blocks_and_linked_notes(tmp_path):
    linter = lint.Linter(copy(tmp_path))
    text = verify.context(linter, [NOTE])
    note = linter.notes[NOTE]
    assert note.text.strip() in text
    for target, block in verify.cited_blocks(linter, note):
        assert f"## Cited block {target}#^{block}" in text
        assert linter.notes[target].blocks[block][0].strip() in text
    assert "## 기초일액" in text


def test_record_sets_verified_and_matches_the_ledger_check(tmp_path):
    root = copy(tmp_path)
    entries = verify.record(lint.Linter(root), root, [NOTE], "opus", "xhigh", "test-session")
    assert entries[0]["blocks"] and entries[0]["session"] == "test-session"
    last = json.loads((root / verify.LEDGER).read_text(encoding="utf-8").splitlines()[-1])
    assert last == entries[0]
    linter = lint.Linter(root)
    assert linter.notes[NOTE].meta["status"] == "verified"
    linter.check_ledger()
    assert not [p for p in linter.problems if NOTE in p]


def test_record_refuses_a_note_that_is_not_draft(tmp_path):
    root = copy(tmp_path)
    verify.record(lint.Linter(root), root, [NOTE], "opus", "xhigh", "first")
    ledger = (root / verify.LEDGER).read_text(encoding="utf-8")
    with pytest.raises(SystemExit):
        verify.record(lint.Linter(root), root, [NOTE], "opus", "xhigh", "second")
    assert (root / verify.LEDGER).read_text(encoding="utf-8") == ledger


def test_record_refuses_a_statute_note(tmp_path):
    root = copy(tmp_path)
    with pytest.raises(SystemExit):
        verify.record(lint.Linter(root), root, ["고용보험법 별표 1"], "opus", "xhigh", "test-session")
