# Claude Haiku 4.5 in Claude Code 2.1.199

The agent setup of every run so far (`agent.json`; the default of `scripts/runner.py`).

- `runs/MTAC-task-NN/<arm>/<stamp>/`: the runs, by task and arm (A, B, C, C-ideal, and the earlier variants C-notes,
  B-toolbox, C-plain).
- `checks/MTAC-task-NN/<arm>/<stamp>/`: runs with a scripted model (`runner.py --mock`), no model calls: checks of the
  chain.
