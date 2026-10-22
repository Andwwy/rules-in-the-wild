"""Map every policy rule of every task onto the enforcer, trigger and target trees, with the Jev classifier in
`rules in the wild/jev mapping/classifier/` (tree_classifier.py).

    python scripts/map_rules.py                     every task in tasks/, every axis (rules already mapped are kept)
    python scripts/map_rules.py --redo              map all rules again
    python scripts/map_rules.py --tasks 46,91 --axes trigger,target
    python scripts/map_rules.py --tasks 91 --select           the route by beam select: one call per rule

The input is MTAC's own rule data (design_process.md, point 6): each rule's text, with MTAC's category as `context` (no
assigner wording: MTAC's rules have none). The result goes into tasks/<task>/rules.json, one field per axis:
`mapping` (enforcer), `mapping_trigger` and `mapping_target`: the leaf, the path, its score, the separation from the
next path, the alternatives (the rest of the beam), and for the trigger the `timing` (the trigger tree's last level,
under each event: before / at / after; Always's is always) and `state_p` attributes. The trigger tree keeps only the
events and timings that can run here (runnable).
Arm C gets the three (design_process.md, point 36).

`--select` is the beam select that makes the routed arm's route (design_process.md, points 78, 93, 94, 96): each
axis's BEAM candidates (the leaf and the rest of the beam), a trigger candidate being an event with its timing (the
timing belongs to the event: the trigger tree's last level), make BEAM³ plans (64), sent in one call with the plans in
an order shuffled by the rule; the plan it picks is the route. The call goes into jev_plan.json under "select"; the
plan goes into rules.json as `route` (the enforcer, trigger and target paths and the timing, with the pick's
probability and its separation from the next plan), which build_tasks.py gives arm C. The earlier modes (--repeat,
--compare, --plan, --shuffle; points 63, 64) are in archive/map-rules-modes-2026-10-21/.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
import paths                                      # noqa: E402

paths.use("jev")
import tree_classifier                                     # noqa: E402
import plan_select                                         # noqa: E402

FIELD = {"enforcer": "mapping", "trigger": "mapping_trigger", "target": "mapping_target"}
PLAN = "jev_plan.json"
BEAM = 4                                          # candidates per axis, and the tree classifier's beam (point 93)


def candidates(rule: dict) -> dict[str, list]:
    """Each axis's BEAM candidates: the leaf and the rest of the beam (point 94). A trigger candidate is its event with
    its timing ({"path", "timing"}; point 93)."""
    out = {}
    for axis, f in FIELD.items():
        m = rule[f]
        found = [{"path": m["path"], "timing": (m.get("attributes") or {}).get("timing")}] + \
                [{"path": a["path"], "timing": a.get("timing")} for a in m["alternatives"]]
        out[axis] = found[:BEAM] if axis == "trigger" else [c["path"] for c in found[:BEAM]]
    return out


def timings_for(runs: dict[str, set[str]], trigger: list[str]) -> list[str]:
    """The timings at which an event can run here (runnable): the trigger tree keeps only these under it."""
    return [t for t in ("before", "at", "after") if t in runs.get(" › ".join(trigger), set())]


def trees_of(axes) -> dict:
    """The trees of the axes; the trigger tree with only the events and timings that can run here (point 93)."""
    runs = runnable()
    return {a: tree_classifier.tree_of(a, (lambda path: timings_for(runs, path)) if a == "trigger" else None)
            for a in axes}


TIMINGS = re.compile(r"^- ((?:before|at|after)(?:, (?:before|at|after))*):", re.M)


def runnable() -> dict[str, set[str]]:
    """The timings at which each trigger can run here: the rows of its node in the toolbox (`- before, at: …`). A node
    that says `not here` has none; Other (`any mechanism above`) has every one."""
    out = {}
    for f in (paths.TOOLBOX / "triggers").rglob("*.md"):
        text = f.read_text(encoding="utf-8")
        head = text.splitlines()[0].lstrip("# ").strip()
        out[head] = ({"before", "at", "after"} if "any mechanism above" in text
                     else {t for row in TIMINGS.findall(text) for t in row.split(", ")})
    return out


def select(folders: list[Path], client) -> None:
    """The beam select (`--select`; points 78, 93, 96): one Jev call per rule over its BEAM³ plans (candidates: a
    trigger with its timing), the plans in an order shuffled by the rule; the route is the plan it picks. Writes
    jev_plan.json["select"] and rules.json's `route`."""
    jobs = [(folder, r) for folder in folders for r in json.loads((folder / "rules.json").read_text())]

    def one(job):
        folder, rule = job
        return plan_select.select_plan(rule["constraint"], candidates(rule), {"mtac_category": " / ".join(rule["tags"])},
                                       client=client, shuffle=f"{folder.name} R{rule['item']} select")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, jobs))
    for folder in folders:
        picks = {rule["item"]: res for (f, rule), res in zip(jobs, results) if f == folder}
        rules = json.loads((folder / "rules.json").read_text())
        path = folder / PLAN
        data = json.loads(path.read_text()) if path.exists() else {}
        data["select"] = {}
        for rule in rules:
            res = picks[rule["item"]]
            route = {a: res[a] for a in ("enforcer", "trigger", "timing", "target")}
            data["select"][str(rule["item"])] = {
                "route": route, "p": res["p"], "separation": res["separation"], "top": res["all"][:4],
                "options": res["options"], "candidates": res["candidates"], "shuffle": res["shuffle"],
                "cost_usd": res["cost_usd"], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            rule["route"] = {**route, "by": "beam select", "p": res["p"], "separation": res["separation"]}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        (folder / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(jobs)} calls in {len(folders)} tasks, ${sum(r['cost_usd'] for r in results):.4f}")
    for folder in folders:
        for rule in json.loads((folder / "rules.json").read_text()):
            rt, m = rule["route"], rule
            call1 = (m["mapping"]["path"][-1], m["mapping_trigger"]["path"][-1],
                     (m["mapping_trigger"].get("attributes") or {}).get("timing"), m["mapping_target"]["path"][-1])
            now = (rt["enforcer"][-1], rt["trigger"][-1], rt["timing"], rt["target"][-1])
            print(f"  {folder.name} R{rule['item']}: {' · '.join(map(str, now))}  p {rt['p']:.2f}, separation "
                  f"{rt['separation']}" + ("" if now == call1 else f"   (call 1: {' · '.join(map(str, call1))})"))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--tasks", help="comma-separated task ids (default: every task folder)")
    p.add_argument("--redo", action="store_true")
    p.add_argument("--axes", default="enforcer,trigger,target", help="comma-separated: enforcer, trigger, target")
    p.add_argument("--select", action="store_true", help="the route by beam select: one call per rule")
    args = p.parse_args()
    axes = args.axes.split(",")
    folders = sorted(paths.TASKS.glob("*-task-*"))
    if args.tasks:
        folders = [paths.task_dir(int(t)) for t in args.tasks.split(",")]
    if args.select:
        return select(folders, tree_classifier._client())
    trees, client = trees_of(axes), tree_classifier._client()
    jobs = []
    for folder in folders:
        path = folder / "rules.json"
        rules = json.loads(path.read_text())
        jobs += [(path, rules, r, a) for r in rules for a in axes if args.redo or not r.get(FIELD[a])]

    def one(job):
        _, _, rule, axis = job
        rule[FIELD[axis]] = tree_classifier.classify(axis, rule["constraint"],
                                                     {"mtac_category": " / ".join(rule["tags"])},
                                                     tree=trees[axis], client=client, beam=BEAM)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(one, jobs))
    written = {}
    for path, rules, _, _ in jobs:
        written[path] = rules
    for path, rules in written.items():
        path.write_text(json.dumps(rules, ensure_ascii=False, indent=1) + "\n")
    cost = sum(r[FIELD[a]]["cost_usd"] for _, _, r, a in jobs)
    print(f"{len(jobs)} mappings ({len({id(r) for _, _, r, _ in jobs})} rules, axes {', '.join(axes)}) in "
          f"{len(written)} tasks, ${cost:.4f}")
    for path in written:
        for r in json.loads(path.read_text()):
            for a in axes:
                m = r.get(FIELD[a]) or {}
                t = (m.get("attributes") or {}).get("timing")
                print(f"  {path.parent.name} #{r['item']} {a:8s} {' > '.join(m.get('path') or []):<45} "
                      f"{m.get('score', 0):.2f}  sep {m.get('separation')}{f'  timing {t}' if t else ''}")


if __name__ == "__main__":
    main()
