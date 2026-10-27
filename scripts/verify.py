"""Prepare and record the verification of wiki notes by a separate agent.

Usage:
    uv run python -X utf8 scripts/verify.py context NOTE...
    uv run python -X utf8 scripts/verify.py record --model MODEL --effort EFFORT --session ID NOTE...

NOTE is a note name. context prints what the verifier reads: each note, the text of every statute block its links cite, the raw notes and the decision record it links, and the wiki notes that link to or from it.
record appends a ledger line for each draft note and sets its status to verified. The line holds the hash of the note without status, reviewedBy and lastReviewed, the ledger hash of every statute block the note links, and the verifier's model, effort and session.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import lawlib as L
import lint as T

LEDGER = Path("ontology") / "verification.jsonl"


def links(note):
    """(name, block or None) of every wikilink in a note, in order."""
    return [(name.strip(), block or None) for _, name, block, _ in T.LINK.findall(note.text)]


def statute_hashes(linter):
    """Ledger hash of each statute block, keyed as <note>#^<block>."""
    found = {}
    for note in linter.wiki():
        if note.statute:
            entry = linter.ledger.get(note.meta.get("identifier")) or {}
            for block, digest in entry.get("blocks", {}).items():
                found[f"{note.stem}#^{block}"] = digest
    return found


def cited_blocks(linter, note):
    """Statute blocks that the links of a note name, without repeats."""
    found = []
    for name, block in links(note):
        target = linter.notes.get(name)
        if target and target.statute and block and (name, block) not in found:
            found.append((name, block))
    return found


def fenced(text, language):
    return [f"````{language}", text.rstrip("\n"), "````", ""]


def context(linter, names):
    """The verifier's reading for a set of notes, as Markdown: the notes, then each cited block, raw note and linked note once."""
    out, blocks, raw, linked = [], {}, {}, set()
    for name in names:
        note = linter.notes[name]
        cited = cited_blocks(linter, note)
        out += [f"# {name}", "", f"File: `{note.where}`", ""] + fenced(note.text, "markdown")
        out += ["Cited blocks: " + (", ".join(f"{target}#^{block}" for target, block in cited) or "none"), ""]
        blocks.update(dict.fromkeys(cited))
        for target in dict.fromkeys(n for n, _ in links(note)):
            other = linter.notes.get(target)
            if other and other.folder in ("raw", "docs"):
                raw[target] = other
            elif other and other.folder == "wiki" and not other.statute and target not in names:
                linked.add(target)
        linked |= {other.stem for other in linter.authored() if other.stem not in names and any(n == name for n, _ in links(other))}
    if blocks:
        out += ["# Cited statute blocks", ""]
        for target, block in blocks:
            text = linter.notes[target].blocks.get(block)
            out += [f"## Cited block {target}#^{block}", ""] + fenced(text[0] if text else "(the note declares no such block)", "text")
    if raw:
        out += ["# Linked raw notes and decision record", ""]
        for target, other in raw.items():
            out += [f"## {target}", ""] + fenced(other.text, "markdown")
    if linked:
        out += ["# Notes that link to or from these notes", ""]
        for target in sorted(linked):
            out += [f"## {target}", "", f"File: `{linter.notes[target].where}`", ""] + fenced(linter.notes[target].text, "markdown")
    return "\n".join(out)


def record(linter, root, names, model, effort, session):
    """Append a ledger line per note and set the notes to verified, after checking every note first."""
    hashes, entries = statute_hashes(linter), []
    for name in names:
        note = linter.notes.get(name)
        if note is None or note.folder != "wiki" or note.statute:
            sys.exit(f"{name}: not a wiki note written by the LLM")
        if note.meta.get("status") != "draft":
            sys.exit(f"{name}: status is {note.meta.get('status')}, not draft")
        blocks = {}
        for target, block in cited_blocks(linter, note):
            key = f"{target}#^{block}"
            if key not in hashes:
                sys.exit(f"{name}: the ledger has no hash for {key}")
            blocks[key] = hashes[key]
        entries.append((note, {"identifier": note.meta["identifier"], "note": L.note_hash(note.text), "blocks": blocks,
                               "model": model, "effort": effort, "session": session}))
    for note, _ in entries:
        note.path.write_text(re.sub(r"^status: draft$", "status: verified", note.text, count=1, flags=re.M), encoding="utf-8", newline="\n")
    with (Path(root) / LEDGER).open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(json.dumps(entry, ensure_ascii=False) + "\n" for _, entry in entries))
    return [entry for _, entry in entries]


def main():
    if not sys.flags.utf8_mode:
        sys.exit("Run with python -X utf8.")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=str(L.VAULT))
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("context")
    show.add_argument("notes", nargs="+")
    write = commands.add_parser("record")
    write.add_argument("--model", required=True)
    write.add_argument("--effort", required=True)
    write.add_argument("--session", required=True)
    write.add_argument("notes", nargs="+")
    args = parser.parse_args()
    linter = T.Linter(args.root)
    missing = [name for name in args.notes if name not in linter.notes]
    if missing:
        sys.exit(f"no such note: {', '.join(missing)}")
    if args.command == "context":
        print(context(linter, args.notes))
    else:
        entries = record(linter, args.root, args.notes, args.model, args.effort, args.session)
        print(f"{len(entries)} notes verified")


if __name__ == "__main__":
    main()
