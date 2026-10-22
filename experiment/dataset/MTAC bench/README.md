# MTAC bench

MTAC-IFBench (Wen et al., arXiv, Sep 2026): instruction following in multi-turn agentic coding. The experiment's tasks
come from here: `scripts/build_tasks.py` copies each chosen task into `experiment/tasks/MTAC-task-NN/`.

| path | what it is |
|---|---|
| `task data/` | download: MTAC-IFBench's `mtac_full.jsonl` (100 tasks with their checkers), from [thu-coai/MTAC-IFBench](https://huggingface.co/datasets/thu-coai/MTAC-IFBench) |
| `base agent/` | download: [abelperry/AgentProbe](https://github.com/abelperry/AgentProbe) at commit `e291570`, unchanged. The experiment uses it as a library (MTAC's turn prompts and checker runner) and installs Claude Code from its `data/offline_package/`. Its environment runs the scripts that read MTAC's data: `uv run --project "dataset/MTAC bench/base agent" python scripts/<name>.py` from `experiment/` |
| `research/` | notes and reports |
