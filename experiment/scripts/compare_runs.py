"""Compare scored runner runs of one task: compliance per policy rule, per arm (after score_runs.py).

    python3 scripts/compare_runs.py agents/haiku-4.5_claude-code-2.1.199/runs/MTAC-task-46/A/<run> agents/haiku-4.5_claude-code-2.1.199/runs/MTAC-task-46/B/<run> agents/haiku-4.5_claude-code-2.1.199/runs/MTAC-task-46/C/<run>

Only the policy rules count (`rules.json`, R1..Rn: the project's CLAUDE.md); a turn's own request, which can change from
turn to turn (task 91's indentation), is not scored (design_process.md, point 110). For each rule: the turns in which
its checker passed, out of the turns in which it was scored. Also the policy rules together, and each run's cost from
the spend ledger (phase 0 and the task apart). Prints a Markdown table.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
import paths                                             # noqa: E402


def cost(label: str) -> tuple[float, float]:
    s1 = task = 0.0
    for r in paths.ledger_rows():
        run = r.get("run") or ""
        if run == f"{label}/translation":
            s1 += r.get("cost") or 0
        elif run == label:
            task += r.get("cost") or 0
    return s1, task


def main(argv: list[str]) -> None:
    runs = [Path(a).resolve() for a in argv]
    infos = [paths.run_info(r) for r in runs]
    rules = json.loads((paths.task_dir(infos[0]["task"]) / "rules.json").read_text(encoding="utf-8"))
    rule_of = {r["constraint"].strip(): f"R{r['item']}" for r in rules}
    table, totals = {}, {}
    names = [i["arm"] for i in infos]
    for run, info in zip(runs, infos):
        arm = info["arm"]
        if names.count(arm) > 1:                          # two runs of one arm: one column each
            arm = f"{arm} {run.name[4:8]}T{run.name[9:13]}"
        scores = json.loads((run / "script_scores.json").read_text(encoding="utf-8"))
        t = totals.setdefault(arm, {"policy": [0, 0]})
        for rnd in scores["rounds"]:
            for item in rnd["items"]:
                if item["passed"] is None:
                    continue
                key = rule_of.get(item["requirement"].strip())
                if key is None:                           # a turn's own request: not scored (point 110)
                    continue
                cell = table.setdefault(key, {}).setdefault(arm, [0, 0])
                cell[0] += item["passed"] is True
                cell[1] += 1
                t["policy"][0] += item["passed"] is True
                t["policy"][1] += 1
        t["cost"] = cost(info["label"])
    arms = list(totals)
    print("| item | " + " | ".join(arms) + " |")
    print("|---|" + "---|" * len(arms))
    text = {f"R{r['item']}": r["constraint"] for r in rules}
    for key in sorted(table, key=lambda k: int(k[1:])):
        print(f"| {key} {text[key][:24]} | " + " | ".join(f"{table[key][a][0]}/{table[key][a][1]}" if a in table[key] else "–" for a in arms) + " |")
    print("| **policy rules** | " + " | ".join(
        f"**{totals[a]['policy'][0]}/{totals[a]['policy'][1]}** ({100 * totals[a]['policy'][0] / max(1, totals[a]['policy'][1]):.0f}%)" for a in arms) + " |")
    print("| cost: phase 0 + task | " + " | ".join(
        f"${totals[a]['cost'][0]:.2f} + ${totals[a]['cost'][1]:.2f}" for a in arms) + " |")
    for k, r in text.items():
        if k not in table:
            print(f"\n{k} ({r[:30]}) has no checker script: not scored.")


if __name__ == "__main__":
    main(sys.argv[1:])
