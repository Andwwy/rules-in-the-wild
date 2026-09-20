"""Stage 2 — majority vote over the assignment replicates.

Routing, per rule and per axis (enforcer / target / trigger):

    fewer than 2 replicates named it ....... NULL. No model.
    the replicates that named it agree ..... take it. No model. (agree = identical value sets after a deterministic
                                             normalisation: case, quotes/backticks, whitespace, trailing punctuation,
                                             a trailing "(...)" qualifier)
    otherwise .............................. the model reconciles that axis, seeing every attempt.

A rule calls the model once if any axis needs it; axes settled without the model keep their result.

Rails on the model's answer: a kept value must cite at least 2 distinct attempts that actually named the axis, and be
byte-identical (after html.unescape) to a string in a cited attempt. Anything else is dropped and recorded. If nothing
survives for an axis the model was asked about, that axis is NULL and marked `no_consensus` — different answers are no answer.
The spec is never written by the judge: it is taken verbatim from the first replicate whose enforcers include a voted one.

Attempt order is shuffled per rule (seeded on clause_id) and recorded, so position cannot favour one replicate.
"""
from __future__ import annotations

import collections
import html
import json
import random
import re
from pathlib import Path

from . import llm
from .assign import AXES
from .rules import CARRIED, REQUIRED

_ITEM = {"type": "object",
         "properties": {"value": {"type": "string"}, "attempts": {"type": "array", "items": {"type": "integer"}}},
         "required": ["value", "attempts"], "additionalProperties": False}
SCHEMA = {"type": "object", "properties": {axis: {"type": "array", "items": _ITEM} for axis in AXES},
          "required": list(AXES), "additionalProperties": False}


# ── deterministic part ───────────────────────────────────────────────────────────────────────────────────────────────────
def norm(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"[`'\"“”‘’]", "", value)
    value = re.sub(r"\s*\([^)]*\)\s*$", "", value)
    return re.sub(r"[\s\-_/]+", " ", value).strip(" .;:")


def agreed(named_lists: list[list[str]]) -> list[str] | None:
    """The shared values if every naming attempt gave the same normalised set (most common spelling wins), else None."""
    sets = [frozenset(norm(v) for v in values) for values in named_lists]
    if any(s != sets[0] for s in sets):
        return None
    spellings = collections.defaultdict(list)
    for values in named_lists:
        for v in dict.fromkeys(values):
            spellings[norm(v)].append(v)
    in_first_attempt_order = dict.fromkeys(norm(v) for v in named_lists[0])      # a set here would make the order random
    return [collections.Counter(spellings[k]).most_common(1)[0][0] for k in in_first_attempt_order]


def plan(attempts: list[dict]) -> tuple[dict, dict, list[str]]:
    """→ (values per axis, how each axis was settled, axes that need the model)."""
    values, how, ask = {}, {}, []
    for axis in AXES:
        named = [a[axis] for a in attempts if a[axis]]
        if len(named) <= 1:
            values[axis], how[axis] = [], "null"
        elif (shared := agreed(named)) is not None:
            values[axis], how[axis] = shared, "pattern"
        else:
            values[axis], how[axis] = None, "llm"
            ask.append(axis)
    return values, how, ask


def attempt_order(clause_id: str, n: int) -> list[int]:
    order = list(range(n))
    random.Random(clause_id).shuffle(order)
    return order


def payload(attempts: list[dict], order: list[int], with_rule: bool = False) -> str:
    lines = []
    if with_rule:
        lines += [f"RULE = {attempts[0]['rule_text']}", f"CONTEXT =\n{attempts[0]['context']}", ""]
    for k, j in enumerate(order, 1):
        shown = {axis: attempts[j][axis] for axis in AXES} | {"spec": attempts[j]["spec"]}
        lines += [f"ATTEMPT {k}:", json.dumps(shown, ensure_ascii=False, separators=(",", ": ")), ""]
    return "\n".join(lines).rstrip()


def apply_rails(attempts: list[dict], order: list[int], axis: str, items: list[dict] | None):
    """→ (kept values, kept items, dropped items). See the module docstring for the two rails."""
    kept, dropped = [], []
    for item in items or []:
        value = item.get("value", "")
        cited = [order[k - 1] for k in dict.fromkeys(item.get("attempts", []))
                 if isinstance(k, int) and 1 <= k <= len(order) and attempts[order[k - 1]][axis]]
        literal = value if any(value in attempts[j][axis] for j in cited) else html.unescape(value)
        ok = len(cited) >= 2 and any(literal in attempts[j][axis] for j in cited)
        (kept if ok else dropped).append({"value": literal if ok else value, "attempts": [f"rep{j + 1}" for j in cited]})
    return list(dict.fromkeys(k["value"] for k in kept)), kept, dropped


