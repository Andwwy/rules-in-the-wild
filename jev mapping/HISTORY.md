# How we got to the Jev enforcer tree

Scope: the enforcer axis, from the first definition (Aug 2026) to the Jev decision tree (Oct 7) and its first use
(Oct 17). The last section prepares the same work for trigger and target.

Sources: Claude Code session logs, the files in this repo, and `../../Rules in the Wild - Google Docs.pdf`.
"Inferred" means that no log or file says it.

## The stages

| # | date | stage | result | what went to the next stage |
|---|---|---|---|---|
| 1 | before Aug | idea | find the system components where a rule can be enforced | the "system component" frame |
| 2 | Aug 17 | definition | enforcer = a class of component (linter, database), not a product | |
| 3 | Aug 18–21 | open values, one-call grouping | 1,332 values → 15 classes; reruns gave 39 to 187 classes | one call is not stable: dropped |
| 4 | Aug 24–30 | multi-pass grouping, hand pruning | 2,758 values → 148 classes → 9 + Other | axis rules: a hook = enforcer + trigger; CI is a trigger |
| 5 | Sep 4–9 | named enforcer, 3-run vote | prompts v6 to v11; NULL 8.9% → 59% | `v1.11.vote`, 10,000 rules |
| 6 | Sep 9–18 | regex subcategory, then LLM class | 619 subcategories; 14 classes by "where enforcement runs" | two levels: regex first, model second |
| 7 | Oct 1 | stronger model | 15 classes (gpt-6-sol); ARI 0.59 against terra | sol replaced terra in the DB |
| 8 | Oct 1 | Jev check | Jev agrees on 78–79% of subcategories | Jev is fast and cheap, not more reliable |
| 9 | Oct 2 | bucket list | 64 buckets kept, 549 small ones dropped, 6 red ones removed | `jev classification.json` |
| 10 | Oct 5 | three groupings exported | regex 9 / terra 14 / sol 15 classes | the "where" prompt was never tuned |
| 11 | Oct 7 | the tree | `enforcer-tree-simple.json` (kind of enforcer, depth ≤ 4) + a beam classifier | current state |
| 12 | Oct 7–17 | first use (MTAC) | 40 rules reach 6 of 103 leaves; no gain from routing shown | open |
| 13 | Oct 21 | a Tests branch | Synthesized CI tests (ASSERT + Other) | the routes made before keep the old tree |
| 14 | Oct 21 | trigger and target audit | a trigger is an event in the agent's or project's work, never the enforcer's own run ("at lint time" means "enforce when the enforcing happens"); a target is what the enforcer reads, never its verdict. Trigger: Check / build removed (420 corpus rules), CI run and Code review (their event is the push or the pull request), Workflow step (no system event; 152); Session start, Task completion, Shell command, Push / merge, Pull request, Schedule described anew. Target: Test result removed (the test runner's verdict), Code change (now in Diff), Requirement (0 rules); Field / value, Domain object, Record / table described apart. The trees before: `../archive/trees-before-audit-2026-10-21/` | the corpus mappings (`mapped/`) and the routes made before keep the old trees |

## 1. Idea (before Aug)
- The project doc sets the goal: "shift towards deterministic enforcement". It plans to identify system components
  (network, file system, system calls, database, compiler, build system) where rules can be enforced.
- Jun 26: a catalog of about 40 enforcement mechanisms in 8 layers (`ENFORCEMENT_MECHANISMS_CATALOG.md`, DAPlab
  "Enforcement list" folder). It came from the ecosystem, not from rules.

## 2. Definition (Aug 17)
- The first written definition: the enforcer is "the system component the rule acts on or against". It is a class
  (linter, database), not a product (ESLint, PostgreSQL).
- The hypothesis list: file system, git hook, agent framework hook, database, terminal, syscall filter, network
  firewall, linter, regex.

