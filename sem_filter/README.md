# sem_filter — is this clause a rule?

An LLM judge labels clauses `is_rule` true / false before anything is assigned.

| | |
|---|---|
| `judge_prompt.txt` | the judge prompt, written out as text |
| `judge_test.ipynb` | where the judge was developed and scored; it holds the `RUBRIC` that the production run reads out of the notebook |
| `run_30k.py` | the production run over 30,000 sampled clauses: `openai/gpt-5.6-terra`, effort `minimal`, tier `flex`, **batch 5**, 30 workers, resumable |
| `annotator/` | the labelling web app (`docker compose up -d`) |

`run_30k.py` expects two inputs you supply: the clauses to judge (`/tmp/30k_input.json`, rows with `rule_clause` and `context`) and
the in-prompt examples (`data/50 sample in prompt.json`). It writes `data/30k filter result.json`. On our sample it labelled
13,056 clauses rules, 16,939 not rules, and left 5 unjudged.

## Jev pilot

`jev_is_rule.py` implements the same decision as a TypeSafe Noul. It keeps each
clause's existing context, but sends up to 10 clauses as independent questions over
one shared rule definition per Jev request. It stores every returned probability,
a thresholded label, latency, token usage, and estimated cost. The default is
deliberately capped at 50 rows for a pilot; pass `--limit 0` only when you intend
to process the full input. Use `--batch-size 1` to reproduce the unbatched shape.

```bash
export TYPESAFE_API_KEY=...  # or put it in .env
python sem_filter/jev_is_rule.py \
  --input /tmp/30k_input.json \
  --out sem_filter/runs/jev-pilot.json
```

If input rows contain a boolean `is_rule`, the summary also reports accuracy,
precision, recall, specificity, Brier score, and review-band coverage. The
default model is pinned to `jev-1.13.0` so a calibrated threshold does not move
when the `jev-latest` alias changes.

Key: `PERPLEXITY_API_KEY` in `.env` (git-ignored). The label source recorded downstream is
`judge v1 · gpt-5.6-terra · batch5 · minimal · flex`.
