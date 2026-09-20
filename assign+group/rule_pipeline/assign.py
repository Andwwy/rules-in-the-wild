"""Stage 1 — assignment. Every rule goes through the assignment prompt, once per replicate.

The model returns, for one rule: enforcer[], target[], trigger[] and a spec. An axis with nothing assigned is an empty list.
Replicates are identical runs of the same prompt; the vote (stage 2) reconciles them.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import llm
from .rules import CARRIED, REQUIRED

AXES = ("enforcer", "target", "trigger")
_LIST = {"type": "array", "items": {"type": "string"}}
SCHEMA = {"type": "object",
          "properties": {"spec": {"type": "string"}, **{axis: _LIST for axis in AXES}},
          "required": ["spec", *AXES]}


def make_input(rule: dict) -> str:
    return f'RULE = {rule["rule_text"]}\nCONTEXT =\n{rule["context"]}'


def to_record(rule: dict, answer: dict | None, usage: dict | None, error: str | None) -> dict:
    record = {k: rule[k] for k in (*REQUIRED, *CARRIED) if k in rule}
    answer = answer or {}
    spec = answer.get("spec") or ""
    record |= {axis: answer.get(axis) or [] for axis in AXES}
    record |= {"spec": " ".join(spec) if isinstance(spec, list) else spec, "usage": usage}
    if error:
        record["error"] = error
    return record


def run(rules: list[dict], prompt: str, settings: llm.Settings, out_dir: Path, replicates: int = 3) -> list[dict]:
    """→ one {clause_id: record} per replicate, written to out_dir/assign.rep<N>.jsonl.

    Replicates run side by side, each with its own `settings.workers` threads — the way the lab runs them.
    """
    def one_replicate(n: int) -> dict:
        return llm.run_many(rules, key="clause_id", make_input=make_input, to_record=to_record, prompt=prompt,
                            schema=SCHEMA, settings=settings, checkpoint=out_dir / f"assign.rep{n}.jsonl",
                            label=f"assign rep{n}")

    with ThreadPoolExecutor(max_workers=replicates) as pool:
        return list(pool.map(one_replicate, range(1, replicates + 1)))