## 3. Open values and one-call grouping (Aug 18–21)
- 1,000 rules. Open assignment of the 4 axes (enforcer, target, trigger, spec) with gpt-5.6-terra and no examples.
- 1,870 enforcer values, 1,332 after dedupe. One reduce call made 15 classes (`enforcer-taxonomy.html`). 402 values
  went into more than one class.
- More runs gave 55, 106, 39, 187 and 68 classes. Two runs of the same prompt agreed at ARI 0.30.
- Decision: stop one-call grouping. The model picks the number of classes freely, so the result is not stable.

## 4. Multi-pass grouping and hand pruning (Aug 24–30)
- Batches of 100 values per call, several passes, largest group first. 1k rules: 516 values → 80 classes. 10k rules
  ($26.84): 2,758 values → 148 classes.
- The user's doubt: the grouping follows "verbal similarity, not by actual functionality".
- The user removed classes by hand. Each removal set a rule for the axis:
  - Automation / execution hook: "a trigger + preset script". A hook is an enforcer plus a trigger.
  - CI/CD: a linter "that runs continuously. Which is the trigger part". CI is a trigger, not an enforcer.
  - Code review: "so it's LLM". Not deterministic.
  - Lifecycle, CLI: not a class. UI & rendering: not enforceable. Domain tool: out of scope.
  - Classifier & filter: "filter is a regex detection".
- Result: 9 classes + Other/None. Then Validator merged into Static analyzer. Access split by level: the agent harness
  (tool list) against an external check (kernel sandbox). This is the first split by where a check runs.
- Aug 30, mapping to 8 tags: Other 41.9%, Static analyzer 34.3%, Test runner 9.1%. The LLM Judge class was removed
  (no reason in the logs; inferred: not deterministic).
- This work used the pass1.5 draw. Its is_rule labels were contaminated, so it went to `archive/`.

## 5. Named enforcer and the vote (Sep 4–9)
- A new 10k draw with clean is_rule labels.
- Prompt v6 reversed the Aug 17 definition: an enforcer is "a specific system that has a name" (ESLint, PostgreSQL).
  NULL enforcers rose from 8.9% to about 59%. The user took a NULL as a sign of an ambiguous rule.
- v7: "the mechanism that enforces the requirement". v10 and v11: 3 runs and a majority-vote judge → `v1.11.vote`.
- The axis rule again: "hook is NOT a enforcer… it's a enforcer + a trigger".

## 6. Regex subcategory, then LLM class (Sep 9–18)
- Multi-pass grouping of v1.11: 749 values → 51 classes, but pass 1 merged too much. The groups followed product
  families, not how enforcement happens.
- New split of the work: "we get the sub-categories by regex matching, then group with LLM".
  - Level 1, subcategory: ordered regex aliases (`assign+group/aliases.json`), no model. 619 subcategories.
  - Level 2, class: one LLM call partitions the subcategories (`assign+group/prompts/classes.txt`).
- Only rules with a voted enforcer, target and trigger count: 1,841 rules.
- Sep 10: one call "by functionality" (44 classes) and one "by enforcing entity" (14 classes). The user removed "by
  functionality". The entity prompt groups by where the check runs: agent harness, local machine, CI, app runtime,
  database, OS, network, client.
- A side product: 9 regex classes by mechanism (linter, schema validator, tool-call gate, shell & CLI, commit & CI gate,
  test runner, compiler/build, database, other). The assistant wrote them; they were not uploaded.
- Sep 9–10: an adversarial audit of the voted rows (judge → critic → fresh judge). Each row: OK, wrong assignment, or
  not a rule.
- Sep 18: MotherDuck tables `rule_subcategory` and `subcategory_class` (the 14 terra classes).

## 7. Stronger model (Oct 1)
- gpt-6-sol at max effort: 15 classes, a clean partition on attempt 1. ARI 0.59 against terra.
- Sol merged local CLI, static analysis and test runner into "Local dev machine" (222 subcategories, 974 rules). It read
  the "where" prompt literally.
