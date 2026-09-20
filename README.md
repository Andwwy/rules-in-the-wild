# rules in the wild

Natural-language rules mined from agent instruction files (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, …): collect them, cut them
into clauses, keep the ones that are rules, work out what could enforce each rule, and evaluate that enforcement.

```
crawl ──► clause extraction ──► is_rule filter ──► assign → vote → categorize ──► enforcement eval
archive/     rule clause           sem_filter/          assign+group/                 enforcement eval/
rule crawling/  extraction/                             (= the rule-pipeline repo)    enforcement eval test/
```

| stage | folder | what it holds | where its output lives |
|---|---|---|---|
| 1 crawl | `archive/rule crawling/` (finished Jul 2026) | the GitHub crawler for rule files | MotherDuck `rules.rule_file` — 2,204,470 files |
| 2 clause extraction | `rule clause extraction/` | the parser that cuts files into clauses, its audit, the bulk loader | MotherDuck `rules.rule_clause` — 55,182,794 clauses; Hugging Face dataset |
| 3 is_rule filter | `sem_filter/` | the judge prompt, the 30k judged sample, labelled control sets, the annotator | `sem_filter/data/30k filter result.json` → the 10k draw in `assign+group/data/` |
| 4 assign → vote → categorize | `assign+group/` | **`rule-pipeline`**, the shareable git repo: three prompted stages in six small modules. Past runs are local-only under its `archive/` and `data/` | MotherDuck `rule_assignment*`, `rule_subcategory`, `subcategory_class` (loader: `assign+group/motherduck upload/`) |
| 5 enforcement eval — **local only** | `enforcement eval/` | related work (≈160 entries), datasets per enforcer class, the proposed end-to-end eval design | — |
| — **local only** | `enforcement eval test/` | the local pilot: 10 rules per enforcer category, two tracks, scored on execution (`REPORT.md`) | — |

Every active folder has its own README; start there. Folder names are kept stable on purpose — Claude Code sessions and a few
scripts are keyed to these paths.

## What is in this repo, and what stays local
In the repo: code, prompts and READMEs of three stages — `rule clause extraction/` (the clause parser and loaders),
`sem_filter/` (the is_rule judge prompt, runner and annotator) and `assign+group/` (the `rule-pipeline` package: start there,
`cd assign+group` and follow its README).

**Local only**, never published: `archive/`, `enforcement eval/`, `enforcement eval test/`, `.venv-jupyter/`, every `.env`, and the
data of the shared stages — `sem_filter/data/` and `sem_filter/archive/`, `rule clause extraction/audit/` and `exports/`,
`assign+group/archive/`, `data/`, `runs/` and `motherduck upload/`. They hold crawled third-party text, labels, run outputs and
past experiments. The `.gitignore` files say the same. A few READMEs therefore mention folders you will not find here.

## archive/ (local only)
Past material, kept locally and never deleted; see `archive/README.md`. Besides the finished crawl it holds the early dev set,
the 8-class enforcer mapping + translation study (`map/`), the enforcement translation test, and the DocETL / semantic-operator
experiments. Scripts in there are records — many carry absolute paths from before they moved.

## Keys and environments
* Secrets live in per-project `.env` files that are never committed: `sem_filter/.env` (Perplexity),
  `rule clause extraction/.env` (MotherDuck, Hugging Face), `assign+group/.env` (copy `.env.example`).
* Perplexity's agent API is the group's default model provider (`openai/gpt-5.6-terra`, `flex`).
* `.venv-jupyter/` is the shared notebook environment; do not move it (virtualenvs hard-code their path).
