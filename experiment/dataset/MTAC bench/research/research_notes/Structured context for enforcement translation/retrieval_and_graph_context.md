# Retrieval-augmented and structured-context methods for tool/API/config code generation

Scope note: notes compiled 2026-10-18. "Foundational" marks pre-2025 work. Star counts and last-push dates come from the GitHub REST API (`api.github.com/repos/<owner>/<repo>`), read on 2026-10-18. Some numbers come from WebFetch extraction of arXiv HTML; where table cells were garbled, this is said. Out of scope (covered by other researchers): guardrail compilers, NL-to-static-analysis-rule synthesis, skill libraries, environment-setup agents.

## 1. What do documentation-retrieval methods for code generation show, and when does retrieval help or hurt?

### Takeaway
Documentation retrieval helps most when the API is rare, new or version-shifted, and when the model is weak; for strong models on common libraries it often gives no gain and can hurt, mainly through near-miss ("hard negative") context. Execution feedback (self-debugging, test loops) gives larger and more reliable gains than retrieval in the version-drift benchmarks.

### Cited Findings

**Foundational doc-retrieval results**
- DocPrompting (Zhou et al., ICLR 2023, arXiv 2207.05987; foundational): retrieve docs for an NL intent, then generate. CodeT5 gains +2.85 pass@1 (52% relative) and +4.39 pass@10 (30% relative) on CoNaLa (Python, execution-based). On tldr (Bash) the gain is up to +6.9 exact match for CodeT5 and GPT-Neo 1.3B. For Codex 3-shot, the gain is minor; the authors suspect data leakage. — [arXiv 2207.05987](https://arxiv.org/pdf/2207.05987); [ICLR 2023 oral](https://iclr.cc/virtual/2023/oral/12584)
- RepoCoder (Zhang et al., EMNLP 2023, arXiv 2303.12570; foundational): iterative retrieve-generate loop. More than 10% over the in-file baseline in all settings. The limitations section says gains are small when a repo has little code duplication, and later iterations can be unstable. — [arXiv 2303.12570](https://arxiv.org/pdf/2303.12570)

**CodeRAG-Bench (Wang, Asai, Yu, Xu, Xie, Neubig, Fried; Findings of NAACL 2025; arXiv 2406.14497)**
- Setup: 10 retrievers and 10 LMs. Five document sources: library docs, competition solutions, tutorials, StackOverflow posts, GitHub. Main finding: high-quality context helps, but retrievers miss useful context when lexical overlap is low, and generators do not use extra context well. — [arXiv 2406.14497](https://arxiv.org/abs/2406.14497v1)
- Gold documents vs. no context, pass@1 (Table 5): GPT-4o DS-1000 52.7 → 51.2, ODEX 44.6 → 44.2, ODEX-hard 20.7 → 27.6. StarCoder2-7B ODEX-hard 10.3 → 17.2. DeepSeekCoder-7B ODEX-hard 17.2 → 24.1. Gold docs help weak open models most. For GPT-4o they help only on the hard (rare-library) split; the paper links this to memorization of common libraries. — [arXiv HTML 2406.14497](https://arxiv.org/html/2406.14497)
- Retrieved docs can beat gold docs for weak models: StarCoder2-7B with BM25 goes 29.2 → 36.7 on DS-1000 (gold-doc score is 30.0). — [arXiv HTML 2406.14497](https://arxiv.org/html/2406.14497)
- Retrieval can hurt sharply: DeepSeekCoder-7B on HumanEval drops 70.1 → 53.0 with OpenAI-rerank retrieval. The paper links this to over-complicated, repetitive generations. — [arXiv HTML 2406.14497](https://arxiv.org/html/2406.14497)
- Chunking matters more than source. HumanEval, docs source: full text 17.7, first ~800-token chunk 29.3, pre-retrieval chunk 32.9, reranked chunk 9.1. About five documents is best in most settings; more low-ranked documents add noise. — [arXiv HTML 2406.14497](https://arxiv.org/html/2406.14497)
- On RepoEval, local repo context dominates: GPT-4o 32.4 (no context) → 62.2 (local repo) vs. 30.3 with open-web sources. — [arXiv HTML 2406.14497](https://arxiv.org/html/2406.14497) (caveat: WebFetch reported misaligned cells in Tables 7–8; values above are from the text)

**API hallucination**
- CloudAPIBench / "On Mitigating Code LLM Hallucinations with API Documentation" (Jain, Kwiatkowski, Ray, Ramanathan, Kumar; Amazon/Columbia; ICSE-SEIP 2025; arXiv 2407.09726): 622 synthetic Python tasks over AWS and Azure APIs; frequency bins from The Stack v2 (low 0–10, medium 11–100, high ≥101). GPT-4o makes only 38.58% valid low-frequency API calls. Documentation Augmented Generation (DAG) raises this to 47.94%, but with weaker retrievers it causes a 39.02% absolute drop on high-frequency APIs. Selective retrieval (trigger only via API-index check or model confidence) gives +8.20% absolute for GPT-4o. — [arXiv 2407.09726](https://arxiv.org/pdf/2407.09726); [ICSE 2025 SEIP](https://conf.researchr.org/details/icse-2025/icse-2025-software-engineering-in-practice/33/On-Mitigating-Code-LLM-Hallucinations-with-API-Documentation)
- De-Hallucinator (Eghbali & Pradel, Univ. Stuttgart; arXiv 2401.01701): uses the model's first prediction as the query to retrieve real project API references (CodeQL-extracted index), then re-prompts, iteratively. v2 (Python): edit distance improves 23–51% and correct-API recall 24–61% relative to a prefix-only prompt; v3 extends to JS test generation and five LLMs. — [arXiv 2401.01701](https://arxiv.org/abs/2401.01701v2)

**Version / library-evolution benchmarks**
- GitChameleon 2.0 (Misra, Caccia, Gehring, Chaudhary et al.; NeurIPS 2025; arXiv 2507.12367): 328 version-conditioned Python completion problems with executable tests. Enterprise models score 48–51% baseline. — [arXiv 2507.12367](https://arxiv.org/abs/2507.12367v1); [NeurIPS 2025](https://neurips.cc/virtual/2025/131646)
- GitChameleon 2.0 RAG (k=3 docs), hidden-test success, greedy → RAG: GPT-4.1 48.5 → 58.5 (+10.0); Mistral Medium 3 43.6 → 52.4; Claude 3.7 Sonnet 48.8 → 56.1 (+7.3); Gemini 2.5 Pro 50.0 → 56.7; Grok 3 48.2 → 54.3; Llama 4 Maverick 40.8 → 45.1. — [arXiv HTML 2507.12367](https://arxiv.org/html/2507.12367)
- GitChameleon 2.0 self-debugging (error feedback) gains are larger: roughly +10–20 points on hidden tests (Llama 3.1 30.2 → 52.1; GPT-4.1-mini 44 → 68); on visible tests Claude 3.7 Sonnet 56 → 83. Zero-shot CoT is inconsistent (o1 51.2 → 41.2; Gemini 2.0 Flash 44.2 → 36.0). Coding assistants: Claude Code (Claude 3.7 Sonnet) 32.0 → 48.8 when given the problem statement; Cline (GPT-4.1) 38.4 → 54.6. Agents with a sandbox gain strongly (GPT-4o + grounded Gemini 25.4 → 50.0). — [arXiv HTML 2507.12367](https://arxiv.org/html/2507.12367)
- LibEvolutionEval (Kuhar et al., Amazon; NAACL 2025, 2025.naacl-long.348): version-specific completion over 8 Python libraries (torch, torchvision, scipy, pil, tqdm, pyyaml, matplotlib, pandas). Library evolution noticeably degrades models; retrieving version-specific docs plus prompting mitigates it (abstract-level; no numbers retrieved). — [ACL Anthology](https://aclanthology.org/2025.naacl-long.348); [Amazon Science](https://amazon.science/publications/libevolutioneval-a-benchmark-and-study-for-version-specific-code-generation)
- VersiCode (Wu et al., arXiv 2406.07411, 2024): 105,569 instances; version-specific completion and version-aware migration at token/line/block granularity; GPT-4o and LLaMA3 show notable limits. — [arXiv 2406.07411](https://arxiv.org/abs/2406.07411v2)
- EVOR (Su et al.; Findings of EMNLP 2024; arXiv 2402.12317): "knowledge soup" of web search, official docs, execution feedback and code snippets; queries and knowledge base evolve together; executed-OK snippets become positive examples, failed snippets plus error messages become negative examples. On updated libraries and long-tail languages ChatGPT goes 8.6% → 34.6%; average gain +24.0% (ChatGPT) and +23.8% (CodeLlama) over no augmentation. — [arXiv 2402.12317](https://www.arxiv.org/pdf/2402.12317); [Findings EMNLP 2024](https://preview.aclanthology.org/dashboard/2024.findings-emnlp.143)

**What to retrieve**
- Gu et al., "What to Retrieve for Effective Retrieval-Augmented Code Generation? An Empirical Study and Beyond" (Sun Yat-sen Univ., TUM, Huawei Cloud; ICSE 2026; arXiv 2503.20589): in-context code and potential-API information improve results; retrieved similar code often adds noise and degrades results by up to 15%. AllianceCoder (CoT decomposition, then API retrieval by semantic description match) gives up to +20% Pass@1 on CoderEval and RepoExec. — [arXiv 2503.20589](https://arxiv.org/abs/2503.20589v1); [ICSE 2026 listing](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/182/What-to-Retrieve-for-Effective-Retrieval-Augmented-Code-Generation-An-Empirical-Stud)

**Noise, distractors, position, context rot**
- Lost in the Middle (Liu et al., TACL 2024, arXiv 2307.03172; foundational): U-shaped accuracy over answer position in multi-doc QA (10/20/30 docs). Secondary write-ups give a ~20-point drop at middle positions for 20 docs, and say the worst middle case can fall below no-documents; exact figures differ across secondary sources. — [Beancount research log](https://beancount.io/bean-labs/research-logs/2026/06/27/lost-in-the-middle-language-models-long-contexts); [arXiv 2307.03172](https://arxiv.org/abs/2307.03172)
- Long-Context LLMs Meet RAG (Jin, Yoon, Han, Arik; ICLR 2025; arXiv 2410.05983): quality first rises, then falls, as retrieved passages increase. The cause is "hard negatives" (relevant-looking passages without the answer). Models are robust to random negatives but not to hard ones. A stronger retriever (e5) yields harder negatives and a steeper decline than BM25; the authors conclude precision alone is an inadequate retrieval-quality measure. Fix: training-free reordering, or RAG-specific fine-tuning. — [arXiv 2410.05983](https://arxiv.org/abs/2410.05983v1)
- Context Rot (Hong, Troynikov, Huber; Chroma technical report, July 2025): 18 models (GPT-4.1, Claude 4, Gemini 2.5, Qwen3 …) all degrade as input length grows with task difficulty held constant; one distractor already lowers accuracy below baseline, and some distractors hurt far more than others; lower question–evidence similarity makes decay faster. On LongMemEval, focused ~300-token prompts beat full ~113K-token prompts across model families (secondary report). — [ZenML summary](https://www.zenml.io/llmops-database/context-rot-evaluating-llm-performance-degradation-with-increasing-input-tokens); primary at [research.trychroma.com/context-rot](https://research.trychroma.com/context-rot)
- Sufficient Context (Joren, Zhang, Ferng, Juan, Taly, Rashtchian; Google; ICLR 2025; arXiv 2411.06037): large models (Gemini 1.5 Pro, GPT-4o, Claude 3.5) answer well when context is sufficient but often answer wrongly instead of abstaining when it is not. Selective generation using a sufficiency signal raises correct answers among responses by ~2–10%. The Google blog says relevance alone is the wrong thing to measure. — [arXiv 2411.06037](https://arxiv.org/pdf/2411.06037.pdf); [Google Research blog](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)

### Inferences
- Semgrep, ESLint, Ruff, git hooks and file permissions are high-frequency tools. CloudAPIBench and CodeRAG-Bench both show that generic docs for well-known tools give strong models little gain and can hurt. So "more docs" is unlikely to fix the observed failures; the failures are about semantics and coverage (arrow functions, shell-written files, hook exit codes), not missing API names.
- The parts that ARE rare or version-sensitive (Claude Code hook JSON/exit-code contract, ESLint flat config vs. legacy `.eslintrc`, Semgrep rule-schema details) match the CloudAPIBench "low-frequency" and GitChameleon "version drift" cases, where precise docs give +7 to +10 points. Retrieval should be selective and targeted at those parts.
- Legacy-format docs (e.g., `.eslintrc` pages next to flat-config pages) are textbook hard negatives (Jin et al.). A curated store must exclude them, not rank them lower.
- GitChameleon shows execution feedback beats retrieval by about 2x in gain. For enforcement translation, the analog is running each generated enforcer against positive/negative test fixtures and feeding failures back.

### Gaps
- No primary numbers found for Gorilla (APIBench) oracle-vs-BM25 retriever accuracy; a secondary blog claims −29.20% (GPT-Index) and −52.27% (BM25) vs. oracle, unverified.
- VersiCode per-model EM@1 values and LibEvolutionEval RAG deltas were not retrieved.
- No study found that measures doc retrieval specifically for linter configs (ESLint flat config, Ruff `pyproject` sections) or for Claude Code hook scripts.

## 2. GraphRAG and knowledge-graph approaches for code and tools: do graphs beat flat retrieval for choosing concrete actions/config?

### Takeaway
Graphs win when the needed item is linked to the query by structure (call/import edges in a repo; "prerequisite" or "used-together" edges between tools) rather than by text similarity; on simple lookups, GraphRAG often ties or loses to vanilla RAG. For a fixed taxonomy, a hierarchical index (category → tool → API) plus a few dependency edges captures most of the measured gains.

### Cited Findings

**General GraphRAG**
- Microsoft GraphRAG (Edge et al. 2024, "From Local to Global", arXiv 2404.16130): LLM-built entity graph plus community summaries for query-focused summarization. Repo microsoft/graphrag: 36,373 stars, last push 2026-10-12. — [GitHub microsoft/graphrag](https://github.com/microsoft/graphrag); [arXiv 2404.16130](https://arxiv.org/abs/2404.16130)
- "When to use Graphs in RAG" / GraphRAG-Bench (Xiang et al., ICLR 2026, arXiv 2506.05690): states GraphRAG frequently underperforms vanilla RAG on many real tasks; cites a prior study with 13.4% lower accuracy on Natural Questions for GraphRAG; basic RAG is comparable or better on simple fact retrieval; graphs pay off on complex reasoning / hierarchical tasks. — [arXiv 2506.05690](https://arxiv.org/html/2506.05690v3); [ICLR 2026](https://iclr.cc/virtual/2026/poster/10007992)

**Code knowledge graphs**
- RepoGraph (Ouyang et al., ICLR 2025, arXiv 2410.14684): line-level repository graph as a plug-in. +2.66 / +2.34 absolute resolve rate on SWE-bench Lite when added to RAG / Agentless (99.63% / 8.56% relative; the RAG baseline was very low). Agentless + RepoGraph = 29.67%, open-source SOTA at the time. — [arXiv 2410.14684](https://arxiv.org/abs/2410.14684); [ICLR 2025 proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/4a4a3c197deac042461c677219efd36c-Abstract-Conference.html)
- CodexGraph (Liu et al., NAACL 2025, 2025.naacl-long.7, arXiv 2408.03910): static analysis builds a code graph DB with a task-agnostic schema (MODULE/CLASS/FUNCTION nodes; CONTAINS/INHERITS/USES edges); the agent writes graph queries. Evaluated on CrossCodeEval Lite (Python, 1,000 instances), SWE-bench, EvoCodeBench; reports "competitive" results (numbers not retrieved). — [ACL Anthology](https://aclanthology.org/2025.naacl-long.7/); [arXiv 2408.03910](https://arxiv.org/pdf/2408.03910)
- CodeRAG (arXiv 2504.10046, Apr 2025): requirement graph + DS-code graph; requirement nodes map to code anchors; agentic tools (web search, graph reasoning, code testing). Pass@1 gains on DevEval vs. no retrieval: +40.90 (GPT-4o), +37.79 (Gemini-Pro); claims to beat Copilot and Cursor. — [arXiv 2504.10046](https://arxiv.org/html/2504.10046v1)
- Programming Knowledge Graph (Seddik et al., arXiv 2601.20810, Jan 2026): finer-grained nodes, tree pruning for retrieval precision, re-ranking that also considers non-RAG solutions; up to +20% pass@1 on HumanEval/MBPP and 34% over baselines on MBPP; designed to avoid breaking already-correct answers. — [arXiv 2601.20810](https://arxiv.org/abs/2601.20810v1)

**Tool graphs and hierarchical tool retrieval**
- ToolNet (Liu et al., 2024, arXiv 2403.00839): tools as nodes in a weighted directed graph; the LLM sees only successors of its last tool; edge weights act as priors; reported better than ReAct/Reflexion/ToT with fewer tokens, especially with noisy or many tools (secondary review; numbers not retrieved). — [arXiv 2403.00839](https://arxiv.org/abs/2403.00839v1); [Moonlight review](https://themoonlight.io/review/toolnet-connecting-large-language-models-with-massive-tools-via-tool-graph)
- Graph RAG-Tool Fusion (Lumer et al., arXiv 2502.07223, Feb 2025): vector retrieval plus graph traversal over a tool KG to pull in prerequisite tools; +71.7% and +22.1% absolute mAP@10 over naive RAG on ToolLinkOS and ToolSandbox. — [arXiv 2502.07223](https://arxiv.org/abs/2502.07223v1)
- Tool Graph Retriever (Gao et al., arXiv 2508.05152, Aug 2025): dependency graph + graph convolution; motivation: prerequisite tools are often semantically unrelated to the request, so similarity search misses them. — [arXiv 2508.05152](https://arxiv.org/html/2508.05152v1)
- Agent-as-a-Graph (Nizar et al., arXiv 2511.18194, Nov 2025): tools and parent agents/servers as KG nodes; +14.9% Recall@5 and +14.6% nDCG@5 over prior SOTA retrievers on LiveMCPBenchmark. — [arXiv 2511.18194](https://arxiv.org/html/2511.18194v1)
- AnyTool (Du, Wei, Zhang; ICML 2024; arXiv 2402.04253; foundational): hierarchical retrieval over 16k+ RapidAPI APIs (meta-agent → category agents → tool agents) with self-reflection. +35.4% average pass rate over ToolLLM on ToolBench; README: 58.2% vs. 31.8% (ToolLLM, GPT-4) on filtered ToolBench, 73.8% vs. 36.6% on AnyToolBench. Authors note prior ToolBench protocol inflated pass rates. — [arXiv 2402.04253](https://arxiv.org/abs/2402.04253v1); [PMLR](https://proceedings.mlr.press/v235/du24h.html); [GitHub README](https://github.com/dyabel/AnyTool/blob/public/README.md)
- RAG-MCP (Gan & Sun, arXiv 2505.03275, May 2025): retrieve only the relevant MCP tool schema instead of loading all; tool-selection accuracy 43.13% vs. 13.62% baseline; prompt tokens cut by over 50% (an alphaXiv summary says 73%; conflict unresolved). Precision degrades as the registry grows. — [arXiv 2505.03275](https://arxiv.org/html/2505.03275v1); [alphaXiv overview](https://www.alphaxiv.org/overview/2505.03275v1)
- Survey "Graph-Augmented LLM Agents" (arXiv 2507.21407): tool graphs model both dependencies and transition preferences for selection from large tool pools. — [arXiv 2507.21407](https://arxiv.org/pdf/2507.21407)

### Inferences
- The project's route (enforcer leaf, trigger leaf, target leaf) is already a deterministic key into a hierarchy. AnyTool-style hierarchy and RAG-MCP-style "inject only the matching schema" are thus achievable with a lookup table, no retriever and no retrieval error.
- Where graphs add real value here is dependency/coverage edges, the same thing Graph RAG-Tool Fusion and Tool Graph Retriever measure: e.g., trigger "Agent action › File write / edit" REQUIRES coverage of Write/Edit tool calls AND shell-written files (PostToolUse on Bash, git pre-commit, or a filesystem check); target "Name / identifier" in JS REQUIRES AST node kinds for function declarations, arrow functions bound to variables, and class methods. These "prerequisite but semantically unrelated" items are exactly what similarity search misses and what the translating agent missed.
- LLM-extracted GraphRAG over raw tool docs is a poor fit: the corpus is small, the queries are lookups, and GraphRAG-Bench shows vanilla RAG ties or wins on that kind of query. A small hand-built graph (~212 leaves, typed edges such as `requires`, `complements`, `conflicts_with`, `verified_by`) is cheaper and auditable.

### Gaps
- No paper found that compares graph vs. flat retrieval for config/DSL generation (linter configs, policy files) specifically; the tool-graph results are on tool-selection benchmarks (mAP, Recall@k), not on end-to-end correctness of generated config.
- CodexGraph and ToolNet numeric results were not retrieved.
- API knowledge-graph work for misuse/constraints (e.g., API-constraint KGs from the pre-LLM SE literature) was not covered due to time; no 2025–2026 LLM-era API-KG paper with config-generation results was found.

## 3. Structured / hierarchical context, context engineering, llms.txt, doc MCP servers, compiled prompts: does precise, small, verified context beat larger retrieved context?

### Takeaway
Practitioner posts (Anthropic, Manus, LangChain) and the few controlled evals agree: a small, always-present, high-signal context beats large or on-demand context. Vercel measured 100% vs. 79% for an 8KB in-context docs index vs. on-demand skills, and Margin Labs found Context7 changed nothing because the agent called it in only 6.7% of tasks. Doc servers are popular (Context7 63k stars) but have little independent outcome evidence.

### Cited Findings

**Context engineering posts (2025)**
- Anthropic, "Effective context engineering for AI agents" (Rajasekaran, Dixon, Ryan, Hadfield; Sep 29, 2025): context is "a finite resource with diminishing marginal returns"; context rot; n² pairwise attention; goal is the "smallest possible set of high-signal tokens"; system prompt at the "right altitude" (between brittle if-else logic and vague guidance); curate "a set of diverse, canonical examples" rather than laundry lists of edge cases; just-in-time retrieval (keep identifiers, load at runtime) vs. pre-retrieval; hybrid used in Claude Code (CLAUDE.md up front, glob/grep just in time); tools should be self-contained, unambiguous and minimally overlapping. — [Anthropic Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Manus, "Context Engineering for AI Agents: Lessons from Building Manus" (Yichao "Peak" Ji, Jul 18, 2025): KV-cache hit rate is the key production metric; ~100:1 input:output token ratio; mask tools instead of removing them; use the filesystem as external context; recitation via a todo.md rewritten at the end of context; keep failed actions in context so the model learns from errors (todo.md and error details from secondary write-ups). — [Manus blog](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus); [tianpan.co summary](https://tianpan.co/blog/2026-03-02-context-engineering-lessons-from-manus)
- LangChain, "Context engineering for agents" (Jul 2, 2025): four strategies — write (save outside the window), select (pull in), compress (keep only needed tokens), isolate (split across sub-agents/state). — [LangChain blog](https://langchain.com/blog/context-engineering-for-agents); [langchain-ai/context_engineering](https://github.com/langchain-ai/context_engineering)

**Controlled evidence: small in-context vs. on-demand**
- Vercel, "AGENTS.md outperforms skills in our agent evals" (Jan 2026): on Next.js 16 APIs absent from training data (`'use cache'`, `connection()`, `forbidden()`), a compressed 8KB docs index embedded in AGENTS.md reached 100% pass rate; skills peaked at 79% even when the prompt told the agent to use them; the skill was never invoked in 56% of cases; a default skill scored the same as no docs (53%). Vendor's own eval, one framework. — [Vercel blog](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals)
- Margin Labs, "Do MCPs Actually Improve Coding Agents? Part 1" (Apr 10, 2026): Codex (GPT-5.4, xhigh) on Terminal-Bench 2.0, 89 tasks: 63/89 (70.8%) without Context7 vs. 64/89 (71.9%) with Context7, "well within noise". Context7 was called in only 6/89 tasks despite an AGENTS.md instruction; in those six, outcomes matched baseline. — [Margin Labs](https://marginlab.ai/blog/do-mcps-improve-coding-agents-part-1/)
- Claude Code dropped vector-DB RAG (Voyage embeddings) for agentic search (grep/glob); Boris Cherny says it "outperformed everything else by a lot" but the evidence was mostly "vibes" plus some internal benchmarks; other reasons were index staleness and permissions. — [Pragmatic Engineer](https://newsletter.pragmaticengineer.com/p/building-claude-code-with-boris-cherny); [OfficeChai](https://officechai.com/ai/claude-researcher-explains-how-agentic-search-performed-better-than-rag-for-code-generation/)
- Contrast: Cursor, "Improving agent with semantic search" (Nov 2025): adding semantic search to grep raised answer accuracy ~12.5% on average (6.5–23.5% by model) on its internal Cursor Context Bench, plus an online A/B test; hybrid works best. Internal, not independently verified. — [Cursor blog](https://cursor.com/en-US/blog/semsearch)

**Doc servers and llms.txt**
- llms.txt: proposed by Jeremy Howard (Answer.AI) on Sep 3, 2024; a Markdown file at site root with a curated summary and links, plus `.md` copies of pages. Community proposal, not a ratified standard; no major model provider has publicly confirmed consuming it. Repo AnswerDotAI/llms-txt: 2,662 stars, last push 2026-09-24. — [GreenGeeks explainer](https://www.greengeeks.com/blog/what-is-llms-txt-does-it-work-and-how-to-add-one-to-your-site/); [PyPI llms-txt](https://pypi.org/project/llms-txt); [GitHub](https://github.com/AnswerDotAI/llms-txt)
- Context7 (Upstash): "Up-to-date docs for AI agents"; 63,247 stars, last push 2026-10-17 (Star History showed 52.9k on Apr 16, 2026). — [GitHub upstash/context7](https://github.com/upstash/context7); [Star History](https://star-history.com/upstash/context7)
- Other doc servers (stars / last push, 2026-10-18): idosal/git-mcp ("remote MCP server for any GitHub project") 8,471 / 2026-05-08; arabold/docs-mcp-server ("Grounded Docs MCP Server: open-source alternative to Context7, Nia, and Ref.Tools") 1,816 / 2026-10-18; regenrek/deepwiki-mcp (fetches deepwiki.com) 1,386 / 2026-03-20; ref-tools/ref-tools-mcp 1,183 / 2026-10-01; docfork/docfork 485 / 2026-06-13. — [git-mcp](https://github.com/idosal/git-mcp); [docs-mcp-server](https://github.com/arabold/docs-mcp-server); [deepwiki-mcp](https://github.com/regenrek/deepwiki-mcp); [ref-tools-mcp](https://github.com/ref-tools/ref-tools-mcp); [docfork](https://github.com/docfork/docfork)

**Structure-constrained generation for DSLs**
- DocCGen (Pimparkhede et al., IIT Bombay + IBM Research; arXiv 2406.11925, 2024): two steps — retrieve the matching library doc, then use schema rules from that doc to constrain decoding; evaluated on Ansible YAML and Bash, in- and out-of-domain; beats fine-tuned baselines out-of-domain on all six metrics. A secondary summary reports Ansible YAML schema correctness 58.82% (StarCoder2-3B) vs. 4.41% for the fine-tuned baseline. — [arXiv 2406.11925](https://arxiv.org/html/2406.11925v2); [Liner summary](https://liner.com/review/doccgen-documentbased-controlled-code-generation)

**Compiled prompts**
- DSPy (stanfordnlp/dspy): "programming—not prompting" LMs; 38,681 stars, last push 2026-10-18. — [GitHub stanfordnlp/dspy](https://github.com/stanfordnlp/dspy)
- GEPA (Agrawal et al., arXiv 2507.19457; ICLR 2026 oral): LLM reads its own execution traces and rewrites prompts; Pareto selection. v2: +6% average over GRPO across six tasks (up to +20%) with up to 35x fewer rollouts; >10% over MIPROv2 (e.g., +12 on AIME-2025). v1 reported +10% over GRPO across four tasks. Repo gepa-ai/gepa: 7,032 stars, last push 2026-10-13. — [arXiv 2507.19457](https://arxiv.org/abs/2507.19457v2); [GitHub gepa-ai/gepa](https://github.com/gepa-ai/gepa)

**"Context precision" as a metric**
- RAGAS context precision is a ranking metric: mean of precision@k at each rank holding a relevant chunk; it rewards relevant chunks ranked first, and an irrelevant chunk at rank 2 need not lower the score. — [RAGAS docs](https://docs.ragas.io/en/latest/concepts/metrics/context_precision.html)
- Jin et al. show higher retriever precision (e5 vs. BM25) can still lower end-to-end accuracy through harder negatives; Sufficient Context argues the right target is sufficiency, not relevance. — [arXiv 2410.05983](https://arxiv.org/abs/2410.05983v1); [Google Research blog](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)

### Inferences

Fit to the route-keyed translation task:
- The user's framing "precision of information" matches the literature only if "precision" means sufficiency with no near-miss content, not the RAGAS ranking metric. The measurable target is: for each route, does the card contain everything needed (sufficiency) and nothing that misleads (no hard negatives, no legacy formats)?
- The strongest-fit pattern is a route-keyed "recipe card" injected up front (Vercel always-in-context; Anthropic hybrid), not an on-demand doc tool (Vercel: skill unused in 56% of cases; Margin Labs: Context7 used in 6.7%). Haiku 4.5 is also a smaller model; CodeRAG-Bench and Sufficient Context show weaker models gain more from precise context and are hurt more by noise.
- Each card should hold: (a) the tested adapter call from the shared toolbox (the human expert's 70/70 came from a toolbox, so the context should describe the toolbox API, not the raw tool); (b) one or two canonical worked examples for that enforcer type; (c) the exact contract facts most often wrong (e.g., hook exit-code semantics, flat-config shape); (d) coverage obligations from graph edges (file writes via Bash, arrow functions, methods); (e) a positive/negative fixture test the agent must run. DocCGen and the Rego validation-loop papers show that schema/validator constraints add gains on top of retrieval.
- DSPy/GEPA-style optimization is a later step: once a card format and a test harness exist, GEPA can tune card text against the compliance metric with few rollouts.

### Gaps
- No independent controlled study of llms.txt effectiveness was found.
- No independent end-to-end eval of Context7/GitMCP/Docfork beyond Margin Labs Part 1 was found; Vercel's and Cursor's numbers are vendor-internal.
- No paper found that tests "taxonomy-conditioned prompting" (injecting context selected by a classifier's route) as such; AnyTool and RAG-MCP are the closest analogs.

## 4. Exemplar / few-shot retrieval of worked examples vs. reference docs: which helps more for config/DSL code?

### Takeaway
For DSL/config generation the best evidence favors well-selected worked examples over API descriptions, with docs/schemas as a complement that cuts parameter hallucinations; "similar code" retrieved by surface similarity can hurt. For tool use with many unfamiliar APIs, docs alone can match or beat demos. Validation loops matter more than either for policy/config DSLs.

### Cited Findings
- Bassamzadeh & Methani (Microsoft), "A Comparative Study of DSL Code Generation: Fine-Tuning vs. Optimized Retrieval Augmentation" (arXiv 2407.02742, Jul 2024): ~67k NL→DSL workflow pairs over ~700 APIs; GPT-4 RAG vs. fine-tuned Codex. Example selection by Target Similarity Tuning (TST) at 20 shots cut API-name hallucination by 8.49 points and parameter-key hallucination by 14.58 points vs. 5-shot pre-trained retrieval. Adding API function definitions (FD) at 5 shots cut parameter hallucination ~20 points but raised unparsed flows +2.75. Retrieving definitions by semantic similarity (SFD) hurt (+6.76 parameter hallucination vs. fine-tuned); too many API descriptions "can confuse rather than help". Best RAG matched the fine-tuned model on similarity, within ~1–2 points on hallucination, with fewer unparsed flows. Authors conclude well-chosen examples matter more than API descriptions. — [arXiv 2407.02742](https://arxiv.org/html/2407.02742v1)
- Hsieh, Chen, Ratner, Krishna, "Tool Documentation Enables Zero-Shot Tool-Usage with LLMs" (arXiv 2308.00675, 2023; foundational): on existing benchmarks, docs-only zero-shot ≈ few-shot demos; on a new dataset with hundreds of tool APIs, zero-shot with docs significantly beats few-shot without docs; demos are costly and can bias usage. — [Google Research](https://research.google/pubs/tool-documentation-enables-zero-shot-tool-usage-with-large-language-models/); [arXiv 2308.00675](https://arxiv.org/pdf/2308.00675)
- CodeRAG-Bench, ODEX with GPT-4o: retrieved programming solutions (worked examples) +4.6 (44.6 → 49.2) vs. docs +3.0 (47.6); tutorials, StackOverflow and GitHub did not help (44.2, 40.3, 39.4). — [arXiv HTML 2406.14497](https://arxiv.org/html/2406.14497)
- Gu et al. (ICSE 2026): retrieved similar code degrades results by up to 15% in repo-level generation; API info helps. — [arXiv 2503.20589](https://arxiv.org/abs/2503.20589v1)
- EVOR: execution-verified snippets as positive examples and failed snippets with error messages as negative examples are part of the knowledge soup that lifts updated-library/long-tail-language tasks from 8.6% to 34.6% (ChatGPT). — [arXiv 2402.12317](https://www.arxiv.org/pdf/2402.12317)
- Anthropic recommends a few diverse, canonical examples over laundry lists of edge cases. — [Anthropic Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

Policy-as-code (Rego) evidence (closest DSL analog to Semgrep YAML / ESLint config):
- ARPaCCino (arXiv 2507.10584, Jul 2025): plain prompting vs. RAG vs. agentic RAG for Rego; Qwen3 and GPT-4o without retrieval produced syntax errors (base models lack OPA/Rego knowledge); Claude Sonnet 4 scored 5/5 syntax and semantics in all three configurations. — [arXiv 2507.10584](https://arxiv.org/pdf/2507.10584)
- Structured decomposition for LLM-generated access-control policies (arXiv 2609.24036): `opa check` + Regal linter feedback for up to three rounds plus semantic guardrails; missing ownership conditions fell from 60% to 0% on its dataset. — [arXiv 2609.24036](https://arxiv.org/pdf/2609.24036)
- SBSeg 2025 study (Portuguese): OPA/Rego policies tested on a vulnerable Terraform plan and its secure twin; RCI raised static-check pass rates and detection but lowered strict pass@1 in four of five models (over-blocking), so detection-only metrics overstate usefulness. — [SBSeg](https://sol.sbc.org.br/index.php/sbseg_estendido/article/view/44493)
- Prose2Policy (Apple, arXiv 2603.15799): 95.3% compile rate for accepted policies on ACRE; automated tests pass 82.2% (positive) and 98.9% (negative). — [arXiv 2603.15799](https://arxiv.org/html/2603.15799v1); [Apple ML Research](https://machinelearning.apple.com/research/prose2policy)

### Inferences
- For the observed failure "installed Semgrep but wrote a rule that does not express the rule", a tested worked example per enforcer pattern (e.g., a Semgrep `pattern-regex`/`metavariable-regex` rule for an identifier-shape constraint, with a passing and failing fixture) is likely worth more than Semgrep reference docs; the DSL study and ODEX result point the same way.
- Examples must be selected by target structure (the route and rule family), not by text similarity of the rule sentence; the DSL study's TST and Gu et al.'s "similar code adds noise" both say surface-similar examples can mislead.
- Minimal-pair fixtures (one compliant, one violating file per rule) serve both as the agent's self-check and as the eval; the Rego studies show compile/lint pass alone is a weak signal.

### Gaps
- No study found that directly compares worked examples vs. reference docs for Semgrep YAML, ESLint flat config, Ruff config or Claude Code hooks.
- Synchromesh (Poesia et al., ICLR 2022: Target Similarity Tuning + constrained semantic decoding for SQL, Vega-Lite, SMCalFlow) and DAIL-SQL example-selection results were not verified from primary sources in this session.

## 5. Trending GitHub projects (2025–2026) for doc/tool knowledge servers and code knowledge graphs for agents

### Takeaway
The most-starred projects are doc servers (Context7) and code-graph MCP servers (GitNexus, codebase-memory-mcp, Serena); graph/memory frameworks (GraphRAG, LightRAG, Graphiti, Cognee) are large but general-purpose. None of them ships a route-keyed, tested "enforcement recipe" store; the closest reusable parts are the doc-server pattern and code-graph indexing for AST-level coverage.

### Cited Findings
All counts from the GitHub REST API on 2026-10-18 ("last push" = `pushed_at`, not a release date).
- upstash/context7 — 63,247 stars; last push 2026-10-17; "Context7 Platform -- Up-to-date docs for AI agents". — [GitHub](https://github.com/upstash/context7)
- abhigyanpatwari/GitNexus — 47,932 stars; last push 2026-10-18; "Zero-Server Code Intelligence Engine". — [GitHub](https://github.com/abhigyanpatwari/GitNexus)
- DeusData/codebase-memory-mcp — 46,841 stars; last push 2026-10-18; code-intelligence MCP server that indexes codebases into a persistent knowledge graph. — [GitHub](https://github.com/DeusData/codebase-memory-mcp)
- HKUDS/LightRAG — 40,200 stars; last push 2026-10-15; EMNLP 2025 graph-RAG. — [GitHub](https://github.com/HKUDS/LightRAG)
- stanfordnlp/dspy — 38,681 stars; last push 2026-10-18. — [GitHub](https://github.com/stanfordnlp/dspy)
- microsoft/graphrag — 36,373 stars; last push 2026-10-12. — [GitHub](https://github.com/microsoft/graphrag)
- topoteretes/cognee — 32,478 stars; last push 2026-10-16; agent memory platform. — [GitHub](https://github.com/topoteretes/cognee)
- getzep/graphiti — 31,970 stars; last push 2026-10-17; real-time knowledge graphs for agents. — [GitHub](https://github.com/getzep/graphiti)
- oraios/serena — 30,365 stars; last push 2026-10-15; MCP toolkit with semantic (LSP-based) retrieval and editing. — [GitHub](https://github.com/oraios/serena)
- idosal/git-mcp — 8,471 stars; last push 2026-05-08. — [GitHub](https://github.com/idosal/git-mcp)
- gepa-ai/gepa — 7,032 stars; last push 2026-10-13. — [GitHub](https://github.com/gepa-ai/gepa)
- potpie-ai/potpie — 5,742 stars; last push 2026-10-16; "Context Graph for AI Native SDLC". — [GitHub](https://github.com/potpie-ai/potpie)
- vitali87/code-graph-rag — 5,264 stars; last push 2026-10-18; multi-language monorepo graph RAG. — [GitHub](https://github.com/vitali87/code-graph-rag)
- CodeGraphContext/CodeGraphContext — 4,295 stars; last push 2026-10-17; MCP server + CLI indexing local code into a graph DB. — [GitHub](https://github.com/CodeGraphContext/CodeGraphContext)
- AnswerDotAI/llms-txt — 2,662 stars; last push 2026-09-24. — [GitHub](https://github.com/AnswerDotAI/llms-txt)
- arabold/docs-mcp-server — 1,816 stars; last push 2026-10-18. — [GitHub](https://github.com/arabold/docs-mcp-server)
- regenrek/deepwiki-mcp — 1,386 stars; last push 2026-03-20. — [GitHub](https://github.com/regenrek/deepwiki-mcp)
- ref-tools/ref-tools-mcp — 1,183 stars; last push 2026-10-01. — [GitHub](https://github.com/ref-tools/ref-tools-mcp)
- docfork/docfork — 485 stars; last push 2026-06-13. — [GitHub](https://github.com/docfork/docfork)
- FalkorDB/code-graph — 348 stars; last push 2026-10-18 (GraphRAG-SDK demo). — [GitHub](https://github.com/FalkorDB/code-graph)
- ozyyshr/RepoGraph (ICLR 2025 code) — 306 stars; last push 2025-04-01. — [GitHub](https://github.com/ozyyshr/RepoGraph)
- Context7 star growth: 48,098 (Mar 8, 2026, OOSMetrics) → 52.9k (Apr 16, 2026, Star History) → 63,247 (Oct 18, 2026, API). — [OOSMetrics](https://oosmetrics.com/repo/upstash/context7); [Star History](https://star-history.com/upstash/context7)

### Inferences
- Popularity does not equal measured benefit: the one independent end-to-end test of the most popular doc server (Context7) found no gain because the agent rarely called it.
- For this project, the useful borrowings are: (1) the doc-server idea of a versioned, curated snippet store, but keyed by taxonomy leaf and pre-loaded instead of called; (2) code-graph indexers (tree-sitter/LSP, as in Serena, CodeGraphContext, code-graph-rag) as a way to make "every function name" checks cover all AST node kinds, instead of regex.

### Gaps
- Star counts of hosted services without public repos (Cognition DeepWiki MCP, Nia) are not available.
- Some very high star counts for recently created repos (GitNexus, codebase-memory-mcp) were not checked for star inflation or creation date.
