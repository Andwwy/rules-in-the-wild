"""Score runs of runner.py with MTAC's checker scripts (free; PROTOCOL.md, Scoring).

    uv run --project "dataset/MTAC bench/base agent" python scripts/score_runs.py agents/haiku-4.5_claude-code-2.1.199/runs/MTAC-task-46/C/<run> [more runs]

For each task turn of a run, every checklist item that is one of the task's policy rules (`rules.json`: the project's
CLAUDE.md) and has a checker script is checked by AgentProbe's checker runner; a turn's own request, which can change
from turn to turn, is not scored (design_process.md, point 110). The checker runner (`run_validation_code`, MTAC's
code, unread here) gets the turn's final reply and a copy of its
workspace (`workspace_snapshot/`) without the files that phase 0 created in /workspace (`phase0/workspace.json`),
also when the task agent changed them later: they are the enforcement, not the task's output (design_process.md, point 46). A checker that crashes or times out is no
verdict (null), as in AgentProbe. The checklist is MTAC's full task (`dataset/MTAC bench/task data/mtac_full.jsonl`). Writes
<run>/script_scores.json and prints one line per run.

The final reply is taken as AgentProbe takes it (task.py, `_round_response`): the last non-empty assistant text of that
turn's part of the transcript (from the turn's prompt to the next turn's; AgentProbe's own `_keep_agent_activity` and
`last_assistant_text`), not Claude Code's `result` field, which is empty when the turn's last message has no text (for
example after a Stop hook); `last_response.txt` is the fallback when there is no transcript (design_process.md, point 50).
Messages that Claude Code writes itself (model `<synthetic>`, e.g. "No response requested." when the agent stops with
nothing to say) are not the agent's reply and are skipped (point 51).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
import paths                                             # noqa: E402

paths.use("agentprobe")
from benchmarks.mtacifbench.models import MTACIFBenchQuestion   # noqa: E402
from benchmarks.mtacifbench.validation import run_validation_code   # noqa: E402
from benchmarks.mtacifbench.prompts import MULTIROUND_MAIN_PROMPT_TEMPLATE   # noqa: E402
from benchmarks.mtacifbench.utils import (_keep_agent_activity, _normalize_prompt_text,   # noqa: E402
                                          extract_text_content, last_assistant_text, parse_trace_messages)

MTAC = paths.MTAC_DATA


def phase0_files(run: Path, workspace_dir: str) -> dict[str, str]:
    """Files that phase 0 created in /workspace, by path relative to it."""
    path = run / "phase0" / "workspace.json"
    if not path.is_file():
        return {}
    created = json.loads(path.read_text(encoding="utf-8")).get("created", {})
    root = workspace_dir.rstrip("/") + "/"
    return {p[len(root):]: h for p, h in created.items() if p.startswith(root)}


def turn_replies(run: Path, q: MTACIFBenchQuestion) -> dict[str, str]:
    """Each turn's final reply from the task transcript, as AgentProbe takes it."""
    traces = [t for t in (run / "traces").glob("*.jsonl") if not t.name.endswith(".enforce.jsonl")]
    if not traces:
        return {}
    raw = traces[0].read_text(encoding="utf-8", errors="ignore")
    own = "\n".join(line for line in raw.splitlines() if '"model":"<synthetic>"' not in line.replace(" ", ""))
    messages = parse_trace_messages(own)
    starts = []                                            # the index of each turn's prompt, in order
    for rnd in q.rounds:
        want = _normalize_prompt_text(MULTIROUND_MAIN_PROMPT_TEMPLATE.format(round_prompt=rnd.prompt))
        after = starts[-1][1] + 1 if starts else 0
        hit = next((i for i in range(after, len(messages)) if str(messages[i].get("role")) == "user"
                    and want and want in _normalize_prompt_text(extract_text_content(messages[i].get("content", "")))), None)
        if hit is None:
            break
        starts.append((rnd.round_id, hit))
    out = {}
    for k, (rid, i) in enumerate(starts):
        end = starts[k + 1][1] if k + 1 < len(starts) else len(messages)
        context = json.dumps(_keep_agent_activity(messages[i + 1:end]), ensure_ascii=False)
        out[str(rid)] = last_assistant_text(context)
    return out


def score(run: Path, tasks: dict) -> dict:
    tid = paths.run_info(run)["task"]
    raw = tasks[tid]
    q = MTACIFBenchQuestion.model_validate(raw)
    leave_out = phase0_files(run, q.workspace_dir)
    policy = {r["constraint"].strip() for r in json.loads((paths.task_dir(tid) / "rules.json").read_text(encoding="utf-8"))}
    replies = turn_replies(run, q)
    rounds = []
    for rnd in raw["rounds"]:
        material = run / "turns" / f"round_{rnd['round_id']}"
        response_path, snapshot = material / "last_response.txt", material / "workspace_snapshot"
        if not (response_path.is_file() and snapshot.is_dir()):
            continue
        saved = response_path.read_text(encoding="utf-8", errors="ignore")
        response = replies.get(str(rnd["round_id"])) or saved
        with tempfile.TemporaryDirectory(prefix="ritw_score_") as tmp:
            work = Path(tmp) / "workspace"
            shutil.copytree(snapshot, work, symlinks=True)
            left_out = []
            for rel in leave_out:
                p = work / rel
                if p.is_file() or p.is_symlink():
                    p.unlink()
                    left_out.append(rel)
            items = [(k, c) for k, c in enumerate(rnd["instruction_following_checklist"])
                     if c["validation_code"].strip() and c["constraint"].strip() in policy]

            def check(item):
                k, c = item
                try:
                    verdict = run_validation_code(c["validation_code"], response, work, q.validation_code_timeout,
                                                  f"[{run.name} r{rnd['round_id']} #{k + 1}]")
                except Exception:
                    verdict = None
                return {"index": k + 1, "requirement": c["constraint"], "passed": verdict}

            with ThreadPoolExecutor(8) as pool:
                rounds.append({"round_id": rnd["round_id"], "left_out": left_out,
                               "reply_from": "transcript" if replies.get(str(rnd["round_id"])) else "last_response.txt",
                               "reply_differs_from_result": bool(replies.get(str(rnd["round_id"]))) and
                               replies.get(str(rnd["round_id"])).strip() != saved.strip(),
                               "items": list(pool.map(check, items))})
    out = {"run": str(run.relative_to(EXP)), "task": tid, "rounds": rounds}
    (run / "script_scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    items = [i for r in rounds for i in r["items"]]
    print(f"{run.relative_to(EXP)}: {len(rounds)} turns, {len(items)} scripted policy-rule items: "
          f"{sum(i['passed'] is True for i in items)} pass, {sum(i['passed'] is False for i in items)} fail, "
          f"{sum(i['passed'] is None for i in items)} not scored; phase 0 files left out: {len(leave_out)}")
    return out


def main(argv: list[str]) -> None:
    tasks = {t["task_id"]: t for t in map(json.loads, MTAC.read_text(encoding="utf-8").splitlines())}
    for a in argv:
        score(Path(a).resolve(), tasks)


if __name__ == "__main__":
    main(sys.argv[1:])
