"""Tests for scripts/review_guard.py, the hook that keeps the reviewed status for the human owner."""

import json
import subprocess
import sys
from pathlib import Path

import review_guard as G

NOTE = G.VAULT / "wiki" / "PublicOrganisation" / "고용노동부.md"


def run(call):
    """Exit code and stderr of the hook for a tool call passed as JSON on stdin, as Claude Code does."""
    result = subprocess.run([sys.executable, "-X", "utf8", str(G.VAULT / "scripts" / "review_guard.py")],
                            input=json.dumps(call, ensure_ascii=False).encode("utf-8"), capture_output=True)
    return result.returncode, result.stderr.decode("utf-8")


def edit(old, new, path=NOTE):
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path), "old_string": old, "new_string": new}}


def test_setting_reviewed_is_blocked():
    code, reason = run(edit("status: draft", "status: reviewed"))
    assert code == 2 and "status: reviewed" in reason


def test_adding_reviewer_keys_is_blocked():
    assert run(edit("status: draft", "status: draft\nreviewedBy: 소유자"))[0] == 2
    assert run(edit("status: draft", "status: draft\nlastReviewed: 2026-10-17"))[0] == 2


def test_other_edits_pass():
    assert run(edit("status: draft", "status: verified"))[0] == 0
    assert run(edit("status: draft", "status: reviewed", path=G.VAULT / "CLAUDE.md"))[0] == 0
    assert run({"tool_name": "Write", "tool_input": {"file_path": str(G.VAULT / "log.md"), "content": "reviewedBy: x"}})[0] == 0


def test_a_reviewed_note_must_return_to_draft(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "VAULT", tmp_path)
    note = tmp_path / "wiki" / "Concept" / "시험.md"
    note.parent.mkdir(parents=True)
    note.write_text("---\ntype: Concept\nstatus: reviewed\nreviewedBy: 소유자\n---\n\n본문이다.\n", encoding="utf-8")
    assert "return" in G.check(edit("본문이다.", "고친 본문이다.", path=note))
    assert G.check(edit("status: reviewed", "status: draft", path=note)) is None
    assert G.check({"tool_name": "Write", "tool_input": {"file_path": str(note),
                                                       "content": "---\ntype: Concept\nstatus: draft\nreviewedBy: 소유자\n---\n"}}) is None


def test_shell_writes_into_notes_are_blocked():
    assert run({"tool_name": "Bash", "tool_input": {"command": "sed -i 's/status: draft/status: reviewed/' wiki/Concept/x.md"}})[0] == 2
    assert run({"tool_name": "PowerShell", "tool_input": {"command": "Set-Content wiki\\x.md 'lastReviewed: 2026-10-17'"}})[0] == 2
    assert run({"tool_name": "Bash", "tool_input": {"command": "grep -rn 'status: reviewed' wiki"}})[0] == 0
    assert run({})[0] == 0


def test_mentions_in_inline_code_pass():
    command = "printf '- `wiki/` 노트에 `status: reviewed`, `reviewedBy`, `lastReviewed`를 쓰지 않는다.' >> log.md"
    assert G.check({"tool_name": "Bash", "tool_input": {"command": command}}) is None
