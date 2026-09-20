# rule clause extraction

Cuts natural-language rule files written for LLM coding agents — `CLAUDE.md`,
`AGENTS.md`, `SKILL.md`, `.cursorrules`, `.mdc` — into individual clauses, with exact
character offsets back into the source.

```
Andwwy/rules                                          Andwwy/rules
 config "files"  ──►  deterministic grammar  ──►       config "clauses"
 data/*.parquet       (markdown, no LLM)               clauses/*.parquet
```

**Deterministic only.** No model, no labelling, no judgement about what counts as a
rule. The parser decides where one unit ends and the next begins and records what each
unit structurally is; deciding which ones are directives is a separate, downstream job.

The mechanism is written up in **[GRAMMAR.md](GRAMMAR.md)** — read that first if you are
changing how text is split.

## Quick start

```bash
pip install -r requirements.txt
python -m clause_extraction.run --schema     # the clause schema
python -m clause_extraction.run --stats      # what is on the Hub right now
python -m clause_extraction.run              # DRY RUN: cut, report, write nothing
python -m clause_extraction.run --push       # commit the clauses config
```

Pushing is opt-in: the target is a public dataset, so a run with no flags never mutates
the Hub. `--push` requires a **write-scoped** `HF_TOKEN` in `.env` or the environment.

| flag | effect |
|------|--------|
| `--push` | actually commit (default: dry run, parquet written locally only) |
| `--grammar v1\|v2` | segmentation grammar (default `v2`; `v1` is the legacy line-splitter) |
| `--compare` | v1 vs v2 defect counts on the corpus, writes nothing |
| `--limit N` | only process the first N rule files |
| `--refresh` | re-cut every file, even ones already done |
| `--mode sync\|append\|replace` | insert semantics (default `sync`) |
| `--out DIR` | where to write the generated parquet |
| `--files-parquet PATH` | read rule files from local parquet instead of the Hub |
| `--motherduck` | read rule files from MotherDuck instead of the Hub (see below) |
| `--md-probe` | check the MotherDuck connection + column mapping, then exit |
| `--stats` / `--schema` | report Hub state / print the schema and exit |
| `--push-card` | write the README declaring the two configs on the dataset |

## Layout

| module | role |
|---|---|
| [grammar.py](clause_extraction/grammar.py) | **the parser** — where a clause starts and ends |
| [extract.py](clause_extraction/extract.py) | one file row → its clause rows |
| [schema.py](clause_extraction/schema.py) | the clause schema written to Hugging Face |
| [hub.py](clause_extraction/hub.py) | read the `files` config, insert into `clauses` |
| [run.py](clause_extraction/run.py) | the CLI |
| [export.py](clause_extraction/export.py) | NL-text export (`exports/*.json`) |
| [bulk.py](clause_extraction/bulk.py) | MotherDuck bulk pipeline (`local/` → `staging/`) |

| directory | contents |
|---|---|
| `local/`, `staging/` | bulk-pipeline working parquet (queried/written by `bulk.py`) |
| `_corpus_cache/` | 57-file test corpus for `--compare` |
| `scripts/` | standalone tools (`make_control_set.py`) |
| `logs/` | run logs |

## The clause schema

One row per clause, 24 columns, all non-null. Three ids, each answering a different
question:

- `file_id` = sha256(repo, path) — **which file**, stable across edits
- `clause_id` = sha256(file_id, content_sha256, idx, span) — **which clause of which
  revision**; re-cutting unchanged text reproduces it exactly, so inserts are idempotent
- `text_sha256` = sha256(normalized text) — **which wording**, corpus-wide, so the same
  rule copied between repos groups with a `GROUP BY`

Provenance (`repo`, `path`, `link`, `stars`, `file_type`) is denormalized onto every row
because a Hugging Face config is loaded on its own — a row carrying only a foreign key
would need a second download and a manual join to be usable.

Position is stored twice: `char_start`/`char_end` are exact and are what an annotation UI
anchors to; `line_start`/`line_end` are what a human reads and what `link#L12` resolves
to. `unit_type` and `is_structural` say what the span structurally is; `heading_path`
gives the enclosing section breadcrumb.

Run `--schema` for the full column list.

## Already cut?

A file is skipped when the clauses config already holds rows for its
`(file_id, content_sha256, grammar, parser_version)`. The check is answered from the
clause data itself — there is no side table of state to drift out of sync.

- **file content changed** → new `content_sha256` → re-cut, old rows replaced by `sync`
- **grammar changed** → bump `PARSER_VERSION` in `config.py` → the corpus re-cuts
- **nothing changed** → skipped

## Insert modes

`hub.insert_clauses(rows, mode=…)` is the write endpoint; `hub.insert_clause(one)`
inserts a single clause. The write is a read-modify-write of the whole `clauses/` folder
committed atomically, so the config never holds duplicate `clause_id`s or clauses from a
file revision that no longer exists.

| mode | behaviour |
|------|-----------|
| `sync` (default) | incoming rows are authoritative for the files they cover — stored clauses of those `file_id`s are replaced |
| `append` | keep everything; add only `clause_id`s not already stored. Default for `insert_clause` |
| `replace` | the incoming rows become the entire clauses config |

## Reading from MotherDuck

An alternative input source. **Reads only** — clauses still go to the Hugging Face
dataset; nothing is written back to the warehouse.

```bash
# 1. put your token in .env
echo 'MOTHERDUCK_TOKEN=...' >> .env

# 2. check the connection and the column mapping before running anything
python -m clause_extraction.run --md-probe

# 3. cut (dry run), then push
python -m clause_extraction.run --motherduck --limit 20
python -m clause_extraction.run --motherduck --push
```

The crawler's `files` table names its columns differently, so they're mapped to the
canonical set the parser expects:

| canonical | MotherDuck `files` | override |
|---|---|---|
| `repo` | `repo_name` | `MD_REPO_COLUMN` |
| `path` | `file_path` | `MD_PATH_COLUMN` |
| `link` | `source_url` | `MD_LINK_COLUMN` |
| `content_sha256` | `content_hash` | `MD_SHA_COLUMN` |
| `file` (text) | `content` | `MD_TEXT_COLUMN` |
| `stars` | *absent* → `0` | `MD_STARS_COLUMN` |

`content_hash` is already `sha256(content)`, which is exactly what `clause_id` needs to
version against — so a file whose content changes in the warehouse re-cuts on the next
run, with its superseded clauses replaced by the `sync` insert.

Scope a run with raw SQL:

```bash
python -m clause_extraction.run --motherduck --md-where "file_type = 'CLAUDE.md' AND content_len < 100000"
```

`--md-db` and `--md-table` override the database (`daily-extraction`) and table (`files`).

## Configuration

Read from `.env` (setdefault-only) or the environment — see `.env.example`:

| variable | default | purpose |
|---|---|---|
| `HF_TOKEN` | — | **write-scoped** token; required for `--push`, optional for reads |
| `HF_RULES_REPO` | `Andwwy/rules` | the dataset repo |
| `HF_FILES_DIR` / `HF_CLAUSES_DIR` | `data` / `clauses` | folders inside it |
| `HF_FILES_TEXT_COLUMN` | `file` | the files column holding the document text |
| `CLAUSE_GRAMMAR` | `v2` | default grammar |
| `MOTHERDUCK_TOKEN` | — | read token; required for `--motherduck` |
| `MOTHERDUCK_DB` / `MD_FILES_TABLE` | `daily-extraction` / `files` | warehouse source |
| `MD_*_COLUMN` | see mapping above | per-column overrides |
