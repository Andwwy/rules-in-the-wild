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
cp ../.env.example .env          # or fill in the slots in DAPlab/.env: every .env up the tree is read, nearest first
python -m rule_pipeline.llm --check perplexity                                       # one tiny request: is the key good?
python -m rule_pipeline.run examples/rules.sample.json --out runs/first --dry-run    # counts the requests, calls nothing
python -m rule_pipeline.run examples/rules.sample.json --out runs/first
```
Run the same command again and it **resumes**: every finished request is in the run folder, only what is missing or failed is
called. A rejected key or an exhausted quota stops the run at once with the provider's message.

## Providers
One switch, `--provider`, and the same model name for all three:

| `--provider` | reached through | key | `openai/gpt-5.6-terra` is sent as | default tier |
|---|---|---|---|---|
| `perplexity` (`pplx`), default | Agent API `/v1/agent`, called directly | `PERPLEXITY_API_KEY` | `openai/gpt-5.6-terra` | flex |
| `openai` | LiteLLM → Chat Completions | `OPENAI_API_KEY` | `gpt-5.6-terra` | flex |
| `bedrock` (`aws`) | LiteLLM → Bedrock's OpenAI-compatible (Mantle) endpoint; other vendors → Converse | `AWS_BEARER_TOKEN_BEDROCK`, else the AWS credential chain (`~/.aws`), region `AWS_REGION_NAME` | `openai.gpt-5.6-terra` | none (Mantle has no flex) |

* Every request asks for the stage's JSON schema in strict mode (each object closed, every property required); without it a vote
  reply once came back in the wrong shape and crashed the vote.
* A setting a provider cannot take stops the run instead of being dropped silently: `--provider bedrock --tier flex` fails at
  once. (LiteLLM's own `bedrock/openai.*` route drops the schema and the effort without a word, which is why it is not used.)
* A 429 waits for the provider's `Retry-After` (else 10, 20, 40 … s, up to 6 times); `insufficient_quota` stops the run.
* `python -m rule_pipeline.llm --check perplexity openai bedrock` sends one tiny request to each and prints the answer or the
  error.
* **Spend:** every answered request goes into the project's spend ledger (shared with the MTAC
  experiment's gateway), and no request starts once `RITW_BUDGET_USD` (default $50) is spent. `python -m rule_pipeline.spend`
  prints the totals by source and by day.

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
| provider | `perplexity` | `--provider perplexity\|openai\|bedrock` | `LLM_PROVIDER` |
| model, tier | `openai/gpt-5.6-terra`, the provider's default tier | `--model`, `--tier` | `LLM_MODEL`, `LLM_TIER` |
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
A provider is one entry in `ROUTES` in [`llm.py`](rule_pipeline/llm.py): its key variables, how it spells a `vendor/model` name,
its default tier, and the function that sends a request (`_send_litellm` for anything LiteLLM serves well, or a direct HTTP call
like `_send_perplexity`). Nothing else in the code knows which provider is used. Add a request-capture test to
`tests/test_providers.py`.

## Code map
```
rule_pipeline/llm.py          call() + run_many(): the provider routes, retries, threads, batching, checkpoint/resume
rule_pipeline/rules.py        load rules from JSON or the DB, validate them
rule_pipeline/assign.py       stage 1: input template + schema
rule_pipeline/vote.py         stage 2: routing, the rails on the judge's answer, spec pick
rule_pipeline/categorize.py   stage 3: the regex aliases (deterministic); the optional class call with its partition check + repair
rule_pipeline/spend.py        the project's spend ledger and budget (standard library only)
rule_pipeline/run.py          the command line; writes the run folder
tests/                        offline: a fake model stands in for llm.call; test_providers.py records what each route sends
```
```bash
python -m pytest              # 19 tests, no network, < 1 s
```
