"""Write one folder per task: everything a run needs, free of any model or agent (paths.py, Layout).

    python scripts/build_tasks.py                 the 5 tasks with the most script-checked policy rules (design_process.md, point 4)
    python scripts/build_tasks.py --top 100       every task, ranked the same way
    python scripts/build_tasks.py --tasks 46,91   these tasks

    tasks/<task>/
        README.md                 the task: category, turns, its policy rules
        data/questions.jsonl      the MTAC task, each turn's checklist cut to the items with a checker script (held
                                  out: holds checker code)
        rules.json                MTAC's policy rules (text and tags, no checker code), with Jev's enforcer, trigger
                                  and target for each (`mapping`, `mapping_trigger`, `mapping_target`;
                                  map_rules.py), and the pilot's expert translation (`mechanism`, a record)
        hidden_fixtures.json      held-out cases that score phase 0's enforcement for this task (score_phase0.py):
                                  written by hand, not by this script, which keeps them and notes
                                  them in README.md
        arms/<arm>/translation/   phase 0's inputs: system.md (prompts/system.md and the arm's parts) and
                                  messages.json (one message with all the rules, prompts/rule_B.md or rule_C.md for
                                  each; C also gets each rule's route from rules.json and the leaf's card, its node in
                                  the toolbox); C's toolbox.json: the part of the toolbox its routes use (the files and
                                  the install recipes; point 97). Arm A has no phase 0.

Scored scope (design_process.md, point 5: policy rules only): a turn's checklist keeps only the items that re-check a policy rule
(same constraint text) and ship a checker script. Ranking counts those items over all turns.
Rebuilding keeps rules.json's mapping fields, the beam select's route, mechanism and constraint_en (English translation).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import paths
from build_graph import leaf_file

EXP = paths.EXP
MTAC = paths.MTAC_DATA
TASKS = EXP / "tasks"

# the sources of phase 0's inputs: the system prompt's parts and the rule templates
TRANSLATION = EXP / "prompts"

def scored(task: dict) -> tuple[dict, int]:
    """The task with each turn's checklist cut to script-checked policy rules, and how many items remain (used to rank
    the tasks for selection, design_process.md point 4; the task data keeps every item)."""
    policy = {c["constraint"].strip() for c in task["repository_policy_checklist"]}
    out, n = json.loads(json.dumps(task)), 0
    for rnd in out["rounds"]:
        rnd["instruction_following_checklist"] = [
            c for c in rnd["instruction_following_checklist"]
            if c["constraint"].strip() in policy and c["validation_code"].strip()]
        n += len(rnd["instruction_following_checklist"])
    return out, n


def script_items(task: dict) -> dict:
    """The task with each turn's checklist cut to the items that ship a checker script (any item, policy or not)."""
    out = json.loads(json.dumps(task))
    for rnd in out["rounds"]:
        rnd["instruction_following_checklist"] = [c for c in rnd["instruction_following_checklist"] if c["validation_code"].strip()]
    return out


def write_task(task: dict) -> int:
    tid = task["task_id"]
    folder = paths.task_dir(tid)
    _, n = scored(task)
    data = script_items(task)                                # the items with a checker script (point 26)
    (folder / "data").mkdir(parents=True, exist_ok=True)
    (folder / "data" / "questions.jsonl").write_text(json.dumps(data, ensure_ascii=False) + "\n")

    rules_path = folder / "rules.json"
    old = {r["item"]: r for r in json.loads(rules_path.read_text())} if rules_path.exists() else {}
    rules = []
    for k, c in enumerate(task["repository_policy_checklist"], 1):
        keep = old.get(k, {})
        rules.append({"item": k, "constraint": c["constraint"], "tags": c["tags"],
                      "scored": bool(c["validation_code"].strip()),
                      "mapping": keep.get("mapping"), "mapping_trigger": keep.get("mapping_trigger"),
                      "mapping_target": keep.get("mapping_target"),
                      **({"route": keep["route"]} if keep.get("route") else {}), "mechanism": keep.get("mechanism"),
                      **({"constraint_en": keep["constraint_en"]} if keep.get("constraint_en") else {})})
    rules_path.write_text(json.dumps(rules, ensure_ascii=False, indent=1) + "\n")
    write_translation_arms(folder, tid, rules)

    lines = [f"# Task {tid}", "", f"{task.get('task_category')}, {len(task['rounds'])} turns, {n} scored checks "
             f"(policy rules with a checker script, summed over turns).", "",
             "| item | policy rule | MTAC category | scored |", "|---|---|---|---|"]
    lines += [f"| {r['item']} | {r['constraint']} | {' / '.join(r['tags'])} | {'yes' if r['scored'] else 'no'} |"
              for r in rules]
    lines += ["", "The policy file the agent gets (`CLAUDE.md`):", "", "```", task["repository_policy"], "```", ""]
    if (folder / "hidden_fixtures.json").exists():
        lines += ["## Held-out cases", "",
                  "`hidden_fixtures.json` holds the cases that score phase 0's enforcement for this task "
                  "(`scripts/score_phase0.py`, through the agent's hooks; design_process.md, point 86). They are written by hand from these rules' text only, not from "
                  "MTAC's checker code, and no agent sees them. They belong to this task: another task gets its own, "
                  "and a new run of this task uses these, not new ones.", ""]
    (folder / "README.md").write_text("\n".join(lines))
    return n


