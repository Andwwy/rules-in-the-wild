"""Why each policy rule passed or failed, turn by turn: by the enforcement or by the model alone (design_process.md, points 60,
73, 79). A pass is the enforcement's when the enforcement of that rule fired in that turn; otherwise it is the model's.

    uv run --project "dataset/MTAC bench/base agent" python scripts/attribute_passes.py <run> [<run> ...]

The enforcement of a rule fired in a turn when, during that turn, any of these names the rule:
  - a hook's violation in the harness's log (a block, a refusal, a stop, or "gave up" after the limit); the rule of each
    hook comes from trajectory_viewer.py (hook_rules), or from the hook's own message (R<n>);
  - a refusal that the agent met: a tool result that failed and names the rule (R<n>), from a command wrapper, a policy
    gate, a git hook or any other mechanism.
Each (rule, turn) that MTAC's checker scored is one of:
  fixed      passed, and the enforcement of that rule fired in that turn
  alone      passed, and it did not fire: the model complied by itself (a yellow ✓ in the viewer)
  not fixed  failed although the enforcement of that rule fired in that turn
  missed     failed, and it did not fire
Arm A has no enforcement: all its passes are "alone". A refusal that names no rule (a bare "Permission denied") is not
counted. Nothing is asked of phase 0 for this: the harness's log and the agent's trajectory are the evidence
(point 79).
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

import trajectory_viewer as tv                             # noqa: E402

KINDS = ("fixed", "alone", "not fixed", "missed")
RULE = re.compile(r"\bR(\d+)\b")


def fired(t: dict, of_rule: dict[str, set[str]]) -> set[str]:
    """The rules whose enforcement fired in one turn."""
    out = set()
    for rid, hooks in of_rule.items():
        if any(sum(t["by_hook"].get(n, {}).get(v, 0) for v in ("block", "deny", "gave up", "stop")) for n in hooks):
            out.add(rid)
    for e in t["events"]:
        if e.get("k") == "hook" and e.get("verdict") not in ("error", "hook_success"):
            out |= {f"R{m}" for m in RULE.findall(e.get("msg") or "")}
        elif e.get("k") == "tool" and e.get("error"):
            out |= {f"R{m}" for m in RULE.findall(e.get("result") or "")}
    return out


def attribute(d: dict) -> dict[str, Counter]:
    hooks = (d["phase0"] or {}).get("install", {}).get("hooks", []) if d.get("phase0") else []
    of_rule: dict[str, set[str]] = {}
    for h in hooks:
        if h.get("rule"):
            of_rule.setdefault(h["rule"], set()).add(str(h["n"]))
    out: dict[str, Counter] = {}
    for t in d["task_part"]["turns"]:
        hit = fired(t, of_rule)
        for s in t["scores"]:
            rid = s.get("rule")
            if not rid or s["passed"] is None:
                continue
            kind = ("fixed" if rid in hit else "alone") if s["passed"] else ("not fixed" if rid in hit else "missed")
            out.setdefault(rid, Counter())[kind] += 1
    return out


def main(argv: list[str]) -> None:
    rows = []
    for a in argv:
        d = tv.load(Path(a).resolve())
        rows.append((f"{d['task']} {d['arm']}", attribute(d)))
    rules = sorted({r for _, att in rows for r in att}, key=lambda r: int(r[1:]))
    print("| run | " + " | ".join(KINDS) + " | per rule: fixed/alone of passes |")
    print("|---|" + "---|" * (len(KINDS) + 1))
    for name, att in rows:
        tot = sum(att.values(), Counter())
        per = " ".join(f"{r} {att[r]['fixed']}/{att[r]['alone']}" for r in rules if r in att)
        print(f"| {name} | " + " | ".join(str(tot[k]) for k in KINDS) + f" | {per} |")


if __name__ == "__main__":
    main(sys.argv[1:])
