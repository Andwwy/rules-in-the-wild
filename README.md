# rules in the wild

Natural-language rules from agent instruction files (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, …) → what could enforce each rule.

```
rule files ─► clause extraction ─► is_rule filter ─► assign ×3 ─► majority-vote judge ─► subcategory
              rule clause           sem_filter/       └──────────────── assign+group/ ───────────────┘
              extraction/
```

| folder | what it does |
|---|---|
| [`rule clause extraction/`](rule%20clause%20extraction/) | cuts rule files into clauses (a markdown parser, no LLM) |
| [`sem_filter/`](sem_filter/) | an LLM judge labels each clause: is it a rule? |
| [`assign+group/`](assign+group/) | **the pipeline**: for each rule, an LLM assigns `enforcer / target / trigger / spec` three times, a judge reconciles the three, and regex aliases group the enforcers into subcategories |

## Run the pipeline
```bash
git clone https://github.com/Andwwy/rules-in-the-wild.git && cd rules-in-the-wild/assign+group
pip install -e .
cp ../.env.example .env                  # fill in PERPLEXITY_API_KEY
python -m rule_pipeline.run examples/rules.sample.json --out runs/first --dry-run    # counts requests, calls nothing
python -m rule_pipeline.run examples/rules.sample.json --out runs/first
```
* **Input**: a JSON list of rules (`clause_id`, `rule_text`, `context`) — or `--from-db` to pull them from MotherDuck with `MOTHERDUCK_TOKEN`.
* **Output**: `runs/first/result.json`, one record per rule. Rerunning the same command resumes where it stopped.
* Stages can run separately (`--stages assign`, `vote`, `subcategory`); threads and batch size are flags (defaults 20 and 1).
* Everything else — settings, prompts, adding a model provider, tests — is in [`assign+group/README.md`](assign+group/README.md).

## Keys
Copy [`.env.example`](.env.example) to `.env` in the folder you run from: `PERPLEXITY_API_KEY` (the model provider),
`MOTHERDUCK_TOKEN` (the database), `GH_TOKEN` (GitHub API). Never commit a `.env`; they are git-ignored.

## Database
Results are stored in the MotherDuck database `rules`. A rule is a `rule_clause` row; it has many assignments, one per version,
and each version keeps the prompt that produced it.

```mermaid
erDiagram
    rule_clause ||..o| rule_draw : "clause_id (checked at push)"
    rule_draw ||--o{ rule_assignment : "clause_id"
    rule_assignment_version ||--o{ rule_assignment : "assign_version"
    rule_assignment ||--o{ rule_subcategory : "assign_version + clause_id"
    subcategory_class ||--o{ rule_subcategory : "assign_version + subcategory"

    rule_clause {
        varchar clause_id "existing, 55M rows, read only"
        varchar text
        varchar context
    }
    rule_draw {
        varchar clause_id PK "the 10,000 drawn rules"
        varchar rule_text
        varchar context "what the model saw"
        boolean is_rule "judge label"
        varchar draw
    }
    rule_assignment_version {
        varchar assign_version PK "12 versions"
        int version_rank UK "highest non-replicate = default"
        varchar kind "single, replicate, vote"
        varchar prompt "one cell"
        varchar model
        varchar effort
        json subcategory_how "NULL = never aggregated"
        json class_how
    }
    rule_assignment {
        varchar assign_version PK, FK
        varchar clause_id PK, FK "many versions per rule"
        list enforcer "empty list = none"
        list target
        list trigger
        varchar spec
        json vote "votes only"
    }
    rule_subcategory {
        varchar assign_version PK, FK
        varchar clause_id PK, FK
        varchar enforcer PK "one enforcer value"
        varchar subcategory FK "regex pass"
    }
    subcategory_class {
        varchar assign_version PK
        varchar subcategory PK "619 in v1.11.vote"
        varchar class "14, LLM grouping, nullable"
        varchar class_long
    }
```

Solid lines are foreign keys; the dashed link is checked at load time. Query through the views `rule_assignment_current` (the
newest assignment of each rule) and `rule_enforcer_current` (one row per enforcer, with its subcategory and class).