- The user: "this should have been sol for the first pass". Sol replaced terra in the DB; terra stays as
  `entity_terra.json`.

## 8. Jev check (Oct 1)
- No hand-labelled taxonomy dev set exists. Only 10 rules have a hand-labelled enforcer.
- The test: Jev gets each subcategory (its name and up to 4 raw values) and one Choice over the classes. Its pick is
  compared with the LLM class. Details: `../assign+group/jev test/RESULTS.md`.

  | against | subcategories | by rules | confidence ≥ 0.8 | cost |
  |---|---|---|---|---|
  | terra (14) | 491/619 = 79% | 85% | 372/397 = 94% | $0.0195 |
  | sol (15) | 483/619 = 78% | 82% | 332/352 = 94% | $0.023 |

- The disagreements are on "where" boundaries: bash and grep → OS; Semgrep and CodeQL → CI; Jest → app runtime.
- The user's verdict: Jev is "not super reliable or superior than our LLM judge. It's just fast", and cheap.
- A side test: an "enforceable" pre-filter on the 10k rules ($0.32). The proposed cut removes 47% of the rules with no
  enforcer and loses 4% of the rules with one. No record shows that it was adopted.

## 9. Bucket list for Jev (Oct 2)
- The user: "curate a list of subcategories for jev to choose (enforcer buckets)". Small buckets (n < 3) get low
  priority. Red buckets are bad.
- Red = the audit found less than 50% of the rows OK. (The user said red means "didn't pass validation/translation";
  the code tests only the audit ratio.)
- Result: 64 primary buckets (1,099 rules) → `jev classification.json` (name and variants only). 549 small buckets
  dropped. 6 red buckets → `jev classification (excluded).json`: OPA 4/67, agent harness (generic) 9/45, PostgreSQL
  6/24, CLI argument parser 3/11, Excel 0/5, Great Expectations 2/5.
- One Jev Choice takes at most 255 options. 64 buckets fit. 613 would need "class first, then bucket".

## 10. Three groupings exported (Oct 5)
- `regex pattern.json` (9 classes; Other holds 230 subcategories), `one call gpt-5.6-terra.json` (14),
  `one call gpt-6-sol.json` (15). The same 1,841 rules and 619 subcategories.
- ARI, computed later: regex–terra 0.33, regex–sol 0.19, terra–sol 0.59.
- The user: the entity prompt is AI-generated and "i haven't tuned that really". The local-against-CI split depends on
  one sentence in it.

## 11. The tree (Oct 7)
- `enforcer-tree-simple.json` came from Slack on Oct 7 (the file has the macOS quarantine tag "Slack"). No session log
  shows how it was designed. Only one version exists.
- Axis: the kind of enforcer (mechanism), not where it runs. The branches look like a regroup of the 9 regex mechanism
  classes (inferred).
- Shape: Enforcer → Analysis, Tests, Validation, Gates, Commands, Build / ops, Other. 134 nodes: 31 inner nodes,
  72 named leaves, 31 "Other" leaves. Depth ≤ 4 (Analysis › Languages › Python / shell › Ruff).
- The leaves are the 64 buckets with short labels. Some buckets split by variant (Ajv / JSON Schema, tsc / Type checker,
  go test / cargo test). Git CLI merged into Git. No red bucket is in the tree. "Project check" has no earlier source.
- The classifier `classifier/enforcer_tree.py` follows TypeSafe's hierarchical-classification cookbook: one Jev Choice
  per node, beam 3, path score = geometric mean, separation = best path / second path. "Other" comes from the tree, not
  from the cookbook. Jev sees the labels only, with no descriptions. A rule takes about 7 calls, 3k tokens, $0.00013.
- The user: "each of the rule should be mapped using this decision tree".

## 12. First use (Oct 7–17, MTAC)
- 40 MTAC rules: 29 → Regex validator or Regex filter, 5 Semgrep, 3 Project check, 2 JSON Schema, 1 CodeQL. They reach
  6 of 103 leaves. 10 rules are near ties (separation < 1.2).
