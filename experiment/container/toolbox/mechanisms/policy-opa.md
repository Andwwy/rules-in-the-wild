# Policy engine: OPA (Rego)
mechanism · before an action (install: `opa`)

A policy over one action at a time: which tool, command, file or value is allowed. The mechanism that sees the action
before it runs (a framework hook, a command wrapper) writes it as JSON (`{"tool": …, "args": {…}}`) and asks OPA; OPA
returns what the policy refuses.

- skeletons: /opt/enforce-toolbox/skeletons/policy.rego (the policy), /opt/enforce-toolbox/skeletons/opa_gate.sh (the question)
- check: `opa eval --fail-defined --format pretty --data policy.rego --input action.json 'data.policy.deny[msg]'`: exit 1 and the messages when the policy refuses
- the agent sees: what the mechanism that asked passes on.
- for permissions that depend on what happened before, and when: /opt/enforce-toolbox/mechanisms/policy-dogwood.md

- docs: https://www.openpolicyagent.org/docs
