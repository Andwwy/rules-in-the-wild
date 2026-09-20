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

Key: `PERPLEXITY_API_KEY` in `.env` (git-ignored). The label source recorded downstream is
`judge v1 · gpt-5.6-terra · batch5 · minimal · flex`.