- The role of the tree: "write the enforcer, then according to its trigger, wire in the trigger."
- A/B/C design (Oct 8): B is unguided, C is guided by Jev's leaf, to "show the classification does help by appointing
  the enforcer".
- Task 46 (Oct 17): scripted items B 40/83, C 53/83. Offline hook test: B 6 of 20 (15 after one field-name fix), C 13.
  Cost B $3.93, C $4.16. 6 of 8 routes were Regex, and C did not follow the other 2. Conclusion: the result does not
  show that routing helps.

## 13. A Tests branch for synthesized tests (Oct 21)
- Why: ASSERT (Microsoft Responsible AI, arXiv 2608.13840) turns a written behavior into a rubric, synthesizes test
  cases from it, runs them against the finished AI system and has an LLM judge score each transcript. No leaf held a
  check of this kind; a rule such as "the bot must escalate likely fraud" could reach only Tests › Other.
- Tests › Synthesized CI tests: ASSERT, Other. Named, as Tests › CI tests is, by the object that a CI run or a release
  runs; "synthesized" sets it apart from the project's own suite. A model judges the result: not deterministic.
- Not taken: "AI evals" and "AI generated tests" (the second also fits a model writing ordinary unit tests);
  "LLM-judged tests" (the user preferred the CI framing); "CI/CD test case" (too close to CI tests). promptfoo and
  Inspect were drafted under the branch and dropped. A second branch, Tests › Generated tests (Hypothesis, fast-check,
  AFL++, EvoSuite: inputs generated by an algorithm, deterministic), was added and then removed at the user's word.
- Jev still sees labels only: neither "ASSERT" nor "Synthesized" tells it that a model judges. The version in the
  experiment's note and toolbox node was checked on Oct 21 (assert-ai 0.3.0). Shape now: 105 leaves (was 103) and 32
  inner nodes (was 31).
- No rule was routed again: the MTAC routes (tasks 46, 91) were made with the earlier tree.

## What the enforcer work teaches
1. Free values have a long tail, and open clustering is not stable (ARI 0.30 between two runs). Fix a class list first,
   then classify each value against it.
2. Keep each axis clean. A hook is an enforcer plus a trigger. CI is a trigger. An LLM review is not deterministic.
3. Do a deterministic pass first (regex aliases), then a model pass.
4. Audit before you trust a bucket. Remove the buckets that fail.
5. Give every node an "Other". Labels alone separate leaves poorly: add a one-line description to each node.
6. No hand-labelled dev set exists. Every agreement number so far is a model against a model.

## Gaps
- The tree design: who made it, how, why "simple", and why mechanism replaced place. The Slack thread probably has it.
- The "Project check" leaf: source unknown.
- The removal of the LLM Judge class (Aug 27–30): no stated reason.
- The origin of the "where enforcement runs" axis. Candidates: the project doc, the Aug 27 harness/external split, the
  Sep 9 assistant proposal, the Sep 10 user goal.
- The tree classifier has no accuracy test against hand labels. Beam width and node descriptions are not tuned.

## Next: trigger and target

### Definitions (prompt v1.19, `../assign+group/prompts/assignment.txt`)
- **Target:** "the noun that the rule is enforced over": a file, a branch, a function name, a record, a message, a
  request. It must be enumerable. v1.19 adds: the target is what the enforcer inspects or acts on; the action that the
  rule gates belongs to the trigger.
