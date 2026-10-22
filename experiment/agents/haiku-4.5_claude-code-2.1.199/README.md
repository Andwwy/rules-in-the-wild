# Claude Haiku 4.5 in Claude Code 2.1.199

The agent setup of every run so far (`agent.json`; the default of `scripts/runner.py`).

- `runs/task_NNN/<arm>/<stamp>/`: the runs, by task and arm (A, B, C, C-ideal, C-notes, B-toolbox; see ../../README.md).
- `checks/task_NNN/<arm>/<stamp>/`: scripted runs (`runner.py --mock`), no model calls: checks of the chain.
- `earlier/`: superseded runs of earlier pipelines, kept as trajectories, not results:
  - `pilot-2026-10-08/`: the pilot's steered arm (an expert translation) on tasks 46, 91, 83, 92, 51, with its toolbox,
    scripts and reports;
  - `agentprobe-2026-10-08/`: the AgentProbe runs of arm A (as root) on tasks 51, 83, 91, 92;
  - `unsuccessful-2026-10-17/`: every earlier A, B and C attempt on task 46 (its README says why each failed);
  - `checks-2026-10-18/`: probes of the runner and the harness.
