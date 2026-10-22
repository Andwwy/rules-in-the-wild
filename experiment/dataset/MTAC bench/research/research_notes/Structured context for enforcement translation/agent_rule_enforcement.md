# Agent rule enforcement: NL-policy compilers, coding-agent hook ecosystems, and instruction-file compliance studies

Research date: 2026-10-18. Scope: (1) research systems that turn natural-language (NL) rules into enforced agent policies; (2) the 2025–2026 hook and rule tooling for Claude Code, Codex and Cursor; (3) empirical studies of instruction-file compliance and of hooks vs. prompts. Out of scope (other researchers cover it): documentation RAG, NL→Semgrep/CodeQL rule synthesis, skill libraries, environment-setup agents.

## 1. Agent policy compilers and runtime enforcement: input, IR, rule→check method, verification, results, overhead

### Takeaway
Most systems split the work in two. One part is a fixed, tested enforcement engine (DSL interpreter, Datalog/SMT engine, workflow verifier, or tool-call guard runtime). The other part is the rule-specific content (predicates, rules, guard bodies, graph nodes), which an LLM writes or a person writes. The best-reported gains come when the LLM writes into a typed skeleton and the output passes a validation loop (tests, schema checks, solver, or critic). Free-form NL→code with no check is rare, and the authors who try it report overfitting and missed cases.

### Cited Findings

