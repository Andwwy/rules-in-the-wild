# Policy engine: Dogwood (temporal permissions)
mechanism · before an action, given what happened before and when (install: `dogwood`)

Dogwood extends Cedar's policies (permit, forbid, when) with conditions on the history of actions and on time: an
action is allowed only if, for example, another action succeeded within the last 15 minutes and nothing failed since
(`formerly within <window>`, `<A> since within <window> <B>`, counts). Useful for timely action permissions: an
action allowed only after, before, or within some time of other actions.

The mechanism that sees each action writes it to a trace: a request event before the action (Dogwood decides ALLOW or
DENY) and a response event after it (with its output, which later decisions read). `dogwood replay` evaluates the trace.
Only past events of the request's principal count: every event names its caller (`callerPrincipal`, `callerResource`).

- skeletons: /opt/enforce-toolbox/skeletons/policy.dw (the policy), /opt/enforce-toolbox/skeletons/schema.cedarschema (the actions it talks about), /opt/enforce-toolbox/skeletons/dogwood_gate.sh (records an action; asks before a request)
- check: `dogwood validate policy.dw --policy-schema schema.cedarschema`; `dogwood replay policy.dw --policy-schema schema.cedarschema --trace trace.log` prints `@<time> (time point <n>): ALLOW|DENY` per request
- the agent sees: what the mechanism that asked passes on.
- where it runs: inside a root service (/opt/enforce-toolbox/mechanisms/root-service.md), which keeps the trace in /var/lib/enforce-state; the agent-side parts ask the service. A trace that the agent can write, the agent can change.
- limits: the trace must hold every action that the policy reads, after it ran (a mechanism after each action).
- docs: https://dogwood-policy.github.io/dogwood/
