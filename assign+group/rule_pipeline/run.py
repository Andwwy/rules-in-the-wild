"""Command line: rules → assignment → majority-vote judge → deterministic grouping.

    python -m rule_pipeline.run rules.json --out runs/first          rules from a JSON file, through all three stages
    python -m rule_pipeline.run --from-db --limit 500 --out runs/db  rules pulled from MotherDuck (needs MOTHERDUCK_TOKEN)
    python -m rule_pipeline.run rules.json --out runs/first          again: resumes, calls only what is missing

Stages can also be run one at a time on the same run folder, each reading what the one before it wrote:

    ... --stages assign          3 replicates per rule                      → assign.rep<N>.jsonl
    ... --stages vote            the judge reconciles the replicates        → vote.jsonl
    ... --stages subcategory     regex aliases, no model                    → subcategories.json, result.json
    ... --stages class           optional: one model call groups the subcategories into classes → classes.json

A run folder holds everything a run read and wrote:

    rules.json                 the input, as processed
    assign.rep<N>.jsonl        stage 1, one file per replicate
    vote.jsonl                 stage 2 (vote.model.jsonl = the rules that needed the judge)
    subcategories.json         stage 3 (deterministic)
    classes.json               only if the optional class stage was run
    result.json                one record per rule: the voted axes, the vote, and the subcategory (+ class) per enforcer
    run.json                   prompts (version + sha), settings, counts, cost
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from . import assign, categorize, llm, rules as rules_io, vote

ROOT = Path(__file__).resolve().parent.parent
STAGES = ("assign", "vote", "subcategory", "class")
DEFAULT_STAGES = ("assign", "vote", "subcategory")            # `class` is one more model call and is opt-in
# Rough $ per request, measured on the v1.11 10,000-rule run (terra, flex). Only used by --dry-run.
COST_PER_CALL = {"assign": 0.0023, "vote": 0.0020}


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="rule_pipeline.run", description=__doc__.splitlines()[0])
    p.add_argument("rules", nargs="?", help="JSON file with the rules (our draw schema)")
    p.add_argument("--out", required=True, type=Path, help="run folder; reuse it to resume")
    p.add_argument("--stages", default=",".join(DEFAULT_STAGES),
                   help=f"comma-separated, default {','.join(DEFAULT_STAGES)}; add `class` for the optional model grouping")
    p.add_argument("--dry-run", action="store_true", help="count the requests, call nothing")

    db = p.add_argument_group("rules from the online DB instead of a file")
    db.add_argument("--from-db", action="store_true")
    db.add_argument("--db", default="rules")
    db.add_argument("--table", default="rule_draw")
    db.add_argument("--where", help="SQL condition, e.g. \"stars > 100\"")
    db.add_argument("--limit", type=int)

    m = p.add_argument_group("model (defaults = the lab's current settings; env: LLM_PROVIDER LLM_MODEL LLM_TIER LLM_WORKERS LLM_BATCH_SIZE)")
    m.add_argument("--provider", default=os.environ.get("LLM_PROVIDER"))
    m.add_argument("--model", default=os.environ.get("LLM_MODEL"))
    m.add_argument("--tier", default=os.environ.get("LLM_TIER"))
    m.add_argument("--workers", type=int, default=_env_int("LLM_WORKERS"), help="concurrent requests [20]")
    m.add_argument("--batch-size", type=int, default=_env_int("LLM_BATCH_SIZE"), help="rules per request [1]")
    for stage in ("assign", "vote"):
        m.add_argument(f"--{stage}-workers", type=int, help=f"override --workers for {stage}")
        m.add_argument(f"--{stage}-batch-size", type=int, help=f"override --batch-size for {stage}")
    m.add_argument("--assign-effort", default="high")
    m.add_argument("--vote-effort", default="medium")
    m.add_argument("--class-effort", default="high")

    o = p.add_argument_group("pipeline")
    o.add_argument("--replicates", type=int, default=3, help="assignment runs per rule [3]")
    o.add_argument("--vote-with-rule", action="store_true", help="show the judge the rule and its context too")
    o.add_argument("--all-rules", action="store_true", help="categorise every rule with an enforcer, not only full triples")
    o.add_argument("--prompts", type=Path, default=ROOT / "prompts")
    o.add_argument("--aliases", type=Path, default=ROOT / "aliases.json")
    o.add_argument("--class-names", type=Path, help="JSON {model's class name: short display name}")
    args = p.parse_args(argv)
    if bool(args.rules) == args.from_db:
        p.error("give a rules file or --from-db (one of them)")
    args.stages = [s.strip() for s in args.stages.split(",") if s.strip()]
    if unknown := [s for s in args.stages if s not in STAGES]:
        p.error(f"unknown stage {unknown}; stages are {', '.join(STAGES)}")
    return args


def _env_int(name):
    return int(os.environ[name]) if os.environ.get(name) else None


def load_prompt(folder: Path, name: str) -> tuple[str, dict]:
    entry = json.loads((folder / "prompts.json").read_text())[name]
    text = (folder / entry["file"]).read_text()
    return text, {**entry, "sha256": hashlib.sha256(text.encode()).hexdigest()}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main(argv=None):
    load_dotenv(ROOT / ".env")
    load_dotenv()                                            # a .env in the working directory wins nothing already set
    args = parse_args(argv)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    base = llm.Settings().but(provider=args.provider, model=args.model, tier=args.tier,
                              workers=args.workers, batch_size=args.batch_size)
    settings = {
        "assign": base.but(effort=args.assign_effort, workers=args.assign_workers, batch_size=args.assign_batch_size),
        "vote": base.but(effort=args.vote_effort, workers=args.vote_workers, batch_size=args.vote_batch_size),
        "class": base.but(effort=args.class_effort, workers=1, batch_size=1),
    }

    # ── input ──
    if (out / "rules.json").exists() and not args.rules:
        rules = rules_io.load_json(out / "rules.json")       # a resumed DB run reads what it pulled the first time
        source = "rules.json of this run folder"
    elif args.from_db:
        rules = rules_io.load_db(args.db, args.table, args.where, args.limit)
        source = f"db {args.db}.{args.table}" + (f" where {args.where}" if args.where else "") + (f" limit {args.limit}" if args.limit else "")
    else:
        rules = rules_io.load_json(args.rules)
        source = str(args.rules)
    (out / "rules.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(rules)} rules from {source}", flush=True)

    if args.dry_run:
        return dry_run(rules, args, settings, out)

    started = time.time()
    prompts_used, voted, rows, class_of = {}, None, [], {}

    if "assign" in args.stages:
        prompt, prompts_used["assignment"] = load_prompt(args.prompts, "assignment")
        assign.run(rules, prompt, settings["assign"], out, args.replicates)

    if "vote" in args.stages:
        name = "vote_with_rule" if args.vote_with_rule else "vote"
        prompt, prompts_used[name] = load_prompt(args.prompts, name)
        replicates = [llm.read_checkpoint(out / f"assign.rep{n}.jsonl", "clause_id") for n in range(1, args.replicates + 1)]
        voted = vote.run([r["clause_id"] for r in rules], replicates, prompt, settings["vote"], out, args.vote_with_rule)

    if {"subcategory", "class"} & set(args.stages):
        if voted is None:
            voted = read_jsonl(out / "vote.jsonl")
        subcats, rows = categorize.subcategories(voted, categorize.load_aliases(args.aliases), not args.all_rules)
        (out / "subcategories.json").write_text(json.dumps(subcats, ensure_ascii=False, indent=1) + "\n")
        print(f"subcategory: {len({r['clause_id'] for r in rows})} rules | {len(rows)} enforcer values | "
              f"{len(subcats)} subcategories", flush=True)
        if "class" in args.stages and subcats:
            prompt, prompts_used["classes"] = load_prompt(args.prompts, "classes")
            class_names = json.loads(args.class_names.read_text()) if args.class_names else None
            class_of = categorize.classify(subcats, prompt, settings["class"], out, class_names)
        else:
            class_of = categorize.load_classes(out, subcats) or {}      # keep the classes of an earlier class run

    # ── outputs ──
    if voted is not None:
        categories = {}
        for row in rows:
            categories.setdefault(row["clause_id"], []).append(
                {"enforcer": row["enforcer"], "subcategory": row["subcategory"], "class": class_of.get(row["subcategory"])})
        result = [record | {"categories": categories.get(record["clause_id"], [])} for record in voted]
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")

    write_run_json(out, args, source, settings, prompts_used, len(rules), time.time() - started)


def dry_run(rules, args, settings, out):
    n = len(rules)
    assign_calls = -(-n // settings["assign"].batch_size) * args.replicates
    print(f"assign: {assign_calls} requests ({args.replicates} replicates, batch {settings['assign'].batch_size}) "
          f"≈ ${assign_calls * COST_PER_CALL['assign']:.2f}")
    replicate_files = [out / f"assign.rep{k}.jsonl" for k in range(1, args.replicates + 1)]
    if all(f.exists() for f in replicate_files):
        reps = [llm.read_checkpoint(f, "clause_id") for f in replicate_files]
        need = sum(1 for i in reps[0] if all(i in r for r in reps) and vote.plan([r[i] for r in reps])[2])
        print(f"vote: {need} rules need the judge ≈ ${need * COST_PER_CALL['vote']:.2f}")
    else:
        print(f"vote: at most {n} requests (known after assignment; about 80% of rules in the lab's 10k run)")
    print("subcategory: no requests (regex aliases)")
    if "class" in args.stages:
        print("class: 1 request (+ a few small repairs)")
    print("nothing was called.")


def write_run_json(out, args, source, settings, prompts_used, n_rules, seconds):
    def cost(path):
        return sum((r.get("usage") or {}).get("cost") or 0 for r in read_jsonl(path)) if path.exists() else 0

    files = [*(out / f"assign.rep{k}.jsonl" for k in range(1, args.replicates + 1)), out / "vote.model.jsonl"]
    summary = {
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"), "seconds_this_invocation": round(seconds),
        "input": source, "rules": n_rules, "stages": args.stages, "replicates": args.replicates,
        "vote_with_rule": args.vote_with_rule, "full_triples_only": not args.all_rules,
        "prompts": prompts_used,
        "settings": {stage: vars(s) for stage, s in settings.items()},
        "unfinished": {f.name: n_rules - len(llm.read_checkpoint(f, "clause_id")) for f in files[:-1] if f.exists()},
        "cost_usd": round(sum(cost(f) for f in files), 4),
    }
    (out / "run.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
    print(f"done → {out}  (cost so far ${summary['cost_usd']:.2f})", flush=True)


if __name__ == "__main__":
    main()
