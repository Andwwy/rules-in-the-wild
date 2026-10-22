# The enforcement toolbox

A library for implementing enforcement in this container, as a graph of small nodes with skeleton code. It is not tied
to one agent framework: a check can run from the agent framework's own hooks (see the framework's documentation), from
the operating system, from git, from a wrapper in front of a command, from a policy engine, or from a process that
keeps running. Which mechanism you use is your choice; you can also build what the library does not describe.

## How to walk it

A rule's route names one leaf of each tree. Start at those three nodes and follow only the links you need: every link
is a path in this container.

- `enforcers/<path>.md`: how to check the rule: the tool to install and the command to run, or the code to write.
- `triggers/<path>.md`: the mechanisms that can run the check before, at or after that moment of the agent's work.
- `targets/<path>.md`: where the target is, and how a check reads it.
- `mechanisms/*.md`: one node per mechanism: what it is, its timing, what the agent sees, its limits, its skeleton.
  Framework hooks, file permissions, command wrappers, git hooks, file watchers, a root service (keeps state that the
  agent cannot change, for the parts that run as the agent), two policy engines (OPA for one action at a time; Dogwood
  for permissions that depend on what happened before, and when), checks that keep running.
- `skeletons/*`: runnable starts: a check script, regular expressions, a project check, a JSON Schema check, a Rego
  policy and its gate, a Dogwood policy, schema and gate, a root service and its client, a command wrapper, a git hook,
  a file watcher, parsers for names in code. `<…>` is yours to fill in. The examples are general; none comes from a
  rule you are given.
- `graph.json`: every node and edge, for a program to read.

A node's path is its tree path in lower case: `Agent action › File write / edit` is
`triggers/agent-action/file-write-edit.md`. A check exits 0 when the target follows the rule, and otherwise exits 1 and
prints each violation: where it is, and what to change.

## Install

`enforce install NAME …` installs a tool by its recipe into /opt/enforce/tool-installs/NAME, links its programs into
/opt/enforce/tool-installs/bin (put that folder first on PATH, or call a program by its full path), makes it readable
by every user, and ends with a smoke test. `enforce install --list` shows the recipes and which are installed. Each
recipe was installed and tested in this container's image.

| Recipe | Tool |
|---|---|
| `semgrep` | Semgrep 1.177.0: pattern-based code scans |
| `jsonschema`, `js-parser` | Python libraries: JSON Schema; tree-sitter with JavaScript and TypeScript (their Python: /opt/enforce/tool-installs/<name>/bin/python) |
| `ruff`, `shellcheck`, `yamllint`, `pytest`, `openapi`, `pre-commit` | Python and shell linters, a test runner, an OpenAPI validator, a git hook framework |
| `node` | Node.js 22.23.3 with npm (the npm recipes install it first) |
| `eslint`, `stylelint`, `biome`, `typescript`, `jest`, `ajv`, `markdownlint`, `remark-lint`, `commitlint`, `pnpm` | JavaScript, CSS and Markdown tools |
| `vale` | Vale 3.24.0: prose linter |
| `opa` | Open Policy Agent 1.0.0: policies in Rego |
| `dogwood` | Dogwood 1.1.0: temporal policies on actions (built with the `rust` recipe, Rust 1.99.1, and `gcc`; about 2.5 minutes) |
| `git`, `jq`, `ripgrep`, `curl`, `inotify-tools`, `gcc` | Debian 12 packages |

For a tool without a recipe, its node (from the leaf's note) or its documentation says how to install it; pin the
version.
