# sem_filter — is this clause a rule?

Stage 3 of the pipeline: an LLM judge labels clauses `is_rule` true / false before anything is assigned.

| | |
|---|---|
| `judge_test.ipynb` | where the judge was developed and scored; it holds the `RUBRIC` that the production run reads **out of the notebook** |
| `judge_prompt.txt` | the judge prompt written out as text (2026-09-09, later than the 30k run) — the copy the enforcement eval cites |
| `run_30k.py` | the production run: 30,000 sampled clauses; system prompt = the notebook's rubric + the 50 examples of `data/50 sample in prompt.json` — `openai/gpt-5.6-terra`, effort `minimal`, tier `flex`, **batch 5**, 30 workers, resumable. Reads `/tmp/30k_input.json`, writes `data/30k filter result.json` |
| `data/30k filter result.json` | the result: 13,056 rules, 16,939 not rules, 5 unjudged of 30,000. The 10,000-rule draw in `../assign+group/data/` was drawn from these |
| `data/labeled 100.json`, `data/50 control set.json` (+ `ANSWERS`), `data/100_sample*.json*` | hand-labelled sets used to score the judge |
| `annotator/` | the labelling web app (`docker compose up -d`); `../rule clause extraction/.claude/launch.json` can start it |
| `archive/` | earlier prompt versions (`v20`), backups, cost experiments |

`data/` and `archive/` are local only (crawled third-party text, labels, old runs) and are not in the repo, so `run_30k.py` and the
notebook need your own copies of the example and input files to run.

Key: `PERPLEXITY_API_KEY` in `.env` (git-ignored). The label source recorded downstream is
`judge v1 · gpt-5.6-terra · batch5 · minimal · flex`.
