"""Map a rule onto a decision tree in `../` with TypeSafe Jev: the enforcer, trigger or target tree.

    python tree_classifier.py enforcer "Every function name must follow snake_case"
    python tree_classifier.py trigger "Run the linter before every commit" --value "at commit time"
    python tree_classifier.py target "…" --value "commit messages" --context '{"heading": "Git"}'

    from tree_classifier import classify                   # (add this folder to sys.path)
    result = classify("trigger", rule_text, value="at commit time")

Hierarchical classification as in TypeSafe's cookbook: at each tree node one Choice question picks among the node's
direct children, and a beam of BEAM paths goes down the tree; a path's score is the geometric mean of its edge
probabilities. A leaf ends a path (every inner node has an "Other" child: none of its listed children fits).

A tree file may carry a `descriptions` map (key: the node's path below the root, "A > B", or its name). Jev then sees
an option as "name: description"; without one, it sees the name only, as for the enforcer tree. `value` is the
assigner's own wording of the axis for this rule (the voted trigger or target); Jev sees it next to the rule.

The timing belongs to the event: under each event of the trigger tree, its last level is the check's timing against
that event, before / at / after (tree_of; Always has no event: its timing is always). The beam picks the event and its
timing together; the result keeps the event as `path` and the timing as the attribute `timing` (each alternative has
its own). tree_of can keep only the timings at which each event can run in an environment. The trigger tree's first
call also asks whether a state must also hold (a mode, a flag, a threshold).

Every Jev call is logged to the project's spend ledger (assign+group/rule_pipeline/spend.py, $0.042 per million input
tokens) and none starts once the project's budget is spent. Key: TYPESAFE_API_KEY, found in the nearest .env up the
tree (~/Desktop/DAPlab/.env).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
RITW = HERE.parents[1]                                     # rules in the wild/
sys.path.insert(0, str(RITW / "assign+group"))
from rule_pipeline import spend                            # noqa: E402

MODEL = "jev-1.13.0"
BEAM = 3
PRICE_PER_TOKEN = 0.042e-6
TAIL = " The answer is inside this branch of the {axis} tree: {branch}. Pick the option that fits best."


@dataclass(frozen=True)
class Axis:
    tree: Path
    question: str                                          # {context} is filled in, or left empty
    source: str                                            # the spend ledger's name for these calls
    value_hint: str = ""


AXES = {
    "enforcer": Axis(HERE.parent / "enforcer-tree-simple.json",
                     "Which kind of enforcer could deterministically check or enforce the rule in `rule`{context}?",
                     "jev classifier (enforcer tree)"),
    "trigger": Axis(HERE.parent / "trigger-tree.json",
                    "Which event should start the check of the rule in `rule`{context}?",
                    "jev classifier (trigger tree)", " An assigner described this event as `trigger`."),
    "target": Axis(HERE.parent / "target-tree.json",
                   "What does the enforcer of the rule in `rule` inspect or act on{context}?",
                   "jev classifier (target tree)", " An assigner described it as `target`."),
}

# The last level of the trigger tree, under each event (tree_of); always: the timing of Always, which has no event.
TIMING = {
    "before": "The check runs before the event, so it can block it (a pre-commit hook, a check before a response "
              "is sent, a check before a command runs).",
    "at": "The check runs at the event or while it happens (at lint time, during code review, when a request is "
          "handled).",
    "after": "The check runs after the event (after a file is written, after a task ends).",
    "always": "There is no event: the rule applies at all times.",
}
TIMING_Q = "When does the check of the rule in `rule` run, against the event {event}{context}?"
STATE = ("Besides its event, does the trigger of the rule in `rule` also need a state or condition to hold, such as a "
         "mode, a flag, a threshold, or a tool that is missing?")


@dataclass
class Node:
    name: str
    children: list["Node"] = field(default_factory=list)
    description: str | None = None


def tree_of(axis: str, timings=None) -> Node:
    """An axis's tree; the trigger tree with the timing as its last level: under each event, before / at / after
    (Always stays a leaf). `timings` (a function of an event's path) keeps only the timings at which that event can run
    in an environment; an event with none, and a branch left empty, are left out."""
    tree = load_tree(AXES[axis].tree)
    if axis != "trigger":
        return tree

    def grow(node: Node, path: list[str]) -> bool:
        if node.children:
            node.children = [kid for kid in node.children if grow(kid, path + [kid.name])]
            return bool(node.children)
        if path == ["Always"]:
            return True
        node.children = [Node(t, description=TIMING[t]) for t in (timings(path) if timings else ("before", "at", "after"))]
        return bool(node.children)
    grow(tree, [])
    return tree


def split(path: list[str]) -> tuple[list[str], str]:
    """A trigger path with its timing → (the event's path, the timing)."""
    return (path[:-1], path[-1]) if len(path) > 1 and path[-1] in TIMING else (path, "always")


def load_tree(path: Path) -> Node:
    data = json.loads(Path(path).read_text())
    descriptions = data.pop("descriptions", {})

    def build(name, kids, prefix):
        node = Node(name, description=descriptions.get(" > ".join(prefix)) or descriptions.get(name)
                    if prefix else None)
        for kid in kids:
            kid_name, grand = (kid, None) if isinstance(kid, str) else next(iter(kid.items()))
            node.children.append(build(kid_name, grand or [], prefix + [kid_name]))
        return node
    root, kids = next(iter(data.items()))
    return build(root, kids, [])


def _load_key() -> None:
    if os.environ.get("TYPESAFE_API_KEY"):
        return
    from dotenv import load_dotenv
    for folder in (HERE, *HERE.parents):
        if (folder / ".env").is_file():
            load_dotenv(folder / ".env", override=False)


def _client():
    from typesafe_sdk import RetryPolicy, TypeSafeClient
    _load_key()
    return TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"], model=MODEL,
                          retry=RetryPolicy(max_retries=5, backoff_initial=1.0, backoff_max=20.0))


def _choose(client, axis: str, state: dict, path: list[Node]) -> tuple[dict[str, float], dict, int]:
    """One Choice over the children of path[-1] → ({child name: probability}, {attribute: answer}, input tokens)."""
    from typesafe_sdk import Choice, Noul
    cfg, kids = AXES[axis], path[-1].children
    first = len(path) == 1
    asks_attributes = first and axis == "trigger"
    if len(kids) == 1 and not asks_attributes:
        return {kids[0].name: 1.0}, {}, 0
    spend.check(cfg.source)
    keys = {f"c{i}": kid for i, kid in enumerate(kids)}
    with_context = ", using what `context` says about it" if "context" in state else ""
    if all(kid.name in TIMING and not kid.children for kid in kids):     # the trigger tree's last level: the timing
        instructions = TIMING_Q.format(event=" > ".join(n.name for n in path[1:]), context=with_context)
    else:
        instructions = cfg.question.format(context=with_context)
        instructions += cfg.value_hint if axis in state else ""
        instructions += TAIL.format(axis=axis, branch=" > ".join(n.name for n in path))
    questions = {"child": Choice(instructions=instructions, criteria={
        key: f"{kid.name}: {kid.description}" if kid.description else kid.name for key, kid in keys.items()})}
    if asks_attributes:
        questions["state"] = Noul(instructions=STATE)
    response = client.system_one(state=state, questions=questions, model=MODEL)
    tokens = (response.usage.input_tokens or 0) if response.usage else 0
    spend.record(cfg.source, response.model, tokens * PRICE_PER_TOKEN, tokens, response.usage.output_tokens
                 if response.usage else None)
    probabilities = response.answers["child"].probabilities
    attributes = {}
    if asks_attributes:
        attributes = {"state_p": round(response.answers["state"].noul, 4)}
    return {kid.name: probabilities[key] for key, kid in keys.items()}, attributes, tokens


def classify(axis: str, rule: str, context: dict | None = None, *, value: str | None = None, tree: Node | None = None,
             client=None, beam: int = BEAM) -> dict:
    tree, client = tree or tree_of(axis), client or _client()
    state = {"rule": rule, **({axis: value} if value else {}), **({"context": context} if context else {})}
    frontier, finished, calls, tokens, attributes = [([tree], [])], [], 0, 0, {}

    def score(probs):
        return math.exp(sum(math.log(max(p, 1e-9)) for p in probs) / len(probs))

    while frontier:
        with ThreadPoolExecutor(max_workers=len(frontier)) as pool:
            answers = list(pool.map(lambda cand: _choose(client, axis, state, cand[0]), frontier))
        grown = []
        for (path, probs), (dist, attrs, used) in zip(frontier, answers):
            calls, tokens = calls + (1 if used else 0), tokens + used
            attributes |= attrs
            for kid in path[-1].children:
                cand = (path + [kid], probs + [dist[kid.name]])
                (finished if not kid.children else grown).append(cand)
        frontier = sorted(grown, key=lambda c: score(c[1]), reverse=True)[:beam]
    ranked = sorted(finished, key=lambda c: score(c[1]), reverse=True)
    best = ranked[0]
    names = lambda path: [n.name for n in path[1:]]         # noqa: E731 — drop the root
    timed = axis == "trigger"                               # the trigger's last level is its timing (tree_of)

    def entry(path, probs):
        if not timed:
            return {"path": names(path)}
        event, timing = split(names(path))
        return {"path": event, "timing": timing, **({"timing_p": round(probs[-1], 4)} if timing != "always" else {})}
    top = entry(*best)
    return {
        "leaf": top["path"][-1],
        "path": top["path"],
        "score": round(score(best[1]), 4),
        "step_probabilities": [round(p, 4) for p in best[1]],
        "separation": round(score(best[1]) / score(ranked[1][1]), 3) if len(ranked) > 1 else None,
        "alternatives": [entry(p, q) | {"score": round(score(q), 4)} for p, q in ranked[1:beam]],
        **({"attributes": attributes | {k: top[k] for k in ("timing", "timing_p") if k in top}}
           if attributes or timed else {}),
        "model": MODEL, "beam": beam, "calls": calls, "input_tokens": tokens,
        "cost_usd": round(tokens * PRICE_PER_TOKEN, 8),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("axis", choices=sorted(AXES))
    p.add_argument("rule")
    p.add_argument("--value", help="the assigner's wording of the axis for this rule (trigger and target)")
    p.add_argument("--context", type=json.loads, help="JSON object sent with the rule as `context`")
    p.add_argument("--beam", type=int, default=BEAM)
    args = p.parse_args()
    print(json.dumps(classify(args.axis, args.rule, args.context, value=args.value, beam=args.beam),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
