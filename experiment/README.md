# experiment

Does system enforcement of a project's rules help a coding agent follow them? The same agent (Claude Haiku 4.5 in
Claude Code 2.1.199) does the same MTAC-IFBench tasks in four arms:

- **A:** the rules are in `CLAUDE.md` only.
- **B:** before the task (phase 0), a translation agent turns the rules into system enforcement. It gets the rules only.
- **C:** as B, and each rule comes with Jev's route (enforcer, trigger with its timing, target), a card for each leaf of
  the route, and the part of the enforcement toolbox that the routes use.
- **C-ideal:** C's routes, translated by hand (task 91): `tasks/MTAC-task-91/arms/C-ideal/translation/`.

Each run is one container. Phase 0 (as root) builds the enforcement; phase 1 (as the user `agent`, without root) does
MTAC's turns, with the enforcement in place. Only the rules of `CLAUDE.md` are scored, by MTAC's checker scripts.

`DESIGN.md` is the design as it is now; `design_process.md` is the decision log ("point N" is a row of its table);
`PROTOCOL.md` is what each agent gets, word for word.

## Results (task 91)

Rules followed, over 10 turns (7 scored rules):

| A | B | C-ideal |
|---|---|---|
| 55/70 | 55/70 | 70/70 (two runs) |

`python3 scripts/compare_runs.py <run> …` makes this table from the runs' `script_scores.json`.

## Layout

| path | what it is |
|---|---|
| `tasks/MTAC-task-NN/` | one task from MTAC-IFBench: `README.md` (its rules), `data/questions.jsonl` (the task and its checker code; no agent sees it), `rules.json` (each rule with Jev's mapping on the three trees and C's route), `jev_plan.json` (the calls that chose the routes), `hidden_fixtures.json` (tasks 46, 91: held-out cases that score phase 0's enforcement), `arms/<arm>/translation/` (phase 0's inputs; for C-ideal, the enforcement itself: `enforce/`, `install.sh`, `README.md`). `tasks/mapping ring.html`: the rules by enforcer-tree path |
| `agents/<agent>/` | one agent setup: `agent.json` (model, Claude Code version, flags). `runs/<task>/<arm>/<stamp>/`: one run (`run.log`, `inputs.json`, `phase0/` with what phase 0 got and left, `turns/round_N/` with each turn's prompt, reply and result, `script_scores.json`, `phase0_score.json`). `checks/`: runs with a scripted model, no model calls |
| `prompts/` | the parts of phase 0's input: `system.md` (its first sentence from `opening.md`, by arm), `frameworks/claude-code.md` (the section on the agent's framework, added at run time), `system_route.md` and `system_toolbox.md` (C), `batch.md`, `rule_B.md`, `rule_C.md` |
| `container/` | what goes into the run container: `harness/` (`try.py`, phase 0's trial of its enforcement; `environment.py`, the record of what phase 0 changed; `docs/`, Claude Code's and git's hook pages), `toolbox/` (the enforcement toolbox: one node per leaf of the enforcer, trigger and target trees, mechanisms, runnable skeletons, `graph.json`, install recipes; see its `README.md`), `probes/` (`mock_api.py`, the scripted model; `phase0_probe.py`, which gives test cases to the agent's hooks) |
| `scripts/` | every script (below), `trajectory_viewer.html` (the viewer's template), `chain_scenario.json` (the scripted model's scenario), `gateway/` (below) |
| `scripts/gateway/` | a LiteLLM gateway: Anthropic-format calls to Bedrock. `budget.py` logs each call's cost and refuses calls once `RITW_BUDGET_USD` is spent |
| `dataset/<bench>/` | one README per benchmark (MTAC-IFBench, CodeIF-Bench, ST-WebAgentBench, τ²-bench): what it is and where to get it. `MTAC bench/research/`: notes and reports |

## Setup

1. **Docker**, and MTAC's default image `alexgshaw/break-filter-js-from-html:20251031` (`linux/amd64`; on Apple silicon
   it runs under emulation).
