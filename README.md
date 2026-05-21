# Rules in the Wild

Three independent Docker stacks plus one Python CLI, all sharing a common MotherDuck DB (`rules_in_the_wild`). Each Docker stack has its own `docker-compose.yml`, its own `.env`, and a different port set — you can run them all at the same time.

| Stack | Path | URL | What it does |
|---|---|---|---|
| Prototype | `prototype/` | http://localhost:8501 | Streamlit admin UI — discovers + embeds + clusters rules from public GitHub repos |
| Labeling UI | repo root (`docker-compose.yml`) | http://localhost:5173 | React + FastAPI UI for reviewing extracted rules |
| Judge agent | `judge-agent/` | http://localhost:8503 | Streamlit dashboard + FastAPI worker that LLM-judges rules |
| Pipeline (CLI) | `rules_pipeline/` | — | Python CLI for rule extraction + classification (no Docker) |

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) before running any of these.

## Spin up

### Prototype — http://localhost:8501

```bash
cd prototype
cp .env.example .env       # fill in PERPLEXITY_API_KEY, optionally GITHUB_TOKEN
docker compose up -d
```

Details: [`prototype/README.md`](prototype/README.md).

### Labeling UI — http://localhost:5173

Run from the **repo root**:

```bash
# Create .env at the repo root with one line:
#   MOTHERDUCK_TOKEN=eyJhbGc...your_token...
# Get a token at https://app.motherduck.com → Settings → Service Tokens.

docker compose up --build
```

Details: [`rules_labeling/README.md`](rules_labeling/README.md).

### Judge agent — http://localhost:8503

```bash
cd judge-agent
cp .env.example .env       # fill in PERPLEXITY_API_KEY and MOTHERDUCK_TOKEN
docker compose up --build
```

### Pipeline (CLI, no Docker)

```bash
cd rules_pipeline
uv sync
export OPENAI_API_KEY=sk-...
uv run rules-in-the-wild --input samples
```

Details: [`rules_pipeline/README.md`](rules_pipeline/README.md).

## Stop

In each stack's directory:

```bash
docker compose down        # stop + remove containers (keeps volumes)
docker compose down -v     # also wipe volumes (e.g. prototype's local DuckDB)
```
