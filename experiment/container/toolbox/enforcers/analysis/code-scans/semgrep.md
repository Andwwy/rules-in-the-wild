# Analysis › Code scans › Semgrep
enforcer · A pattern-based static analyzer. A rule is a code pattern that Semgrep matches against each file's syntax tree, for
many languages (Python, JavaScript, TypeScript, HTML script blocks, Bash, …).

- install: `semgrep`
- check: `semgrep scan --config <rules.yml> --error --metrics=off --quiet <file>` (exit 1 on a finding; `--json` for a report)
- rules: `rules: [{id: <id>, languages: [<language>], severity: ERROR, message: "<what to change>", pattern: "<code pattern>"}]`; Semgrep matches syntax, it cannot compute values (a length, a count): let Semgrep find the code (`--json` gives each match's file, start and end lines), and compute the value from that in a check script (/opt/enforce-toolbox/skeletons/check.py)
- skeleton: /opt/enforce-toolbox/skeletons/semgrep_check.py (Semgrep finds the code; judge() decides, and computes what Semgrep cannot)

Rule syntax: https://semgrep.dev/docs/writing-rules/rule-syntax
