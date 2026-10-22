# Agent action › Tool / MCP call
trigger · The agent calls any other tool: an MCP server, a web fetch or search, an external API.

- before: the agent framework's hook (/opt/enforce-toolbox/mechanisms/framework-hooks.md) before that tool; a policy engine on the call (/opt/enforce-toolbox/mechanisms/policy-opa.md, /opt/enforce-toolbox/mechanisms/policy-dogwood.md)
