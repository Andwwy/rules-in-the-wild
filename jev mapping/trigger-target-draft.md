# Trigger and target: draft first level

Status: replaced by `trigger-tree.json` and `target-tree.json` (Oct 17). In the trees, "Agent work step" and
"Agent turn & session" are merged into "Agent loop", and "State condition" is an attribute, not a class. This page
stays for its sample values.

- Data: `../assign+group/data/pass1.11-10000/v1.11_result/assignment output.json` (prompt v1.11, 10,000 rules).
- Method: ordered keyword rules, first match wins, on each voted value. This is a rough sort to show the classes
  with real values. It is not the classifier. The final sort will be a Jev pass over the tree, as for the enforcer.
- Counts: "mentions" counts voted values (a rule can have more than one). "Rules" counts rules. "Full triple"
  counts rules from the 1,841 that have a voted enforcer, target and trigger.
- Samples: the most frequent values (with counts), then random values that occur once.
- Trees: `trigger-tree.json` and `target-tree.json` hold this first level only, in the format of
  `enforcer-tree-simple.json`.

## Trigger

6,810 voted values.

| class | what it means | mentions | rules | full triple |
|---|---|---|---|---|
| Always | The rule applies at all times. No event starts it. | 866 (13%) | 866 | 52 |
| State condition | The rule applies while a state holds: a mode, a flag, a threshold, a missing tool. | 252 (4%) | 246 | 64 |
| Agent tool call | The agent calls a tool, a shell command, an MCP server, a skill or a subagent. | 243 (4%) | 242 | 112 |
| Code host & review | A pull request event, a code review, an issue event or a CI run. | 415 (6%) | 412 | 131 |
| Application runtime | The running app does something: a request, a query, a log, an error, a UI event, a schedule, a storage write. | 422 (6%) | 421 | 139 |
| Static check | A linter, a formatter, a type checker or a scanner runs. | 249 (4%) | 247 | 217 |
| Build & test run | A build, a compile or a test run. | 169 (2%) | 168 | 74 |
| Release & deploy | A deploy, a release, a publish step or a production change. | 166 (2%) | 164 | 47 |
| Version control | A local git event: commit, push, merge, branch, tag. | 195 (3%) | 195 | 93 |
| File access (read / write / edit) | A file or code is read, created, changed or deleted. | 876 (13%) | 869 | 204 |
| Agent work step | The agent does one step of a task or a domain workflow: a phase, an assessment, a draft, a submission. | 1,084 (16%) | 1,078 | 285 |
| Agent turn & session | An agent lifecycle event: a prompt arrives, a response is made or sent, a task completes, a session starts. | 944 (14%) | 934 | 231 |
| Other | None of the above. Non-English values are here for now. | 929 (14%) | 912 | 227 |

### Trigger: sample values

