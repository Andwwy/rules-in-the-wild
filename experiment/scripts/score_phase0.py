"""Score phase 0's translation without a model (design_process.md, point 86): feed a task's held-out cases to the hooks
that the agent's Claude Code will load, as Claude Code would call them. It commits the run's kept container to a
temporary image, starts a copy without network, runs container/probes/phase0_probe.py in it, and removes the copy and
the image; the run's own container is not changed. No agent sees the cases (tasks/<task>/hidden_fixtures.json).

    python3 scripts/score_phase0.py agents/haiku-4.5_claude-code-2.1.199/runs/MTAC-task-91/C/<run> [...]
    python3 scripts/score_phase0.py --summary-only <run> [...]      the summary again, from the saved results

Writes <run>/phase0_score.json and prints, per rule, how many of its cases a hook caught when the agent writes the
file with its file tools (tool), with a shell command (shell), or in its reply (reply), and how many of those flags
named the rule; then the flags on cases that must pass, and the hooks that failed to run.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
import paths                                                     # noqa: E402
# a hook that fails to run can still exit 2; its "flag" is a crash, not a catch (as in trajectory_viewer.py)
CRASH = re.compile(r"[Ss]yntax ?[Ee]rror|Traceback \(most recent|command not found|: not found|No such file|"
                   r"Permission denied|unexpected EOF|cannot execute|ModuleNotFoundError")


def container_of(run: Path) -> str:
    ctr = paths.container_of(run)
    if not ctr:
        raise SystemExit(f"{run}: run.log names no container")
    return ctr


def probe(run: Path) -> dict:
    fixtures = paths.task_dir(paths.run_info(run)["task"]) / "hidden_fixtures.json"
    ctr, tag = container_of(run), f"ritw-s1probe:{uuid.uuid4().hex[:8]}"
    copy = f"ritw-s1probe-{uuid.uuid4().hex[:8]}"
    subprocess.run(["docker", "commit", ctr, tag], check=True, capture_output=True)
    try:
        subprocess.run(["docker", "run", "-d", "--name", copy, "--platform", "linux/amd64", "--network", "none",
                        "--entrypoint", "sleep", tag, "infinity"], check=True, capture_output=True)
        subprocess.run(["docker", "exec", copy, "mkdir", "-p", "/opt/s1probe"], check=True, capture_output=True)
        for src, dst in ((paths.PROBES / "phase0_probe.py", "/opt/s1probe/probe.py"), (fixtures, "/opt/s1probe/fixtures.json")):
            subprocess.run(["docker", "cp", str(src), f"{copy}:{dst}"], check=True, capture_output=True)
        done = subprocess.run(["docker", "exec", "-u", "root", copy, "python3", "-I", "/opt/s1probe/probe.py", "/opt/s1probe/fixtures.json"],
                              capture_output=True, text=True, timeout=3600)
        if done.returncode:
            raise SystemExit(f"{run}: the probe failed: {done.stderr[-1500:]}")
        return json.loads(done.stdout)
    finally:
        subprocess.run(["docker", "rm", "-f", copy], capture_output=True)
        subprocess.run(["docker", "rmi", "-f", tag], capture_output=True)


def summarize(res: dict) -> dict:
    caught: dict[str, dict] = {}
    false_flags, errors = [], set()
    for c in res["cases"]:
        hits = [r for r in c["rows"] if r["verdict"] in ("flag", "fix") and not CRASH.search(r.get("msg", ""))]
        errors.update(r["hook"] for r in c["rows"] if r["verdict"] in ("error", "timeout")
                      or (r["verdict"] == "flag" and CRASH.search(r.get("msg", ""))))
        if c["rule"] is None:
            false_flags += [f"{c['name']} ({c['channel']}): {r['event']}: {r['msg'].strip().splitlines()[0][:110]}" for r in hits]
            continue
        cell = caught.setdefault(c["rule"], {}).setdefault(c["channel"], [])
        cell.append({"case": c["name"], "caught": bool(hits),
                     "named": any(re.search(rf"\b{c['rule']}\b", r.get("msg", "")) for r in hits),
                     "early": any(r["event"] != "Stop" for r in hits), "at": sorted({r["event"] for r in hits})})
    return {"hooks": res["hooks"], "rules": caught, "false_flags": false_flags, "hook_errors": sorted(errors)}


def main(argv: list[str]) -> None:
    again = "--summary-only" in argv                       # recompute the summary from the saved probe results
    for a in [x for x in argv if x != "--summary-only"]:
        run = Path(a).resolve()
        res = json.loads((run / "phase0_score.json").read_text(encoding="utf-8"))["raw"] if again else probe(run)
        summary = summarize(res)
        (run / "phase0_score.json").write_text(json.dumps({"summary": summary, "raw": res}, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
        print(f"\n{run.relative_to(EXP)}: {summary['hooks']} hooks")
        for rule, by in sorted(summary["rules"].items(), key=lambda kv: int(kv[0][1:])):
            cells = []
            for ch in ("reply", "tool", "shell"):
                if ch in by:
                    n, k, named = len(by[ch]), sum(x["caught"] for x in by[ch]), sum(x["named"] for x in by[ch])
                    cells.append(f"{ch} {k}/{n} (named {named})")
            print(f"  {rule}: " + " · ".join(cells))
        print(f"  false flags on cases that must pass: {len(summary['false_flags'])}")
        for f in summary["false_flags"][:6]:
            print(f"    {f}")
        if summary["hook_errors"]:
            print(f"  hooks that failed to run: {len(summary['hook_errors'])}")


if __name__ == "__main__":
    main(sys.argv[1:])
