# Always
trigger · The rule applies at all times. No event starts the check.

- before: file permissions (/opt/enforce-toolbox/mechanisms/file-permissions.md); the agent framework's hooks (/opt/enforce-toolbox/mechanisms/framework-hooks.md) before each action
- at: file watchers (/opt/enforce-toolbox/mechanisms/file-watchers.md); the framework's hooks (/opt/enforce-toolbox/mechanisms/framework-hooks.md) after each action
- after: the framework's hook (/opt/enforce-toolbox/mechanisms/framework-hooks.md) at the end of the turn; checks that keep running (/opt/enforce-toolbox/mechanisms/keep-running.md)
