# Guardrail Studio

Turn a natural-language rule into a runnable check. Jev recommends an enforcer; Codex generates its rule or configuration. Review the result, try passing and failing inputs, and download a bundle to run locally.

## Setup

Requirements:

- Python 3.10+ and Node.js 22+.
- Codex CLI installed and logged in, for generation.
- A TypeSafe API key, for Jev recommendations. You can also select an enforcer manually.
- Conftest 0.71.1 on `PATH`, for file and directory checks.

From this directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm ci --ignore-scripts
cp .env.example .env
```

Set `TYPESAFE_API_KEY` in `.env`, then start Studio:

```sh
python server.py
```

Open http://127.0.0.1:8787. Bundled examples work without model credentials. This directory runs independently of the rest of the repository.

## Use

1. Enter a rule and any context needed to interpret it.
2. Click **Find generator**, or select one yourself.
3. Click **Generate**. Review and edit the generated check.
4. Try passing and failing inputs with **Run check**.
5. Download the bundle and follow its README to run it against your own artifacts.

| Category | Enforcer | Output |
| --- | --- | --- |
| Text / regex | pre-commit pygrep | `regex-check.yaml` |
| Structured data | check-jsonschema | `schema.json` |
| Files & directories | Conftest | `policy.rego` over a path inventory |
| Git changes | Danger JS | `dangerfile.js` |
| Source code | Semgrep | `semgrep.yml` |

Checks run when invoked; your agent harness, local workflow, or CI decides when to invoke them. Hook installation is optional. Review scope and test your own cases before using a generated check to block changes.

For Git checks, choose **staged changes** for the next commit or **committed branch** for changes relative to a base branch. Studio tests Danger fixtures with QuickJS; downloaded bundles run with Danger itself.

## Configuration

Settings come from this directory's `.env` or the process environment; environment variables take precedence.

| Variable | Purpose |
| --- | --- |
| `TYPESAFE_API_KEY` | Jev routing credentials |
| `STUDIO_CODEX_MODEL` | Optional model override; otherwise uses the Codex CLI default |
| `STUDIO_JEV_CAP_USD` | Aggregate routing budget; defaults to `$0.10` |

Codex generation uses your local account's quota and ignores user CLI configuration. Jev responses and spending records are saved in `data/`; keep this directory to preserve budget accounting. Failed requests with uncertain billing are not retried automatically.

`.env`, `data/`, installed dependencies, and caches are gitignored.

## Tests

With the dependencies installed and the virtual environment active:

```sh
python -m unittest discover -s tests -v
```

The suite tests generated bundles and native checkers without calling either model provider.
