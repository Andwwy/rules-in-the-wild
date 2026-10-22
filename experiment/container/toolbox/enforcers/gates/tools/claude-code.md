# Gates › Tools › Claude Code
enforcer · The agent's own Claude Code settings: permission rules (`permissions.deny`, `ask` and `allow`, on tools and patterns
such as `Bash(rm:*)` or `Write(/workspace/secrets/**)`) and hooks, in /opt/enforce/settings.json. Nothing to install.
The agent works with its permission prompts skipped; a `PreToolUse` hook that exits 2 refuses a tool call in that mode
(checked). Whether the permission rules apply in that mode is not checked here.

- check: the agent framework's own settings, when the agent is Claude Code: permission rules and hooks in the settings file that it reads (here /opt/enforce/settings.json; its documentation: /opt/docs/claude-code/)

Docs: https://docs.anthropic.com/en/docs/claude-code/settings
