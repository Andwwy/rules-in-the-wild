# Agent action › Shell command
trigger · A shell or CLI command runs.

- before: the agent framework's hook (/opt/enforce-toolbox/mechanisms/framework-hooks.md) before its shell tool (the command line); command wrappers (/opt/enforce-toolbox/mechanisms/command-wrappers.md); a policy engine (/opt/enforce-toolbox/mechanisms/policy-opa.md, /opt/enforce-toolbox/mechanisms/policy-dogwood.md)
- at, after: the framework's hook (/opt/enforce-toolbox/mechanisms/framework-hooks.md) after its shell tool; file watchers (/opt/enforce-toolbox/mechanisms/file-watchers.md) (what the command changed)
