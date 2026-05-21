# Rules-in-the-Wild — Local Prototype

A fully local prototype to validate the design from `../Design docs/DESIGN.md` against real ingested rules, and to drive the cluster-threshold calibration session described in §8 of that doc.

Everything runs in Docker on your laptop. No AWS, no Supabase, no public URL. You bring **one** API key — `PERPLEXITY_API_KEY` — and an optional GitHub token. Perplexity covers both the Haiku judge (`anthropic/claude-haiku-4-5` via the Agent API, passthrough pricing) and 1024-d embeddings (`pplx-embed-v1-0.6b`, int8-quantized, ~$0.004 per million tokens). Data lives in a single DuckDB file inside a named volume — `docker compose down -v` wipes it clean.

The Haiku judge ships **disabled** in this prototype (`JUDGE_ENABLED=False` in `src/config.py`) so you can iterate on the extractor + embedder + clustering without burning judge tokens. Flip it back on when the rest of the pipeline is stable. Production per DESIGN.md spec'd `voyage-3` for embeddings, not Perplexity — see [memory note](#) for the swap-back recipe.

## What this prototype does

1. **Discovers** trending agent projects on public GitHub each pass — `topic:agents`, `topic:agentic-ai`, `topic:cursor-rules`, `topic:claude-code` via `/search/repositories`, plus direct `path:AGENTS.md`, `path:CLAUDE.md`, `path:.cursorrules` via `/search/code`. Each repo is probed for the canonical filenames; repos crawled in the past 24 h are skipped, so passes naturally explore new content as GitHub's trending set rotates.
2. **Extracts** individual rules from each source file (bullet-list parser, filters out file-path bullets).
3. **Embeds** each rule (1024-d via Perplexity `pplx-embed-v1-0.6b`).
4. (Optional, off by default) **Classifies** each rule along the DESIGN.md taxonomy via Claude Haiku.
5. **Dedups** via the pipeline (exact-hash → embedding NN) into `rule_semantic_cluster` (v0.3 schema — see [`../Design docs/SCHEMA-REDESIGN.md`](../Design%20docs/SCHEMA-REDESIGN.md)). The `rule_related` see-also band is deferred until the §8 calibration session.
6. **Serves** a Streamlit admin UI at `http://localhost:8501` to start/stop the continuous crawler, browse the corpus, and run the cluster-threshold **Calibration** session.

## Quick start — host (no Docker)

```bash
cp .env.example .env                 # fill in PERPLEXITY_API_KEY, optionally GITHUB_TOKEN
set -a; source .env; set +a          # load keys into the shell
uv venv && source .venv/bin/activate # or: python -m venv .venv && source .venv/bin/activate
uv pip install -r pyproject.toml     # or: pip install -e .
streamlit run src/admin_app.py
open http://localhost:8501
```

The DuckDB file lands at `./data/rules.duckdb` (host-relative). `./data/` is created on first run. Browse the file with any local DuckDB tool: `duckdb ./data/rules.duckdb`, DBeaver, or your editor's DuckDB plugin.

## Quick start — Docker

```bash
cp .env.example .env       # fill in PERPLEXITY_API_KEY, optionally GITHUB_TOKEN
docker compose up -d       # starts admin (Streamlit + DuckDB)
open http://localhost:8501
```

> **After editing `.env`** — `docker compose up -d --force-recreate admin`. docker-compose reads `.env` at container *create* time only; a plain `restart` keeps the old env.

Inside the container the DuckDB file lives at `/data/rules.duckdb` in the `prototype_duckdata` named volume. `docker cp rules_admin_ui:/data/rules.duckdb ./rules.duckdb` copies it to host.

Then in the browser: open the **Crawl** tab → click **Start continuous crawl**. A preflight pings the embedder, the judge (if enabled), and GitHub `/rate_limit` and reports timings. On success the crawler enters continuous mode: a background thread re-runs the discovery queries every 60 seconds, accumulating new files and rules into the same DuckDB file. The `source_project.last_crawled_at`-based 24 h skip prevents re-fetching the same repos each minute. Progress shows in the **Corpus** panel.

**Continuous mode is persistent.** Clicking Start writes `continuous_mode = on` into a `crawl_settings` table in DuckDB. When the admin process restarts (Ctrl-C, `docker compose restart`, machine reboot), Streamlit reads that setting and re-spawns the thread — but the re-spawn fires when the admin **script next runs**, which is on the first browser visit after restart, not at process boot. In practice: restart admin, open the tab, the crawl resumes from where it was. The production architecture in `Design docs/ADR-001-24-7-crawler-architecture.md` uses a separate worker container precisely so this isn't tab-dependent; for a single-laptop prototype it's the right trade-off. Clicking **Stop** flips the setting back to `off`.

