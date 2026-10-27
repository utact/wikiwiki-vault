"""Coverage of the statutes in scope: the articles that wiki notes cite and those they do not, by chapter.

The scope is `coverage` in scripts/sources.yaml: the chapters and articles of each law, and the articles left out with a reason.
It also takes in every article of a lower law that receives a delegation from an article in scope, by the 위임조문 data of 법제처.
An article counts as covered when a wiki note other than a statute note links to it or to one of its blocks.
"""

import argparse
import re

import lawlib as L
import statutes as S

LABEL = re.compile(r"제(\d+)(조|장)(?:의(\d+))?")
LINK = re.compile(r"\[\[([^\]|#]+)")


def key_of(label):
    """Unit key of a label such as 제10조의2 or 제5장의2."""
    match = LABEL.fullmatch(label)
    if not match:
        raise ValueError(f"unknown unit {label}")
    if match[2] == "조":
        return L.article_key(match[1], match[3])
    return "heading-ch" + match[1] + (f"-{match[3]}" if match[3] else "")


DELETED = re.compile(r"제\d+조(?:의\d+)?\s*삭제")


def articles(law):
    """Keys of the articles of the current version, without deleted ones such as 제39조 삭제 <2019. 8. 27.>."""
    return [key for key, (kind, row) in law.rows_of(law.current).items()
            if kind == "article" and not (not row.get("조문제목") and DELETED.match(row.get("조문내용", "")))]


def scope(statutes, config):
    """Articles in scope as a set of (law, key), and the articles left out as {(law, key): reason}."""
    chosen, left_out = set(), {}
    for name, entry in config.items():
        law = statutes.laws[name]
        keys = {key_of(label) for label in entry.get("units", [])}
        for label, reason in (entry.get("exclude") or {}).items():
            left_out[name, key_of(label)] = reason
        for key in articles(law):
            if key in keys or any(unit.key in keys for unit in S.Unit(law, key).ancestors()):
                chosen.add((name, key))
    chosen -= set(left_out)
    changed = True
    while changed:
        changed = False
        for (lower, key), uppers in statutes.delegations.items():
            if (lower, key) in chosen or (lower, key) in left_out or lower not in statutes.laws:
                continue
            if key not in articles(statutes.laws[lower]):
                continue
            for upper, provision in uppers:
                try:
                    upper_key = S.provision_block(provision)[0]
                except ValueError:
                    continue
                if (upper, upper_key) in chosen:
                    chosen.add((lower, key))
                    changed = True
                    break
    return chosen, left_out


def citations(statutes, wiki):
    """The notes that link each unit, as {(law, key): set of note names}, from every note but statute notes."""
    found = {}
    for path in sorted(wiki.rglob("*.md")):
        if path.parent.name in ("LegalResource", "LegalResourceSubdivision"):
            continue
        for name in set(LINK.findall(path.read_text(encoding="utf-8"))):
            unit = statutes.unit_named(name.strip())
            if unit is not None:
                found.setdefault((unit.law.name, unit.key), set()).add(path.stem)
    return found


def chapter(law, key):
    """The 장 that holds an article, or None for an article outside any 장."""
    headings = [unit for unit in S.Unit(law, key).ancestors() if unit.kind == "heading"]
    return headings[-1] if headings else None


def report(statutes, config, wiki, every=False):
    """Lines that count the cited articles in scope by law and 장, and list the others."""
    chosen, left_out = scope(statutes, config)
    cited = citations(statutes, wiki)
    lines, total, covered = [], 0, 0
    for name in config:
        law = statutes.laws[name]
        keys = [key for key in articles(law) if (name, key) in chosen]
        done = [key for key in keys if (name, key) in cited]
        total, covered = total + len(keys), covered + len(done)
        lines.append(f"{name}: {len(done)}/{len(keys)}")
        groups = {}
        for key in keys:
            heading = chapter(law, key)
            groups.setdefault(f"{heading.number} {heading.title}" if heading else "장 밖", []).append(key)
        for title, group in groups.items():
            lines.append(f"  {title}: {sum(1 for key in group if (name, key) in cited)}/{len(group)}")
            for key in group:
                if every or (name, key) not in cited:
                    unit = S.Unit(law, key)
                    mark = "o" if (name, key) in cited else "-"
                    lines.append(f"    {mark} {unit.number}" + (f" {unit.title}" if unit.title != unit.number else ""))
    lines.append(f"total: {covered}/{total}")
    if left_out:
        lines.append("left out:")
        for (name, key), reason in left_out.items():
            lines.append(f"  {S.Unit(statutes.laws[name], key).name}: {reason}")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="list the cited articles too")
    args = parser.parse_args()
    as_of, _ = L.release()
    statutes = S.Statutes(as_of)
    print("\n".join(report(statutes, S.SOURCES["coverage"], S.WIKI, args.all)))


if __name__ == "__main__":
    main()
