# τ²-bench

τ²-bench (Barres et al., arXiv 2506.07982, Jun 2025; ICML 2026): tool-using conversational agents that must follow a
domain policy document (airline, retail, telecom, banking_knowledge), with an LLM-simulated user; scored by the final
database state and actions, as pass^k over repeated runs. A backup benchmark for this study: widely used, but policy
compliance is part of task success. Not used yet.

To use it: clone [sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench) (now released as
τ³-bench) at commit `4ce7c03` into `tau2-bench/`. License: MIT (the repository's `LICENSE`).
