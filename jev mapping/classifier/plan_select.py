"""Pick a rule's whole enforcement plan (enforcer, trigger with its timing, target) in one Jev call.

    from plan_select import select_plan                    # (add this folder to sys.path)
    result = select_plan(rule_text, candidates, context={"mtac_category": "..."})

n-best reranking: each axis is first classified on its own (tree_classifier.py, a beam per tree, repeated); its best
paths are the axis's candidates. A timing belongs to its trigger: a trigger candidate is an event with its timing (the
trigger tree's last level, tree_classifier.tree_of). The candidates of the three axes are combined into plans (4 x 4 x 4 = 64 at most with 4
per axis; a Choice takes up to 255 options), and one Choice picks the plan whose parts fit the rule and fit each other.
The axes were decided apart; this call decides them together.

`candidates`: {"enforcer": [path, ...], "trigger": [{"path": path, "timing": timing}, ...], "target": [path, ...]},
each path a list of node names below the tree's root. Jev sees each part once in `parts` (with the tree's description
where the tree has one) and each plan as one line of four parts. `shuffle` (a seed) sends the plans in a random order,
since the pick follows the order of the options. `allowed` (a function of a plan) keeps only the plans it accepts. The
result has every option's probability (`all`), so that calls with the plans in different orders can be averaged.
"""
from __future__ import annotations

import itertools
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tree_classifier                                     # noqa: E402
from tree_classifier import MODEL, PRICE_PER_TOKEN, TIMING, spend   # noqa: E402

SOURCE = "jev classifier (plan select)"
AXES = ("enforcer", "trigger", "target")
INSTRUCTIONS = (
    "Which enforcement plan fits the rule in `rule` best{context}? A plan has four parts that must work together: an "
    "enforcer that could deterministically check or enforce the rule, the event that starts the check, when the "
    "check runs against that event, and what the enforcer inspects or acts on. `parts` describes each part. Pick the "
    "plan whose parts fit the rule and fit each other.")


def _descriptions() -> dict[str, dict[str, str]]:
    return {a: json.loads(tree_classifier.AXES[a].tree.read_text()).get("descriptions", {}) for a in AXES}


def plans(candidates: dict[str, list]) -> list[dict]:
    """Every combination of the candidates: an enforcer, a trigger with its timing, a target."""
    return [{"enforcer": e, "trigger": t["path"], "timing": t["timing"], "target": g}
            for e, t, g in itertools.product(candidates["enforcer"], candidates["trigger"], candidates["target"])]


def _line(plan: dict) -> str:
    return (f"enforcer: {' > '.join(plan['enforcer'])}; trigger: {' > '.join(plan['trigger'])}, timing: "
            f"{plan['timing']}; target: {' > '.join(plan['target'])}")


def key(plan: dict) -> str:
    """A plan as one line, the same in every call: for averaging over calls."""
    return _line(plan)


def select_plan(rule: str, candidates: dict[str, list], context: dict | None = None, client=None,
                shuffle: str | None = None, allowed=None) -> dict:
    from typesafe_sdk import Choice
    client = client or tree_classifier._client()
    desc = _descriptions()
    paths = {a: [c["path"] if a == "trigger" else c for c in candidates[a]] for a in AXES}
    parts = {f"{a}s": {" > ".join(p): desc[a].get(" > ".join(p)) or desc[a].get(p[-1]) or "" for p in paths[a]}
             for a in AXES}
    parts["timings"] = TIMING
    state = {"rule": rule, **({"context": context} if context else {}), "parts": parts}
    options = [p for p in plans(candidates) if allowed is None or allowed(p)]
    if not options:
        raise ValueError("no plan is allowed")
    if shuffle is not None:
        random.Random(shuffle).shuffle(options)
    keys = {f"p{i}": plan for i, plan in enumerate(options)}
    spend.check(SOURCE)
    instructions = INSTRUCTIONS.format(context=", using what `context` says about it" if context else "")
    response = client.system_one(state=state, model=MODEL, questions={
        "plan": Choice(instructions=instructions, criteria={k: _line(p) for k, p in keys.items()})})
    tokens = (response.usage.input_tokens or 0) if response.usage else 0
    spend.record(SOURCE, response.model, tokens * PRICE_PER_TOKEN, tokens,
                 response.usage.output_tokens if response.usage else None)
    answer = response.answers["plan"]
    ranked = sorted(keys, key=lambda k: answer.probabilities[k], reverse=True)
    best, p = keys[ranked[0]], answer.probabilities
    return {
        **best,
        "p": round(p[ranked[0]], 4),
        "separation": round(p[ranked[0]] / p[ranked[1]], 3) if len(ranked) > 1 and p[ranked[1]] else None,
        "confidence": round(answer.confidence, 4) if answer.confidence is not None else None,
        "alternatives": [{**keys[k], "p": round(p[k], 4)} for k in ranked[1:4]],
        "all": [[key(keys[k]), round(p[k], 6)] for k in ranked],
        "candidates": candidates, "options": len(options), **({"shuffle": shuffle} if shuffle is not None else {}),
        "model": MODEL, "input_tokens": tokens, "cost_usd": round(tokens * PRICE_PER_TOKEN, 8),
    }
