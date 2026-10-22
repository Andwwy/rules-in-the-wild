"""Every path of the experiment, and the one place that reaches code outside it (`use`). Every script imports this
module as a sibling; run each script from the experiment folder: `python scripts/runner.py 46 C` (README.md, Layout).

    dataset/<bench>/           each benchmark as downloaded, with its paper (MTAC bench/: task data/, base agent/)
    tasks/<SRC>-task-NN/       a task copied from its benchmark (MTAC-task-46), free of any model or agent: data/,
                               rules.json (with Jev's routes),
                               README.md, and arms/<arm>/translation/ (phase 0's inputs)
    agents/<agent>/            one agent setup (agent.json: model, harness, flags) and what it produced:
                               runs/<task>/<arm>/<stamp>/ and checks/<task>/<arm>/<stamp>/ (scripted, no model)
    prompts/                   the sources of phase 0's inputs: system prompt parts, rule templates, guides/
    container/                 what is copied into the run container: harness/, toolbox/, probes/
    scripts/                   every script, and gateway/ (the model gateway)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
TASKS = EXP / "tasks"
AGENTS = EXP / "agents"
PROMPTS = EXP / "prompts"
FRAMEWORKS = PROMPTS / "frameworks"                # phase 0's section per agent framework (agent.json "harness")
CONTAINER = EXP / "container"
HARNESS_SRC = CONTAINER / "harness"                # copied to /opt/enforce-harness
TOOLBOX = CONTAINER / "toolbox"                    # copied to /opt/enforce-toolbox (the toolbox arms)
PROBES = CONTAINER / "probes"                      # the scripted model and the phase 0 probe (checks and scoring)
SCRIPTS = EXP / "scripts"
GATEWAY = SCRIPTS / "gateway"                      # LiteLLM to Bedrock; gateway.log, budget.py
DATASET = EXP / "dataset"                          # the benchmarks, as downloaded, each with its paper
MTAC_BENCH = DATASET / "MTAC bench"
MTAC_DATA = MTAC_BENCH / "task data" / "mtac_full.jsonl"   # MTAC-IFBench's 100 tasks (task_id 1..100)
BASE_AGENT = MTAC_BENCH / "base agent"             # AgentProbe, used as a library (MTAC's prompts and checkers)
RITW = EXP.parent                                  # rules in the wild/
SPEND = RITW / "spend.jsonl"                       # the current ledger: the budget cap counts it (RITW_BUDGET_USD)
# every ledger: the current one and the archived ones (spend.until-<date>.jsonl), for a run's cost
# Code outside the experiment, by name: the folders `use` puts on the import path
OUTSIDE = {"agentprobe": [BASE_AGENT / "src", BASE_AGENT],             # benchmarks.mtacifbench (run with uv, base agent)
           "jev": [RITW / "jev mapping" / "classifier"],             # tree_classifier, plan_select, enforcer_tree
           "spend": [RITW / "assign+group"]}                         # rule_pipeline.spend (the shared ledger)
DEFAULT_AGENT = "haiku-4.5_claude-code-2.1.199"
# A: CLAUDE.md only; B: the rules only; C: the rules with Jev's route and the toolbox (design_process.md, points 60, 96);
# C-ideal: C's routes translated by hand, the ideal translation (no translation agent; its install.sh; point 107)
ARMS = ("A", "B", "C", "C-ideal")
TOOLBOX_ARMS = ("C", "C-ideal")


def use(name: str) -> None:
    """Make code outside the experiment importable: "agentprobe", "jev" or "spend" (OUTSIDE)."""
    for folder in reversed(OUTSIDE[name]):
        if str(folder) in sys.path:              # first, also before an installed copy (base agent's venv has one)
            sys.path.remove(str(folder))
        sys.path.insert(0, str(folder))


def ledger_rows():
    """Every row of every ledger (current and archived): a run's cost can span a rotation."""
    for f in sorted(RITW.glob("spend*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def task_name(tid: int, source: str = "MTAC") -> str:
    """A task's folder name: its benchmark, then its id there (MTAC-task-46)."""
    return f"{source}-task-{tid:02d}"


def task_id(name: str) -> int:
    """The id in a task's folder name or run label: MTAC-task-46, or task_046 (the name before 2026-10-20, in older run labels)."""
    return int(re.fullmatch(r"(?:.+-task-|task_)(\d+)", name)[1])


def task_dir(tid: int) -> Path:
    return TASKS / task_name(tid)


def arm_inputs(tid: int, arm: str) -> Path:
    """phase 0's inputs of one arm of one task: system.md and messages.json."""
    return task_dir(tid) / "arms" / arm / "translation"


def runs_dir(agent: str, tid: int, arm: str, kind: str = "runs") -> Path:
    return AGENTS / agent / kind / task_name(tid) / arm


def agent_config(agent: str) -> dict:
    return json.loads((AGENTS / agent / "agent.json").read_text(encoding="utf-8"))


def run_info(run: Path) -> dict:
    """A run's agent, task, arm and ledger label, from its place (agents/<agent>/<kind>/<task>/<arm>/<stamp>) and
    its inputs.json (the label the spend ledger knows it by)."""
    run = Path(run).resolve()
    parts = run.relative_to(AGENTS).parts
    inputs = json.loads((run / "inputs.json").read_text(encoding="utf-8")) if (run / "inputs.json").exists() else {}
    return {"agent": parts[0], "kind": parts[1], "task": task_id(parts[2]), "arm": parts[3],
            "stamp": parts[4], "label": inputs.get("run", "/".join((parts[2], parts[3], parts[4]))),
            "container": container_of(run)}


def container_of(run: Path) -> str | None:
    """The run's Docker container, as its run.log names it."""
    log = Path(run) / "run.log"
    if log.exists():
        for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
            if " container ritw-" in line:
                return line.split(" container ", 1)[1].split()[0]
    return None


def latest_runs(agent: str, tasks: tuple[int, ...], arms: tuple[str, ...]) -> list[Path]:
    out = []
    for t in tasks:
        for a in arms:
            d = runs_dir(agent, t, a)
            if d.is_dir() and any(d.iterdir()):
                out.append(sorted(p for p in d.iterdir() if p.is_dir())[-1])
    return out