**AgentSpec (Wang, Poskitt, Sun; Singapore Management Univ.; arXiv 2503.18666, Mar 2025, v3 Jul 2025; ICSE 2026, Rio de Janeiro, Apr 12–18 2026)**
- Input: rules written in a small DSL. Each rule is `rule <Id>` / `trigger <Event>` / zero or more `check <Pred>` (combined with AND) / one or more `enforce <Enforce>` / `end`. — [arXiv HTML v3](https://arxiv.org/html/2503.18666v3)
- Triggers: `state_change`, `before_action`, `agent_finish`, or domain events (for example `PythonREPL`). Enforcements: `user_inspection`, `llm_self_examine`, `invoke_action(params)`, `stop`. — [arXiv HTML v3](https://arxiv.org/html/2503.18666v3)
- Predicates are Python Boolean functions written by developers (for example `is_destructive_cmd`, `request_untrusted_source`). Users can also supply them, or an LLM can generate them. The paper does not give the size of the predicate library. — [arXiv HTML v3](https://arxiv.org/html/2503.18666v3)
- LLM rule generation: OpenAI o1, prompted with an agent and tool description, 3 example rules with predicate functions, and optional in-context examples. Code agent: 750 scenarios, 75 examples (10%), 25 rules, 87.26% of risky code enforced. Embodied: 95.56% (the abstract calls it precision, with 70.96% recall). AV, zero-shot: 5/8 (62.5%). — [arXiv HTML v3](https://arxiv.org/html/2503.18666v3); [arXiv abs](https://arxiv.org/pdf/2503.18666)
- Code-agent setting: RedCode-Exec (25 risk categories × 30 cases) on CodeAct. Abstract claims >90% of unsafe code executions prevented. A tally of Table 3 by the fetch model gives 333 flagged of 422 (about 79%), so the 90% definition is unclear. — [arXiv HTML v3](https://arxiv.org/html/2503.18666v3)
- Overhead: parse about 1.42 ms; predicate evaluation about 2.83 ms (code) and 1.11 ms (embodied). Baseline agent runtimes are about 25.4 s and 9.82 s. — [arXiv HTML v3](https://arxiv.org/html/2503.18666v3)
- Stated limits: LLM-generated rules overfit to the given examples, miss unlisted sensitive files, or are too rigid (for example "ban all pouring"). Code-agent predicates check source text with no data-flow analysis. Embodied safe-task completion fell from 58.62% to 54.26% with enforcement. — [arXiv HTML v3](https://arxiv.org/html/2503.18666v3)

**ShieldAgent (Zhaorun Chen, Mintong Kang, Bo Li; ICML 2025, PMLR 267:8313–8344; arXiv 2503.22738)**
- It extracts rules from policy documents, refines them, and groups them by action type into probabilistic "rule circuits". At inference it checks only the circuits tied to the invoked action. It then makes a shielding plan and runs formal verification code. — [arXiv HTML v2](https://arxiv.org/html/2503.22738v2); [mlanthology](https://mlanthology.org/icml/2025/chen2025icml-shieldagent)
- ShieldAgent-Bench: 3K safety-related (instruction, trajectory) pairs. Reported 90.1% recall, 64.7% fewer API queries, 58.2% lower inference time vs. prior methods. — [arXiv HTML v1](https://arxiv.org/html/2503.22738v1)

**GuardAgent (Zhen Xiang, …, Dawn Song, Bo Li; arXiv 2406.09187, v3 May 2025; older work, first posted Jun 2024)**
- Pipeline: an LLM writes a step-by-step plan from the guard request, the target-agent spec, and the agent I/O. It gets k demonstrations retrieved from a memory module by smallest Levenshtein distance. Then it turns the plan into guardrail code that may call only functions from an extendable toolbox. An engine runs the code; a debug step runs up to 3 times. — [arXiv HTML](https://arxiv.org/html/2406.09187)
- Label prediction accuracy (GPT-4 core): EICU-AC 98.7 (vs. 97.5 for a model-guarding-agent baseline), Mind2Web-SC 90.0 (vs. 82.5). Hard-coded safety rules: LPA 65.8–87.9 (EICU-AC) and 52.5–77.5 (Mind2Web-SC). LlamaGuard: about 50 (near chance). — [arXiv HTML](https://arxiv.org/html/2406.09187)

**Progent (UC Berkeley / UCSB / NUS; arXiv 2504.11703)**
- A DSL for least-privilege policies on tool calls: when a call is allowed and what fallback runs if not. An LLM can write the policies from the user query and update them during the run. The authors report attack success reduced to 0% on AgentDojo, ASB and AgentPoison while keeping utility. — [arXiv HTML v2](https://arxiv.org/html/2504.11703v2); [HF papers](https://huggingface.co/papers/2504.11703)

**CaMeL (Debenedetti, Shumailov, …, Carlini, Tramèr; arXiv 2503.18813, Mar 2025, v2 Jun 2025)**
- A system layer extracts control and data flow from the trusted query, so untrusted data cannot change program flow. Capabilities plus tool-call security policies block exfiltration. AgentDojo: 77% of tasks solved with provable security vs. 84% undefended. — [arXiv abs](https://arxiv.org/abs/2503.18813)

**Conseca (Lillian Tsai, Eugene Bagdasarian; Google; HotOS 2025; arXiv 2501.17070)**
- A policy generator writes a per-task policy from the user request, trusted context and tool docs. A deterministic enforcer checks each proposed action and returns a rationale on deny. The paper presents it as a first step; the search found no evaluation numbers. — [arXiv](https://arxiv.org/pdf/2501.17070); [Google Research](https://research.google/pubs/context-is-key-for-agent-security/)

**Agent-C, "Enforcing Temporal Constraints for LLM Agents" (Kamath, Zhang, Xu, Ugare, Singh, Misailovic; UIUC + Meta; arXiv 2512.23738; ICLR 2026)**
- Developers write rules in a DSL (predicates such as Before, After, Forall, Exists). The DSL compiles to first-order logic. SMT solving runs together with constrained decoding, so a non-compliant action is caught during token generation; it backtracks and samples a compliant one. Retail and airline tasks. — [arXiv](https://arxiv.org/abs/2512.23738v1); [ICLR 2026](https://iclr.cc/virtual/2026/10012627)
- Numbers differ between versions: arXiv reports Claude Sonnet 4.5 conformance 77.4% → 100%; the ICLR listing reports utility 66.1% → 69.3% for Sonnet 4.5. A 2026 survey notes the constraints are hand-written by domain experts. — [arXiv](https://arxiv.org/abs/2512.23738v1); [ICLR 2026](https://iclr.cc/virtual/2026/10012627); [OAE survey](https://www.oaepublish.com/articles/aiagent.2026.22)

**FORGE, "Formal Policy Enforcement for Agentic Systems" (Palumbo, Choudhary, Choi, Amir, Chalasani, Dillig, Jha; arXiv 2602.16708, Feb 2026, v4 12 Oct 2026; code sasy-labs/sasy)**
- Policies are Datalog (recursion, stratified negation, foreign functions), evaluated by Soufflé over an event graph (messages, tool calls, tool results; happens-before edges). Deny-overrides verdicts. An aspect weaver puts the monitor at LLM-call and tool-dispatch join points. A denied action returns a denial trace and structured feedback. — [arXiv HTML v4](https://arxiv.org/html/2602.16708v4)
- NL→Datalog can be done by an off-the-shelf LLM, but the paper says this step has no formal guarantee and needs coverage and faithfulness checks before deployment. — [arXiv HTML v4](https://arxiv.org/html/2602.16708v4)
- τ²-bench (Claude Opus 4.5 user sim; agents Opus 4.5, GPT-5.2, Gemini 3.1 Pro; 4 trials): pass^1 airline 74.7% → 81.5%, retail 86.3% → 87.4%; pass^4 airline 58.0% → 67.3%, retail 71.9% → 74.6%. Runtime airline 67.1 s → 70.7 s. Authorization latency 0.19 ms server / 0.72 ms client at 32 concurrent agents. — [arXiv HTML v4](https://arxiv.org/html/2602.16708v4)
- AgentDojo (GPT-4o, tool_knowledge attack, with built-in defense): no runtime defense ASR 14.1%, utility 83.7%; FORGE provenance policy ASR 0.9%, utility 62.5%; FORGE IFC policy ASR 0.6%, utility 33.2%. — [arXiv HTML v4](https://arxiv.org/html/2602.16708v4)
- Its comparison table says Progent, NeMo Guardrails, Invariant Guardrails, AgentSpec and ShieldAgent lack recursive queries, causal dependencies and multi-agent support; GuardAgent lacks deterministic enforcement. (This is the FORGE authors' own claim.) — [arXiv HTML v4](https://arxiv.org/html/2602.16708v4)

**ToolGuard, "Towards Enforcing Company Policy Adherence in Agentic Workflows" (Zwerdling, Boaz, Rabinovich, Uziel, Amid, Anaby-Tavor; IBM Research; EMNLP 2025 Industry, pp. 595–606; arXiv 2507.16459)**
- Build time, 3 steps: (1) an LLM Tool-Policy Mapper (multi-stage LangGraph reflection) maps policy fragments to tools and writes compliance/violation examples; (2) a policy-independent spec skeleton (types, tool signatures, empty guard stubs) is generated deterministically from the OpenAPI spec (>800 lines for Airlines); (3) an LLM fills the guard stubs with test-driven development, using the examples as tests plus pyright type-check feedback. — [arXiv HTML](https://arxiv.org/html/2507.16459v1)
- Run time: each guard runs before its tool call; a failing guard blocks and tells the agent which policy failed. — [arXiv HTML](https://arxiv.org/html/2507.16459v1)
- τ-bench Airlines (22 of 50 tasks where the user asks for a policy-violating action): baseline pass^1 0.450 / pass^10 0.227; reflection with the policy document or mapper output reached pass^10 0.273 at best; ToolGuards pass^1 0.685 / pass^10 0.500. Guard code from GPT-4.1 passed 0.82 of 61 hand-written unit tests with ground-truth mapping and 0.75 with automatic mapping. — [arXiv HTML](https://arxiv.org/html/2507.16459v1)
- Limits: guards only gate tool calls; they cannot catch a missing required call. Guard failures came from code hallucinations. Productized as the Langflow "Policies (Beta)" component (NL policy → generated, cached guard code). — [arXiv HTML](https://arxiv.org/html/2507.16459v1); [Langflow docs](https://docs.langflow.org/policies)

**PolicyGuide (Seongjae Kang, Taehyung Yu, Sung Ju Hwang; KAIST; arXiv 2608.19861, 20 Aug 2026)**
- Offline, GPT-5.4 compiles each domain's NL policy + tool specs into one workflow graph in 6 stages (extract tools and mutating actions; derive request types and subflows; review plan; generate and schema-validate subflows; connect to an intake spine; validate schema, tool coverage, reachability, pruning). Graphs were checked by hand against the policies. — [arXiv HTML](https://arxiv.org/html/2608.19861v1)
- Nodes are typed (agent action, user input, read-only tool call, tool authorization, decision, subflow). Each node names actor, expected action and a condition. Mutating tools are enabled only at authorization nodes. Code (not the model) holds state and tool gating. A verifier LLM runs at each user-turn boundary and after an intercepted mutating call, and returns step-specific remediation. — [arXiv HTML](https://arxiv.org/html/2608.19861v1)
- τ²-bench Pass^4 (GPT-5.4 agent): airline ReAct 0.460 / ToolGuard 0.520 / PolicyGuard 0.580 / PolicyGuide 0.620; retail 0.596 / – / 0.360 / 0.614; telecom 0.193 / – / 0.202 / 0.614. Telecom Pass^1 0.384 → 0.866. Cost about $0.40 per conversation for guide calls. — [arXiv HTML](https://arxiv.org/html/2608.19861v1)
- Ablation (telecom test split): ReAct 0.250; PolicyGuide-Raw (raw policy text instead of compiled graph) 0.350; PolicyGuide-Self 0.325; FlowAgent 0.350; PolicyGuard 0.325; full PolicyGuide 0.675. — [arXiv HTML](https://arxiv.org/html/2608.19861v1)
- It describes PolicyGuard (arXiv 2606.29225) as a per-tool checklist verifier for mutating calls (pass/block plus remediation) that does not track workflow position. — [arXiv HTML](https://arxiv.org/html/2608.19861v1); [PolicyGuard PDF](https://arxiv.org/pdf/2606.29225)

**VeriGuard (Google; arXiv 2510.05156, Oct 2025)**
- Offline: from the agent spec and an NL security request, it writes a policy function plus formal constraints, then loops on unit tests and formal verification (Nagini verifier); counterexamples drive refinement. Online: the verified policy is a runtime monitor that checks each proposed action. One search result says ACL 2026 acceptance (not confirmed from a primary page). — [arXiv](https://arxiv.org/abs/2510.05156); [Google Research](https://research.google/pubs/veriguard-enhancing-llm-agent-safety-via-verified-code-generation/)

**Other 2026 NL→enforcement papers (abstract-level only)**
- In-car verification harness (Bouchekir, Safin, Momcilovic; arXiv 2608.23282, 24 Aug 2026; CAR-bench Track 1): each NL policy is compiled once into typed, machine-checkable rules; a subset gets an executable form run by a deterministic obligation engine against live tool results and simulated post-write state. On violation it emits remedial tool calls with computed arguments, not NL reminders. 25 deterministic gates (identifier provenance, schema/enum validity, gather-before-act order, confirmation protocols) plus an LLM critic feed a bounded revision loop. — [arXiv abs](https://arxiv.org/abs/2608.23282)
- Autoformalization of Agent Instructions into Policy-as-Code (Mondl, Maisel, Brock; arXiv 2606.26649, Jun 2026; ICML 2026 AIWILD workshop): an LLM generator–critic loop turns agent prompts, MCP tool descriptions and policy docs into Cedar policies; on MedAgentBench it covers "substantially more" of the NL spec than prior hand-coded enforcement. No numbers in the abstract. — [arXiv abs](https://arxiv.org/abs/2606.26649)
- VIGIL (Ying Li, …, Yu Feng, Yuan Tian; arXiv 2606.26524, Jun 2026): policies from skill specs, operator constraints and global rules, over agent-tool events (temporal order, argument constraints, value flow), compiled to SMT over finite traces. Reports >95% recall and <10% false-positive rate on real agent runs (office, ops, engineering tasks). — [arXiv abs](https://arxiv.org/abs/2606.26524)
- Policy-as-Prompt (Kholkar, Ahuja; Pure Storage; arXiv 2509.23994; NeurIPS 2025 Regulatable ML workshop): builds a policy tree from PRDs, TDDs and code, then compiles it into prompt-based classifiers; a small LLM judges agent I/O at run time. Results stated qualitatively only. — [arXiv](https://arxiv.org/pdf/2509.23994)

**Guardrail toolkits**
- LlamaFirewall (Meta; arXiv 2505.03574, May 2025): PromptGuard 2 + AlignmentCheck (goal-hijack check on agent reasoning) + CodeShield (static analysis of generated code). AgentDojo ASR 17.6% → 1.75%; utility 47.7% → 42.7%. CodeShield 96% precision / 79% recall on a labeled set. — [arXiv](https://arxiv.org/pdf/2505.03574); [DeepLearning.AI](https://deeplearning.ai/the-batch/meta-releases-llamafirewall-an-open-source-defense-against-ai-hijacking/)
- Microsoft Agent Governance Toolkit (microsoft/agent-governance-toolkit; 6,439 stars, pushed 2026-10-18; "Public Preview", v4.1.0 Python distributions): YAML policies with expression conditions and actions such as `deny` / `require_approval`; diagram lists YAML/OPA/Cedar; a "stateless, deterministic, fail-closed" Rust policy engine; ships a Claude Code governance plugin and Codex CLI, Copilot CLI and OpenCode packages. No NL→policy compiler and no latency figures on the page. — [GitHub](https://github.com/microsoft/agent-governance-toolkit)
- Invariant Labs (ETH Zurich spin-off) Guardrails: contextual security rules enforced on agent systems, plus MCP scanning; Snyk acquired Invariant on 24 Jun 2025. Repo invariantlabs-ai/invariant: 472 stars, last push 2026-01-12. — [Snyk](https://snyk.io/jp/news/snyk-acquires-invariant-labs-to-accelerate-agentic-ai-security-innovation/); [SiliconANGLE](https://siliconangle.com/2025/06/24/snyk-acquires-invariant-labs-expand-ai-agent-security-capabilities/); GitHub API lookup 2026-10-18
- NeMo Guardrails (NVIDIA-NeMo/Guardrails): 7,323 stars, last push 2026-10-15. — GitHub API lookup 2026-10-18 ([repo](https://github.com/NVIDIA-NeMo/Guardrails))

**Policy-compliance benchmark**
- ST-WebAgentBench (IBM; arXiv 2410.06703; ICLR 2026): 222 tasks (GitLab, ShoppingAdmin, SuiteCRM) with 646 policy instances in 6 dimensions. Completion under Policy (CuP) counts only completions that respect all policies. Three open SOTA agents: completion 24.3% but CuP 15.0%. CuP falls from 18.2% with 1 active policy to 7.1% with ≥5. — [arXiv HTML v5](https://arxiv.org/html/2410.06703v5); [ICLR 2026](https://iclr.cc/virtual/2026/poster/10009904)

### Inferences
- Common shape across AgentSpec, ToolGuard, PolicyGuide, FORGE and the in-car harness: a fixed engine + typed slots + a validation loop. AgentSpec's (trigger, check, enforce) triple maps almost 1:1 to the project's arm-C route (trigger tree, target tree, enforcer tree). ToolGuard's deterministic "spec skeleton with empty guard stubs" is the closest analog to the human expert's "shared, tested runner + adapters".
- The user's arm-B failures (made-up hook event names, invalid hook schema, exit 1 instead of exit 2) are errors in the engine/wiring layer, not in rule logic. Every system above keeps that layer fixed and out of the LLM's hands. That suggests a better arm B/C: give the agent a fixed, pre-tested runner and ask it only to fill the per-rule predicate or pattern.
- Tool-call gates (ToolGuard, PreToolUse) cannot enforce "must do X" rules. ToolGuard says so directly. PolicyGuide and the in-car harness handle this with workflow position or with obligations that push remedial actions. In Claude Code terms, that maps to Stop hooks (exit 2 forces the agent to keep working) and PostToolUse feedback, not PreToolUse.
- Overheads for deterministic checks are small (ms level: AgentSpec, FORGE). LLM-in-the-loop checks cost more (PolicyGuide about $0.40 per conversation).

### Gaps
- No system above targets coding-agent repository rules (style, naming, file layout, response format) of the MTAC-IFBench kind. All target safety, privacy or business-workflow policies (RedCode, AgentDojo, τ-bench, CAR-bench, MedAgentBench).
- GuardAgent's venue: the arXiv page lists only the preprint (it is often cited as ICML 2025; not confirmed here). Progent's venue: not confirmed.
- NeMo Guardrails/Colang internals and Invariant's policy-language syntax were not re-checked in this pass (only repo metadata and press releases).
- PolicyGuard (2606.29225), the in-car harness (2608.23282) and the Cedar autoformalization paper (2606.26649) were read at abstract level only; their numbers are missing.
- "Microsoft agent-governance": the toolkit was found; no NL→policy compilation is documented for it.

## 2. Retrieval, verified predicate/template libraries, and action graphs: evidence that structure beats free-form LLM code

### Takeaway
Several systems use retrieval (GuardAgent's demo memory), fixed function or predicate libraries (GuardAgent toolbox, AgentSpec predicates, ToolGuard skeleton), or action/workflow graphs (PolicyGuide, ShieldAgent's action-grouped circuits, FORGE's event graph). The ablation evidence favors structure, but it is small and comes from non-coding domains. No study compares a fixed predicate library with free-form LLM hook code for coding-agent rules.

### Cited Findings
- Retrieval: GuardAgent retrieves k demonstrations by Levenshtein distance (k=1 EICU-AC, k=3 Mind2Web-SC). Using the least-similar demos instead (GPT-4): EICU-AC 98.7 → 98.1, Mind2Web-SC 90.0 → 84.0. — [arXiv HTML](https://arxiv.org/html/2406.09187)
- Function library: removing the required toolbox functions (GPT-4, EICU-AC) dropped label accuracy 98.7 → 90.8; executable rate before debugging dropped 100% → 90.8% (93.7% after debugging). — [arXiv HTML](https://arxiv.org/html/2406.09187)
- Without code instructions, GPT-4 wrote code-based guardrails for only 68.0% of EICU-AC examples (62% when databases were described in NL instead of a structured format). — [arXiv HTML](https://arxiv.org/html/2406.09187)
- Compiled graph vs. raw policy: PolicyGuide 0.675 vs. PolicyGuide-Raw 0.350 (telecom test split, same verifier, raw policy text instead of the compiled workflow graph). — [arXiv HTML](https://arxiv.org/html/2608.19861v1)
- Code guards vs. policy text in context: ToolGuard pass^10 0.500 vs. 0.273 for reflection with the policy document (τ-bench Airlines, 22-task violating subset). — [arXiv HTML](https://arxiv.org/html/2507.16459v1)
- Grouping by action type: ShieldAgent checks only rule circuits tied to the invoked action and reports 64.7% fewer API queries and 58.2% lower inference time. — [arXiv HTML v1](https://arxiv.org/html/2503.22738v1)
- Free-form LLM-written rules: AgentSpec's o1-generated rules overfit to examples, missed unlisted sensitive files, and were sometimes over-rigid; AV zero-shot rules were "oversimplified" and caused abrupt stops. — [arXiv HTML v3](https://arxiv.org/html/2503.18666v3)
- FORGE: LLM NL→Datalog translation "has no formal guarantee"; it needs coverage and faithfulness checks. — [arXiv HTML v4](https://arxiv.org/html/2602.16708v4)
- Verification loops used: ToolGuard (generated compliance/violation examples as unit tests, pyright, red-green-refactor) — [arXiv HTML](https://arxiv.org/html/2507.16459v1); VeriGuard (unit tests + Nagini formal verification + counterexample refinement) — [arXiv](https://arxiv.org/abs/2510.05156); PolicyGuide (schema, tool coverage, reachability validation) — [arXiv HTML](https://arxiv.org/html/2608.19861v1); Cedar autoformalization (generator–critic) — [arXiv](https://arxiv.org/abs/2606.26649); in-car harness (25 deterministic gates + LLM critic) — [arXiv](https://arxiv.org/abs/2608.23282).
- MTAC-IFBench itself uses a shared helper library when it writes checkers: each objective constraint gets a Python validation function (response + workspace path → Boolean) that "must use shared helpers" for word counts, sentence splitting and emoji detection. — [arXiv HTML](https://arxiv.org/html/2609.14992v1)

### Inferences
- For the project's RAG vs. "graph of concrete actions keyed by route" choice: the evidence leans toward the graph/skeleton option. GuardAgent's retrieval effect is small to moderate (−0.6 and −6.0 points when retrieval gets worse). Removing the function library or the compiled structure costs more (−7.9 points GuardAgent; PolicyGuide-Raw at about half of full PolicyGuide). This is indirect evidence from different tasks.
- MTAC-IFBench's own checker design (LLM writes a small function on top of shared helpers) is a ready template for the route-keyed library: the same helpers could back the hooks.
- A cheap self-test stage, as in ToolGuard, would have caught the arm-B wiring errors: for each rule, generate one violating and one compliant example, run the installed hook, and assert exit 2 / deny on the violating one.

### Gaps
- No head-to-head study found of "fixed, verified predicate library + LLM slot filling" vs. "LLM writes the whole hook/enforcer" for coding-agent instruction files.
- No published system found that uses RAG over a corpus of verified hook implementations for Claude Code.

## 3. Claude Code / Codex / Cursor hooks and rule-enforcement ecosystem (2025–2026)

### Takeaway
Hooks are now a standard feature in Claude Code and Codex CLI (same 3-level schema, exit 2 blocks). Cursor has hooks with patchy CLI coverage. The open-source scene has many hook collections and rule-sync tools. Only one tool converts NL rules into enforced hooks: Anthropic's official `hookify` plugin. It uses a fixed engine and a regex-based markdown rule template; it is not a general compiler. Claude Code's `/init` can also propose hooks. Exact hook semantics explain the arm-B "never blocked" result.

### Cited Findings

**Claude Code hook semantics (official docs, fetched 2026-10-18)**
- 33 events, including `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`, `Stop`, `SubagentStop`, `UserPromptSubmit`, `SessionStart`, `InstructionsLoaded`, `FileChanged`, `PreCompact`. — [Hooks reference](https://code.claude.com/docs/en/hooks)
- Exit 0 = success (JSON fields apply). Exit 2 = blocking error on events that can block; stderr is the reason. Any other code (for example 1) = non-blocking error; the action proceeds. The docs say: "If your hook is meant to enforce a policy, use `exit 2`." — [Hooks reference](https://code.claude.com/docs/en/hooks)
- JSON is parsed only when stdout is exactly one JSON object. With exit 2 + JSON, the fields cannot override the block. With another exit code + valid JSON, "the fields alone decide." — [Hooks reference](https://code.claude.com/docs/en/hooks)
- Decision fields differ by event. PreToolUse uses `hookSpecificOutput.permissionDecision` (`allow`/`deny`/`ask`/`defer`) + `permissionDecisionReason`. Top-level `decision: "block"` is documented for UserPromptSubmit, PostToolUse, PostToolUseFailure, PostToolBatch, Stop, SubagentStop, ConfigChange, PreCompact (not PreToolUse). — [Hooks reference](https://code.claude.com/docs/en/hooks)
- Per event: PreToolUse exit 2 blocks the call; Stop exit 2 "prevents Claude from stopping, continues the conversation"; PostToolUse exit 2 shows stderr to Claude but "the tool already ran"; PermissionRequest ignores exit 2. A timed-out command hook does not block unless `onFailure` is `"block"`. — [Hooks reference](https://code.claude.com/docs/en/hooks)
- Schema: `hooks → <Event> → [{matcher, hooks: [{type, if, command, timeout, …}]}]`. Handler types: `command`, `http`, `mcp_tool`, `prompt` (single-turn model decision as JSON; default timeout 30 s), `agent` (subagent with Read/Grep/Glob; experimental; 60 s). Command default timeout 600 s. — [Hooks reference](https://code.claude.com/docs/en/hooks)
- Managed settings: managed hooks cannot be removed by user/project/local settings; `disableAllHooks` outside managed settings cannot disable them; `allowManagedHooksOnly` blocks user, project, local and plugin hooks. — [Hooks reference](https://code.claude.com/docs/en/hooks)
- Memory docs: CLAUDE.md and auto memory are "context, not enforced configuration. To block an action regardless of what Claude decides, use a PreToolUse hook." CLAUDE.md is "delivered as a user message after the system prompt"; target under 200 lines; path-scoped rules in `.claude/rules/` with `paths:` frontmatter; "Settings rules are enforced by the client regardless of what Claude decides to do." — [Memory docs](https://code.claude.com/docs/en/memory)
- With `CLAUDE_CODE_NEW_INIT=1`, `/init` asks which artifacts to set up ("CLAUDE.md files, skills, and hooks"), explores the codebase with a subagent, and shows a proposal before writing files. — [Memory docs](https://code.claude.com/docs/en/memory)

**Codex CLI hooks (official docs; developers.openai.com/codex/hooks redirects to learn.chatgpt.com/docs/hooks)**
- Events: SessionStart, SessionEnd, PreToolUse, PermissionRequest, PostToolUse, PreCompact, PostCompact, UserPromptSubmit, SubagentStart, SubagentStop, Stop, Interrupt. PreToolUse covers shell (`Bash`, `exec_command`), `apply_patch` (matchable as `apply_patch`, `Edit`, `Write`), MCP tools and local function tools; not hosted tools like WebSearch. — [Codex hooks docs](https://learn.chatgpt.com/docs/hooks)
- Exit 2 blocks PreToolUse/UserPromptSubmit and requests continuation on Stop. PreToolUse JSON `permissionDecision: "deny"`, or `"allow"` + `updatedInput`; `"ask"` not supported yet; legacy `{"decision":"block"}` accepted. Hooks must be trusted (hash-pinned) via `/hooks`; managed hooks via `requirements.toml`; `allow_managed_hooks_only = true`. — [Codex hooks docs](https://learn.chatgpt.com/docs/hooks)
- Third-party blogs disagree on PreToolUse scope in earlier versions (Bash-only vs. all tools); the official page now lists the broader scope. — [Daniel Vaughan blog](https://codex.danielvaughan.com/2026/05/17/codex-cli-hooks-lifecycle-pretooluse-posttooluse-governance-enforcement/); [Trellis docs](https://docs.trytrellis.app/advanced/custom-hooks)

**Cursor hooks**
- Cursor has `beforeShellExecution` and `preToolUse`/`postToolUse` events. Forum reports say the Cursor CLI drops several documented hooks and that AskQuestion skips pre/postToolUse. Evidence is forum-level only. — [Cursor forum: CLI hooks](https://forum.cursor.com/t/cursor-cli-hooks/148511); [Cursor forum: AskQuestion](https://forum.cursor.com/t/cursor-cli-askquestion-tool-skips-pretooluse-and-posttooluse-hooks/161836)

**NL rule → hook converters**
- `hookify` (official Anthropic plugin, anthropics/claude-code/plugins/hookify): `/hookify Don't use console.log in TypeScript files` writes `.claude/hookify.<name>.local.md`. With no arguments it mines the recent conversation for behaviors the user corrected. Rule = YAML frontmatter (`name`, `enabled`, `event`: bash/file/prompt/stop/all, `pattern` or `conditions` [field, operator e.g. `regex_match`/`contains`, pattern], `action`: `warn` default or `block`) + a message body. A fixed engine applies rules on the next tool use with no restart. — [hookify README (GitHub API read)](https://github.com/anthropics/claude-code/tree/main/plugins/hookify)
- Prompt-recipe approach: aihero.dev gives a prompt that asks Claude to read CLAUDE.md, pick the deterministic rules (for example banned CLI commands), and turn them into PreToolUse hooks after user confirmation. It warns that only that kind of rule fits. — [aihero.dev](https://www.aihero.dev/how-to-use-claude-code-hooks-to-enforce-the-right-cli)
- A `gh search repos "CLAUDE.md hooks enforce rules"` on 2026-10-18 returned no results; no dedicated CLAUDE.md→hooks/linter compiler found. — GitHub CLI search, 2026-10-18

**Hook collections, SDKs and rule-sync tools (GitHub API, 2026-10-18: stars, last push)**
- hesreallyhim/awesome-claude-code — 55,950 stars, 2026-10-18 (curated list incl. hooks). — [GitHub](https://github.com/hesreallyhim/awesome-claude-code)
- agentsmd/agents.md — 24,981 stars, 2026-09-10 (AGENTS.md format). — [GitHub](https://github.com/agentsmd/agents.md)
- disler/claude-code-hooks-mastery — 3,944 stars, 2026-03-04. — [GitHub](https://github.com/disler/claude-code-hooks-mastery)
- intellectronica/ruler — 2,947 stars, 2026-10-14 ("apply the same rules to all coding agents"; `.ruler/` source → per-agent files; CI drift check). — [GitHub](https://github.com/intellectronica/ruler); [Algolia doc index](https://docsearch.algolia.com/mcp/docs/repo/intellectronica/ruler)
- dyoshikawa/rulesync — 1,532 stars, 2026-10-18 (CLI to generate per-agent rule files). — [GitHub](https://github.com/dyoshikawa/rulesync)
- carlrannaberg/claudekit — 763 stars, 2026-03-31 (commands, hooks, utilities). — [GitHub](https://github.com/carlrannaberg/claudekit)
- shanraisshan/claude-code-hooks — 558 stars, 2026-06-04 (voice per hook). — [GitHub](https://github.com/shanraisshan/claude-code-hooks)
- karanb192/claude-code-hooks — 543 stars, 2026-10-17 (hooks + plugin marketplace: safety, cost, observability; includes a hook that fires when CLAUDE.md or `.claude/rules/*.md` load). — [GitHub](https://github.com/karanb192/claude-code-hooks)
- johnlindquist/claude-hooks — 396 stars, 2025-08-08 (TypeScript hooks). — [GitHub](https://github.com/johnlindquist/claude-hooks)
- GowayLee/cchooks — 131 stars, 2026-04-08 ("A Python SDK for claude-code hooks"). — [GitHub](https://github.com/GowayLee/cchooks)
- decider/claude-hooks — 75 stars, 2025-07-20 (clean-code enforcement hooks). — [GitHub](https://github.com/decider/claude-hooks)
- webdevtodayjason/claude-hooks — 74 stars, 2025-07-10 (CLI hooks manager). — [GitHub](https://github.com/webdevtodayjason/claude-hooks)
- zhuyansen/awesome-claude-code-hooks (security-graded list) and ithiria894/awesome-claude-code-hooks (27 stars per search snapshot). — [GitHub](https://github.com/zhuyansen/awesome-claude-code-hooks); [GitHub](https://github.com/ithiria894/awesome-claude-code-hooks)
- Enterprise: microsoft/agent-governance-toolkit ships a Claude Code governance plugin and a Codex CLI package (see §1). — [GitHub](https://github.com/microsoft/agent-governance-toolkit)
- Rule-sync context: Claude Code reads AGENTS.md only if no CLAUDE.md exists (per a third-party guide), which is why sync tools exist. — [developertoolkit.ai](https://developertoolkit.ai/en/ecosystem/frameworks/rules-sync/)

### Inferences
- Arm B's result ("exited 1 with a JSON block decision, so Claude Code never blocked") matches the docs on two counts. Exit 1 is non-blocking. And on PreToolUse, top-level `decision: "block"` is not the documented field (`hookSpecificOutput.permissionDecision: "deny"` is). Codex accepts the legacy shape; Claude Code's current docs do not list it for PreToolUse. Check the Claude Code version used in the runs, because hook semantics changed across versions.
- The arm-B wiring errors (made-up event names, invalid schema) are the failure mode that hookify and the SDKs (cchooks, claude-hooks) were built to remove: the agent writes a pattern or a predicate, and the tested engine handles event names, exit codes and JSON.
- For "must do X" rules, Stop hooks with exit 2 (or `decision: "block"`) are the documented way to force more work. Claude Code also offers `prompt`/`agent` hook types for subjective rules, which mirrors MTAC-IFBench's split between code checkers and LLM judges.

### Gaps
- No primary source found for an automatic CLAUDE.md→hooks or Cursor-rules→linter compiler beyond hookify (single-rule, regex-based) and prompt recipes.
- "On the Maintenance and Co-evolution of Agent Plugins: An Empirical Study of Claude Code Plugin Marketplaces" (arXiv 2608.28497) exists but was not read. — [arXiv](https://arxiv.org/pdf/2608.28497)
- Cursor's official hooks docs were not fetched; Cursor data above is forum-level.

## 4. Empirical studies of instruction-file compliance, and of hooks vs. prompts

### Takeaway
2025–2026 benchmarks agree that coding agents often break repository rules, and that compliance drops over turns and as more code is written. Instance-level perfect compliance is near zero after about six turns on MTAC-IFBench. File structure (size, position, split) shows no detectable effect in a controlled 1,650-session study. No controlled study compares hooks with prompts for the same rules; the "hooks = 100%" claims are blog-level. Anthropic's docs state the hook/CLAUDE.md split as design, not as a measured result.

### Cited Findings

**MTAC-IFBench (Bosi Wen, Cunxiang Wang, …, Minlie Huang; Tsinghua CoAI, Zhipu AI, UESTC; arXiv 2609.14992, 14 Sep 2026; dataset thu-coai/MTAC-IFBench)**
- 100 instances; 9,133 constraints; average 7.04 turns, 12.97 constraints per turn, 91.33 constraint-checklist items and 16.07 function-checklist items per instance; 6 primary / 18 secondary categories. — [arXiv HTML](https://arxiv.org/html/2609.14992v1); [HF dataset](https://huggingface.co/datasets/thu-coai/MTAC-IFBench)
- Constraints first go into a repository policy file (for example Claude.md) that stays fixed. User turns then add or replace up to two constraints per turn; only user-instruction constraints can be replaced. — [arXiv HTML](https://arxiv.org/html/2609.14992v1)
- Verification: Python scripts written by Claude-Opus-4.6 check objective constraints (keywords, exact values); DeepSeek-V4-Pro judges subjective constraints; Claude-Sonnet-4.6 in Claude Code (with Playwright) checks function items. Agreement with humans: 0.921 (code), 0.924 (judge), 0.855 (function). — [arXiv HTML](https://arxiv.org/html/2609.14992v1)
- Claude Code harness, CSR / C-ISR (%): GLM-5.2 80.4 / 12.7; Claude-Opus-4.6 78.6 / 8.7; GLM-5.1 76.5 / 8.9; DeepSeek-V4-Pro 74.7 / 6.4; Kimi-K2.6 73.2 / 7.8; Gemini-3.1-Pro 71.0 / 11.1; DeepSeek-V4-Flash 70.0 / 3.4; Qwen3.6-Plus 68.8 / 2.0; Seed-2.0-Pro 66.9 / 2.6; **Claude-Haiku-4.5 64.7 / 1.9**; Qwen3.5-27B 60.6 / 1.1. — [arXiv HTML](https://arxiv.org/html/2609.14992v1)
- Decline over turns: Opus-4.6 CSR 82.4% (turns 1–2) → 76.2% (turns 9–10), C-ISR 19.0% → 2.3%; most models reach near-zero C-ISR after about 6 turns. — [arXiv HTML](https://arxiv.org/html/2609.14992v1)
- Harder: Orchestration, Paradigm, Naming, Quantity. Easier: File Encoding, File Path. Policy-file constraints decay less than user-instruction constraints; updating a constraint is harder than adding one. In a 30-instance placement test, policy-file placement gave the best compliance; system-prompt and user-prompt placement were similar. OpenCode scores below Claude Code (GLM-5.2 76.8 / 6.7). No mitigation (hooks, reminders) experiments reported. — [arXiv HTML](https://arxiv.org/html/2609.14992v1)

**Harness-IF (Zining Huang, Haoran Que, Hong Zeng, …, Shen Yan, Wenhao Huang; ByteDance Seed; arXiv 2608.11727, 12 Aug 2026)**
- 642-rule library; 60 multi-turn coding items; 256 rules get verdicts; rules placed on 5 surfaces (system prompt, tool description, skill description, project file such as CLAUDE.md, user instruction). Against-Prior Accuracy (AP-Acc) scores only rules that oppose the model's unprompted default. — [arXiv PDF](https://arxiv.org/pdf/2608.11727)
- 12 models: Acc 72.1–85.9%, AP-Acc 66.1–78.6%; every model is 3.6–7.4 points worse on against-prior rules (mean 5.81). Claude-Opus-4.7 85.9 / 78.6; Claude-Sonnet-4.6 82.5 / 78.5; **Claude-Haiku-4.5 79.0 / 71.9**; GPT-5.5 83.1 / 77.0. Judge: GPT-5.2, 3-vote majority. — [arXiv PDF](https://arxiv.org/pdf/2608.11727)
- Pooled accuracy by surface: tool description 83.1%; project file 79.1% (N=11,756); skill description 78.6%; system prompt 73.6%; user instruction 54.5% (all against-prior, not comparable). — [arXiv PDF](https://arxiv.org/pdf/2608.11727)
- By family: quantitative 82.6%, tool use 81.6%, conditional 80.9%, code style 79.2%, workflow 76.0%, output control 70.9%. Output control and workflow hold 53.9% of all failures (27.6% + 26.3%). Failures lean to omission over excess; soft preferences fail at 9.4%. — [arXiv PDF](https://arxiv.org/pdf/2608.11727)
- Conflict pilot (9 older builds): system prompt, project file and user instruction tie on precedence (mean rank 2.22), ahead of tool description (3.78) and skill description (4.56). — [arXiv PDF](https://arxiv.org/pdf/2608.11727)

**Instruction Adherence in Coding Agent Configuration Files: A Factorial Study (Damon McMillan, HxAI Australia; arXiv 2605.10039, 2026)**
- 1,650 Claude Code CLI sessions, 16,050 function-level observations, 2 TypeScript codebases, Sonnet 4.6 (main), Opus 4.6, Opus 4.7; target rule = start each function with `// @tracked`, checked by AST on the final repo. Zero spontaneous emission in no-config baselines. — [arXiv PDF](https://arxiv.org/pdf/2605.10039)
- No detectable effect of file size (25–500 lines), position, file architecture, or a conflicting instruction after correction (BF10 0.05–0.10 for size and conflict nulls). — [arXiv PDF](https://arxiv.org/pdf/2605.10039)
- Within-session decline: about 5.6% lower odds of compliance per generated function (OR 0.944); median first omission at position 4. Task identity matters more than file structure. Recommended action: add in-session mechanisms ("agent hooks that re-surface the rule") plus post-hoc enforcement (linters, CI). Hooks were not tested. — [arXiv PDF](https://arxiv.org/pdf/2605.10039)

**OctoBench (Ding et al.; ACL 2026 Long; arXiv 2601.10343)**
- 34 environments, 217 tasks, 3 scaffold types, 7,098 checklist items; sources include CLAUDE.md/AGENTS.md conventions, system constraints, tool protocols and multi-turn persistence. Eight models show "a systematic gap between task-solving and scaffold-aware compliance." Public HF set: 72 instances, 2,422 checks, 15 centered on CLAUDE.md, 54 on Claude Code 2.0.69. — [ACL Anthology](https://preview.aclanthology.org/ingest-acl/2026.acl-long.269/); [HF dataset card](https://huggingface.co/datasets/MiniMaxAI/OctoCodingBench/blob/refs%2Fpr%2F3/README.md)

**AgentIF (Tsinghua + Zhipu AI; arXiv 2505.16944; NeurIPS 2025 D&B)**
- 707 human-annotated instructions from 50 real agentic apps; average 1,723 words (max 15,630) and 11.9 constraints per instruction; code, LLM or hybrid checks. Models do poorly, mainly on complex constraint structures and tool specs. — [arXiv HTML](https://arxiv.org/html/2505.16944v1); [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2025/hash/51bb3a8a33610a25aae074bfc51b1b1f-Abstract-Datasets_and_Benchmarks_Track.html)

**Context-file studies (effect on task success)**
- Evaluating AGENTS.md (Gloaguen, Mündler-Sasahara, Müller, Raychev, Vechev; arXiv 2602.11988, Feb 2026, v3 Sep 2026): context files (LLM-generated or developer-written) do not generally raise task success and raise inference cost by "over 20% on average"; agents do follow the instructions in them; repository overviews do not help. — [arXiv](https://arxiv.org/abs/2602.11988)
- Agent READMEs (Chatlatanagulchai et al.; arXiv 2511.12884, Nov 2025): 2,303 context files from 1,925 repos; mostly functional content; security in 14.8% and performance in 14.5%. — [arXiv](https://arxiv.org/abs/2511.12884)
- Do Context Files Help Coding Agents? (arXiv 2607.27250, Jul 2026): across Claude Code and Codex, context strategy does not measurably change correctness; failures come from implementation skill, not missing repo knowledge. — [arXiv HTML](https://arxiv.org/html/2607.27250v1)

**Hooks vs. prompts**
- Anthropic docs: CLAUDE.md "shape[s] Claude's behavior but [is] not a hard enforcement layer"; rules that must run at fixed points belong in hooks, which "apply regardless of what Claude decides to do." — [Memory docs](https://code.claude.com/docs/en/memory)
- A consultancy blog claims 70–90% compliance for prompt instructions vs. 100% for hooks, with no cited experiment. — [Dotzlaw Consulting](https://dotzlaw.com/insights/claude-hooks/)
- Practitioner reports (single cases) say moving a rule from CLAUDE.md to a PreToolUse hook took failures to zero; they also note hooks cover only what they intercept. — [Blake Crosley](https://blakecrosley.com/blog/claude-code-hooks-explained); [Medium](https://medium.com/data-science-collective/claude-code-hooks-when-claude-md-stops-being-enough-0c66c548dbbd)

### Inferences
- The project's arm-A score with Haiku 4.5 (43/70 ≈ 61%) is close to MTAC-IFBench's benchmark-wide Haiku 4.5 CSR (64.7%). That suggests the one-task baseline is typical, but one task is a small sample.
- Harness-IF and MTAC-IFBench both point to rule types that a PreToolUse gate cannot catch: omission/"shortfall" failures, output control (response format), workflow/orchestration. These need Stop-hook checks on the final response/workspace (exit 2 to continue) or prompt/agent hooks, not tool-call blocking.
- MTAC-IFBench's split (scripts for objective constraints, judges for subjective) gives a natural upper bound on what deterministic hooks can cover; the objective share of constraints per task is the ceiling for arm B/C gains from command hooks alone.
- The within-session and over-turn decay (OR 0.944 per function; C-ISR near zero after ~6 turns) is the gap that hooks address: a hook does not decay over turns. This is the strongest argument for the A/B/C design, and also the effect no paper has yet measured directly.

### Gaps
- No controlled study found that holds rules fixed and compares CLAUDE.md-only vs. hook enforcement on per-rule compliance and task success. The project's A/B/C design would fill this gap.
- MTAC-IFBench per-category and per-source numbers (its Figures 5–6) were not in the fetched text; the full category definitions and an example Claude.md were not retrieved.
- AgentIF per-model numbers were not retrieved.
- A "Lulla et al., 2026" study (AGENTS.md lowers runtime and output tokens for Codex agents) appeared only in a search summary; the primary source was not confirmed.
- No study found that measures how often LLM-written hooks are wired wrongly (bad event names, schema, exit codes), which is the arm-B failure mode.
