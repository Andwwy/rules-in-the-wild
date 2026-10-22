# Agent action › File write / edit
trigger · A file or code is created, changed, renamed or deleted.

- before: the agent framework's hook (/opt/enforce-toolbox/mechanisms/framework-hooks.md) before its write tools (it sees the new content); file permissions (/opt/enforce-toolbox/mechanisms/file-permissions.md) (the write fails)
- at: the framework's hook (/opt/enforce-toolbox/mechanisms/framework-hooks.md) after its write tools; file watchers (/opt/enforce-toolbox/mechanisms/file-watchers.md); the framework's hook after a shell command (files that the command changed)
- after: the framework's hook (/opt/enforce-toolbox/mechanisms/framework-hooks.md) at the end of the turn (every file); git hooks (/opt/enforce-toolbox/mechanisms/git-hooks.md) (at commit); checks that keep running (/opt/enforce-toolbox/mechanisms/keep-running.md)
