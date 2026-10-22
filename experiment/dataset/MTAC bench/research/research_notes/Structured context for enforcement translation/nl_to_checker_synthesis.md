# LLM synthesis of executable checkers and policies from natural-language rules

Scope: NL (or examples) to static-analysis rules, linter rules and configs, policy-as-code, and temporal or program specs, plus the verification loops that make the output correct. Research date: 2026-10-18. Older (pre-2025) work is marked "foundational".

## Q1. LLM-generated static analyzers and queries: success rates, and what scaffolding raised them

### Takeaway
Every strong 2025-2026 system wraps the LLM in an executable oracle (the checker must fire on a "bad" version and stay silent on a "good" version), a compiler or language-server feedback loop, and a fixed scaffold (template, utility functions, query skeleton, or DSL subset). Without these tools, agents fail most of the time: in QLCoder, Claude Code alone wrote correct CodeQL queries for only 10% of CVEs, and the full loop reached 53.4%.

### Cited Findings

#### KNighter (SOSP 2025): LLM writes Clang Static Analyzer checkers from bug-fix patches
- Paper: "KNighter: Transforming Static Analysis with LLM-Synthesized Checkers". Chenyuan Yang, Zijie Zhao, Lingming Zhang (UIUC), Zichen Xie (Zhejiang U.), Haoyu Li (SJTU). SOSP '25, Seoul, Oct 13-16, 2025. arXiv:2503.09002. — [arXiv v3](https://arxiv.org/html/2503.09002v3)
- Pipeline: (1) bug-pattern analysis of the patch, (2) plan synthesis, (3) checker implementation from a template, with a debugging agent that repairs compile errors (up to 5 attempts), (4) validation. Steps repeat over several iterations. — [arXiv v3](https://arxiv.org/html/2503.09002v3)
- Validation oracle: a checker is "valid" if N_buggy > N_patched and N_patched < 50 (reports on the buggy version must exceed reports on the patched version). Validation is scoped to patch-modified files. — [arXiv v3](https://arxiv.org/html/2503.09002v3)
- Success rate: 39 of 61 hand-labeled bug-fix commits (about 64%) gave valid checkers; 22 gave none. The abstract's "61%" matches the 37 "plausible" checkers. Valid checkers needed 2.4 synthesis attempts on average. — [arXiv v3](https://arxiv.org/html/2503.09002v3)
- Refinement for false positives: 26 of 39 valid checkers were plausible without refinement; a triage agent plus refinement agent (up to 3 iterations) made 11 of the other 13 plausible. A refined checker is accepted only if it stops flagging the known false positives and stays valid. False-positive rate among reports labeled "bug": 32.2% (61 of 90 confirmed). — [arXiv v3](https://arxiv.org/html/2503.09002v3)
- Bugs: 92 new Linux kernel bugs, 77 confirmed, 57 fixed, 30 CVEs (v3). Earlier versions reported 70 bugs / 11 CVEs (v1) and 16 CVEs (v2), so the counts changed across versions. — [arXiv v3](https://arxiv.org/html/2503.09002v3); [search summary of v1/v2](https://arxiv.org/abs/2503.09002v1)
- Structured context given to the LLM: a checker template, 9 utility functions with signatures and descriptions (e.g., getMemRegionFromExpr), and 3 hand-built few-shot examples (about 40 person-hours to build). — [arXiv v3](https://arxiv.org/html/2503.09002v3)
- Ablation (20 commits): default multi-stage pipeline gave 12 valid checkers; single-stage gave 8 (and 52 syntax errors vs 28); RAG-selected examples gave 12 at about double the token cost; GPT-4o 11, DeepSeek-R1 11, Gemini-2-flash 4 (130 errors). Default model: o3-mini. Cost about $0.24 per commit. — [arXiv v3](https://arxiv.org/html/2503.09002v3)

#### QLCoder (arXiv 2511.08462; ICLR 2026 poster per search summary): agent writes CodeQL queries from CVE data
- Authors: Claire Wang (UPenn), Ziyang Li (JHU), Saikat Dutta (Cornell), Mayur Naik (UPenn). — [arXiv v4](https://arxiv.org/html/2511.08462v4); venue from [search result](https://arxiv.org/html/2511.08462v2)
- Loop: agent proposes a query; a CodeQL validator runs it on the vulnerable and the patched version; it reports compile results, match counts on both versions, recall, counterexample traces and templated next-step hints. Up to 10 outer iterations, 50 agent turns each. — [arXiv v4](https://arxiv.org/html/2511.08462v4)
- Tools: CodeQL Language Server through a custom MCP server (complete, hover, definition, references, diagnostics, format), and a vector DB with CWE definitions, CodeQL API docs, sample queries and AST snippets. The first prompt includes a query skeleton. — [arXiv v4](https://arxiv.org/html/2511.08462v4)
- Results (176 CVEs, CWE-Bench-Java, Claude Code with Sonnet 4): 100% compile rate, 94/176 = 53.4% success (query fires on vulnerable version, silent on fixed version). On 130 shared CVEs: F1 0.700 vs IRIS 0.048 and CodeQL 0.073; recall 80.0% vs 35.4% and 20.0%. — [arXiv v4](https://arxiv.org/html/2511.08462v4)
- Ablation (20 CVEs): full 55% success; without LSP 25%; without docs/reference retrieval 20%; without AST cache 25%; Claude Code with no tools 10%. — [arXiv v4](https://arxiv.org/html/2511.08462v4)
- Other agents with the QLCoder loop (20 CVEs from 2025): Claude Code success 10% to 35%; Codex GPT-5 medium compile 0% to 55%, success 0% to 20%; Gemini CLI 2.5 Pro compile 35% to 75%, success stayed 0%. Cost about $2.90 and about 1 hour per query. — [arXiv v4](https://arxiv.org/html/2511.08462v4)
- Data-leak check: pre-2025 CVEs 57.7% success vs 2025 CVEs 46.2%. — [arXiv v4](https://arxiv.org/html/2511.08462v4)

#### IRIS (ICLR 2025): LLM infers taint specs that plug into fixed CodeQL queries
- "IRIS: LLM-Assisted Static Analysis for Detecting Security Vulnerabilities", Ziyang Li, Saikat Dutta, Mayur Naik. The LLM infers taint source/sink specifications for CodeQL and does contextual triage; it does not write whole queries. — [ICLR 2025 proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/582d4e27fa24168f3af1f4582655034b-Abstract-Conference.html)
- On CWE-Bench-Java (120 vulns): CodeQL found 27; IRIS + GPT-4 found 55 (+28), with average false discovery rate 84.82% (5.21 points lower than CodeQL); 4 previously unknown vulns in 30 projects. arXiv v1 had reported 69, so the counts differ by version. — [ICLR 2025 proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/582d4e27fa24168f3af1f4582655034b-Abstract-Conference.html); [arXiv v1](https://arxiv.org/html/2405.17238v1)

#### QLPro (arXiv 2506.23644, June 2025): multi-role CodeQL query writing
- One LLM instance writes the query, one compiles and runs it, one repairs compile errors. Syntax correctness rose from 70.01% (single instance) to 90.90% (collaborating instances). On a 62-vuln Java set (JavaTest), CodeQL found 24, QLPro 41. — [QLPro arXiv](https://arxiv.org/html/2506.23644v3); [search summary](https://www.alphaxiv.org/overview/2506.23644)

#### MoCQ (arXiv 2504.16057): LLM-generated Joern/CodeQL queries with a symbolic validator
- Before generation, MoCQ extracts the query-language spec from tool docs and implementations and keeps a core DSL subset "so the LLM isn't overwhelmed". A validator runs each query and reports syntax/semantic errors for revision. v3 abstract: 12 vulnerability types, 4 languages, 46 new patterns, precision/recall comparable to expert-written queries. — [arXiv 2504.16057](https://arxiv.org/html/2504.16057v3)

#### LLMSA / NESA (arXiv 2412.14399; FSE 2026)
- Users write an analysis in a policy language (restricted Datalog in the NESA version); syntactic sub-problems go to parsing-based analysis and semantic sub-problems to the LLM. On customized taint detection (TaintBench): precision 66.27%, recall 78.57%, F1 0.72, 0.20 F1 above an industrial tool; 13 real memory-leak bugs fixed. — [arXiv 2412.14399](https://arxiv.org/pdf/2412.14399); [FSE 2026 listing](https://conf.researchr.org/details/fse-2026/fse-2026-research-papers/103/NESA-Relational-Neuro-Symbolic-Static-Program-Analysis)

#### Semgrep rule generation
- Autogrep (Lambda Security, Feb 2025): LLM (DeepSeek Chat) turns vulnerability patches into Semgrep rules; each rule must fire on the vulnerable parent commit and not on the fixed commit. 39,931 patches gave 3,591 valid rules (8.99%); filtering removed 386 duplicates, 5 trivial and 2,555 "overly specific" rules (71.15%), leaving 645 rules in 20 languages. — [Security Boulevard / Lambda Security](https://securityboulevard.com/2025/02/autogrep-automated-generation-and-filtering-of-semgrep-rules-from-vulnerability-patches/)
- RuleLLM (arXiv 2504.17198, 2025): generates YARA and Semgrep rules from malicious packages in three stages (crafting, refining, aligning); 763 rules (311 Semgrep); 85.2% precision, 91.8% recall on 1,633 malicious packages. — [arXiv 2504.17198](https://arxiv.org/abs/2504.17198)
- SemOpt (arXiv 2510.16384): mines optimization examples from commits, clusters them by strategy, and generates Semgrep rules per cluster; evaluated on a 151-problem C/C++ benchmark. — [arXiv 2510.16384](https://arxiv.org/html/2510.16384v1)
- Semgrep Assistant (vendor): the 2024 GA blog says AI rule writing (beta) takes one "bad code" example, one "good code" example and a description; current docs say only an English prompt is required. The two sources disagree on whether examples are required. No accuracy numbers are published. — [Semgrep GA blog 2024](https://ai.semgrep.dev/blog/2024/assistant-ga-launch); [Semgrep Assistant docs](https://semgrep.dev/docs/semgrep-assistant/overview)
- Semgrep 2023 blog: rule syntax is simpler than a full language, so LLMs handle it well; "even if generated rules only get people halfway there", that has value. — [Semgrep blog 2023](https://semgrep.dev/blog/2023/using-ai-to-write-secure-code-with-semgrep)
- Trail of Bits `semgrep-rule-creator` Claude Code skill: a test-first workflow (analyze problem, write tests first, inspect AST, build patterns, validate with `semgrep --test`, optimize). It requires 100% test pass, includes "safe" cases to catch false positives, and outputs a YAML rule plus a test file with `ruleid:` and `ok:` annotations. — [Mintlify docs page](https://mintlify.com/trailofbits/skills/plugins/semgrep-rule-creator); [skills.sh listing](https://www.skills.sh/trailofbits/skills/semgrep-rule-creator)

#### Expressiveness limits of the target tool (relevant to the "prime length" failure)
- Semgrep `metavariable-comparison` supports only literals, `not/or/and`, `+ - * / %`, comparisons, `in/not in`, and the functions `int()`, `str()`, `today()`, `strptime()`, `re.match()`, `lower()`, `upper()`. No `len()`, user-defined functions or loops are documented. `%` supports fixed divisibility checks. `metavariable-regex` uses PCRE2 and is left-anchored. — [Semgrep rule syntax docs](https://docs.semgrep.dev/writing-rules/rule-syntax)
- Ruff has no plugin system for user-written lint rules; it re-implements popular Flake8 plugins in Rust (from a mirror of Ruff's FAQ, undated). — [Ruff FAQ mirror](https://git.joshthomas.dev/mirrors/ruff/src/commit/b47f85eb697265364da2c2a1d2b5c3e13ba4e93a/docs/faq.md)

#### ESLint, tree-sitter, style-guide linters
- ESLint: no peer-reviewed study found. Evidence is practitioner posts (e.g., ChatGPT writes a working ESLint rule with selector and visitor) and third-party "ESLint Custom Rule Generator" skills without accuracy data. — [Brinqa blog](https://www.brinqa.com/blog/chatgpt-the-eslint-rule-maker); [skills.sh listing](https://skills.sh/agentskillexchange/skills/eslint-custom-rule-generator/security/agent-trust-hub)
- Tree-sitter: no paper on LLM synthesis of tree-sitter queries found. tree-sitter-mcp exposes build/adapt/run query tools and tells the LLM to validate a query string before running it. — [tree-sitter-mcp skill](https://lmstudio.ai/hoonowng/tree-sitter-mcp/files/skills/tree-sitter.md)
- Checkstyle+ (arXiv 2510.23068, Oct 2025, Ella Dodor and Cristina V. Lopes, UC Irvine): hybrid Checkstyle + LLM module for 9 Google Java style rules (Javadoc fragments, comment format, naming of classes, methods, constants, fields, parameters, locals, type variables); evaluated on 380 Java files from Codeforces; beats plain Checkstyle on these "semantically nuanced" rules. Repo: ellacodee/CheckstylePlus. — [arXiv 2510.23068](https://arxiv.org/html/2510.23068v1)
- LintCFG, "Still Manual? Automated Linter Configuration via DSL-Based LLM Compilation of Coding Standards" (arXiv 2602.07783, Feb 2026, Zejun Zhang et al.; FSE 2026): see Q4. — [arXiv 2602.07783](https://arxiv.org/abs/2602.07783)
- Code transformation rule synthesis (arXiv 2609.03592, ASE '26, Allain, Blot, Khelladi, Acher): LLM gets a before/after diff and 8 example rules, and writes Comby, ast-grep or GritQL rules; no feedback loop. Failures: DSL syntax (comments inside rules, missing ast-grep separators, invalid multi-node patterns), over- and under-generalization. Correctness (exact/AST match) e.g. 67.5% (GPT-oss-120B) and 63.4% (GPT-5.4) on API-misuse with Comby+RAG; Llama3.1-8B often below 30%. RAG sometimes hurt (retrieved examples were biased to Python). — [arXiv 2609.03592](https://arxiv.org/html/2609.03592)

### Inferences
- The scaffolds that raised success are: (a) a bad/good oracle run by a real tool; (b) compiler/LSP/docs access (QLCoder's ablation shows LSP and docs each worth about 30 points of success); (c) a fixed template plus a small, documented helper API (KNighter's 9 utility functions; IRIS restricts the LLM to taint specs). The human expert's "tested toolbox" matches (c).
- The observed Haiku failures map to known failure classes: wrong tool for the predicate (Semgrep cannot compute length or primality, per its docs), incomplete coverage of syntactic forms (function-name regex misses arrow functions and methods, which a bad-version fixture would expose), and over-inclusion of targets (a must-pass fixture like `config.json` would expose it).
- Autogrep's 71% "overly specific" rate and the transformation-rule over/under-generalization show that one example pair is not enough to prevent overfitting; held-out fixtures are needed.
- An expressiveness check (can this tool express this predicate?) should come before the enforcer choice. For arithmetic predicates on names (prime length, odd length), the enforcer should be a script over an AST parser, not Semgrep or Ruff.

### Gaps
- No peer-reviewed study on LLM-written ESLint or Ruff-plugin rules, and no study on LLM tree-sitter query synthesis, was found.
- No published accuracy numbers for Semgrep Assistant rule generation.
- QLCoder's token figures look inconsistent in the paper (per the fetch summary); not verified.
- The Ruff FAQ text came from an undated mirror, not the official docs site.

## Q2. NL to policy/spec (Rego, Cedar, LTL, program specs) and how output is validated

### Takeaway
Policy work in 2026 converges on: extract a structured intermediate form from the NL, validate it against a schema, generate code, then lint, compile and run positive and negative tests (Rego), or check against a reviewed target with a verifier (Cedar). Structured decomposition tripled end-to-end Rego correctness (50.3% vs 15.3%). For specs, verifier acceptance is the usual metric, but several papers warn that "verifies" does not mean "correct".

### Cited Findings

#### Rego / OPA
- Prose2Policy (P2P), Vatsal Gupta and Darshan Sreenivasamurthy (Apple), arXiv:2603.15799, 16 Mar 2026. Pipeline: policy detection and segmentation; extraction of decision, subject, action, resource, condition, purpose (DSARCP) as JSON; schema validation against organization JSON schemas (stops and notifies if subject/action/resource missing); deny-by-default Rego generation; Regal linting; OPA compile; generated positive/negative unit tests run with `opa test`. — [arXiv 2603.15799](https://arxiv.org/html/2603.15799v1)
- P2P results on ACRE (485 statements, 389 accepted as policies): compile rate 95.3% (371/389); LLM-generated tests: positive pass 82.2% (305/371), negative pass 98.9% (367/371); rule-based tests: 62.1% and 97.1%. No single-shot baseline in this paper. — [arXiv 2603.15799](https://arxiv.org/html/2603.15799v1)
- "Structured Decomposition for Reliable LLM-Generated Access Control Policies", same authors, arXiv:2609.24036, 21 Sep 2026. On 372 statements vs a single-prompt baseline: end-to-end correctness 50.3% vs 15.3%; correct deny semantics 87.5% vs 37.5%; ownership conditions 100% vs 40%; status-qualified conditions 100% vs 55.6%. "Correct" = compiles, passes lint, passes positive and negative tests. — [arXiv abs 2609.24036](https://arxiv.org/abs/2609.24036)
- Smaller works: a Politecnico di Milano thesis uses LLMs to generate test inputs for OPA policies; a TUM 2024 thesis generates Rego from role descriptions. — [PoliMi thesis](https://www.politesi.polimi.it/handle/10589/252309); [TUM](https://sec.in.tum.de/i20/student-work/applying-nlp-for-ac-policy-generation-from-responsibility-definitions)

#### Cedar
- AutoCedar, Adarsh Vatsa, Sachi Shome, Yingming Zhou, William Eiers (Stevens Institute of Technology), arXiv:2607.03656, 4 Jul 2026. NL requirements are split into small "intent atoms" (reviewable claims about vocabulary and behavior); atoms get mechanical validation and human intent review; then the model synthesizes Cedar policies, and each verifier failure becomes a repair signal (broaden, narrow, restructure) without changing the target. Converges on all 221 tasks of the new CedarBench. — [alphaXiv abs](https://www.alphaxiv.org/abs/2607.03656); [arXiv PDF](https://arxiv.org/pdf/2607.03656)
- AutoCedar cites a round-trip-generation study: semantic equivalence to ground-truth policies was 45.8% for non-reasoning models vs 93.7% for reasoning models. — [alphaXiv abs](https://www.alphaxiv.org/abs/2607.03656)
- Permit.io describes the same generate, verify, feedback loop and argues for reviewable evidence packages so owners approve semantics, not formatting. — [Permit.io blog](https://www.permit.io/blog/can-ai-generate-authorization-policy-safely)
- (Borderline, out of scope: arXiv 2606.26649 autoformalizes agent prompts/tool docs into Cedar with a generator-critic loop.) — [emergentmind](https://www.emergentmind.com/papers/2606.26649)

#### LTL / temporal logic
- nl2spec (CAV 2023, foundational; Cosler, Hahn, Mendoza, Schmitt, Trippel): decomposes NL into editable sub-translations with confidence scores. — [CAV 2023 PDF](https://trippel-lab.stanford.edu/pubs/cosler_CAV23.pdf)
- ConformalNL2LTL (arXiv 2504.21022, 2025): in its baseline table, nl2spec reaches 73.16% translation success vs 82.87% for Lang2LTL (few-shot) and 87.4% for an uncertainty-agnostic ConformalNL2LTL variant; the method adds conformal-prediction correctness guarantees. — [arXiv 2504.21022](https://arxiv.org/pdf/2504.21022)
- NL2TL (EMNLP 2023, foundational, MIT): 28K NL-TL pairs; fine-tuned T5 on "lifted" text (atomic propositions abstracted) reaches >95% accuracy with <10% of training data. — [arXiv 2305.07766](https://arxiv.org/html/2305.07766v2)
- arXiv 2507.00877 notes that NL-to-TL systems reach near-perfect accuracy on existing benchmarks, but the benchmarks ignore grounding of atomic propositions in new environments. — [arXiv 2507.00877](https://arxiv.org/pdf/2507.00877)

#### Program specs and invariants
- SpecGen (arXiv 2401.08807): phase 1 feeds verifier failures back to the LLM (up to 10 rounds); phase 2 mutates near-miss specs and picks verifiable ones. Verifiable specs for 279/385 programs vs Daikon 72, Houdini 98, conversational 218, AutoSpec 247. Verifier calls per run: conversational 7.07, AutoSpec 16.19, SpecGen 15.51. — [arXiv 2401.08807](https://arxiv.org/html/2401.08807v5)
- A 2026 paper (arXiv 2602.13851) argues that approaches rely on verifier acceptance as the main quality measure, but verification success does not mean the spec is correct or complete. — [arXiv 2602.13851](https://arxiv.org/html/2602.13851)

### Inferences
- The Rego and Cedar pipelines are the closest analogue to CLAUDE.md enforcement: first a structured extraction (DSARCP JSON, intent atoms), then a deterministic schema check, then code, then executable positive/negative tests. The 3.3x gain is the clearest quantitative case for this design.
- Negative tests pass much more often than positive tests (98.9% vs 82.2% in P2P). This suggests that generated enforcers tend to fail by missing violations (false negatives), which matches the project's 0/10 function-name failure.
- Verifier-only acceptance can certify a wrong target (SpecGen caveat, AutoCedar's human review step). For CLAUDE.md rules, the fixtures that define "correct" should be reviewed or generated by a separate step, not by the same agent that writes the checker.

### Gaps
- Models used in the two Apple Rego papers are not stated in the pages read.
- AutoCedar's iteration counts and no-verifier baselines were not available in the abstract page.
- nl2spec's own headline accuracy (from its CAV paper) was not retrieved.
- AutoSpec's own venue and headline number were not verified from a primary source.

## Q3. Example-driven synthesis: do must-pass and must-fail examples improve correctness?

### Takeaway
Yes, as a verification oracle the evidence is strong: every top checker system uses a "fires on bad, silent on good" test, and test-driven code generation shows large gains (TiCoder pass@1 48.39% to 85.48%; AlphaCodium pass@5 19% to 44%). No paper isolates the effect of "2-3 examples per rule" for linter rules, and one example pair alone overfits (Autogrep discarded 71% of rules as overly specific).

### Cited Findings
- KNighter uses the bug-fix pair as a must-fire (buggy) and must-not-fire (patched) oracle; 39/61 patches yield valid checkers. — [arXiv 2503.09002v3](https://arxiv.org/html/2503.09002v3)
- QLCoder uses vulnerable/fixed versions as the success predicate and feeds counterexample traces back; 53.4% success vs 10% for the agent without the loop and tools. — [arXiv 2511.08462v4](https://arxiv.org/html/2511.08462v4)
- Autogrep: patch-pair validation keeps only 8.99% of rules; of these, 71.15% were then removed as overly specific by an LLM quality review. — [Security Boulevard](https://securityboulevard.com/2025/02/autogrep-automated-generation-and-filtering-of-semgrep-rules-from-vulnerability-patches/)
- Prose2Policy runs generated positive and negative tests; LLM-generated tests pass 82.2% (positive) and 98.9% (negative) of accepted policies. — [arXiv 2603.15799](https://arxiv.org/html/2603.15799v1)
- Semgrep Assistant's AI rule writer (2024 beta) asked for one bad and one good code example plus a description. — [Semgrep GA blog](https://ai.semgrep.dev/blog/2024/assistant-ga-launch)
- Trail of Bits skill: tests first, `semgrep --test` with `ruleid:` and `ok:` annotations, 100% pass required, explicit "safe" cases for false positives. — [Mintlify](https://mintlify.com/trailofbits/skills/plugins/semgrep-rule-creator)
- TiCoder (foundational; arXiv 2208.05950, Microsoft Research): the system generates tests at points of ambiguity and asks the user to approve or reject; Codex on MBPP pass@1 rose from 48.39% to 70.49% with one query and to 85.48% with up to 5. The TSE 2024 version (arXiv 2404.10100) reports +45.97% absolute pass@1 on average across 4 LLMs and 2 datasets within 5 interactions. — [arXiv 2208.05950](https://arxiv.org/pdf/2208.05950); [arXiv 2404.10100](https://arxiv.org/abs/2404.10100v2)
- AlphaCodium (foundational; arXiv 2401.08500, CodiumAI, Jan 2024): test-driven flow that iterates on public tests and AI-generated tests; GPT-4 pass@5 on CodeContests validation rose from 19% (single tuned prompt) to 44%. — [arXiv 2401.08500](https://www.arxiv.org/pdf/2401.08500); [Qodo blog](https://qodo.ai/blog/qodoflow-state-of-the-art-code-generation-for-code-contests)
- Transformation-rule synthesis from a single before/after diff (no feedback) shows over- and under-generalization as main failure modes. — [arXiv 2609.03592](https://arxiv.org/html/2609.03592)

### Inferences
- For CLAUDE.md rules, the cheap analogue of KNighter's oracle is a per-rule fixture set: files that must be flagged and files that must pass, with a KNighter-style accept rule (all must-fail flagged, zero must-pass flagged). The fixtures should cover syntactic variants on purpose (JS `function`, arrow function, class method; Python `def`, `async def`, nested def), and target-scope traps (a `.json`, `.yaml`, `.html` file that must not be treated as code).
- Examples help most as tests the agent must run, not as prompt text only. The evidence (QLCoder, AlphaCodium) is for executable feedback loops.
- To limit overfitting, keep some fixtures hidden from the writing agent and use them for acceptance (an inference from the Autogrep overfit rate; not tested in these papers).

### Gaps
- No study measures how many must-pass/must-fail examples per rule are needed for linter or style rules, or compares 2-3 examples vs none for checker correctness.
- No study found on LLM-generated tests for style-rule checkers specifically.

## Q4. Constrained decoding / typed IR vs raw tool config or scripts

### Takeaway
The best direct evidence favors a typed intermediate form compiled by deterministic code: Rego correctness rose from 15.3% (single prompt) to 50.3% (structured decomposition), and LintCFG's DSL route beat baselines by over 100% in precision for Checkstyle configs. Systems that restrict the LLM to filling slots in a fixed query (IRIS) or to a DSL subset (MoCQ, NESA) also do well. One caveat: hard format constraints can hurt reasoning, so the free-text reasoning should come before the structured fields.

### Cited Findings
- Structured decomposition (NL to DSARCP JSON, schema check, then Rego) vs single-prompt Rego: 50.3% vs 15.3% end-to-end correctness on 372 statements. — [arXiv 2609.24036](https://arxiv.org/abs/2609.24036)
- LintCFG (arXiv 2602.07783, FSE 2026; Zejun Zhang, Yixin Gan, Zhenchang Xing, Tian Zhang, Yi Li, Xiwei Xu, Qinghua Lu, Liming Zhu): parses NL coding standards into a tool-agnostic DSL, matches them to DSL "configuration instructions" (config names, options, values) mined from linter docs, checks consistency, then generates linter-specific configs (Checkstyle main; ESLint for generality). DSL representation >90% precision and recall; fine-grained Checkstyle config generation accuracy/precision/recall/F1 near 70%; precision over baselines improved by over 100%. — [arXiv 2602.07783](https://arxiv.org/abs/2602.07783); [ResearchGate](https://www.researchgate.net/publication/400603359_Still_Manual_Automated_Linter_Configuration_via_DSL-Based_LLM_Compilation_of_Coding_Standards)
- IRIS keeps the CodeQL query fixed and has the LLM infer only taint specs (sources/sinks). — [ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/582d4e27fa24168f3af1f4582655034b-Abstract-Conference.html)
- MoCQ extracts a core subset of the query DSL from docs and implementation before generation. — [arXiv 2504.16057](https://arxiv.org/html/2504.16057v3)
- LLMSA/NESA decompose analyses in a restricted-Datalog policy language; parser handles syntactic facts, LLM handles semantic ones. — [arXiv 2412.14399](https://arxiv.org/pdf/2412.14399)
- KNighter: multi-stage (analysis, plan, then code from a template) gave 12 valid checkers vs 8 for single-stage, with fewer syntax errors (28 vs 52). — [arXiv 2503.09002v3](https://arxiv.org/html/2503.09002v3)
- Grammar Prompting (foundational; NeurIPS 2023; Bailin Wang, Zi Wang, Xuezhi Wang, Yuan Cao, Rif A. Saurous, Yoon Kim): the model first predicts a small BNF grammar for the input, then generates output that follows it; competitive on SMCalFlow, Overnight, GeoQuery, PDDL and SMILES. — [NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/cd40d0d65bfebb894ccc9ea822b47fa8-Abstract-Conference.html)
- "Let Me Speak Freely?" (Tam et al., EMNLP 2024 Industry, arXiv 2408.02442): format restrictions (JSON mode, format instructions) cause significant drops on reasoning tasks, with stricter constraints causing larger drops; JSON mode is competitive on classification; a failure case put the "answer" key before the "reason" key. — [arXiv 2408.02442](https://arxiv.org/pdf/2408.02442)
- DSL syntax errors were a main failure source when LLMs wrote raw Comby/ast-grep/GritQL rules (comments in rules, missing separators, invalid multi-node patterns). — [arXiv 2609.03592](https://arxiv.org/html/2609.03592)
- Raw-config generation is limited by tool expressiveness: Semgrep's comparison language has no `len()` or loops; Ruff has no custom-rule plugins. — [Semgrep docs](https://docs.semgrep.dev/writing-rules/rule-syntax); [Ruff FAQ mirror](https://git.joshthomas.dev/mirrors/ruff/src/commit/b47f85eb697265364da2c2a1d2b5c3e13ba4e93a/docs/faq.md)

### Inferences
- A small typed IR per rule (for example: target kind, node kinds to enumerate, file-extension set, property, comparator, value) that a tested compiler turns into a Semgrep rule, an ESLint selector, or a tree-sitter-based script would remove three of the observed failures: the compiler, not the agent, owns the list of function-like node kinds; the "code file" extension set is a fixed enum; and predicates that Semgrep cannot express (length, primality) route to the script backend at compile time.
- Classification-like steps (pick the enforcer, target, trigger) fit constrained JSON well (Tam et al. find JSON mode competitive on classification). Steps needing reasoning should let the model write reasoning first, then fill the schema.
- The IR does not remove the need for fixtures: Rego correctness with the IR was still only 50.3%, so the test loop stays necessary.

### Gaps
- LintCFG's baselines (whether they include direct LLM config writing) and models were not visible on the abstract page.
- No study compares, on the same lint rules, (a) LLM writes raw Semgrep/ESLint config, (b) LLM writes a Python script, (c) LLM fills a typed IR compiled by deterministic code.
- No study found on grammar-constrained decoding for Semgrep/ESLint/tree-sitter output specifically.

## Q5. Relevant GitHub projects (stars and last push, from the GitHub API on 2026-10-18)

### Takeaway
The most-used project relevant to this toolchain is Trail of Bits' Claude Code skills repo (7,632 stars, active), which ships a test-first Semgrep rule creator. Research repos (KNighter, IRIS) are smaller but public; Cedar synthesis code is new and small.

### Cited Findings
- trailofbits/skills: 7,632 stars, last push 2026-10-15; Claude Code skills incl. `semgrep-rule-creator` and `semgrep-rule-variant-creator`. — [GitHub](https://github.com/trailofbits/skills)
- semgrep/semgrep: 17,117 stars, last push 2026-10-16. semgrep/semgrep-rules (community rules, useful as exemplars): 1,276 stars, last push 2026-10-16. — [semgrep](https://github.com/semgrep/semgrep); [semgrep-rules](https://github.com/semgrep/semgrep-rules)
- iris-sast/iris: 444 stars, last push 2026-07-02. — [GitHub](https://github.com/iris-sast/iris)
- ise-uiuc/KNighter: 190 stars, last push 2025-10-26. — [GitHub](https://github.com/ise-uiuc/KNighter)
- IBM/nl2ltl: 102 stars, last push 2025-09-17. — [GitHub](https://github.com/IBM/nl2ltl)
- realChrisHahn2/nl2spec: 66 stars, last push 2024-02-13 (foundational, inactive). — [GitHub](https://github.com/realChrisHahn2/nl2spec)
- neselab/cedar-synthesis-engine (AutoCedar): 3 stars, last push 2026-09-08; "human-in-the-loop Cedar policy synthesis ... with symbolic verification". — [GitHub](https://github.com/neselab/cedar-synthesis-engine)
- Codium-ai/AlphaCodium: 3,966 stars, last push 2024-11-25 (foundational). — [GitHub](https://github.com/Codium-ai/AlphaCodium)
- ellacodee/CheckstylePlus (Checkstyle+ research code; star count not retrieved). — [arXiv 2510.23068](https://arxiv.org/html/2510.23068v1)
- tree-sitter-mcp (LM Studio hub; build/adapt/run tree-sitter query tools). — [tree-sitter-mcp](https://lmstudio.ai/hoonowng/tree-sitter-mcp/files/skills/tree-sitter.md)

### Inferences
- The Trail of Bits skill is the most direct, ready-made template for a "fixtures first, then rule, then `semgrep --test`" step inside Claude Code; its structure could be copied for ESLint (RuleTester) and tree-sitter scripts.

### Gaps
- Star counts for QLCoder, LintCFG, Autogrep, CheckstylePlus and grammar-prompting repos were not retrieved (repos not found or not linked in the pages read).