- **Trigger:** the predicate for when the rule is evaluated, terse and observable ("at commit time", "when a file is
  written"). "always" if the rule always applies.

### Data
The only full voted set: `../assign+group/data/pass1.11-10000/v1.11_result/assignment output.json` (prompt v1.11,
10,000 rules). v1.11 is older than the v1.19 change to target.

| | trigger | target |
|---|---|---|
| rules with a value | 6,665 | 8,185 |
| distinct values | 5,636 | 9,135 |
| values seen once | 5,508 (98%) | 8,661 (95%) |
| top 40 values cover | 16% | 5% |

- Trigger: "always" 866, then at commit time 40, during code review 20, at lint time 18. First word: when 64%,
  always 13%, before 11%.
- Target: use head nouns, not full strings. 1,304 distinct head nouns; the top 40 cover 47% (file, response, request,
  invocation, entry, declaration, record, field, message, configuration).

### Earlier attempts
| date | where | result |
|---|---|---|
| Jul | `../../Archieve/components v1/components_v2.jsonc` | a trigger tree: 13 parents, 28 leaves (git hooks, filesystem, agent runtime, agent lifecycle, CI/build/test, app runtime, …). No target. |
| Aug 7 | `../archive/sem_reduce/trigger_taxonomy.csv` | 9 trigger classes (filesystem write, UI interaction, command executed, …) |
| Aug 17 | `../archive/k-LLMmeans/out/` | k = 12 clusters per axis; the target clusters are vague |
| Aug 25 | `../assign+group/archive/runs/pass1.4-1000/` | 5-pass grouping on 1k rules: trigger 35 classes, target 56 |
| Oct | `../MTAC enforcement eval/experiment/translation/system.md` | closed sets: 5 triggers (before-write, after-write, after-edit, before-command, end-of-turn), 4 targets (reply, code-file, any-file, project) |

Past decisions by the user:
- Aug 17: "so target should not be clustered, should stay as is?" (target did not converge at k = 12).
- Aug 26: "assume ~50 classes enforcer, 30 for target & trigger".
- Oct 17: trigger and target do not need the depth of the enforcer tree.

### Draft first level (proposal, not checked)
Current trees (depth 2, with a description per node): `trigger-tree.json` (6 branches, 36 leaves) and
`target-tree.json` (11 branches, 73 leaves). Classifier: `classifier/tree_classifier.py`; rings: `ring/ring.py`.
The first keyword draft with sample values: `trigger-target-draft.md`.

Oct 17 run (`mapped/`, `ring/`): Jev mapped all 1,902 trigger and 2,578 target values of the 1,841 full-triple rules for
$0.46 (4 calls and $0.0001 per value). Trigger: 35 of 36 leaves reached, 14% close calls, 3% "Other". Target: 66 of 73
leaves reached, 16% close calls, 2% "Other". No hand labels yet, so accuracy is not measured.

Keyword rules on the 10k data cover about 79% of trigger mentions and 74% of target mentions (82% of each in the 1,841
full-triple rules).

Trigger, by event source. Keep before / after / during as a separate attribute, not as classes.
1. Always
2. Agent turn & session (prompt received, session start, end of turn, task done)
3. Agent tool call (shell command, tool or MCP call, subagent)
4. File write / edit
5. Static check (lint, format, type check)
6. Build & test run
7. Version control (commit, push, merge, branch)
8. Code host & review (pull request, review, CI run)
9. Release & deploy
10. Application runtime (request, query, log, error, UI event, schedule)
11. Other

Target, by what the enforcer inspects.
1. Agent output (response, plan, report)
2. Agent actions (tool calls, commands)
3. User input (requests, prompts)
4. Source code (files and code units: function, declaration, import)
5. Tests
6. Config, dependency and build files
7. Docs and text files
8. Version-control objects (commit, branch, PR, diff)
9. Data & runtime objects (records, fields, endpoints, logs, secrets)
10. Other

Depth: 2 levels (class → a few leaves) is enough.

### Steps
1. Choose the data: v1.11 now, or a v1.19 re-run first (the meaning of target changed).
2. Fix the first-level classes. Check Slack for a team version, as for the enforcer tree.
3. Write `trigger-tree.json` and `target-tree.json` in the format of `enforcer-tree-simple.json`, with "Other" at each
   inner node.
4. Let the classifier take a tree path (now it reads only the enforcer tree).
5. Hand-label about 50 rules per axis as a dev set.
6. Run one small batch, measure the real cost, then ask before a full run.
