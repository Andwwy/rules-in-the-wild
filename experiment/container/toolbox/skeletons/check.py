#!/usr/bin/env python3
"""<rule id>: <the rule>.   check.py FILE ...   or   check.py - < TEXT
Exit 0: the target follows the rule. Exit 1: each violation on stderr (where, and what to change)."""
import sys

def problems(text: str, where: str) -> list[str]:
    out = []
    # <the rule>: out.append(f"{where}:<line>: <what breaks the rule>; <what to change>")
    return out

if sys.argv[1:] == ["-"]:
    items = [(sys.stdin.read(), "the text")]
else:
    items = [(open(f, encoding="utf-8", errors="replace").read(), f) for f in sys.argv[1:]]
found = [p for text, where in items for p in problems(text, where)]
print("\n".join(found), file=sys.stderr)
sys.exit(1 if found else 0)
