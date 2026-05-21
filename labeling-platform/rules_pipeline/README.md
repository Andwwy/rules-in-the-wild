# Rules in the Wild

LLM-backed rules extraction and classification pipeline built around DuckDB and the
Flock DuckDB extension. Python is only the runner: ingestion, Flock setup, and SQL
execution. The extraction and classification logic lives in package resource
subdirectories `src/rules_in_the_wild/extract/` and
`src/rules_in_the_wild/classify/`.

## Setup

```bash
uv sync
export OPENAI_API_KEY=...
```

The project pins DuckDB Python to `1.5.2` and expects the Flock community
extension build `ed1ee54`. Flock is installed from DuckDB's community extension
repository by default. For an OpenAI-compatible provider, set `OPENAI_BASE_URL`
and optionally override `--model-name`.

## Run

Run both stages:

```bash
uv run rules-in-the-wild --input samples
```

Run only extraction:

```bash
uv run rules-in-the-wild --extract --input path/to/docs
```

Run only classification against already extracted rules:

```bash
uv run rules-in-the-wild --classify
```

Useful flags:

```bash
uv run rules-in-the-wild \
  --input path/to/docs \
  --db rules.duckdb \
  --model-name gpt-5.4-mini \
  --force
```

## Prompts

Default prompts live in `prompts/extract.md` and `prompts/classify.md`. The
packaged wheel also includes these files as fallbacks, but local runs read the
top-level files by default so prompts can be edited without touching Python or
SQL.

Override one or both prompts from alternate files:

```bash
uv run rules-in-the-wild \
  --input samples \
  --extract-prompt-file experiments/extract-v2.txt \
  --classify-prompt-file experiments/classify-v2.txt
```

For quick experiments, pass literal prompt text:

```bash
uv run rules-in-the-wild \
  --input samples \
  --extract-prompt "Extract rule text plus start/end line numbers only."
```

The project-level wrapper also works:

```bash
uv run python run.py --input samples
```

## Tables

- `source_documents`: ingested text documents keyed by content hash.
- `extraction_runs`: raw structured LLM responses for document-level extraction.
- `extracted_rules`: normalized rules with deterministic document metadata and
  source line spans.
- `classification_runs`: raw structured LLM responses for rule classification.
- `classified_rules`: normalized classification output with prerequisites,
  enforcement mechanisms, triggers, and ambiguity.

## SQL Entry Points

- `src/rules_in_the_wild/extract/extract_rules.sql`
- `src/rules_in_the_wild/classify/classify_rules.sql`

Both files expect the Python wrapper to install Flock prompt objects and set
`rules_model_alias`, `force_rerun`, and the relevant prompt-name session
variables before execution.
