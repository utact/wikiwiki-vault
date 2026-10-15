"""Fail if a staged file contains a value from .env.

Usage:
    uv run python -X utf8 scripts/secret_scan.py
"""

import subprocess
import sys

import lawlib as L


def staged():
    names = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"],
        cwd=L.VAULT, capture_output=True, check=True,
    ).stdout.decode("utf-8").split("\0")
    return [n for n in names if n]


def main():
    secrets = [s.encode("utf-8") for s in L.secrets()]
    found = []
    for name in staged():
        content = subprocess.run(["git", "show", f":{name}"], cwd=L.VAULT, capture_output=True, check=True).stdout
        if any(s in content for s in secrets):
            found.append(name)
    for name in found:
        print(f"secret value in staged file: {name}", file=sys.stderr)
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
