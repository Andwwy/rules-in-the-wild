# Gates › Workflow › Agent workflow
enforcer · The agent must do its work in steps, in a fixed order (for example a plan before code, tests before "done"); a
step out of order is refused.

- check: a state that records the steps done (a file that only root writes, or the agent's own plan file), and a check that refuses a step before the steps it needs (a Rego policy (/opt/enforce-toolbox/mechanisms/policy-opa.md) over the action and the state)
