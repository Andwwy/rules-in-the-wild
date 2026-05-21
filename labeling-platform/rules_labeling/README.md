# Rules Labeling

Local labeling UI for reviewing extracted rules and classification output from the rules pipeline.

## Run Locally

Start the API against a pipeline DuckDB file:

```bash
cd rules_labeling/backend
uv run rules-labeling-api --db ../../rules_pipeline/rules.duckdb
```

Start the React app:

```bash
cd rules_labeling/frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Tests

Backend:

```bash
cd rules_labeling/backend
uv run pytest
```

Frontend unit tests:

```bash
cd rules_labeling/frontend
npm test -- --run
```

Browser smoke test:

```bash
cd rules_labeling/frontend
npm run test:e2e
```
