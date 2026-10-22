# experiment

The same agent on the same MTAC tasks in three arms (design_process.md, points 30–35 and 60):

- **A:** the policy as `CLAUDE.md` only.
- **B:** before the task, in phase 0, the translation agent turns each rule into system enforcement. It gets only the
  rule ("Implement system enforcement for this rule").
- **C:** as B, but each rule comes with Jev's route (enforcer, trigger, target), a card for each leaf, and the
  enforcement toolbox (design_process.md, points 60, 65).

Phase 0 is one session and one message with all the task's rules; the harness does not plan, check or correct its
work, and the arms differ only by the route (point 96).

Two phases run in one container (`scripts/runner.py`):

- **Phase 0, the translation agent** (B and C, as root): it reads the rules and sets up the enforcement.
- **Phase 1, the task agent** (every arm, as the user `agent`): MTAC's turns, with phase 0's enforcement installed.

The design as it is now is in `DESIGN.md`; how it came to be, with the user's answers, in `design_process.md` (the
decision log: "point N" is a row of its table); what each agent gets, word for word, in `PROTOCOL.md`.

## Layout

Tasks are free of any model or agent; everything a model or agent produced is under that agent. A new model or agent
is a new folder in `agents/`, run on the same `tasks/`. Every script is in `scripts/` and runs from this folder
(`python scripts/runner.py …`); `scripts/paths.py` holds every path and is the one place that reaches code outside the
experiment (`paths.use`: AgentProbe, the Jev classifier, the spend ledger).

