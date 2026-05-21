"""Run the judge against golden.yaml; print per-axis agreement.

Doesn't gate anything — just a measurement. Edit `prompts/judge.md`, restart
the container, rerun this script, watch the numbers move.

  docker compose run --rm judge python evals/run_eval.py
"""

import collections
import sys
from pathlib import Path

import yaml

# Run as a module-style script: `python evals/run_eval.py` from repo root, or
# `python -m evals.run_eval` if you've installed evals as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db import connect  # noqa: E402
from src.judge import Judge, TAXONOMY_AXES  # noqa: E402


GOLDEN_PATH = Path(__file__).resolve().parent / "golden.yaml"


def main() -> int:
    golden = yaml.safe_load(GOLDEN_PATH.read_text())
    con = connect()
    judge = Judge(con)
    print(f"prompt_version: {judge.prompt_version}")
    print(f"running judge on {len(golden)} golden rules…\n")

    axis_correct: collections.Counter = collections.Counter()
    axis_total: collections.Counter = collections.Counter()
    confusion: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    confidence_correct: list[float] = []
    confidence_wrong: list[float] = []
    parse_failures: list[tuple[int, str | None]] = []

    for i, entry in enumerate(golden):
        result = judge.classify(entry["rule_text"], entry["source_kind"])
        if not result.parse_ok or result.label is None:
            parse_failures.append((i, result.parse_error))
            print(f"  [{i}] PARSE FAIL: {result.parse_error}")
            continue
        label = result.label
        any_wrong = False
        for axis in TAXONOMY_AXES:
            expected = entry["expected"][axis]
            actual = label.values.get(axis)
            axis_total[axis] += 1
            if expected == actual:
                axis_correct[axis] += 1
            else:
                any_wrong = True
                confusion[axis][(expected, actual)] += 1
        # artifacts compared as a set
        exp_art = set(entry["expected"].get("artifacts_required", []))
        act_art = set(label.artifacts_required)
        axis_total["artifacts_required"] += 1
        if exp_art == act_art:
            axis_correct["artifacts_required"] += 1
        else:
            any_wrong = True
            confusion["artifacts_required"][(tuple(sorted(exp_art)), tuple(sorted(act_art)))] += 1
        (confidence_wrong if any_wrong else confidence_correct).append(label.confidence)

    print("\n=== per-axis agreement ===")
    for axis in list(TAXONOMY_AXES) + ["artifacts_required"]:
        total = axis_total[axis]
        correct = axis_correct[axis]
        pct = (correct / total * 100) if total else 0.0
        print(f"  {axis:28s}  {correct:2d}/{total:<2d}  ({pct:5.1f}%)")

    print("\n=== confusions (top 3 per axis) ===")
    any_conf = False
    for axis, c in confusion.items():
        if not c:
            continue
        any_conf = True
        print(f"  {axis}:")
        for (exp, act), n in c.most_common(3):
            print(f"    expected={exp}  got={act}  ×{n}")
    if not any_conf:
        print("  (no disagreements — every axis perfect or all parse-failed)")

    def avg(xs: list[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    print("\n=== confidence ===")
    print(f"  on fully-correct rules:    {avg(confidence_correct):.3f}  (n={len(confidence_correct)})")
    print(f"  on rules with ≥1 mismatch: {avg(confidence_wrong):.3f}  (n={len(confidence_wrong)})")

    if parse_failures:
        print(f"\n{len(parse_failures)} parse failures — fix prompt and re-run.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