2. **AgentProbe** ([abelperry/AgentProbe](https://github.com/abelperry/AgentProbe), commit `e291570`) in
   `dataset/MTAC bench/base agent/`. The runner uses it as a library (MTAC's turn prompts, the checker runner) and installs
   the Claude Code package from its `data/offline_package/`. Its environment runs the scripts that read MTAC's data:
   `uv run --project "dataset/MTAC bench/base agent" python scripts/<name>.py`.
3. **MTAC-IFBench's data** ([thu-coai/MTAC-IFBench](https://huggingface.co/datasets/thu-coai/MTAC-IFBench)):
   `mtac_full.jsonl` in `dataset/MTAC bench/task data/`. Only `build_tasks.py` reads it; `tasks/` has the copied tasks.
4. **Gateway.** `python3.13 -m venv scripts/gateway/.venv && scripts/gateway/.venv/bin/pip install -r
   scripts/gateway/requirements.txt`. `scripts/gateway/start.sh` reads its keys from a `.env` (the repository's
   `.env.example` lists them: `BEDROCK_PROFILE_ARN`, an application inference profile for the model; `RITW_BUDGET_USD`;
   `GATEWAY_API_KEY`) and serves on port 4000.
5. **A run.** `uv run --project "dataset/MTAC bench/base agent" python scripts/runner.py <task> <arm>`, then
   `score_runs.py`, `compare_runs.py` and `attribute_passes.py` on the run folders.

## Scripts

Run from this folder. `map_rules.py`, `build_graph.py`, `ring.py`, `compare_runs.py` and `watch_runs.py` run with
`python3` (`map_rules.py` needs the TypeSafe SDK); the others run in AgentProbe's environment (Setup, 2).

| script | what it does |
|---|---|
| `build_tasks.py` | writes `tasks/MTAC-task-NN/`: the task's data, `rules.json`, each arm's phase 0 inputs (`--tasks 46,91`) |
| `map_rules.py` | Jev's mapping of each rule on the three trees (`../jev mapping/`); `--select` chooses C's route among 4 × 4 × 4 plans |
| `build_graph.py` | the toolbox's `graph.json`, and its checks |
| `runner.py` | one arm of one task in one container: phase 0, the record of what it left, phase 1. `--agent` picks the agent setup; `--turns 0` runs phase 0 only; `--mock <scenario>` runs the scripted model into `checks/`. For C-ideal it installs the hand-written enforcement in place of phase 0 |
| `watch_runs.py` | watches running runs and reports alerts and milestones |
| `score_phase0.py` | gives the task's held-out cases to the hooks phase 0 left, as Claude Code would, and counts per rule what they block |
| `score_runs.py` | MTAC's checker scripts on each turn, for the rules of `CLAUDE.md`; writes `script_scores.json` |
| `compare_runs.py` | per rule and arm, the turns its checker passed, and each run's cost |
| `attribute_passes.py` | for each passed rule: did the enforcement of that rule fire in that turn, or did the model comply alone |
| `mtac_locate.py` | where MTAC's checker failed; used by the viewer |
| `trajectory_viewer.py` | a page of every action of the latest A, B and C runs |
| `ring.py` | builds `tasks/mapping ring.html` |
| `paths.py` | every path, and `use()` for the code outside the experiment (AgentProbe, `../jev mapping/classifier/`, `../assign+group/`) |

## A new agent or model

1. Copy `agents/haiku-4.5_claude-code-2.1.199/agent.json` to `agents/<name>/agent.json` and change the model (and the
   Claude Code version and package, if needed). The gateway must serve the model.
2. `uv run --project "dataset/MTAC bench/base agent" python scripts/runner.py <task> <arm> --agent <name>`.
3. An agent other than Claude Code needs its own support in `scripts/runner.py` and `container/harness/`, and its own
   section, `prompts/frameworks/<harness>.md`.
