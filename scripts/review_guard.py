"""Block the LLM from marking vault notes as reviewed, as the Review rules of CLAUDE.md require.

Usage:
    a Claude Code PreToolUse hook in .claude/settings.json, which passes the tool call as JSON on stdin

It blocks, with exit code 2 and the reason on stderr:
- a Write, Edit or MultiEdit of a note in wiki/ or synthetic/ that sets `status: reviewed` or adds `reviewedBy` or `lastReviewed`
- any edit of a note whose status is reviewed that does not first return it to draft, because any edit returns a note to draft
- a shell command that names wiki/ or synthetic/, writes, and carries one of those keys

The shell check reads only the command text, so a script that writes the keys from its own code passes it.
"""

import json
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
GUARDED = ("wiki", "synthetic")
REVIEWED = re.compile(r"^\s*status:\s*['\"]?reviewed\b", re.M)
REVIEW_KEYS = re.compile(r"^\s*(?:reviewedBy|lastReviewed)\s*:.*$", re.M)
# Keys as YAML writes them; a mention in inline code, such as `status: reviewed` in a log entry, is not one.
TOKENS = re.compile(r"(?<!`)(?:status:\s*['\"]?reviewed\b|reviewedBy\s*:|lastReviewed\s*:)")
WRITES = re.compile(r">|\btee\b|\bsed\s+-i|\bperl\b|\bpython\b|\buv\s+run\b|Set-Content|Add-Content|Out-File|\bcp\b|\bmv\b|<<")


def guarded(path):
    """Whether a path is a Markdown note in wiki/ or synthetic/ of this vault."""
    try:
        relative = Path(path).resolve().relative_to(VAULT)
    except (ValueError, OSError):
        return False
    return relative.suffix == ".md" and relative.parts[0] in GUARDED


def added_keys(old, new):
    """reviewedBy and lastReviewed lines of new that old does not have."""
    before = {line.strip() for line in REVIEW_KEYS.findall(old)}
    return [line.strip() for line in REVIEW_KEYS.findall(new) if line.strip() not in before]


def check_edits(path, edits):
    """The reason to block a list of (old, new) replacements in one note, or None."""
    current = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    for old, new in edits:
        if REVIEWED.search(new):
            return f"{path}: only the human owner sets status: reviewed"
        keys = added_keys(old, new)
        if keys:
            return f"{path}: only the human owner records {keys[0].split(':')[0]}"
    if REVIEWED.search(current) and not any(REVIEWED.search(old) and not REVIEWED.search(new) for old, new in edits):
        return f"{path}: the note is reviewed; set its status to draft in the same edit, because any edit returns a note to draft"
    return None


def check_write(path, content):
    current = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    if REVIEWED.search(content):
        return f"{path}: only the human owner sets status: reviewed"
    keys = added_keys(current, content)
    if keys:
        return f"{path}: only the human owner records {keys[0].split(':')[0]}"
    return None


def check(call):
    """The reason to block a tool call, or None."""
    tool, data = call.get("tool_name", ""), call.get("tool_input") or {}
    path = data.get("file_path") or data.get("notebook_path") or ""
    if tool == "Write" and guarded(path):
        return check_write(path, data.get("content", ""))
    if tool == "Edit" and guarded(path):
        return check_edits(path, [(data.get("old_string", ""), data.get("new_string", ""))])
    if tool == "MultiEdit" and guarded(path):
        return check_edits(path, [(e.get("old_string", ""), e.get("new_string", "")) for e in data.get("edits", [])])
    if tool in ("Bash", "PowerShell"):
        command = data.get("command", "")
        if TOKENS.search(command) and WRITES.search(command) and re.search(r"wiki|synthetic", command):
            return "the command may write status: reviewed, reviewedBy or lastReviewed into a note, which only the human owner does"
    return None


def main():
    try:
        call = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return
    reason = check(call)
    if reason:
        sys.stderr.write(reason + "\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
