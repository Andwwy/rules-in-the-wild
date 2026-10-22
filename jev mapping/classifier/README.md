# classifier

`tree_classifier.py` maps a rule onto one of the decision trees in `../` with TypeSafe Jev (`jev-1.13.0`):
`enforcer-tree-simple.json`, `trigger-tree.json` or `target-tree.json`.

- At each tree node, one Choice question picks among the node's direct children. A beam of 3 paths (`--beam`) goes down the tree,
  and a path's score is the geometric mean of its step probabilities (TypeSafe's hierarchical-classification cookbook).
- Every inner node has an `Other` child for "none of these".
- A tree file can have a `descriptions` map. Jev then sees each option as "name: description". The enforcer tree has
  none, so Jev sees its labels as they are.
- For trigger and target, `value` is the assigner's wording (the voted trigger or target). Jev sees it next to the rule.
- The trigger tree's first call also asks `state_p`, the probability that a state must also hold (a mode, a flag, a
  threshold).
- The result has the leaf, the path, the score, the separation from the next path (1.0 means a tie), the other paths of
  the beam as alternatives (two with a beam of 3), and the calls, tokens and cost.
- The timing belongs to the event: `tree_of("trigger")` adds it as the tree's last level, before / at / after under each
  event (Always has no event: its timing is always). The beam picks the event and its timing together; the result keeps the
  event as `path` and the timing as the attribute `timing`, and each alternative has its own. `tree_of` can keep only the
  timings at which each event can run in an environment (MTAC `map_rules.py`).
- Each call goes into the project's spend ledger (`assign+group/rule_pipeline/spend.py`). An enforcer rule takes about 7
  calls and $0.00013; a trigger or target value takes 4 calls and $0.0001.

```bash
python tree_classifier.py enforcer "Every function name must follow snake_case"
python tree_classifier.py trigger "Run the linter before every commit" --value "at commit time"
python map_values.py trigger --limit 5     # the voted values of the v1.11 vote → ../mapped/trigger.jsonl
```

| file | |
|---|---|
| `tree_classifier.py` | the classifier, for all three trees |
| `enforcer_tree.py` | the enforcer axis under the names that the MTAC scripts import (`map_rules.py`, `ring.py`); same prompt and output as before |
| `plan_select.py` | the whole plan in one call: the candidates of the three axes as plans, a trigger candidate with its timing (4 × 4 × 4 = 64 with 4 per axis), one Choice picks one (n-best reranking; MTAC `map_rules.py --select`). The pick follows the order of the plans (MTAC design_process.md, points 64, 93) |
| `map_values.py` | maps the voted trigger or target values of `v1.11.vote` (the 1,841 full-triple rules by default) and resumes |

The rings of the trigger and target mappings: `../ring/ring.py`. Needs `typesafe-sdk` and `TYPESAFE_API_KEY`
(`~/Desktop/DAPlab/.env`).
