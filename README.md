# Rules in the Wild

Three independent Docker stacks sharing a common MotherDuck DB (`rules_in_the_wild`). Each stack has its own `docker-compose.yml`, its own `.env`, and a different port set — you can run them all at the same time.

| Stack | Path | URL | What it does |
|---|---|---|---|
| Crawling agent | `crawling-agent/` | http://localhost:8501 | Streamlit admin UI — discovers + embeds + clusters rules from public GitHub repos |
| Labeling platform | `labeling-platform/` | http://localhost:5173 | React + FastAPI UI for reviewing extracted rules |
| Judge agent | `judge-agent/` | http://localhost:8503 | Streamlit dashboard + FastAPI worker that LLM-judges rules |

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) before running any of these.

## Spin up

### Crawling agent — http://localhost:8501

```bash
cd crawling-agent
cp .env.example .env       # fill in PERPLEXITY_API_KEY, optionally GITHUB_TOKEN
docker compose up -d
```

Details: [`crawling-agent/README.md`](crawling-agent/README.md).

### Labeling platform — http://localhost:5173

```bash
cd labeling-platform
# Create .env in this dir with one line:
#   MOTHERDUCK_TOKEN=eyJhbGc...your_token...
# Get a token at https://app.motherduck.com → Settings → Service Tokens.

docker compose up --build
```

Details: [`labeling-platform/rules_labeling/README.md`](labeling-platform/rules_labeling/README.md).

### Judge agent — http://localhost:8503

```bash
cd judge-agent
cp .env.example .env       # fill in PERPLEXITY_API_KEY and MOTHERDUCK_TOKEN
docker compose up --build
```

## Stop

In each stack's directory:

```bash
docker compose down        # stop + remove containers (keeps volumes)
docker compose down -v     # also wipe volumes (e.g. crawling-agent's local DuckDB)
```
