"""Map the voted trigger or target values of the v1.11 vote onto their tree, with `tree_classifier.py`.

    python map_values.py trigger --limit 5      a pilot: 5 values of a fixed random order
    python map_values.py trigger                every value of the 1,841 rules with a voted enforcer, target and trigger
    python map_values.py target --scope all     every value of all 10,000 rules

Each value is sent with its rule: Jev sees the rule text and the assigner's wording (`trigger` or `target`). One line per
(rule, value) goes into ../mapped/<axis>.jsonl; a value already there is not sent again, so a run can stop and resume.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tree_classifier import RITW, _client, classify, tree_of

DATA = RITW / "assign+group/data/pass1.11-10000/v1.11_result/assignment output.json"
OUT = Path(__file__).resolve().parent.parent / "mapped"


def values(rule: dict, key: str) -> list[str]:
    v = rule.get(key) or []
    return [x.strip() for x in (v if isinstance(v, list) else [v]) if x and x.strip()]


def jobs(axis: str, scope: str) -> list[tuple[dict, str]]:
    rules = json.loads(DATA.read_text())
    if scope == "full":
        rules = [r for r in rules if all(values(r, k) for k in ("enforcer", "target", "trigger"))]
    out = [(r, v) for r in rules for v in values(r, axis)]
    random.Random(0).shuffle(out)                          # a --limit takes a random sample, the same every time
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("axis", choices=["trigger", "target"])
    p.add_argument("--scope", choices=["full", "all"], default="full",
                   help="full: the 1,841 rules with a voted enforcer, target and trigger (default); all: 10,000 rules")
    p.add_argument("--limit", type=int, help="map only the first N values of the fixed random order")
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args()

    OUT.mkdir(exist_ok=True)
    path = OUT / f"{args.axis}.jsonl"
    done = set()
    if path.exists():
        done = {(d["clause_id"], d["value"]) for d in map(json.loads, path.read_text().splitlines())}
    todo = jobs(args.axis, args.scope)
    total = len(todo)
    todo = todo[:args.limit] if args.limit else todo
    todo = [(r, v) for r, v in todo if (r["clause_id"], v) not in done]
    print(f"{args.axis}: {total} values in scope '{args.scope}', {len(done)} already mapped, {len(todo)} to send")
    if not todo:
        return
    tree, client = tree_of(args.axis), _client()

    def one(job):
        rule, value = job
        mapping = classify(args.axis, rule["rule_text"], value=value, tree=tree, client=client)
        return {"clause_id": rule["clause_id"], "value": value, "rule_text": rule["rule_text"], "mapping": mapping}

    start, cost, calls = time.time(), 0.0, 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool, path.open("a") as out:
        for i, row in enumerate(pool.map(one, todo), 1):
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            cost, calls = cost + row["mapping"]["cost_usd"], calls + row["mapping"]["calls"]
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}  ${cost:.4f}", file=sys.stderr)
    n = len(todo)
    print(f"{n} values mapped in {time.time() - start:.1f} s: ${cost:.5f} (${cost / n:.6f} per value), "
          f"{calls / n:.1f} calls per value → {path}")
    if len(done) + n < total:
        print(f"Estimate for all {total} values in scope: ${cost / n * total:.2f}")


if __name__ == "__main__":
    main()