TOOLBOX_AT = "/opt/enforce-toolbox"
LINK = re.compile(TOOLBOX_AT + r"/([^\s),;]+)")
INSTALL = re.compile(r"`enforce install ([\w-]+)`|install: `([\w-]+)`(?:, `([\w-]+)`)?")
TIMINGS = ("before", "at", "after")


def node_lines(kind: str, path: list[str], timing: str | None = None) -> tuple[str, list[str]]:
    """A route leaf's node in the toolbox (its file, and its lines below the title). A trigger's node keeps only the row
    of the route's timing (`- before, at: …`); with `always` (the trigger Always), every row."""
    rel = leaf_file(kind, " › ".join(path))
    lines = (paths.TOOLBOX / rel).read_text(encoding="utf-8").splitlines()[1:]
    if kind == "triggers" and timing in TIMINGS:
        def other_timing(line):
            m = re.match(r"- ([\w ,]+):", line)
            keys = [k.strip() for k in m[1].split(",")] if m else []
            return bool(keys) and set(keys) <= set(TIMINGS) and timing not in keys
        lines = [line for line in lines if not other_timing(line)]
    return rel, lines


def card(kind: str, path: list[str], timing: str | None = None) -> str:
    """Arm C's card for a route leaf, as sent to the agent (`# <Kind> card: <leaf> (<path>)`): its node in the toolbox
    (design_process.md, point 72), a trigger's with only the route's timing (point 97)."""
    rel, lines = node_lines(kind, path, timing)
    return (f"# {kind[:-1].capitalize()} card: {path[-1]} ({' › '.join(path)})\n\n(node: {TOOLBOX_AT}/{rel})\n"
            + "\n".join(lines).strip())


def route_share(routes: list[dict]) -> dict:
    """The part of the toolbox that the routes use (point 97): each route leaf's node (a trigger's row of the route's
    timing), every file its lines link to but the nearest other leaves (mechanisms, skeletons, the nodes it builds on),
    the skeletons that those files link to, and the install recipes named on the way, with the recipes they need."""
    sys.path.insert(0, str(paths.TOOLBOX))
    from enforce_lib.recipes import RECIPES
    files, recipes, hop1 = set(), set(), set()

    def follow(lines, into, only_skeletons):
        for line in lines:
            if re.match(r"- nearest:", line):
                continue
            recipes.update(x for m in INSTALL.findall(line) for x in m if x)
            for rel in LINK.findall(line):
                rel = rel.rstrip(".")
                if (paths.TOOLBOX / rel).is_file() and (not only_skeletons or rel.startswith("skeletons/")):
                    into.add(rel)
    for rt in routes:
        for kind, key in (("enforcers", "enforcer"), ("triggers", "trigger"), ("targets", "target")):
            rel, lines = node_lines(kind, rt[key], rt["timing"])
            files.add(rel)
            follow(lines, hop1, False)
    for rel in sorted(hop1 - files):
        follow((paths.TOOLBOX / rel).read_text(encoding="utf-8").splitlines(), files, True)
    files |= hop1
    todo = list(recipes)
    while todo:                                       # what `enforce install` installs first
        r = RECIPES[todo.pop()]
        for dep in r.get("needs", []) + (["node"] if "npm" in r else []) + (["rust"] if "cargo" in r else []):
            if dep not in recipes:
                recipes.add(dep)
                todo.append(dep)
    return {"files": sorted(files), "recipes": sorted(recipes)}


