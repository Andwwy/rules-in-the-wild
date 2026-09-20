# rule-pipeline

Takes natural-language rules mined from agent instruction files (`CLAUDE.md`, `AGENTS.md`, …) and, for each rule, works out
**what could enforce it**:

```
JSON list of rules ─┐
                    ├─► 1 assign ──► 2 vote ──► 3 subcategory ──► result.json        ( ──► class, optional )
pulled from the DB ─┘   3 × prompt   judge      regex aliases,
                                     prompt     no model
```

| stage | what it does | model calls |
|---|---|---|
| **1 assign** | per rule: `enforcer[]`, `target[]`, `trigger[]`, `spec` — run 3 times with the same prompt | 3 per rule |
| **2 vote** | the judge: reconciles the 3 attempts per axis. Agreement is settled in code; only real disagreement goes to the judge prompt, and the judge may only pick values the attempts actually gave | ≤ 1 per rule |
| **3 subcategory** | deterministic grouping: each voted enforcer value → a **subcategory** by ordered regex aliases (`aliases.json`) | none |
| *class* (optional, `--stages class`) | one grouping call puts the subcategories into **classes**, checked to be an exact partition | 1 (+ small repairs) |

The default run does stages 1–3 and stops. Stages are separate: each reads what the previous one wrote into the run folder, so
they can be run one at a time (`--stages assign`, then `--stages vote`, then `--stages subcategory`) or all at once.

The whole pipeline is prompted LLM calls. [`rule_pipeline/llm.py`](rule_pipeline/llm.py) is the only file that talks to a model:
`call()` makes one JSON-schema-constrained request, `run_many()` threads it over many items with a checkpoint. Each stage is a
prompt, an input template, an output schema, and whatever plain code checks the answer.

## Quick start
```bash
cd assign+group
pip install -e .                 # add ".[db]" to read rules from the online DB, ".[test]" for the tests
cp .env.example .env             # then put your PERPLEXITY_API_KEY in it
python -m rule_pipeline.run examples/rules.sample.json --out runs/first --dry-run    # counts the requests, calls nothing
python -m rule_pipeline.run examples/rules.sample.json --out runs/first
```
Run the same command again and it **resumes**: every finished request is in the run folder, only what is missing or failed is
called. A rejected key or an exhausted quota stops the run at once with the provider's message.

## Input
A JSON list of rules in our draw schema — see [`examples/rules.sample.json`](examples/rules.sample.json).

| key | |
|---|---|
| `clause_id`, `rule_text`, `context` | **required**. `context` is what the model reads around the rule: the heading path, a blank line, then up to 8 prose lines before and 2 after the clause, code elided as `⋯`. |
| `text_sha`, `heading_path`, `repo`, `path`, `link`, `stars`, `n_dup_text`, `is_rule`, `is_rule_source` | optional, carried through to the output untouched |

Rules are expected to be judged already (`is_rule` true or absent); a rule marked `is_rule: false` is refused. Bad input fails
up front with the offending ids.

**From the online DB** instead of a file (read-only; needs `MOTHERDUCK_TOKEN` and the `db` extra):
```bash
python -m rule_pipeline.run --from-db --limit 500 --where "stars > 100" --out runs/db500
```
`--db` (default `rules`) and `--table` (default `rule_draw`) choose the source. What was pulled is saved as `rules.json` in the run
folder, so the run can be repeated without the DB.

## Output — the run folder
| file | |
|---|---|
| `rules.json` | the input as processed |
| `assign.rep1.jsonl` … | stage 1, one record per rule per replicate (also the checkpoint) |
| `vote.jsonl` | stage 2: voted `enforcer / target / trigger / spec` + a `vote` block (every attempt, how each axis was settled, what the judge kept and dropped). `vote.model.jsonl` is the checkpoint of the rules that needed the judge |
| `subcategories.json` | stage 3: `[{id, name, rules, variants}]`. `classes.json` appears only if the optional class stage was run |
| **`result.json`** | one record per rule, in input order: the vote record + `categories: [{enforcer, subcategory, class}]` (`class` is null unless the class stage was run) |
| `run.json` | prompt versions and hashes, every setting used, unfinished counts, cost |

