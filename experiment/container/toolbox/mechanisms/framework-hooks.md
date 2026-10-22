# Agent framework hooks
mechanism · before, at and after the agent's own actions

The agent framework runs a command at its own events: before and after each tool call, when a prompt comes, when the
turn ends. The command gets the event as JSON (the tool and its input, the reply) and can refuse the action, or give
the agent a message. Each framework has its own events and protocol: see its documentation. It is the only mechanism that sees the agent's reply, and an action's content before it
runs.

- the agent sees: the refusal or the message, in its context.
- runs: the check of the rule (/opt/enforce-toolbox/skeletons/check.py), or a policy engine (/opt/enforce-toolbox/mechanisms/policy-opa.md, /opt/enforce-toolbox/mechanisms/policy-dogwood.md).

- limits: a hook sees only the events it is set for: a hook on the framework's file tools does not see a file that a shell command writes; a hook at the end of the turn can check every file on disk
- runs as the agent: state that the agent must not change (a history, a count) belongs to a root service: /opt/enforce-toolbox/mechanisms/root-service.md