# arm -> (message template, the system prompt's parts after system.md): B the rules only; C the rules with their
# routes, a card for each leaf, and the toolbox (design_process.md, points 60, 96)
ARMS = {"B": ("B", []), "C": ("C", ["system_route.md", "system_toolbox.md"])}


def write_translation_arms(folder: Path, tid: int, rules: list[dict]) -> None:
    """Arms B and C (design_process.md, point 96): phase 0 gets one system prompt (prompts/system.md, with the arm's
    opening and parts) and one message that holds all the task's rules, in the file's order (prompts/batch.md, then
    rule_B.md or rule_C.md for each). B gets each rule only; C also gets its route, the beam select's (rules.json
    `route`; map_rules.py --select), and the card of each enforcer, trigger (with its timing) and target the first time
    it comes. Written to tasks/<task>/arms/<arm>/translation/: system.md, messages.json, and for C toolbox.json (the
    toolbox's share for its routes, route_share; point 97)."""
    system = (TRANSLATION / "system.md").read_text()
    opening = dict(line.split(": ", 1) for line in (TRANSLATION / "opening.md").read_text().splitlines() if line.strip())
    header = dict(line.split(": ", 1) for line in (TRANSLATION / "batch.md").read_text().splitlines() if line.strip())
    for arm, (base, parts) in ARMS.items():
        template = (TRANSLATION / f"rule_{base}.md").read_text()
        blocks, seen = [], set()
        for r in rules:
            fill = {"id": f"R{r['item']}", "rule": r["constraint"].strip()}
            if base == "C":
                rt = r.get("route")
                if not rt:
                    raise SystemExit(f"task {tid}, rule {r['item']}: no route (map_rules.py --select)")
                leaves = [("enforcers", rt["enforcer"], None), ("triggers", rt["trigger"], rt["timing"]),
                          ("targets", rt["target"], None)]
                details = [card(kind, path, timing) for kind, path, timing in leaves if (kind, tuple(path), timing) not in seen]
                seen.update((kind, tuple(path), timing) for kind, path, timing in leaves)
                fill |= {"enforcer": rt["enforcer"][-1], "enforcer_path": " › ".join(rt["enforcer"]),
                         "trigger": rt["trigger"][-1], "trigger_path": " › ".join(rt["trigger"]),
                         "timing": f", timing: {rt['timing']}", "target": rt["target"][-1],
                         "target_path": " › ".join(rt["target"]), "details": "".join("\n" + d + "\n" for d in details)}
            text = template
            for k, v in fill.items():
                text = text.replace("{" + k + "}", v)
            blocks.append(text.strip())
        messages = [{"rules": [f"R{r['item']}" for r in rules], "text": header[base] + "\n\n" + "\n\n".join(blocks) + "\n"}]
        out = folder / "arms" / arm / "translation"
        out.mkdir(parents=True, exist_ok=True)
        (out / "system.md").write_text(system.replace("{opening}", opening[base])
                                       + "".join((TRANSLATION / part).read_text() for part in parts))
        (out / "messages.json").write_text(json.dumps(messages, ensure_ascii=False, indent=1) + "\n")
        if base == "C":                                   # the toolbox's share for these routes (point 97)
            (out / "toolbox.json").write_text(json.dumps(route_share([r["route"] for r in rules]), indent=1) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--tasks", help="comma-separated task ids instead of the ranking")
    args = p.parse_args()
    tasks = {t["task_id"]: t for t in map(json.loads, MTAC.read_text().splitlines())}
    if args.tasks:
        chosen = [int(x) for x in args.tasks.split(",")]
    else:
        chosen = sorted(tasks, key=lambda tid: (-scored(tasks[tid])[1], tid))[:args.top]
    for tid in chosen:
        n = write_task(tasks[tid])
        print(f"{paths.task_name(tid)}: {tasks[tid].get('task_category')}, {len(tasks[tid]['rounds'])} turns, {n} scored checks")


if __name__ == "__main__":
    main()