Only rules with a voted enforcer **and** target **and** trigger are categorised (`--all-rules` lifts that), so most rules have
empty `categories` — in our 10,000-rule run 1,981 rules got an enforcer and 1,841 a full triple.

## Settings
Defaults are the lab's current settings. Command line beats environment beats default, and `run.json` records what was used.

| | default | command line | env |
|---|---|---|---|
| concurrent requests | 20 | `--workers`, `--assign-workers`, `--vote-workers` | `LLM_WORKERS` |
| rules per request | 1 | `--batch-size`, `--assign-batch-size`, `--vote-batch-size` | `LLM_BATCH_SIZE` |
| provider | `perplexity` | `--provider` | `LLM_PROVIDER` |
| model, tier | `openai/gpt-5.6-terra`, `flex` | `--model`, `--tier` | `LLM_MODEL`, `LLM_TIER` |
| reasoning effort | assign `high`, vote `medium`, classes `high` | `--assign-effort`, `--vote-effort`, `--class-effort` | |
| replicates | 3 | `--replicates` | |
| stages | `assign,vote,subcategory` | `--stages vote`, `--stages assign,vote,subcategory,class`, … | |

* Replicates run side by side, each with its own workers — 3 × 20 requests in flight by default.
* **Batch size above 1** packs several rules into one request. The prompt files are not changed: each rule gets a header with its
  id, the answer schema becomes a list keyed by id, and any rule the reply drops, repeats or invents is redone alone. The default
  stays 1 because rules sharing a request influence each other's answers, and everything we measured was measured at 1.
* `--vote-with-rule` shows the judge the rule and its context as well as the three attempts (`prompts/vote_with_rule.txt`).
  Every run we have evaluated used the default, attempts-only prompt.
* Cost, from our 10,000-rule run on `flex`: about $6.8 per 1,000 rules for the three assignment replicates and $1.6 for the vote.
  The current assignment prompt is longer than the one that was measured.

## Prompts and aliases
`prompts/prompts.json` names the prompt file and version of each stage — the only place a version lives. To change a prompt, edit
or add a file there and update that entry; its hash lands in `run.json`. Prompts are used verbatim; the code never edits them.

`aliases.json` is an ordered list of `[regex, subcategory]`. The first regex that matches an enforcer value (case-insensitive)
names its subcategory; a value that matches nothing is its own subcategory. The list was tuned on our 10,000-rule run, so on new
data expect more values to stay verbatim until you add rules for them. `--class-names FILE` maps the model's class names to
shorter display names (the model's name is kept as `class_long`).

## Adding a provider
A provider is one entry in `PROVIDERS` in [`llm.py`](rule_pipeline/llm.py): the URL, the name of the key variable, a function that
builds the request body and one that reads the reply into `(text, usage)`. Nothing else in the code knows which provider is used.

## Code map
```
rule_pipeline/llm.py          call() + run_many(): providers, retries, threads, batching, checkpoint/resume
rule_pipeline/rules.py        load rules from JSON or the DB, validate them
rule_pipeline/assign.py       stage 1: input template + schema
rule_pipeline/vote.py         stage 2: routing, the rails on the judge's answer, spec pick
rule_pipeline/categorize.py   stage 3: the regex aliases (deterministic); the optional class call with its partition check + repair
rule_pipeline/run.py          the command line; writes the run folder
tests/                        offline, a fake model stands in for llm.call
```
```bash
python -m pytest              # 21 tests, no network, < 1 s
```
`tests/test_parity_local.py` additionally replays our recorded 10,000-rule run through `vote.py` and `categorize.py` and
requires the same result; it is skipped when that run is not on disk (it is not part of the repo).

## Not in this repo
`archive/`, `data/`, `runs/` and `motherduck upload/` are git-ignored: past runs and scripts, the rule draws, run outputs and the
lab's warehouse loader stay local. `result.json` keeps the keys of the lab's `assignment output.json`, so a finished run can be
staged for the warehouse by adding one line to `motherduck upload/build_staging.py`.
