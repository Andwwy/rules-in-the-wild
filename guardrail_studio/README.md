# Guardrail Studio

Natural-language rule + context → Jev recommends a target → Codex generates a native checker artifact → inspect, test, and download. The model-generated checks are not human-validated.

## Run

Run these commands from this directory, which can be copied or checked out independently:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm ci --ignore-scripts
cp .env.example .env
# Set TYPESAFE_API_KEY in .env for live routing.
python server.py
```

Open http://127.0.0.1:8787. No frontend build step. Requires Python 3.10+, Node.js 22+, and a local Codex CLI installation/login for live generation. The bundled examples work without model credentials. Native Python checkers are installed by requirements.txt; Conftest is a separate binary: install version 0.71.1 from the official project release/package manager and put it on PATH. Danger dependencies are pinned by package-lock.json.

Configuration is read only from this directory's `.env` and the process environment; process environment values take precedence. Studio does not load a parent repository's configuration or depend on the classifier, corpus, or generator-taxonomy outputs. Runtime caches and the aggregate routing-spend ledger live in `data/`. Keep that directory when resuming usage so the budget history is preserved.

The project directories are `static/`, `tests/`, and `audits/`, plus generated `data/`, `.venv/`, `__pycache__/`, and `node_modules/`. Project directories use snake_case (including the enclosing `guardrail_studio/`); installed dependency names are managed by their package managers. `.env`, runtime data, virtual environments, caches, and node_modules are excluded by .gitignore. Commit `.env.example` and both npm manifests.

## Native outputs

| Target | Generated artifact | Manual invocation |
| --- | --- | --- |
| pygrep | regex-check.yaml, a native pre-commit configuration | pre-commit run --config regex-check.yaml --all-files, or --files ... |
| JSON Schema | schema.json | check-jsonschema --schemafile schema.json input.json input.yaml |
| Conftest / path inventory | policy.rego | conftest test inventory.json --policy policy.rego --rego-version v1 --strict --show-builtin-errors --capabilities capabilities.json |
| Danger / local Git | dangerfile.js | npm run check -- --repo /path/to/repo in the downloaded bundle |
| Semgrep | semgrep.yml | semgrep scan --config semgrep.yml --error --strict --metrics=off TARGET |

Hook installation is not required for these commands. The four new native bundles contain no hook installers or custom Python policy engine. Danger's previously implemented hook installer remains optional. Studio does not install hooks or modify a target repository automatically.

The app retains an internal spec envelope for metadata, application scope and orchestration. The editor, copy button and download expose native source/configuration. Editing source is parsed and validated through /api/source without a model call. Previously saved custom JSON specs remain readable for compatibility; new routing uses the native targets.

## Input preparation and meaning

- **pygrep**: test plain text directly, or supply `{ "files": {"relative/path.txt":"text"} }`. Native `files` and `exclude` are filename regexes. Missing deployment paths do not prevent generation. Default pygrep scans byte lines. `--multiline` scans the whole file with MULTILINE/DOTALL; `--negate` means at least one match per file, not every line. Whole-value predicates need absolute anchors, and every-line obligations need explicit invalid-line detection. Multiple native hooks can compose checks. It does not parse PDF or source ASTs.
- **JSON Schema**: paste a raw JSON document or use file fixtures with JSON, YAML, JSONL or NDJSON text. YAML is parsed first; JSONL is validated one record at a time. The exported check_jsonl.py only splits/parses records and invokes check-jsonschema; it contains no generated predicate. Empty/unparseable input does not silently pass. Schemas are Draft 2020-12 and self-contained with internal references; missing authoritative contracts still need context. Missing types remain unconstrained. Scope is optional until repository application.
- **Conftest**: paste `{ "entries": [{"path":"services/api","kind":"directory"},{"path":"services/api/Dockerfile","kind":"file"}] }`. Kinds are file/directory/symlink/other; symlinks include a lexical target string. The exported manifest.py is a generic, read-only metadata collector: it skips .git, follows no symlinks, and reads no file contents. It contains no rule predicates. Rules are native Rego, evaluated by Conftest with capabilities derived from OPA 1.21.1 and excluding HTTP, DNS lookup and runtime access. A service definition must come from source/context, not an invented glob. The collector takes an explicitly selected inventory root.
- **Semgrep**: supply source-file fixtures. Native per-rule paths, options, metadata, nested operators, and supported taint rules are passed to the actual engine. A previous custom top-level allowlist has been removed. Search and taint use the installed community engine; no proprietary/interfile guarantees are inferred. Active network validators, autofixes and dependency/secrets scanning require a separate interface. Scan errors and no applicable files are not passes.
- **Danger**: fixture tests run the same generated JS in a resource-limited, capability-free QuickJS context with a defined subset of the Danger API. Downloaded source runs with the real Danger runtime. Staged mode checks the index against HEAD and respects partial staging; branch mode compares committed HEAD from merge-base(base, HEAD), excluding the proposed staged commit. No PR, CI, token or network is needed for local runtime after dependencies are installed. See the generated bundle README for details.

These checks inspect supplied artifacts. They do not prevent each intermediate file write. A working-tree scan is distinct from a staged-snapshot check; Studio does not claim that wrapping every checker in a commit hook validates staged contents. Runtime permissions, approvals and transient actions remain separate targets.

## Models and accounting

Jev selects from defined targets and no-match outcomes; it does not generate code. Codex translates to the selected native format. It runs in a temporary read-only directory, ignores user configuration, and is instructed to use no tools. Optional STUDIO_CODEX_MODEL selects a specific CLI model. STUDIO_GENERATOR defaults to codex. No automatic generation retries.

Jev 1.14.0 price was checked 2026-10-27: $0.042/M input tokens, output free. A persistent $0.10 default Studio cap is enforced in data/jev-ledger.json. Completed responses are cached; uncertain requests retain a conservative reservation and are not automatically retried. The ledger is separate from the previous taxonomy-run ledger. Codex uses the local account's quota. Requests use the full supplied rule/context within a 16,000-character input bound; they are not silently truncated.

## Validation

```sh
source .venv/bin/activate
npm ci --ignore-scripts
python -m unittest discover -s tests -v
```

Tests exercise native engines and exported artifacts: pygrep matching and file filtering, standalone JSON Schema with YAML/JSONL parsing, typed inventories and universal/count Rego predicates, Semgrep paths and taint, plus local Danger file/line counts, conditional changesets and actual commit acceptance/rejection in disposable repositories. Native tests require the corresponding executable on PATH. No tests install hooks in this project.

Audits under audits/ record the pre-fix implementation findings and reproducible evidence. They are historical snapshots, not claims that all generators or all 9,839 clauses have been validated.