| path | what it is |
|---|---|
| `dataset/<bench>/` | each benchmark as downloaded, with its paper: `MTAC bench/` (the MTAC-IFBench paper, `task data/`: its 100 tasks in `mtac_full.jsonl` and its checkers, `base agent/`: [abelperry/AgentProbe](https://github.com/abelperry/AgentProbe) at `e291570`, unchanged, used as a library for MTAC's turn prompts and checker runner, with the offline Claude Code package in `data/offline_package/`; `research/`: notes and reports), `CodeIF-Bench/`, `ST-WebAgentBench enforcement eval/`, `τ²-bench/` (each folder's README says what it holds) |
| `tasks/<SRC>-task-NN/` | one task copied from its benchmark, named by the benchmark and its id there (`MTAC-task-46`); model-free: `README.md` (its policy rules), `data/questions.jsonl` (MTAC's task, the checklist cut to the items with a checker script; held out from every agent: it holds checker code), `rules.json` (the rules, each with Jev's call 1: `mapping`, `mapping_trigger`, `mapping_target`, and C's route by beam select: `route`), `jev_plan.json` (the beam select's calls), `hidden_fixtures.json` (tasks 46, 91: held-out cases that score phase 0's enforcement, written by hand for that task only), `arms/<arm>/translation/` (phase 0's inputs: `system.md`, `messages.json`; for C-ideal, phase 0 written by hand: `enforce/`, `install.sh`, its README). `tasks/mapping ring.html`: the rules by enforcer-tree path, and the whole tree |
| `agents/<agent>/` | one agent setup: `agent.json` (model, Claude Code version and package, flags, gateway), `runs/<task>/<arm>/<stamp>/` (the runs), `checks/<task>/<arm>/<stamp>/` (scripted runs, no model calls), `earlier/` (runs of earlier pipelines; local only), `trajectories.html` (every action of the latest runs, in one page; local only) |
| `prompts/` | the sources of phase 0's inputs: `system.md` (every arm; its first sentence from `opening.md`, by arm), `frameworks/<harness>.md` (the section on the agent's framework, which `runner.py` puts in place of `{framework}` at run time, by agent.json's `harness`: `claude-code.md`), `system_route.md` and `system_toolbox.md` (C), `batch.md` (the message's first line, by arm), `rule_B.md`, `rule_C.md` (each rule in the message) |
| `container/` | what is copied into the run container: `harness/` (`try.py`: phase 0's `try`; `environment.py`: what phase 0 changed, the agent's settings files and their hooks, and the fingerprint; `docs/`: Claude Code's and git's hook pages), `toolbox/` (the toolbox, below), `probes/` (`mock_api.py`, the scripted model; `phase0_probe.py`, which gives test cases to the agent's hooks). The harness installs nothing: the agent loads the settings phase 0 left (point 81) |
| `container/toolbox/` | the enforcement toolbox (C gets only the share its routes use, `toolbox.json`; point 97): a library for implementing enforcement in the container, not tied to an agent framework, as a graph (points 71, 72): one node file per leaf of the enforcer, trigger and target trees (`enforcers/`, `triggers/`, `targets/`, by tree path in lower case; C's card for a leaf is its node), `mechanisms/` (framework hooks, file permissions, command wrappers, git hooks, file watchers, a root service, OPA, Dogwood, checks that keep running), `skeletons/` (runnable starts), `graph.json` (every node and edge; `scripts/build_graph.py`), `README.md` (how to walk it) and recipes (`enforce install`, `enforce_lib/recipes.py`: 30 tools). Edges are paths in the container. `tests/` never leaves the host: `in_image.sh` runs `test_library.py` in MTAC's image |
| `scripts/` | every script (below), `trajectory_viewer.html` (the viewer's template), `chain_scenario.json` (the scripted model's scenario for B: a free-form plan, and a task turn that meets each hook), and `gateway/` |
| `scripts/gateway/` | LiteLLM gateway: Anthropic-format calls → Claude Haiku 4.5 on Bedrock. `budget.py` logs each call to `rules in the wild/spend.jsonl` (the current ledger; older ones are `spend.until-<date>.jsonl`) and refuses calls once the budget is spent (`RITW_BUDGET_USD` in `~/Desktop/DAPlab/.env`, read when the gateway starts). Setup: `python3.13 -m venv scripts/gateway/.venv && scripts/gateway/.venv/bin/pip install -r scripts/gateway/requirements.txt` |
| `archive/` | local only; no longer used: `agentprobe-path-2026-10-19/` (the AgentProbe pipeline), `guides-2026-10-18/`, `toolbox-plan-2026-10-18.md` (the toolbox plan; superseded by points 57, 60, 65), `toolbox-cards-2026-10-19.md` (C's cards before the catalog), `toolbox-claude-hooks-2026-10-20/` (the toolbox's Claude Code hook engine, its tests and its catalog; point 71), `phase0-probe-2026-10-20/` (the phase 0 probe; point 73), `harness-report-2026-10-20/` (`report.py`; point 79), `harness-wrap-2026-10-21/` (`wrap.py`: the install into managed settings, the hook wrapper, the recorder; point 81); `phase0-scaffolding-2026-10-21/` (C's compiled plan, the harness's checks of phase 0, B's plan, the variant arms C-notes, B-toolbox, C-plain, score_checks.py; point 96), `chain-compiled-2026-10-21/`, `map-rules-modes-2026-10-21/`, `routes-before-timed-trigger-2026-10-21/`, `routes-before-tree-audit-2026-10-21/`, `toolbox-nodes-before-audit-2026-10-21/` (points 93 to 95) |

### Not in the repository

`experiment/.gitignore` keeps these on the machine that made them; the repository has the code, the docs, the tasks and,
for every run, its log, inputs, phase 0 record (replies, settings, install record, held-out scores), each turn's prompt,
reply and result, and the scores.

- `archive/` and `agents/<agent>/earlier/`: material no longer used.
- The runs' snapshots: `turns/*/workspace_snapshot/`, `workspace.tar.gz`, `phase0/files.json` (what phase 0 left in
  /opt/enforce).
- The trajectories: `traces/` (the task transcript, the fingerprint, the enforcement log of earlier runs), the phase 0
  transcripts (`phase0/*.jsonl`), `mock_api.jsonl`, `claude_debug.log`, `agents/<agent>/trajectories.html`.
- Downloads: the papers (`dataset/**/*.pdf`), `dataset/MTAC bench/base agent/` (AgentProbe at `e291570`, with the
  offline Claude Code package), `dataset/MTAC bench/task data/`, `dataset/τ²-bench/tau2-bench/`,
  `dataset/ST-WebAgentBench enforcement eval/ST-WebAgentBench/`; each benchmark's README says where it comes from.
- `scripts/gateway/.venv/` (its setup is in the table above), `gateway.log`, `gateway.pid`.

### Scripts

Run from this folder. Scripts that read MTAC's data run in AgentProbe's environment
(`uv run --project "dataset/MTAC bench/base agent" python scripts/<name>.py`); `map_rules.py`, `build_graph.py`, `ring.py`,
`compare_runs.py` and `watch_runs.py` run with the system `python3` (it has the TypeSafe SDK for `map_rules.py`).

| script | what it does |
|---|---|
| `build_tasks.py` | writes `tasks/MTAC-task-NN/` (data, `rules.json`, each arm's phase 0 inputs); `--tasks 46,91`, `--top 100` |
| `map_rules.py` | Jev's route for each rule (`rules.json`): call 1 on each axis (a beam of 4; the trigger tree's last level is the timing); `--select 4` is the beam select that makes C's route (`route` in `rules.json`, the calls in `jev_plan.json`; points 78, 93, 94: 4 candidates per axis, 64 plans) |
| `build_graph.py` | the toolbox's `graph.json`, and its checks (every link resolves, every leaf has a node) |
| `runner.py` | one arm of one task in one container with plain Docker: phase 0 (root, one session, one message), the record of what it left, phase 1 (as `agent`); `--agent` picks the agent setup; writes `agents/<agent>/runs/<task>/<arm>/<stamp>/` (`run.log`, `inputs.json`, `phase0/` with the inputs it got, `turns/`, `traces/`). `--turns 0` runs phase 0 only; `--max-cost` stops it at a cost; `--mock scripts/chain_scenario.json` runs the scripted model into `checks/` |
| `watch_runs.py` | watches running runs: alerts (root attempts, permission errors, touching the enforcement, hook errors, refusals, stalls, the gateway, spend) and milestones; `--since <stamp>` |
| `score_phase0.py` | the translation, without a model: the task's held-out cases given to the hooks phase 0 left, as Claude Code would (a file by a file tool and by a shell command, or the reply), per rule how many were blocked and named (point 86) |
| `score_runs.py` | MTAC's checker scripts on each turn (free); writes `<run>/script_scores.json` |
| `compare_runs.py` | per policy rule and arm, the turns its checker passed; totals and each run's cost |
| `attribute_passes.py` | why each rule passed: the enforcement of that rule fired in that turn (a hook's violation in the harness's log, or a refusal naming the rule in the transcript), or the model alone |
| `mtac_locate.py` | where MTAC's checker failed (black-box, its code unread); used by the viewer |
| `trajectory_viewer.py` | builds `agents/<agent>/trajectories.html` from the latest A, B and C runs |
| `ring.py` | builds `tasks/mapping ring.html` |
| `paths.py` | every path; `use()` for code outside the experiment |

Tasks: 46, 91, 83, 92, 51, the five with the most script-checked policy rules (54–70 scored checks over 9–10 turns).
Runs so far: tasks 46 and 91.

## A new agent or model

1. Copy `agents/haiku-4.5_claude-code-2.1.199/agent.json` to `agents/<name>/agent.json` and change the model (and the
   Claude Code version and package, if needed). The gateway must serve the model.
2. `uv run --project "dataset/MTAC bench/base agent" python scripts/runner.py <task> <arm> --agent <name>`.
3. `tasks/` and `prompts/` stay as they are. An agent other than Claude Code needs its own support in
   `scripts/runner.py` and `container/harness/` (the hooks are Claude Code's), and its own section,
   `prompts/frameworks/<harness>.md`.

## Before a run

1. **Bedrock profile.** Done (2026-10-08). The lab account denies direct model calls (`RequiredTagsPolicy`), so the
   gateway calls through the user's own application inference profile, `rules-in-the-wild-ww2780-haiku-4-5` (tagged
   `project=rules-in-the-wild`, `billing-tag1=ww2780`); its ARN is `BEDROCK_PROFILE_ARN` in `~/Desktop/DAPlab/.env`.
   Leave `AWS_BEARER_TOKEN_BEDROCK` out of `.env` (an empty value makes AWS tools send an empty token).
2. **Image.** Every arm runs in MTAC's default image, `alexgshaw/break-filter-js-from-html:20251031` (`linux/amd64`;
   on Apple silicon it runs under emulation).
3. **Docker** and the offline Claude Code package (`dataset/MTAC bench/base agent/data/offline_package/`).
4. **Gateway.** `scripts/gateway/start.sh` (it takes the region from the profile ARN; it reads the budget cap when it
   starts).
5. Per task and arm: `uv run --project "dataset/MTAC bench/base agent" python scripts/runner.py <task> <arm>` (arms run in parallel,
   each in its own container); watch with `python3 scripts/watch_runs.py`; then `score_runs.py`, `compare_runs.py` and
   `attribute_passes.py` on the run folders.

Scoring: MTAC's checker scripts only (free), by AgentProbe's own checker runner on each turn's saved reply and
workspace. No judge: items without a script are not scored. Every run keeps its full trajectory (transcripts, each
turn's reply and workspace snapshot, the final workspace), so a judge can score it later.

## Names before 2026-10-20

Runs keep what they recorded (`inputs.json` says "session1", and `task_046/…` as the run's label); their folders follow the names below.

| before | now |
|---|---|
| `build/`, `run/`, `score/`, `report/`, `lib/` (by step; `python -m <step>.<name>`) | `scripts/` (`python scripts/<name>.py`; point 74) |
| `MTAC enforcement eval/experiment/` | `experiment/` (in `rules in the wild/`) |
| `MTAC enforcement eval/` (its README, the paper, `task data/`, `base agent/`, `research/`) | `dataset/MTAC bench/` |
| `tasks/task_046/`, `runs/task_046/`, `checks/task_046/` | `tasks/MTAC-task-46/`, `runs/MTAC-task-46/`, `checks/MTAC-task-46/` (a run's `inputs.json` and the spend ledger keep the label `task_046/…`) |
| `gateway/` | `scripts/gateway/` |
| `report/trajectories.html`, `report/mapping ring.html` | `agents/<agent>/trajectories.html`, `tasks/mapping ring.html` |
| `DESIGN.md` (the decision log) | `design_process.md`; `DESIGN.md` is now the design as it is |
| `harness/`, `toolbox/` | `container/harness/`, `container/toolbox/` |
| Session 1, Session 2 | phase 0 (the translation agent), phase 1 (the task agent) |
| a run's `session1/`, `session1_score.json`; `score_session1.py` | `phase0/`, `phase0_score.json`; `score_phase0.py` (archived on 2026-10-20 with its probe and fixtures: `archive/phase0-probe-2026-10-20/`) |
| `prompts/guides/toolbox_cards.md` | C's card is the leaf's node in the toolbox (`archive/toolbox-cards-2026-10-19.md`) |
| `docs/toolbox-plan.md` | `archive/toolbox-plan-2026-10-18.md` |

## Arm names before 2026-10-19

Runs made before the reorganisation keep their old names inside (`inputs.json` "run", the spend ledger, the container):

| old folder | now |
|---|---|
| `tasks/task_NNN/base/runs/` | `agents/haiku-4.5_claude-code-2.1.199/runs/MTAC-task-NN/A/` |
| `tasks/task_NNN/B/runs/` | `…/runs/MTAC-task-NN/B/` |
| `tasks/task_NNN/CT/runs/` (route + toolbox) | `…/runs/MTAC-task-NN/C/` |
| `tasks/task_NNN/C/runs/` (route + notes) | `…/runs/MTAC-task-NN/C-notes/` |
| `tasks/task_NNN/BT/runs/` | `…/runs/MTAC-task-NN/B-toolbox/` |
| `tasks/task_NNN/<arm>/translation/` | `tasks/MTAC-task-NN/arms/<arm>/translation/` |
| `translation/` | `prompts/` (system parts, rule templates, guides) and `harness/` (wrap, try, environment, docs) |
| `archive/unsuccessful-2026-10-17/`, `checks-2026-10-18/`, `pilot-2026-10-08/` | `agents/haiku-4.5_claude-code-2.1.199/earlier/` |
| `tasks/task_NNN/base/output/` (AgentProbe runs of A, Oct 8) | `…/earlier/agentprobe-2026-10-08/task_NNN/A/output/` |
| `../with tool box.md` | `archive/toolbox-plan-2026-10-18.md` |
