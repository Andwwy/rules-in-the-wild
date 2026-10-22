# MTAC bench

MTAC-IFBench (Wen et al., arXiv Sep 2026): instruction following in multi-turn agentic coding. The experiment's tasks
come from here: `scripts/build_tasks.py` copies each chosen task into `experiment/tasks/MTAC-task-NN/`.

| path | what it is |
|---|---|
| `MTAC-IFBench - … .pdf` | the paper |
| `task data/` | MTAC-IFBench's data, as downloaded: `mtac_full.jsonl` (100 tasks, `task_id` 1–100) and the checkers |
| `base agent/` | [abelperry/AgentProbe](https://github.com/abelperry/AgentProbe) at `e291570`, unchanged, used as a library: MTAC's turn prompts and checker runner; `data/offline_package/` holds the offline Claude Code package. Its Python environment runs the scripts that read MTAC's data: `uv run --project "dataset/MTAC bench/base agent" python scripts/<name>.py` from `experiment/` |
| `research/` | notes and a report on structured context for enforcement translation |