- **Always**: `always (866)`
- **State condition**: `when a user invokes a skill in plan mode (2)` · `when mcp tools are unavailable` · `when operating in report-only mode` · `before executing worktree mode` · `when asking user questions in interactive mode` · `when the --lean flag is present` · `when selecting a code tour delivery mode` · `when no grounding document is available`
- **Agent tool call**: `before executing a shell command (6)` · `before calling askuserquestion (4)` · `when an askuserquestion call is generated (3)` · `when an askuserquestion tool-use payload is emitted (2)` · `when this skill is invoked (2)` · `when a subagent closes a ticket` · `when defining a tool description` · `when a tool result payload is generated`
- **Code host & review**: `during code review (20)` · `when a pull request is created or updated (5)` · `when a pull request is opened or updated (3)` · `during each ci run (3)` · `when a github issue is opened or edited (2)` · `when reviewing a ui screenshot` · `when a code review change contains 20 to 100 changed files` · `when issuing a review report`
- **Application runtime**: `when a log record is emitted (4)` · `when a log entry is emitted (3)` · `when an http response is sent (3)` · `when an error occurs (2)` · `annually (2)` · `when a convex function attempts a database write` · `when a seed phrase is stored or shared` · `before writing a custom api call`
- **Static check**: `at lint time (18)` · `when javascript or typescript source files are linted (11)` · `when typescript source files are linted (8)` · `when css stylesheets are linted (6)` · `when javascript or typescript source is linted (4)` · `when ui source code is scanned` · `when css or stylesheet source files are linted` · `when scoped css rules are linted`
- **Build & test run**: `at build time (8)` · `when tests are run (3)` · `when unit tests are run (2)` · `when a test case is executed (2)` · `at c# build time (2)` · `during slow-motion animation testing` · `when building a c++ plugin targeting windows or linux` · `before running android tests`
- **Release & deploy**: `before deployment (12)` · `before a release (3)` · `before release (3)` · `before tagging a release (2)` · `before publishing (2)` · `before changing production code` · `when a static release artifact is built or published` · `when no posts are published`
- **Version control**: `at commit time (40)` · `at git commit time (6)` · `when creating a git commit (4)` · `when creating a commit (4)` · `before committing (3)` · `when a git staging command is submitted for execution` · `at commit time when requirements.txt is changed` · `before presenting a commit message`
- **File access (read / write / edit)**: `when test code is added or modified (3)` · `when source code is created or modified (3)` · `after code changes (2)` · `when a diagram is created or modified (2)` · `when a prd is created or modified (2)` · `when an audit finding is written` · `when a send_raw_message call is added or modified` · `when modifying kernel code`
- **Agent work step**: `before delivery (4)` · `when generating the implementation plan (2)` · `before submission (2)` · `before manuscript submission (2)` · `when executing downstream phases after source ingestion` · `when the user confirms the plan audit` · `during phase 4 re-verification after a fix` · `when creating an answer to a question`
- **Agent turn & session**: `when generating a response (18)` · `when generating an assistant response (11)` · `when a user request is received (5)` · `before an assistant response is sent (5)` · `before marking work complete (3)` · `when generating a user summary` · `when generating a legal ethics and investigations agent response` · `when generating new code`
- **Other**: `server.py セッションへコマンドを投入するとき` · `before a page is shipped` · `当生成或修改 operation-matrix.md 时` · `when dispatching an init-command invocation` · `after debugging` · `before dispatching a destructive operation` · `when the registry loader loads registry data` · `when a service connects to another service`

## Target

10,390 voted values.

| class | what it means | mentions | rules | full triple |
|---|---|---|---|---|
| Tests | Test cases, test files, test suites, assertions. | 384 (4%) | 348 | 82 |
| Agent actions | What the agent does: tool calls, commands, invocations, operations. | 840 (8%) | 774 | 319 |
| Version-control objects | Commits, branches, pull requests, diffs, issues, tags. | 378 (4%) | 347 | 101 |
| Agent output | What the agent says or writes back: responses, messages, reports, plans, findings. | 1,600 (15%) | 1,501 | 262 |
| User input & tasks | What the user gives: requests, prompts, tasks, requirements, stories. | 525 (5%) | 490 | 90 |
| Agent setup & instructions | The agent's own setup: agents, skills, rules, memory, workflows, CLAUDE.md-type files. | 457 (4%) | 422 | 108 |
| Data & runtime objects | Records, fields, queries, endpoints, logs, errors, secrets, business data. | 1,727 (17%) | 1,527 | 442 |
| Config, dependency & infra | Config files, settings, dependencies, packages, environments, deployments. | 579 (6%) | 537 | 155 |
| Docs & text files | Documentation, READMEs, comments, prose, sections, templates. | 863 (8%) | 791 | 159 |
| Source code | Code files and code units: functions, classes, components, names, code changes. | 1,197 (12%) | 1,087 | 252 |
| UI & media | Pages, on-screen elements, images, layouts, accessibility attributes. | 416 (4%) | 374 | 60 |
| Files & directories (any kind) | Files, folders, paths and artifacts of no specific kind. | 241 (2%) | 227 | 58 |
| Other | None of the above. Non-English values are here for now. | 1,183 (11%) | 1,055 | 179 |

