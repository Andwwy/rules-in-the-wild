# Agent loop › Response sent
trigger · The agent makes or sends a response, an answer or a message.

- before, at: the agent framework's hook (/opt/enforce-toolbox/mechanisms/framework-hooks.md) at the end of the turn: it sees the reply, and can keep the agent working until the reply follows the rule
- after: the reply in the framework's transcript (/opt/enforce-toolbox/targets/agent-output/response-message.md)