**What stops vs. doesn't stop the crawl:**
- **Tab close**: no effect. The crawler is a server, not a tab-bound thing.
- **Laptop sleep / close**: OS suspends the whole process; on wake, the thread continues from where it was. No state is lost because `rules_file UNIQUE (project_id, path, commit_sha)` and `rule UNIQUE (rules_file_id, line_start, line_end)` make any re-run idempotent.
- **Admin restart**: setting persists; thread re-spawns on next boot.
- **Stop button**: sets `stop_event`, thread exits at the next pass-interval check. Setting flipped to `off` so the crawler doesn't auto-restart.

**Token note.** GitHub's `/search/repositories` and `/search/code` endpoints both require authentication for any meaningful rate budget — 60 anonymous req/hr is essentially useless. Without `GITHUB_TOKEN`, the preflight blocks Start. With a token: 5 000 core req/hr + 30 search req/min, comfortable for the prototype's ~9 queries × 25 repos × 3 paths per pass.

## CLI mode (host only)

DuckDB is single-process-write, so the CLI lives outside Docker — run it from the host venv with the admin stopped. Same code, same database file (just at `./data/rules.duckdb` instead of inside the volume).

```bash
docker compose stop admin              # release the writer lock
source .venv/bin/activate              # the host venv from Quick start
set -a; source .env; set +a            # load PERPLEXITY_API_KEY / GITHUB_TOKEN

python -m src.crawl                    # one discovery pass
python -m src.crawl --cluster          # dedup pass
python -m src.crawl --stats            # row counts

docker compose start admin             # bring the UI back when done
```

If you run the host venv against the Docker volume's DuckDB file, point `DUCKDB_PATH` at it: `DUCKDB_PATH=/var/lib/docker/volumes/prototype_duckdata/_data/rules.duckdb python -m src.crawl --stats`. On macOS that path is inside the Docker VM, so the easiest path is `docker cp rules_admin_ui:/data/rules.duckdb ./data/rules.duckdb` first, then run the CLI on the local copy.

## Calibration session (§8 of DESIGN.md)

After your first ingest:

1. Open `http://localhost:8501` → **Calibration** tab.
2. Click **Load 200 stratified pairs** — 40 pairs each at cosine ≈ 0.85, 0.88, 0.91, 0.94, 0.97, drawn at random from the corpus.
3. For each pair, click **Same rule for labeling** or **Different rules**.
4. The page plots precision vs threshold as you go; pick the cosine value where precision stays ≥ 0.90.
5. Update **two places in sync** (the rule from DESIGN.md §8):
   - `src/config.py` → `CLUSTER_THRESHOLD` (and `SEE_ALSO_FLOOR`)
   - `../Design docs/DESIGN.md` §8 calibration bullet

The current placeholders (`CLUSTER_THRESHOLD = 0.93`, `SEE_ALSO_FLOOR = 0.80`) were chosen for a higher-similarity embedder. The Perplexity 0.6b model puts paraphrases around 0.9+ and unrelated pairs around 0.15; a real calibration session will need at least a thousand rules of corpus to be meaningful.

## Layout

```
prototype/
├── docker-compose.yml         # admin service only — Streamlit + crawler thread + DuckDB
├── Dockerfile                 # python:3.12-slim + duckdb wheels
├── pyproject.toml             # uv-managed deps (no torch, no postgres libs)
├── .env.example
├── db/
│   └── duckdb_schema.sql      # DuckDB-flavored schema applied on first connect
└── src/
    ├── config.py              # thresholds + JUDGE_ENABLED + EMBEDDING_MODEL
    ├── db.py                  # DuckDB connection helper + enum_values() + setting helpers
    ├── adapters/
    │   ├── base.py            # FetchedFile dataclass + Adapter Protocol
    │   └── github.py          # _fetch_one, _search_repos, _code_search, GitHubAdapter
    ├── extractor.py           # markdown → list of (rule_text, line_start, line_end)
    ├── embedder.py            # Perplexity /v1/embeddings client
    ├── judge.py               # Perplexity Agent API client (skipped when JUDGE_ENABLED=False)
    ├── cluster.py             # dedup pass: hash → embedding NN (DuckDB vss)
    ├── api_smoke.py           # preflight: embedder + judge + GitHub /rate_limit
    ├── crawl.py               # discovery + ingest; _DISCOVERY_QUERIES, run_one_pass, continuous_loop
    └── admin_app.py           # Streamlit UI: Crawl / Browse / Calibration / Stats tabs
```

## Tearing it down

Host mode:

```bash
# Ctrl-C the streamlit process. To start fresh:
rm -rf ./data
```

Docker mode:

```bash
docker compose down          # stop containers; DuckDB file in the duckdata volume survives
docker compose down -v       # stop containers + wipe the DuckDB file (clean slate)
```