### Target: sample values

- **Tests**: `test cases (29)` · `test files (16)` · `tests (15)` · `test suite (9)` · `unit tests (5)` · `$workflow-code-to-spec workflow execution` · `unit test cases` · `spec`
- **Agent actions**: `agent actions (7)` · `git command invocations (7)` · `actions (6)` · `skill invocations (6)` · `agent tool calls (5)` · `curl invocations in the ad-hoc http fallback poller` · `generator file-write operations` · `action parameters`
- **Version-control objects**: `git commits (17)` · `pull requests (14)` · `issues (9)` · `pull request (8)` · `commit messages (6)` · `diff item objects` · `subagent dispatch instructions` · `local git branch associated with the merged pull request`
- **Agent output**: `assistant responses (39)` · `assistant response (32)` · `agent responses (20)` · `findings (17)` · `plan (16)` · `flagged dead-code findings` · `health dashboard score` · `daily report markdown filenames`
- **User input & tasks**: `user requests (20)` · `tasks (17)` · `task (15)` · `user input (6)` · `user messages (5)` · `subagent tasks` · `requirement traceability matrix status entries` · `canonical research, specification, or task files`
- **Agent setup & instructions**: `agents (6)` · `skill.md (6)` · `memory.md (6)` · `workflow steps (4)` · `skill (4)` · `agent sessions` · `freeform memory records` · `preliminary interview handoff document`
- **Data & runtime objects**: `api endpoints (11)` · `database queries (6)` · `error messages (6)` · `database tables (5)` · `data (5)` · `pilot records` · `candidate execution` · `framework/library version metadata`
- **Config, dependency & infra**: `tsconfig.json (4)` · `dependencies (4)` · `deployments (3)` · `packages (2)` · `apps (2)` · `next.js app router catch-all route directory segments` · `container cpu priority configuration` · `production dockerfile stage`
- **Docs & text files**: `documentation (10)` · `documentation files (8)` · `examples (7)` · `code comments (6)` · `comments (6)` · `slash characters in documentation text` · `edited copy` · `the step 4-referenced `references/*.md` file`
- **Source code**: `code changes (28)` · `functions (19)` · `source code (17)` · `source files (10)` · `source code files (10)` · `pharmacological fmri interpretations` · `proposed code-review approaches` · `fix`
- **UI & media**: `page (8)` · `pages (8)` · `web pages (5)` · `buttons (5)` · `image elements (5)` · `python reviews` · `clickable elements` · `ui edge cases`
- **Files & directories (any kind)**: `files (19)` · `changed files (7)` · `generated artifacts (5)` · `repository files (5)` · `artifacts (4)` · `html artifact` · `files that would be modified` · `repository files matching `*.rb` or named `gemfile``
- **Other**: `team members (2)` · `scan targets (2)` · `kpi targets` · `non-owner interactions` · `framework selection` · `gdd acceptance-criterion groups` · `game codebase` · `ask`

## Known problems in this draft
- Trigger "Agent work step" and "Agent turn & session" overlap. One is a step in a task ("before delivery"),
  the other is a lifecycle event ("when generating a response"). Merge them, or keep them apart with descriptions.
- Trigger "State condition" is not an event. It matches the EARS state-driven pattern. Keep it, or make it an
  attribute next to the class, as before / after / during.
- Target "Files & directories (any kind)" catches values with no file kind ("files", "changed files"). The
  MTAC set has the same idea (`any-file`).
- Target "Agent setup & instructions" is new. Without it, SKILL.md, CLAUDE.md and agents fall into Docs or Other.
- Many "Other" values are not in English, or come from non-software domains (legal, finance, research).
- v1.11 targets still hold some gated actions. Prompt v1.19 moves those to the trigger.
