# Gates › Tools › Command filter
enforcer · A check on each shell command before it runs, which refuses the command or changes it.

- check: a check on each shell command before it runs: a regular expression, Python's `shlex.split`, or a Rego policy (/opt/enforce-toolbox/mechanisms/policy-opa.md), on the command line; refuse the command or change it (/opt/enforce-toolbox/triggers/agent-action/shell-command.md)
