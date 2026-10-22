# τ²-bench

Material from τ²-bench (Barres et al., arXiv 2506.07982, Jun 2025; ICML 2026, oral, PMLR 306): tool-using conversational agents that must follow a
domain policy document (airline, retail, telecom, banking_knowledge), with an LLM-simulated user; scored by the final
database state and actions, as pass^k over repeated runs. Backup base benchmark for the rules-in-the-wild study:
widely used, but policy compliance is folded into task success.

| path | what it is |
|---|---|
| `τ²-Bench - … .pdf` | the τ²-bench paper |
| `tau2-bench/` | the benchmark's code and data (now released as τ³-bench): [sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench), commit `4ce7c03` (2026-10-06), shallow clone of 2026-10-12, unchanged; 853 MB |

Other papers the repo asks to cite (not downloaded): τ-bench (Yao et al., arXiv 2406.12045), τ-Knowledge (arXiv
2603.04370), τ-Voice (arXiv 2603.13686), task fixes (arXiv 2512.07850). License: MIT (the repo's `LICENSE`).
