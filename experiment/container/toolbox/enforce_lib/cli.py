"""The `enforce` command: installs tested tools (enforce_lib/recipes.py; README.md, Install).

  enforce install NAME ...      install tools by their recipes (pinned versions, a smoke test at the end)
  enforce install --list        the recipes, and which are installed
"""
from __future__ import annotations

from . import recipes


def main(argv: list[str]) -> int:
    if argv[:1] == ["install"] and argv[1:] == ["--list"]:
        print(recipes.describe())
        return 0
    if argv[:1] == ["install"] and argv[1:]:
        return max(recipes.install(x) for x in argv[1:])
    print(__doc__)
    return 0 if argv[:1] in ([], ["help"], ["-h"], ["--help"]) else 2