def pick_spec(attempts: list[dict], enforcer: list[str]) -> str:
    if not enforcer:
        return ""
    for a in attempts:                                # original replicate order
        if a["spec"] and any(e in a["enforcer"] for e in enforcer):
            return a["spec"]
    return next((a["spec"] for a in attempts if a["spec"] and a["enforcer"]), "")


def resolve(attempts: list[dict], answer: dict | None = None, usage: dict | None = None, error: str | None = None) -> dict:
    """The voted record of one rule. `answer` is the judge's reply for rules that needed it, None for the rest."""
    n, first = len(attempts), attempts[0]
    values, how, ask = plan(attempts)
    order = attempt_order(first["clause_id"], n)
    vote = {"replicates": [f"rep{j + 1}" for j in range(n)],
            "values": {axis: [a[axis] for a in attempts] for axis in AXES},
            "specs": [a["spec"] for a in attempts],
            "named_count": {axis: sum(1 for a in attempts if a[axis]) for axis in AXES},
            "how": how,
            "attempt_order": [f"rep{j + 1}" for j in order]}
    record = {k: first[k] for k in (*REQUIRED, *CARRIED) if k in first}
    record |= {axis: values[axis] or [] for axis in AXES} | {"spec": "", "vote": vote}

    if ask and answer is not None:
        vote |= {"model_output": answer, "kept": {}, "dropped": {}}
        for axis in ask:
            record[axis], vote["kept"][axis], dropped = apply_rails(attempts, order, axis, answer.get(axis))
            if dropped:
                vote["dropped"][axis] = dropped
            how[axis] = "llm" if record[axis] else "no_consensus"
        record["usage"] = usage
    if error:
        record["error"] = error

    record["spec"] = pick_spec(attempts, record["enforcer"])
    unanimous = all(vote["named_count"][axis] in (0, n) for axis in AXES)
    vote["stability"] = (f"{n}/{n}" if unanimous else f"{n - 1}/{n}") if n == 3 else ("unanimous" if unanimous else "split")
    return record


# ── the stage ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def run(clause_ids: list[str], replicates: list[dict], prompt: str, settings: llm.Settings, out_dir: Path,
        with_rule: bool = False) -> list[dict]:
    """replicates: one {clause_id: assignment record} per replicate → voted records in the order of `clause_ids`,
    written to out_dir/vote.jsonl. A rule missing from a replicate (its call failed) is left out until a rerun fills it."""
    if len(replicates) < 2:
        raise ValueError("a vote needs at least 2 replicates")
    if len(replicates) != 3:
        print("note: the vote prompt speaks of three attempts; running it over", len(replicates), flush=True)
    ids = [i for i in clause_ids if all(i in rep and not rep[i].get("error") for rep in replicates)]
    if len(ids) < len(clause_ids):
        print(f"note: {len(clause_ids) - len(ids)} rules are not in every replicate yet — rerun to finish them", flush=True)
    attempts = {i: [rep[i] for rep in replicates] for i in ids}

    ask_model = [{"clause_id": i, "attempts": attempts[i]} for i in ids if plan(attempts[i])[2]]
    judged = llm.run_many(
        ask_model, key="clause_id", prompt=prompt, schema=SCHEMA, settings=settings,
        make_input=lambda item: payload(item["attempts"], attempt_order(item["clause_id"], len(replicates)), with_rule),
        to_record=lambda item, answer, usage, error: resolve(item["attempts"], answer, usage, error),
        checkpoint=out_dir / "vote.model.jsonl", label="vote")

    voted = [judged.get(i) or resolve(attempts[i]) for i in ids]
    (out_dir / "vote.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in voted))
    how = collections.Counter((axis, r["vote"]["how"][axis]) for r in voted for axis in AXES)
    for axis in AXES:
        print(f"  {axis:9s} " + "  ".join(f"{h}: {how[(axis, h)]:5d}" for h in ("null", "pattern", "llm", "no_consensus")), flush=True)
    return voted
